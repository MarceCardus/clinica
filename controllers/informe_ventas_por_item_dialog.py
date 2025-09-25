# controllers/informe_ventas_por_item_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QDateEdit, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox,
    QLineEdit, QCheckBox, QWidget, QSizePolicy, QCompleter
)
from PyQt5.QtCore import QDate, Qt, QStringListModel
from PyQt5.QtGui import QIcon, QFont

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import os

from utils.db import SessionLocal
from models.item import Item, ItemTipo
from services.informe_ventas_service import get_informe_ventas_por_item

# Export
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

import xlsxwriter


def fmt_int(n) -> str:
    try:
        v = int(Decimal(n or 0).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except Exception:
        v = 0
    s = f"{v:,}"
    return s.replace(",", ".")


class InformeVentasPorItemDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Informe - Ventas por Tipo / Ítem")
        self.db = SessionLocal()

        # ---- Filtros (1 sola línea) ----
        self.dtDesde = QDateEdit(calendarPopup=True); self.dtDesde.setDisplayFormat("dd/MM/yyyy")
        self.dtHasta = QDateEdit(calendarPopup=True); self.dtHasta.setDisplayFormat("dd/MM/yyyy")
        hoy = QDate.currentDate()
        self.dtDesde.setDate(hoy.addDays(-30)); self.dtHasta.setDate(hoy)

        self.cboTipo = QComboBox()
        self.txtProducto = QLineEdit()
        self.txtProducto.setPlaceholderText("Producto (escribí para buscar)")
        self.chkIncluirAnuladas = QCheckBox("Incluir anuladas")

        self.btnBuscar = QPushButton("Buscar")
        self.btnPdf = QPushButton("Exportar PDF")
        self.btnXlsx = QPushButton("Exportar Excel")

        top = QHBoxLayout()
        def add_pair(lbl, w: QWidget, w_fixed=False):
            top.addWidget(QLabel(lbl))
            if w_fixed:
                w.setFixedWidth(150)
            top.addWidget(w)

        add_pair("Desde:", self.dtDesde, True)
        add_pair("Hasta:", self.dtHasta, True)
        add_pair("Tipo:", self.cboTipo, True)
        add_pair("Producto:", self.txtProducto, False)
        top.addWidget(self.chkIncluirAnuladas)
        top.addStretch(1)
        top.addWidget(self.btnBuscar)
        top.addWidget(self.btnPdf)
        top.addWidget(self.btnXlsx)

        # ---- Tabla ----
        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["Tipo", "Ítem", "Cantidad", "Monto", "Promedio"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setVisible(True)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.tbl)

        # Eventos
        self.btnBuscar.clicked.connect(self.on_buscar)
        self.btnPdf.clicked.connect(self.on_export_pdf)
        self.btnXlsx.clicked.connect(self.on_export_excel)
        self.cboTipo.currentIndexChanged.connect(self._sync_completer)

        # Cargar combos y completer (excluye INSUMO)
        self._cargar_tipos()
        self._armar_completer()

        # Abrir maximizado
        self.setWindowState(Qt.WindowMaximized)

    # ---------- Carga de filtros ----------
    def _cargar_tipos(self):
        self.cboTipo.blockSignals(True)
        self.cboTipo.clear()
        self.cboTipo.addItem("— Todos —", None)
        tipos = (
            self.db.query(ItemTipo)
            .filter(ItemTipo.nombre != 'INSUMO')
            .order_by(ItemTipo.nombre.asc())
            .all()
        )
        for t in tipos:
            self.cboTipo.addItem(t.nombre, t.iditemtipo)
        self.cboTipo.blockSignals(False)

    def _armar_completer(self):
        self.items_data = (
            self.db.query(Item)
            .join(ItemTipo, ItemTipo.iditemtipo == Item.iditemtipo)
            .filter(Item.activo == True, ItemTipo.nombre != 'INSUMO')
            .order_by(Item.nombre.asc())
            .all()
        )
        nombres = [it.nombre for it in self.items_data]

        # Usar un QStringListModel para poder cambiar la lista después
        self.model_nombres = QStringListModel(nombres, self)
        self.completer = QCompleter(self.model_nombres, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.txtProducto.setCompleter(self.completer)

    def _sync_completer(self):
        idtipo = self.cboTipo.currentData()
        if not idtipo:
            filt = [it.nombre for it in self.items_data]
        else:
            filt = [it.nombre for it in self.items_data if it.iditemtipo == idtipo]
        self.model_nombres.setStringList(filt)
    # ---------- Buscar ----------
    def on_buscar(self):
        d1_q, d2_q = self.dtDesde.date(), self.dtHasta.date()
        d1 = date(d1_q.year(), d1_q.month(), d1_q.day())
        d2 = date(d2_q.year(), d2_q.month(), d2_q.day())
        if d1 > d2:
            QMessageBox.warning(self, "Informe", "La fecha 'Desde' no puede ser mayor que 'Hasta'.")
            return

        iditemtipo = self.cboTipo.currentData()
        txt = (self.txtProducto.text() or "").strip()
        incluir_anuladas = self.chkIncluirAnuladas.isChecked()

        data = get_informe_ventas_por_item(
            self.db,
            fecha_desde=d1,
            fecha_hasta=d2,
            iditemtipo=iditemtipo,
            iditem=None,                         # usamos búsqueda por nombre
            item_nombre_like=txt if txt else None,
            incluir_anuladas=incluir_anuladas,
        )
        self._pintar(data)

    def _pintar(self, data):
        filas = data.get("items", [])
        tot = data.get("totales", {})
        self.tbl.setRowCount(0)

        for r in filas:
            row = self.tbl.rowCount()
            self.tbl.insertRow(row)
            self.tbl.setItem(row, 0, QTableWidgetItem(str(r["tipo_nombre"])))
            self.tbl.setItem(row, 1, QTableWidgetItem(str(r["item_nombre"])))

            it_cant = QTableWidgetItem(fmt_int(r["cantidad_total"]))
            it_cant.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl.setItem(row, 2, it_cant)

            it_monto = QTableWidgetItem(fmt_int(r["monto_total"]))
            it_monto.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl.setItem(row, 3, it_monto)

            it_prom = QTableWidgetItem(fmt_int(r["promedio"]))
            it_prom.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl.setItem(row, 4, it_prom)

        # Totales
        row = self.tbl.rowCount()
        self.tbl.insertRow(row)
        self.tbl.setSpan(row, 0, 1, 2)
        tot_lbl = QTableWidgetItem("TOTAL")
        tot_lbl.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.tbl.setItem(row, 0, tot_lbl)

        it_cant = QTableWidgetItem(fmt_int(tot.get("cantidad_total", 0)))
        it_cant.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.tbl.setItem(row, 2, it_cant)

        it_monto = QTableWidgetItem(fmt_int(tot.get("monto_total", 0)))
        it_monto.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.tbl.setItem(row, 3, it_monto)

        self.tbl.setItem(row, 4, QTableWidgetItem(""))

        self.tbl.resizeColumnsToContents()

    # ---------- Exportar PDF ----------
    def on_export_pdf(self):
        if self.tbl.rowCount() == 0:
            QMessageBox.information(self, "PDF", "No hay datos para exportar.")
            return

        fn, _ = QFileDialog.getSaveFileName(self, "Exportar a PDF", "informe_ventas_por_item.pdf", "PDF (*.pdf)")
        if not fn:
            return

        try:
            doc = SimpleDocTemplate(fn, pagesize=landscape(A4), rightMargin=18, leftMargin=18, topMargin=18, bottomMargin=18)
            styles = getSampleStyleSheet()
            elems = []
            elems.append(Paragraph("Informe - Ventas por Tipo / Ítem", styles["Heading2"]))
            elems.append(Spacer(1, 8))

            # Construir datos de tabla
            headers = [self.tbl.horizontalHeaderItem(c).text() for c in range(self.tbl.columnCount())]
            data = [headers]
            for r in range(self.tbl.rowCount()):
                row = []
                for c in range(self.tbl.columnCount()):
                    it = self.tbl.item(r, c)
                    row.append(it.text() if it else "")
                data.append(row)

            t = Table(data, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E8EBF7")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                ('ALIGN', (2,1), (-1,-1), 'RIGHT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#FAFAFA")]),
            ]))
            elems.append(t)
            doc.build(elems)
            QMessageBox.information(self, "PDF", f"Archivo guardado:\n{fn}")
        except Exception as e:
            QMessageBox.critical(self, "PDF", f"Error al exportar PDF:\n{e}")

    # ---------- Exportar Excel ----------
    def on_export_excel(self):
        if self.tbl.rowCount() == 0:
            QMessageBox.information(self, "Excel", "No hay datos para exportar.")
            return

        fn, _ = QFileDialog.getSaveFileName(self, "Exportar a Excel", "informe_ventas_por_item.xlsx", "Excel (*.xlsx)")
        if not fn:
            return

        try:
            wb = xlsxwriter.Workbook(fn)
            ws = wb.add_worksheet("Informe")

            fmt_header = wb.add_format({'bold': True, 'bg_color': '#E8EBF7', 'border': 1})
            fmt_text = wb.add_format({'border': 1})
            fmt_int = wb.add_format({'border': 1, 'num_format': '#,##0'})  # Excel aplicará separadores según configuración regional

            # Encabezados
            for c in range(self.tbl.columnCount()):
                ws.write(0, c, self.tbl.horizontalHeaderItem(c).text(), fmt_header)

            # Filas
            for r in range(self.tbl.rowCount()):
                for c in range(self.tbl.columnCount()):
                    it = self.tbl.item(r, c)
                    val = it.text() if it else ""
                    if c >= 2 and val:  # columnas numéricas
                        # escribir como número entero
                        try:
                            ws.write_number(r+1, c, int(val.replace('.', '')), fmt_int)
                        except Exception:
                            ws.write(r+1, c, val, fmt_text)
                    else:
                        ws.write(r+1, c, val, fmt_text)

            # Auto ancho
            for c in range(self.tbl.columnCount()):
                ws.set_column(c, c, 18)

            wb.close()
            QMessageBox.information(self, "Excel", f"Archivo guardado:\n{fn}")
        except Exception as e:
            QMessageBox.critical(self, "Excel", f"Error al exportar Excel:\n{e}")
