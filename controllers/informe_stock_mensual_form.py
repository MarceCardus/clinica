# controllers/informe_stock_mensual_form.py
from __future__ import annotations
from datetime import datetime
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QWidget, QFileDialog,QAbstractItemView,QHeaderView
)
from PyQt5.QtCore import Qt, QDate
from decimal import Decimal
from utils.db import new_session
from sqlalchemy.exc import OperationalError, InterfaceError,DisconnectionError
from services.informe_stock_mensual_service import (
    obtener_informe_stock_mensual,
    exportar_pdf_informe_stock_mensual,
    exportar_excel_informe_stock_mensual,
    SPANISH_MONTHS,
)

class InformeStockMensualForm(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
     
        
        self.setWindowTitle("Informe de Stock Mensual")
        self.resize(1100, 700)

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
        self.txt_anio.setFixedWidth(80)
        top.addWidget(self.txt_anio)

        self.btn_generar = QPushButton("Generar")
        self.btn_excel = QPushButton("Exportar a Excel")
        self.btn_pdf = QPushButton("PDF")
        self.btn_cerrar = QPushButton("Cerrar")

        top.addStretch()
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
        self.tbl.setColumnWidth(0, 50)
        self.tbl.setColumnWidth(1, 420)
        self.tbl.setColumnWidth(2, 90)
        for c in range(3, 7):
            self.tbl.setColumnWidth(c, 110)
        lay.addWidget(self.tbl, 1)  # <-- FALTABA: agrega la tabla al layout y que estire
        self.lbl_totales = QLabel("")
        self.lbl_totales.setStyleSheet("font-weight: bold; padding-top: 6px;")
        lay.addWidget(self.lbl_totales)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl.setSortingEnabled(False)
        self.tbl.setAlternatingRowColors(True)
        # -------- Signals --------
        self.btn_generar.clicked.connect(self.buscar)
        self.btn_pdf.clicked.connect(self.exportar_pdf)
        self.btn_excel.clicked.connect(self.exportar_excel)
        self.btn_cerrar.clicked.connect(self.close)

        # Primera carga
        self.buscar()


    def _num(self, x) -> QTableWidgetItem:
        # texto formateado + dato crudo para ordenar numéricamente
        it = QTableWidgetItem(self._fmt(x))
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        try:
            n = int(Decimal(str(x)).quantize(Decimal("1")))
        except Exception:
            n = 0
        it.setData(Qt.EditRole, n)  # <- sorting numérico
        return it
    # -------- Util --------
    def _fmt(self, x) -> str:
        try:
            n = int(Decimal(str(x)).quantize(Decimal("1")))
        except Exception:
            n = int(x or 0)
        return f"{n:,}".replace(",", ".")

    def _cell(self, text: str, right: bool = False) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        if right:
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return it


    def _correr_con_sesion(self, fn):
        """Corre una función con sesión fresca y la cierra. Reintenta 1 vez si la conexión cae."""
        try:
            s = new_session()
            try:
                return fn(s)
            finally:
                s.close()
        except (OperationalError, InterfaceError, DisconnectionError):
            # Reintento limpio
            s = new_session()
            try:
                return fn(s)
            finally:
                s.close()
    def _busy(self, v: bool):
        for b in (self.btn_generar, self.btn_excel, self.btn_pdf):
            b.setEnabled(not v)

    def buscar(self):
        self._busy(True)
        try:
            mes  = self.cmb_mes.currentData()
            anio = int(self.txt_anio.text().strip())

            info = self._correr_con_sesion(lambda s: obtener_informe_stock_mensual(s, year=anio, month=mes))

            self.lbl_leyenda.setText(
                f"Inicial = stock al {info.corte_inicial.strftime('%d/%m/%Y')}   •   "
               
            )

            self.tbl.setSortingEnabled(False)
            self.tbl.setUpdatesEnabled(False)
            self.tbl.setRowCount(0)

            # inicializar acumuladores
            grand_ini = Decimal(0)
            grand_ing = Decimal(0)
            grand_ven = Decimal(0)
            grand_otr = Decimal(0)
            grand_act = Decimal(0)

            i = 1
            for g in info.grupos:
                for it in g.items:
                    r = self.tbl.rowCount()
                    self.tbl.insertRow(r)
                    self.tbl.setItem(r, 0, self._cell(str(i)))
                    self.tbl.setItem(r, 1, self._cell(it.nombre))
                    self.tbl.setItem(r, 2, self._num(it.inicial))
                    self.tbl.setItem(r, 3, self._num(it.ingreso))
                    self.tbl.setItem(r, 4, self._num(it.ventas))
                    self.tbl.setItem(r, 5, self._num(it.otros))
                    self.tbl.setItem(r, 6, self._num(it.actual))
                    i += 1

                    # acumular totales
                    grand_ini += it.inicial
                    grand_ing += it.ingreso
                    grand_ven += it.ventas
                    grand_otr += it.otros
                    grand_act += it.actual

            # Pie (footer) de totales fuera de la tabla
            if i == 1:
                self.lbl_totales.setText("TOTAL GENERAL — (sin datos)")
            else:
                self.lbl_totales.setText(
                    f"TOTAL GENERAL — Inicial: {self._fmt(grand_ini)}   •   "
                    f"Ingreso: {self._fmt(grand_ing)}   •   "
                    f"Ventas: {self._fmt(grand_ven)}   •   "
                    f"Insumo: {self._fmt(grand_otr)}   •   "
                    f"Actual: {self._fmt(grand_act)}"
                )

            self.tbl.resizeRowsToContents()
            # mostrar y forzar orden por NOMBRE (columna 1)
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
        mes = self.cmb_mes.currentData()
        anio = int(self.txt_anio.text().strip())

        stamp = datetime.now().strftime("%H_%M")              # <-- hh_mm
        sug = f"informe_stock_{anio}_{mes:02d}_{stamp}.pdf"   # <-- nombre con hora

        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", sug, "PDF (*.pdf)")
        if not ruta:
            return
        if not ruta.lower().endswith(".pdf"):                # asegura extensión
            ruta += ".pdf"

        self._busy(True)
        try:
            self._correr_con_sesion(lambda s: exportar_pdf_informe_stock_mensual(s, year=anio, month=mes, ruta_pdf=ruta))
            QMessageBox.information(self, "PDF", f"PDF generado:\n{ruta}")
        except Exception as e:
            QMessageBox.critical(self, "Error PDF", str(e))
        finally:
            self._busy(False)

    def exportar_excel(self):
        mes = self.cmb_mes.currentData()
        anio = int(self.txt_anio.text().strip())
        sug = f"informe_stock_{anio}_{mes:02d}.xlsx"
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar Excel", sug, "Excel (*.xlsx)")
        if not ruta: return
        self._busy(True)
        try:
            self._correr_con_sesion(lambda s: exportar_excel_informe_stock_mensual(s, year=anio, month=mes, ruta_xlsx=ruta))
            QMessageBox.information(self, "Excel", f"Excel generado:\n{ruta}")
        except Exception as e:
            QMessageBox.critical(self, "Error Excel", str(e))
        finally:
            self._busy(False)

