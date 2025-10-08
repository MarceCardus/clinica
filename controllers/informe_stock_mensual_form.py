# controllers/informe_stock_mensual_form.py
from __future__ import annotations
import os
from datetime import datetime
from decimal import Decimal

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QWidget,
    QFileDialog, QAbstractItemView, QHeaderView, QCheckBox, QSpacerItem,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QBrush, QFont

from utils.db import new_session
from sqlalchemy.exc import OperationalError, InterfaceError, DisconnectionError

from services.informe_stock_mensual_service import (
    obtener_informe_stock_mensual,
    exportar_pdf_informe_stock_mensual,
    exportar_excel_informe_stock_mensual,
    SPANISH_MONTHS,
)


class InformeStockMensualForm(QDialog):
    """
    Informe de stock mensual (UI)
    BONUS:
      - Filtro de texto por ítem.
      - Checkbox “Ocultar sin movimiento”.
      - Checkbox “Solo stock negativo”.
      - Coloreado: stock negativo en rojo; filas sin movimiento en gris (si no se ocultan).
      - Orden numérico correcto gracias a EditRole en celdas numéricas.
      - Indicador de totales fuera de la grilla.
      - Reintento de conexión si se cae el DB-connection.
    """
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("Informe de Stock Mensual")
        self.resize(1150, 720)

        lay = QVBoxLayout(self)

        # -------- Filtros --------
        top = QHBoxLayout()

        top.addWidget(QLabel("Mes:"))
        self.cmb_mes = QComboBox()
        for i in range(1, 13):
            self.cmb_mes.addItem(SPANISH_MONTHS[i], i)
        hoy = QDate.currentDate()
        self.cmb_mes.setCurrentIndex(hoy.month() - 1)
        top.addWidget(self.cmb_mes)

        top.addWidget(QLabel("Año:"))
        self.txt_anio = QLineEdit(str(hoy.year()))
        self.txt_anio.setFixedWidth(90)
        self.txt_anio.setAlignment(Qt.AlignCenter)
        top.addWidget(self.txt_anio)

        # BONUS: filtro por texto y toggles
        top.addSpacing(12)
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Buscar ítem...")
        self.txt_buscar.setClearButtonEnabled(True)
        self.txt_buscar.setFixedWidth(220)
        top.addWidget(self.txt_buscar)

        self.chk_ocultar_cero = QCheckBox("Ocultar sin movimiento")
        self.chk_solo_neg = QCheckBox("Solo stock negativo")
        top.addWidget(self.chk_ocultar_cero)
        top.addWidget(self.chk_solo_neg)

        top.addItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.btn_generar = QPushButton("Generar")
        self.btn_excel = QPushButton("Exportar a Excel")
        self.btn_pdf = QPushButton("PDF")
        self.btn_cerrar = QPushButton("Cerrar")
        top.addWidget(self.btn_generar)
        top.addWidget(self.btn_excel)
        top.addWidget(self.btn_pdf)
        top.addWidget(self.btn_cerrar)

        lay.addLayout(top)

        # -------- Leyenda --------
        self.lbl_leyenda = QLabel("")
        self.lbl_leyenda.setStyleSheet("color: gray;")
        lay.addWidget(self.lbl_leyenda)

        # -------- Tabla --------
        self.tbl = QTableWidget(0, 7)
        self.tbl.setHorizontalHeaderLabels(["#", "Ítem", "Inicial", "Ingreso", "Ventas", "Insumo", "Actual"])
        self.tbl.setColumnWidth(0, 60)
        self.tbl.setColumnWidth(1, 460)
        self.tbl.setColumnWidth(2, 100)
        for c in range(3, 7):
            self.tbl.setColumnWidth(c, 120)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl.setSortingEnabled(False)
        self.tbl.setAlternatingRowColors(True)
        lay.addWidget(self.tbl, 1)

        # -------- Totales --------
        self.lbl_totales = QLabel("")
        self.lbl_totales.setStyleSheet("font-weight: bold; padding-top: 6px;")
        lay.addWidget(self.lbl_totales)

        # -------- Signals --------
        self.btn_generar.clicked.connect(self.buscar)
        self.btn_pdf.clicked.connect(self.exportar_pdf)
        self.btn_excel.clicked.connect(self.exportar_excel)
        self.btn_cerrar.clicked.connect(self.close)

        # BONUS: filtros reactivos
        self.txt_buscar.textChanged.connect(lambda _=None: self.buscar(redraw_only=True))
        self.chk_ocultar_cero.stateChanged.connect(lambda _=None: self.buscar(redraw_only=True))
        self.chk_solo_neg.stateChanged.connect(lambda _=None: self.buscar(redraw_only=True))

        # Cache último resultado para filtrar sin ir a DB
        self._last_info = None

        # Primera carga
        self.buscar()

    # -------- Util --------
    @staticmethod
    def _fmt(x) -> str:
        try:
            n = int(Decimal(str(x)).quantize(Decimal("1")))
        except Exception:
            n = int(x or 0)
        return f"{n:,}".replace(",", ".")

    def _num_item(self, x) -> QTableWidgetItem:
        """Texto formateado + dato crudo (EditRole) para ordenar numéricamente."""
        it = QTableWidgetItem(self._fmt(x))
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        try:
            n = int(Decimal(str(x)).quantize(Decimal("1")))
        except Exception:
            n = 0
        it.setData(Qt.EditRole, n)
        return it

    @staticmethod
    def _cell(text: str, right: bool = False) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        it.setTextAlignment((Qt.AlignRight if right else Qt.AlignLeft) | Qt.AlignVCenter)
        return it

    def _busy(self, v: bool):
        for b in (self.btn_generar, self.btn_excel, self.btn_pdf, self.btn_cerrar):
            b.setEnabled(not v)

    def _correr_con_sesion(self, fn):
        """Corre una función con sesión fresca y la cierra. Reintenta 1 vez si la conexión cae."""
        try:
            s = new_session()
            try:
                return fn(s)
            finally:
                s.close()
        except (OperationalError, InterfaceError, DisconnectionError):
            s = new_session()
            try:
                return fn(s)
            finally:
                s.close()

    # -------- Búsqueda / Render --------
    def buscar(self, redraw_only: bool = False):
        """
        Si redraw_only=True, vuelve a dibujar la tabla aplicando filtros UI
        sobre self._last_info (sin tocar base).
        """
        self._busy(True)
        try:
            mes = self.cmb_mes.currentData()
            anio = int(self.txt_anio.text().strip())

            if not redraw_only or self._last_info is None:
                info = self._correr_con_sesion(lambda s: obtener_informe_stock_mensual(s, year=anio, month=mes))
                self._last_info = info
            else:
                info = self._last_info

            # Leyenda más completa
            try:
                f_ini = info.corte_inicial.strftime('%d/%m/%Y')
                f_fin = info.corte_final.strftime('%d/%m/%Y') if hasattr(info, "corte_final") else f"{mes:02d}/{anio}"
            except Exception:
                f_ini, f_fin = "-", "-"
            self.lbl_leyenda.setText(
                "Inicial = stock al {ini}  •  "
                "Ingreso = compras/ajustes(+)  •  "
                "Ventas = ventas  •  "
                "Insumo = egresos/ajustes(-)  •  "
                "Actual = Inicial + Ingreso - Ventas - Insumo  •  "
                "Período: {fin}"
                .format(ini=f_ini, fin=f_fin)
            )

            # Filtros UI (bonus)
            txt = (self.txt_buscar.text() or "").strip().lower()
            ocultar_cero = self.chk_ocultar_cero.isChecked()
            solo_neg = self.chk_solo_neg.isChecked()

            def pasa_filtros(it) -> bool:
                nombre_ok = (txt in (it.nombre or "").lower()) if txt else True
                ing = Decimal(it.ingreso or 0)
                ven = Decimal(it.ventas or 0)
                otr = Decimal(it.otros or 0)
                act = Decimal(it.actual or 0)
                sin_mov = (ing == 0 and ven == 0 and otr == 0)
                neg_ok = (act < 0) if solo_neg else True
                sinmov_ok = (not ocultar_cero) or (not sin_mov)
                return nombre_ok and neg_ok and sinmov_ok

            # Render
            self.tbl.setSortingEnabled(False)
            self.tbl.setUpdatesEnabled(False)
            self.tbl.setRowCount(0)

            grand_ini = Decimal(0)
            grand_ing = Decimal(0)
            grand_ven = Decimal(0)
            grand_otr = Decimal(0)
            grand_act = Decimal(0)

            row_idx = 1
            for g in (info.grupos or []):
                for it in (g.items or []):
                    if not pasa_filtros(it):
                        continue

                    r = self.tbl.rowCount()
                    self.tbl.insertRow(r)
                    self.tbl.setItem(r, 0, self._cell(str(row_idx)))
                    self.tbl.setItem(r, 1, self._cell(it.nombre or ""))

                    self.tbl.setItem(r, 2, self._num_item(it.inicial))
                    self.tbl.setItem(r, 3, self._num_item(it.ingreso))
                    self.tbl.setItem(r, 4, self._num_item(it.ventas))
                    self.tbl.setItem(r, 5, self._num_item(it.otros))
                    self.tbl.setItem(r, 6, self._num_item(it.actual))

                    # Coloreado bonus
                    ing = Decimal(it.ingreso or 0)
                    ven = Decimal(it.ventas or 0)
                    otr = Decimal(it.otros or 0)
                    act = Decimal(it.actual or 0)
                    sin_mov = (ing == 0 and ven == 0 and otr == 0)

                    if act < 0:
                        # rojo si negativo
                        for c in range(self.tbl.columnCount()):
                            self.tbl.item(r, c).setForeground(QBrush(QColor("#b00020")))
                    elif sin_mov and not ocultar_cero:
                        # gris si sin movimiento (solo si se muestra)
                        for c in range(self.tbl.columnCount()):
                            self.tbl.item(r, c).setForeground(QBrush(QColor("#888888")))

                    # Totales
                    grand_ini += Decimal(it.inicial or 0)
                    grand_ing += ing
                    grand_ven += ven
                    grand_otr += otr
                    grand_act += act

                    row_idx += 1

            # Pie de totales
            if row_idx == 1:
                self.lbl_totales.setText("TOTAL GENERAL — (sin datos)")
            else:
                self.lbl_totales.setText(
                    f"TOTAL GENERAL — "
                    f"Inicial: {self._fmt(grand_ini)}   •   "
                    f"Ingreso: {self._fmt(grand_ing)}   •   "
                    f"Ventas: {self._fmt(grand_ven)}   •   "
                    f"Insumo: {self._fmt(grand_otr)}   •   "
                    f"Actual: {self._fmt(grand_act)}"
                )

            self.tbl.resizeRowsToContents()
            # Ordenar por NOMBRE asc por defecto
            self.tbl.setUpdatesEnabled(True)
            self.tbl.setSortingEnabled(True)
            self.tbl.horizontalHeader().setSortIndicatorShown(True)
            self.tbl.horizontalHeader().setSortIndicator(1, Qt.AscendingOrder)
            self.tbl.sortItems(1, Qt.AscendingOrder)

        except ValueError:
            QMessageBox.warning(self, "Validación", "Año inválido.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
        finally:
            self.tbl.setUpdatesEnabled(True)
            self.tbl.setSortingEnabled(True)
            self._busy(False)

    # -------- Exportaciones --------
    def exportar_pdf(self):
        """
        Nota: la exportación se hace desde el service y no respeta
        los filtros UI (texto/negativos/sin movimiento). Para exportar
        exactamente lo visible, hacé la exportación a Excel y filtrá allí,
        o adaptá el service para recibir filtros.
        """
        try:
            mes = self.cmb_mes.currentData()
            anio = int(self.txt_anio.text().strip())
        except Exception:
            QMessageBox.warning(self, "Validación", "Mes/Año inválido.")
            return

        stamp = datetime.now().strftime("%H_%M")
        sug = f"informe_stock_{anio}_{mes:02d}_{stamp}.pdf"
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", sug, "PDF (*.pdf)")
        if not ruta:
            return
        if not ruta.lower().endswith(".pdf"):
            ruta += ".pdf"

        self._busy(True)
        try:
            self._correr_con_sesion(
                lambda s: exportar_pdf_informe_stock_mensual(s, year=anio, month=mes, ruta_pdf=ruta)
            )
            QMessageBox.information(self, "PDF", f"PDF generado:\n{ruta}")
        except Exception as e:
            QMessageBox.critical(self, "Error PDF", str(e))
        finally:
            self._busy(False)

    def exportar_excel(self):
        """
        Igual que PDF: el service exporta el conjunto completo del mes,
        sin filtros UI.
        """
        try:
            mes = self.cmb_mes.currentData()
            anio = int(self.txt_anio.text().strip())
        except Exception:
            QMessageBox.warning(self, "Validación", "Mes/Año inválido.")
            return

        sug = f"informe_stock_{anio}_{mes:02d}.xlsx"
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar Excel", sug, "Excel (*.xlsx)")
        if not ruta:
            return
        if not ruta.lower().endswith(".xlsx"):
            ruta += ".xlsx"

        self._busy(True)
        try:
            self._correr_con_sesion(
                lambda s: exportar_excel_informe_stock_mensual(s, year=anio, month=mes, ruta_xlsx=ruta)
            )
            QMessageBox.information(self, "Excel", f"Excel generado:\n{ruta}")
        except Exception as e:
            QMessageBox.critical(self, "Error Excel", str(e))
        finally:
            self._busy(False)


# --- Runner manual ----
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    w = InformeStockMensualForm()
    w.show()
    sys.exit(app.exec_())
