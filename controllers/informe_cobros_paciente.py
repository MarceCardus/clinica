# controllers/informe_cobros_paciente.py
from datetime import date
from decimal import Decimal

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDateEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCompleter, QFileDialog, QMessageBox
)
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor, QBrush

from sqlalchemy.orm import Session

from services.inf_cobros_pac_service import (
    get_cobros_por_paciente, buscar_pacientes_min
)
from utils.db import SessionLocal


class InformeCobrosPorPacienteDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Informe de Cobros por Paciente (agrupado por venta)")

        # Ventana grande
        self.setMinimumSize(1700, 720)
        self.resize(1700, 820)
        # Abrir maximizado (opcional):
        # self.setWindowState(self.windowState() | Qt.WindowMaximized)

        self.session: Session = SessionLocal()

        # ===== Filtros =====
        top = QHBoxLayout()
        lbl_pac = QLabel("Paciente:")
        self.txt_pac = QLineEdit()
        self.txt_pac.setPlaceholderText("Buscar paciente por nombre, apellido o CI…")
        self.txt_pac.textEdited.connect(self._on_paciente_text)
        self._idpaciente_sel = None

        self.model = QStandardItemModel(self)
        self.completer = QCompleter(self.model, self)
        self.completer.setCaseSensitivity(False)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.activated.connect(self._on_completer_activated)
        self.txt_pac.setCompleter(self.completer)

        lbl_desde = QLabel("Desde:")
        self.dt_desde = QDateEdit(calendarPopup=True)
        hoy = date.today()
        self.dt_desde.setDate(QDate(hoy.year, hoy.month, 1))

        lbl_hasta = QLabel("Hasta:")
        self.dt_hasta = QDateEdit(calendarPopup=True)
        self.dt_hasta.setDate(QDate(hoy.year, hoy.month, hoy.day))

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(self._buscar)

        self.btn_export_xlsx = QPushButton("Exportar Excel")
        self.btn_export_xlsx.clicked.connect(self._exportar_xlsx)

        top.addWidget(lbl_pac)
        top.addWidget(self.txt_pac, 2)
        top.addSpacing(12)
        top.addWidget(lbl_desde)
        top.addWidget(self.dt_desde)
        top.addWidget(lbl_hasta)
        top.addWidget(self.dt_hasta)
        top.addSpacing(12)
        top.addWidget(self.btn_buscar)
        top.addWidget(self.btn_export_xlsx)

        # ===== Tabla =====
        self.tbl = QTableWidget(0, 6, self)
        self.tbl.setHorizontalHeaderLabels([
            "Fecha cobro", "ID Cobro", "Forma de pago", "Monto cobrado", "Saldo después", "Observaciones"
        ])
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)  # anchos ajustables
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        self.tbl.setAlternatingRowColors(True)

        # Anchos compactos
        self.tbl.setColumnWidth(0, 110)  # Fecha cobro
        self.tbl.setColumnWidth(1, 80)   # ID Cobro
        self.tbl.setColumnWidth(2, 140)  # Forma pago
        self.tbl.setColumnWidth(3, 130)  # Monto
        self.tbl.setColumnWidth(4, 130)  # Saldo
        hh.setStretchLastSection(True)   # Observaciones se estira

        # Layout
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.tbl)

        # Precargar sugerencias
        self._refrescar_sugerencias("")

    # ---------- buscador paciente ----------
    def _refrescar_sugerencias(self, texto):
        self.model.clear()
        for idp, rotulo in buscar_pacientes_min(self.session, texto, limit=25):
            it = QStandardItem(rotulo)
            it.setData(idp, Qt.UserRole)
            self.model.appendRow(it)

    def _on_paciente_text(self, texto):
        self._idpaciente_sel = None
        self._refrescar_sugerencias(texto)

    def _on_completer_activated(self, text):
        for i in range(self.model.rowCount()):
            it = self.model.item(i)
            if it.text() == text:
                self._idpaciente_sel = it.data(Qt.UserRole)
                self.txt_pac.setText(text)
                break

    # ---------- acciones ----------
    def _buscar(self):
        if not self._idpaciente_sel:
            QMessageBox.warning(self, "Falta paciente", "Seleccioná un paciente de la lista.")
            return
        desde = self.dt_desde.date().toPyDate()
        hasta = self.dt_hasta.date().toPyDate()
        if hasta < desde:
            QMessageBox.warning(self, "Rango inválido", "La fecha 'Hasta' no puede ser menor que 'Desde'.")
            return

        bloques = get_cobros_por_paciente(self.session, self._idpaciente_sel, desde, hasta)
        self._poblar_tabla(bloques)

    def _poblar_tabla(self, bloques):
        self.tbl.setRowCount(0)

        header_brush = QBrush(QColor(205, 92, 35))      # tono oscuro
        header_fg    = QBrush(QColor(255, 255, 255))    # texto blanco
        sep_brush    = QBrush(QColor(245, 235, 230))    # separador suave

        def add_header_row(texto: str):
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            it = QTableWidgetItem(texto)
            it.setFlags(Qt.ItemIsEnabled)
            it.setBackground(header_brush)
            it.setForeground(header_fg)
            f = it.font(); f.setBold(True); it.setFont(f)
            it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.tbl.setSpan(r, 0, 1, self.tbl.columnCount())
            self.tbl.setItem(r, 0, it)

        def add_total_venta_row(v, montototal: Decimal):
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            etiqueta = (f"Total Venta")
            it_lbl = QTableWidgetItem(etiqueta)
            it_monto = QTableWidgetItem(f"{montototal:,.0f}".replace(",", "."))
            # itálico
            f1 = it_lbl.font(); f1.setItalic(True); it_lbl.setFont(f1)
            f2 = it_monto.font(); f2.setItalic(True); it_monto.setFont(f2)
            self.tbl.setSpan(r, 0, 1, 3)   # texto ocupa 3 cols
            self.tbl.setItem(r, 0, it_lbl)
            self.tbl.setItem(r, 3, it_monto)

        for b in bloques:
            v = b["venta"]
            header = (f"VENTA #{v['idventa']}  |  Fecha venta: {v['fecha'].strftime('%d/%m/%Y')}  |  "
                      f"N° Factura: {v['nro_factura'] or '-'}  |  "
                      f"Monto total: {v['montototal']:,.0f}")
            header = header.replace(",", ".")
            add_header_row(header)

            # Mostrar TOTAL VENTA (monto total de la factura)
            add_total_venta_row(v, v["montototal"])

            # Eventos (cobros) con saldo corrido
            for ev in b["eventos"]:
                r = self.tbl.rowCount()
                self.tbl.insertRow(r)
                self.tbl.setItem(r, 0, QTableWidgetItem(ev["fecha"].strftime("%d/%m/%Y")))
                self.tbl.setItem(r, 1, QTableWidgetItem(str(ev["idcobro"])))
                self.tbl.setItem(r, 2, QTableWidgetItem(ev["formapago"]))
                self.tbl.setItem(r, 3, QTableWidgetItem(f"{ev['monto']:,.0f}".replace(",", ".")))
                self.tbl.setItem(r, 4, QTableWidgetItem(f"{ev['saldo_despues']:,.0f}".replace(",", ".")))
                self.tbl.setItem(r, 5, QTableWidgetItem(ev["observaciones"]))

            # Fila “Saldo” (saldo al final del rango)
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            it_lab = QTableWidgetItem("Saldo")
            f = it_lab.font(); f.setBold(True); it_lab.setFont(f)
            self.tbl.setItem(r, 0, it_lab)
            it_val = QTableWidgetItem(f"{b['saldo_final_rango']:,.0f}".replace(",", "."))
            f2 = it_val.font(); f2.setBold(True); it_val.setFont(f2)
            self.tbl.setItem(r, 4, it_val)

            # Separador
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            sep = QTableWidgetItem(" ")
            sep.setFlags(Qt.ItemIsEnabled)
            sep.setBackground(sep_brush)
            self.tbl.setSpan(r, 0, 1, self.tbl.columnCount())
            self.tbl.setItem(r, 0, sep)

        self.tbl.scrollToTop()

    # ---------- exportar a Excel ----------
    @staticmethod
    def _to_number(txt: str):
        """Convierte '1.234.567' a número para Excel."""
        if not txt:
            return 0
        try:
            return int(txt.replace(".", "").replace(",", ""))
        except Exception:
            try:
                return float(txt.replace(".", "").replace(",", "."))
            except Exception:
                return 0

    def _exportar_xlsx(self):
        if self.tbl.rowCount() == 0:
            QMessageBox.information(self, "Sin datos", "No hay datos para exportar.")
            return

        from datetime import datetime
        ahora = datetime.now().strftime("%d%m%y_%H%M")
        default_name = f"informe_cobros_paciente_{ahora}.xlsx"

        fn, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Excel",
            default_name,
            "Excel (*.xlsx)"
        )
        if not fn:
            return

        try:
            import xlsxwriter
        except ImportError:
            QMessageBox.warning(
                self, "Falta dependencia",
                "Para exportar a Excel instalá: pip install xlsxwriter"
            )
            return

        headers = ["Fecha cobro", "ID Cobro", "Forma de pago",
                   "Monto cobrado", "Saldo después", "Observaciones"]

        wb = xlsxwriter.Workbook(fn)
        ws = wb.add_worksheet("Informe")

        # Formatos
        fmt_hdr    = wb.add_format({"bold": True, "bg_color": "#D9D9D9", "border": 1})
        fmt_group  = wb.add_format({"bold": True, "font_color": "#FFFFFF",
                                    "bg_color": "#8B4513", "align": "left", "valign": "vcenter"})
        fmt_sep    = wb.add_format({"bg_color": "#F5EBE6"})
        fmt_money  = wb.add_format({"num_format": "#,##0"})
        fmt_italic = wb.add_format({"italic": True})
        fmt_bold   = wb.add_format({"bold": True})

        # Encabezados
        for c, h in enumerate(headers):
            ws.write(0, c, h, fmt_hdr)

        excel_row = 1
        col_widths = [len(h) for h in headers]

        for r in range(self.tbl.rowCount()):
            # Cabecera de venta (span total)
            if self.tbl.columnSpan(r, 0) == self.tbl.columnCount():
                txt = (self.tbl.item(r, 0).text() if self.tbl.item(r, 0) else "").strip()
                if not txt:
                    ws.set_row(excel_row, None, fmt_sep)
                    excel_row += 1
                    continue
                ws.merge_range(excel_row, 0, excel_row, len(headers) - 1, txt, fmt_group)
                col_widths[0] = max(col_widths[0], len(txt))
                excel_row += 1
                continue

            fila = []
            for c in range(len(headers)):
                it = self.tbl.item(r, c)
                fila.append(it.text() if it else "")

            label = (fila[0] or "").lower()
            if label.startswith("total venta"):
                # "Total Venta — Venta #.. | Fecha ... | N° Factura: -"
                ws.merge_range(excel_row, 0, excel_row, 2, fila[0], fmt_italic)
                ws.write_number(excel_row, 3, self._to_number(fila[3]), fmt_italic)
            elif label == "saldo":
                ws.write(excel_row, 0, fila[0], fmt_bold)
                ws.write_number(excel_row, 4, self._to_number(fila[4]), fmt_bold)
            else:
                ws.write(excel_row, 0, fila[0])
                ws.write(excel_row, 1, fila[1])
                ws.write(excel_row, 2, fila[2])
                ws.write_number(excel_row, 3, self._to_number(fila[3]), fmt_money if fila[3] else None)
                ws.write_number(excel_row, 4, self._to_number(fila[4]), fmt_money if fila[4] else None)
                ws.write(excel_row, 5, fila[5])

            for i, val in enumerate(fila):
                col_widths[i] = max(col_widths[i], len(val))

            excel_row += 1

        # Ajuste de anchos
        for i, w in enumerate(col_widths):
            ws.set_column(i, i, min(w + 2, 60))

        wb.close()
        QMessageBox.information(self, "Exportado", f"Excel guardado:\n{fn}")
