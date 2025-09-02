# controllers/informe_stock_mensual_form.py
from __future__ import annotations
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QWidget, QFileDialog
)
from PyQt5.QtCore import Qt, QDate
from decimal import Decimal

from services.informe_stock_mensual_service import (
    obtener_informe_stock_mensual,
    exportar_pdf_informe_stock_mensual,
    exportar_excel_informe_stock_mensual,
    SPANISH_MONTHS,
)

class InformeStockMensualForm(QDialog):
    def __init__(self, session, parent: QWidget | None = None):
        super().__init__(parent)
        self.session = session

        self.setWindowTitle("Informe de Stock Mensual (Agrupado por Tipo)")
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
        self.tbl = QTableWidget(0, 8)
        self.tbl.setHorizontalHeaderLabels([
            "#", "Tipo / Ítem", "Unidad", "Inicial", "Ingreso", "Ventas", "Otros (Insumo)", "Actual"
        ])
        self.tbl.setColumnWidth(0, 50)
        self.tbl.setColumnWidth(1, 420)
        self.tbl.setColumnWidth(2, 90)
        for c in range(3, 8):
            self.tbl.setColumnWidth(c, 110)
        lay.addWidget(self.tbl)

        # -------- Signals --------
        self.btn_generar.clicked.connect(self.buscar)
        self.btn_pdf.clicked.connect(self.exportar_pdf)
        self.btn_excel.clicked.connect(self.exportar_excel)
        self.btn_cerrar.clicked.connect(self.close)

        # Primera carga
        self.buscar()

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

    # -------- Cargar datos --------
    def buscar(self):
        try:
            mes = self.cmb_mes.currentData()
            anio = int(self.txt_anio.text().strip())
        except Exception:
            QMessageBox.warning(self, "Validación", "Año inválido.")
            return

        info = obtener_informe_stock_mensual(self.session, year=anio, month=mes)

        # Leyenda clara (coincide con el cálculo del service: ingreso = todos los INGRESOS del mes)
        self.lbl_leyenda.setText(
            f"Inicial = stock al {info.corte_inicial.strftime('%d/%m/%Y')}   •   "
            f"Ingreso = ingresos de {SPANISH_MONTHS[mes]} {anio}   •   "
            f"Ventas = ventas de {SPANISH_MONTHS[mes]} {anio}   •   "
            f"Otros (Insumo) = salidas no-venta de {SPANISH_MONTHS[mes]} {anio}"
        )

        self.tbl.setRowCount(0)
        i = 1
        for g in info.grupos:
            # Cabecera del grupo (Tipo)
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setSpan(r, 1, 1, 7)
            hdr = QTableWidgetItem(f"{g.tipo}")
            hdr.setFlags(Qt.ItemIsEnabled)
            hdr.setBackground(Qt.lightGray)
            self.tbl.setItem(r, 1, hdr)

            # Ítems del grupo
            for it in g.items:
                r = self.tbl.rowCount()
                self.tbl.insertRow(r)
                self.tbl.setItem(r, 0, self._cell(str(i)))
                self.tbl.setItem(r, 1, self._cell(it.nombre))
                self.tbl.setItem(r, 2, self._cell(it.unidad or ""))
                self.tbl.setItem(r, 3, self._cell(self._fmt(it.inicial), True))
                self.tbl.setItem(r, 4, self._cell(self._fmt(it.ingreso), True))
                self.tbl.setItem(r, 5, self._cell(self._fmt(it.ventas), True))
                self.tbl.setItem(r, 6, self._cell(self._fmt(it.otros), True))
                self.tbl.setItem(r, 7, self._cell(self._fmt(it.actual), True))
                i += 1

        self.tbl.resizeRowsToContents()

    # -------- Exportaciones --------
    def exportar_pdf(self):
        mes = self.cmb_mes.currentData()
        anio = int(self.txt_anio.text().strip())
        sug = f"informe_stock_{anio}_{mes:02d}.pdf"
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", sug, "PDF (*.pdf)")
        if not ruta:
            return
        try:
            exportar_pdf_informe_stock_mensual(self.session, year=anio, month=mes, ruta_pdf=ruta)
            QMessageBox.information(self, "PDF", f"PDF generado:\n{ruta}")
        except Exception as e:
            QMessageBox.critical(self, "Error PDF", str(e))

    def exportar_excel(self):
        mes = self.cmb_mes.currentData()
        anio = int(self.txt_anio.text().strip())
        sug = f"informe_stock_{anio}_{mes:02d}.xlsx"
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar Excel", sug, "Excel (*.xlsx)")
        if not ruta:
            return
        try:
            exportar_excel_informe_stock_mensual(self.session, year=anio, month=mes, ruta_xlsx=ruta)
            QMessageBox.information(self, "Excel", f"Excel generado:\n{ruta}")
        except Exception as e:
            QMessageBox.critical(self, "Error Excel", str(e))
