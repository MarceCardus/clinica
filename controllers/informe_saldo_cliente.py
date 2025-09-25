# controllers/informe_saldo_cliente.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDateEdit, QPushButton,
    QTableView, QWidget, QGroupBox, QRadioButton, QFormLayout, QMessageBox, QSpacerItem,
    QSizePolicy, QAbstractItemView, QHeaderView, QDialogButtonBox, QTableWidget,
    QTableWidgetItem
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from datetime import date, timedelta
from models.paciente import Paciente
from services.saldo_cliente_service import (
    get_saldo_por_cliente, get_detalle_por_venta
)
from decimal import Decimal, ROUND_HALF_UP
# Opcional: exportadores
import csv
import json
try:
    import pandas as pd
except Exception:
    pd = None

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
except Exception:
    canvas = None


class InformeSaldoClienteDialog(QDialog):
    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Informe - Saldo por Cliente")
        self.session = session
        self._booting = True                 # <<< flag de arranque

        self._build_ui()
        self._setup_table()                  # <<< crear self.model ANTES de conectar eventos
        self._load_pacientes()
        self._set_default_dates()            # <<< setear fechas con signals bloqueados (ver abajo)
        self._wire_events()                  # <<< recién acá conectamos eventos

        # aspecto
        self.resize(1100, 700)
        self.setWindowState(self.windowState() | Qt.WindowMaximized)

        self._booting = False                # <<< fin de arranque
        # opcional: primera búsqueda automática
        self._buscar()

    # ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        # ----- Filtros (en una línea) -----
        filtros = QGroupBox("Filtros")
        fl = QHBoxLayout(filtros); fl.setSpacing(8)

        self.dtpDesde = QDateEdit(calendarPopup=True); self.dtpDesde.setDisplayFormat("dd/MM/yyyy")
        self.dtpHasta = QDateEdit(calendarPopup=True); self.dtpHasta.setDisplayFormat("dd/MM/yyyy")

        # Cliente como QLineEdit con autocompletar
        from PyQt5.QtWidgets import QLineEdit
        self.txtPaciente = QLineEdit()
        self.txtPaciente.setPlaceholderText("Cliente (escribí para buscar)")
        self.txtPaciente.setClearButtonEnabled(True)

        # Modo (a la derecha, como en tu ejemplo “todo arriba”)
        modoWrap = QWidget(); modoLay = QHBoxLayout(modoWrap); modoLay.setContentsMargins(0,0,0,0)
        self.rbResumen = QRadioButton("Resumen"); self.rbDetalle = QRadioButton("Detalle")
        self.rbResumen.setChecked(True); modoLay.addWidget(self.rbResumen); modoLay.addWidget(self.rbDetalle)

        self.btnBuscar = QPushButton("Buscar")
        self.btnExportPDF = QPushButton("Exportar PDF")
        self.btnExportExcel = QPushButton("Exportar Excel")

        fl.addWidget(QLabel("Desde:")); fl.addWidget(self.dtpDesde)
        fl.addWidget(QLabel("Hasta:")); fl.addWidget(self.dtpHasta)
        fl.addWidget(QLabel("Cliente:")); fl.addWidget(self.txtPaciente, 2)
        fl.addWidget(QLabel("Modo:")); fl.addWidget(modoWrap)
        fl.addWidget(self.btnBuscar); fl.addWidget(self.btnExportPDF); fl.addWidget(self.btnExportExcel)

        # ----- Tabla -----
        self.tbl = QTableView()
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.doubleClicked.connect(self._on_double_click)

        # ----- Totales -----
        totLay = QHBoxLayout()
        self.lblTotalVentas = QLabel("Total Ventas: 0")
        self.lblTotalSaldo  = QLabel("Total Saldo: 0")
        totLay.addStretch(1); totLay.addWidget(self.lblTotalVentas); totLay.addSpacing(20); totLay.addWidget(self.lblTotalSaldo)

        # Armado
        root.addWidget(filtros)
        root.addWidget(self.tbl, 1)
        root.addLayout(totLay)

        # Cerrar
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Close)
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.button(QDialogButtonBox.Close).setText("Cerrar")
        root.addWidget(self.buttonBox)

    def _wire_events(self):
        self.btnBuscar.clicked.connect(self._buscar)
        self.btnExportExcel.clicked.connect(self._export_excel)
        self.btnExportPDF.clicked.connect(self._export_pdf)

        # cambios de filtro disparan búsqueda
        self.dtpDesde.dateChanged.connect(lambda _: self._buscar())
        self.dtpHasta.dateChanged.connect(lambda _: self._buscar())
        self.txtPaciente.textChanged.connect(lambda _: self._buscar())
        try:
            self.txtPaciente.returnPressed.connect(self._buscar)
        except Exception:
            pass

    def _fmt0(self, x) -> str:
        q = Decimal(str(x if x is not None else 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return f"{q:,.0f}".replace(",", ".")  # 1.234.567

    def _load_pacientes(self):
        # Traemos "Apellido, Nombre" e ID para el autocompletar y para match exacto
        stmt = (
            select(Paciente.idpaciente,
                func.concat(Paciente.apellido, ', ', Paciente.nombre).label('nom'))
            .where(Paciente.estado.is_(None) | (Paciente.estado.is_(True)))
            .order_by(Paciente.apellido, Paciente.nombre)
        )
        rows = self.session.execute(stmt).fetchall()

        # índice: nombre visible -> id
        self._pac_index = {nom: pid for pid, nom in rows}

        from PyQt5.QtWidgets import QCompleter
        comp = QCompleter(list(self._pac_index.keys()), self)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        self.txtPaciente.setCompleter(comp)

    def _set_default_dates(self):
        hoy = QDate.currentDate()
        desde = QDate(hoy.year(), hoy.month(), 1)
        # evitar que dispare _buscar durante el boot
        self.dtpDesde.blockSignals(True)
        self.dtpHasta.blockSignals(True)
        self.dtpDesde.setDate(desde)
        self.dtpHasta.setDate(hoy)
        self.dtpDesde.blockSignals(False)
        self.dtpHasta.blockSignals(False)

    def _setup_table(self):
        self.model = QStandardItemModel(self)
        self.tbl.setModel(self.model)
        self._config_headers()

    def _config_headers(self):
        if self.rbResumen.isChecked():
            # payload = oculta (idventa+json para doble click)
            headers = ["Fecha", "Id Venta", "N° Factura", "Paciente", "Monto Total", "Saldo", "payload"]
        else:
            headers = ["Fecha", "Id Venta", "N° Factura", "Paciente", "Item", "Cant.", "Precio", "Desc.", "Subtotal", "Total Venta", "Saldo Venta", "payload"]
        self.model.setColumnCount(len(headers))
        self.model.setHorizontalHeaderLabels(headers)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setColumnHidden(len(headers) - 1, True)  # ocultar 'payload'

    # ---------- Acciones ----------
    def _buscar(self):
        if getattr(self, "_booting", False):
            return
        try:
            d = self.dtpDesde.date().toPyDate()
            h = self.dtpHasta.date().toPyDate()
            if h < d:
                QMessageBox.warning(self, "Informe", "La fecha Hasta no puede ser menor que Desde.")
                return
            txt = (self.txtPaciente.text() or "").strip()
            idpac = self._pac_index.get(txt) if hasattr(self, "_pac_index") else None
            modo = "resumen" if self.rbResumen.isChecked() else "detalle"

            data = get_saldo_por_cliente(self.session, d, h, idpac, modo, paciente_txt=txt or None)
            self._populate_table(data, modo)
            self._update_totals(data, modo)
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Ocurrió un error al buscar:\n{ex}")

    def _populate_table(self, data, modo):
        self._config_headers()
        self.model.removeRows(0, self.model.rowCount())

        if modo == "resumen":
            for row in data:
                payload = QStandardItem(str(row["idventa"]))  # usamos para guardar JSON
                if "detalle_items" in row and row["detalle_items"]:
                    payload.setData(row["detalle_items"], Qt.UserRole)

                items = [
                    QStandardItem(row["fecha"].strftime("%d/%m/%Y") if row["fecha"] else ""),
                    QStandardItem(str(row["idventa"])),                  # Id visible
                    QStandardItem(row.get("nro_factura") or ""),
                    QStandardItem(row["paciente"] or ""),
                    QStandardItem(self._fmt0(row["total"])),            # Monto Total
                    QStandardItem(self._fmt0(row["saldo"])),            # Saldo
                    payload                                             # oculto
                ]

                # alinear números: 4=total, 5=saldo
                self._align_right(items[4])
                self._align_right(items[5])

                for it in items:
                    it.setEditable(False)
                self.model.appendRow(items)
            return

        # ----- modo detalle -----
        for row in data:
            items = [
                QStandardItem(row["fecha"].strftime("%d/%m/%Y") if row["fecha"] else ""),
                QStandardItem(str(row.get("idventa") or "")),   # Id visible
                QStandardItem(row.get("nro_factura") or ""),
                QStandardItem(row["paciente"] or ""),
                QStandardItem(row["item"] or ""),
                QStandardItem(self._fmt0(row["cantidad"])),
                QStandardItem(self._fmt0(row["preciounitario"])),
                QStandardItem(self._fmt0(row["descuento"])),
                QStandardItem(self._fmt0(row["subtotal_item"])),
                QStandardItem(self._fmt0(row["total_venta"])),
                QStandardItem(self._fmt0(row["saldo_venta"])),
                QStandardItem(str(row.get("idventa") or ""))   # payload oculto (sin JSON aquí)
            ]
            for idx in (5,6,7,8,9,10):
                self._align_right(items[idx])
            for it in items:
                it.setEditable(False)
            self.model.appendRow(items)

    def _update_totals(self, data, modo):
        from decimal import Decimal
        D = lambda x: Decimal(str(x if x is not None else 0))

        if modo == "resumen":
            total_ventas = sum(D(r.get("total")) for r in data)
            total_saldo  = sum(D(r.get("saldo")) for r in data)
            self.lblTotalVentas.setText(f"Total Ventas: {self._fmt0(total_ventas)}")
            self.lblTotalSaldo.setText(f"Total Saldo: {self._fmt0(total_saldo)}")
            return

        # detalle
        total_ventas = sum(D(r.get("subtotal_item")) for r in data)
        vistos = set()
        total_saldo = Decimal("0")
        for r in data:
            idv = r.get("idventa")
            if idv is None or idv in vistos:
                continue
            vistos.add(idv)
            total_saldo += D(r.get("saldo_venta"))

        self.lblTotalVentas.setText(f"Total Ítems: {self._fmt0(total_ventas)}")
        self.lblTotalSaldo.setText(f"Total Saldo: {self._fmt0(total_saldo)}")

    def _limpiar(self):
            self._set_default_dates()
            self.cboPaciente.setCurrentIndex(0)
            self.rbResumen.setChecked(True)
            self.model.removeRows(0, self.model.rowCount())
            self.lblTotalVentas.setText("Total Ventas: 0")
            self.lblTotalSaldo.setText("Total Saldo: 0")

    def _align_right(self, qitem: QStandardItem):
            qitem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)    


    def _on_double_click(self, index):
        if not self.rbResumen.isChecked():
            return
        row = index.row()
        payload_item = self.model.item(row, self.model.columnCount()-1)  # oculto
        detalle_json = payload_item.data(Qt.UserRole)
        idventa_vis = self.model.item(row, 1).text()  # columna "Id Venta"

        if isinstance(detalle_json, str):
            try: import json; detalle_json = json.loads(detalle_json)
            except Exception: detalle_json = None

        if detalle_json:
            items = [{
                "item": d.get("item"),
                "cantidad": float(d.get("cantidad") or 0),
                "preciounitario": float(d.get("precio") or 0),
                "descuento": float(d.get("descuento") or 0),
                "subtotal_item": float(d.get("subtotal") or 0),
            } for d in detalle_json]
            self._show_detalle_dialog(idventa_vis, items)
            return

        # fallback a vista detalle
        try:
            idv = int(idventa_vis)
        except:
            return
        det = get_detalle_por_venta(self.session, idv)
        self._show_detalle_dialog(idv, det)

    def _show_detalle_dialog(self, idventa: int, items: list[dict]):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Detalle de Venta #{idventa}")
        lay = QVBoxLayout(dlg)
        tbl = QTableWidget()
        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels(["Item", "Cantidad", "Precio", "Descuento", "Subtotal"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl.setRowCount(len(items))
        for r, it in enumerate(items):
            tbl.setItem(r, 0, QTableWidgetItem(str(it["item"])))
            tbl.setItem(r, 1, QTableWidgetItem(f'{it["cantidad"]:.2f}'))
            tbl.setItem(r, 2, QTableWidgetItem(f'{it["preciounitario"]:.2f}'))
            tbl.setItem(r, 3, QTableWidgetItem(f'{it["descuento"]:.2f}'))
            tbl.setItem(r, 4, QTableWidgetItem(f'{it["subtotal_item"]:.2f}'))
        lay.addWidget(tbl)
        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.button(QDialogButtonBox.Close).setText("Cerrar")
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        dlg.resize(800, 400)
        dlg.exec_()

    # ---------- Exportadores ----------
    def _export_excel(self):
        if self.model.rowCount() == 0:
            QMessageBox.information(self, "Exportar", "No hay datos para exportar.")
            return
        try:
            headers = [self.model.headerData(c, Qt.Horizontal) for c in range(self.model.columnCount()-1)]
            rows = []
            for r in range(self.model.rowCount()):
                fila = []
                for c in range(self.model.columnCount()-1):  # sin idventa
                    fila.append(self.model.item(r, c).text())
                rows.append(fila)
            if pd:
                df = pd.DataFrame(rows, columns=headers)
                ruta = self._suggest_filename("SaldoPorCliente", "xlsx")
                df.to_excel(ruta, index=False)
                QMessageBox.information(self, "Exportar", f"Excel generado:\n{ruta}")
            else:
                # CSV fallback
                ruta = self._suggest_filename("SaldoPorCliente", "csv")
                with open(ruta, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f, delimiter=";")
                    w.writerow(headers)
                    w.writerows(rows)
                QMessageBox.information(self, "Exportar", f"CSV generado:\n{ruta}")
        except Exception as ex:
            QMessageBox.critical(self, "Exportar", f"Error al exportar:\n{ex}")

    def _export_pdf(self):
        if self.model.rowCount() == 0:
            QMessageBox.information(self, "Exportar", "No hay datos para exportar.")
            return
        if not canvas:
            QMessageBox.warning(self, "Exportar", "ReportLab no está instalado. Exportá a Excel/CSV.")
            return
        try:
            ruta = self._suggest_filename("SaldoPorCliente", "pdf")
            c = canvas.Canvas(ruta, pagesize=A4)
            w, h = A4
            y = h - 2*cm
            c.setFont("Helvetica-Bold", 12)
            c.drawString(2*cm, y, "Informe - Saldo por Cliente")
            y -= 0.8*cm
            c.setFont("Helvetica", 9)

            # Encabezados (máx. simple, 6-8 cols sin desbordar)
            max_cols = min(self.model.columnCount()-1, 8)
            headers = [self.model.headerData(cix, Qt.Horizontal) for cix in range(max_cols)]
            col_w = (w - 4*cm) / max_cols
            # header row
            for i, htxt in enumerate(headers):
                c.drawString(2*cm + i*col_w, y, str(htxt))
            y -= 0.6*cm
            c.line(2*cm, y, w-2*cm, y)
            y -= 0.4*cm

            # filas
            for r in range(self.model.rowCount()):
                if y < 2*cm:
                    c.showPage()
                    y = h - 2*cm
                for i in range(max_cols):
                    txt = self.model.item(r, i).text()
                    c.drawString(2*cm + i*col_w, y, txt[:28])
                y -= 0.5*cm

            # totales
            y -= 0.4*cm
            c.line(2*cm, y, w-2*cm, y)
            y -= 0.6*cm
            c.setFont("Helvetica-Bold", 10)
            c.drawString(2*cm, y, self.lblTotalVentas.text())
            y -= 0.5*cm
            c.drawString(2*cm, y, self.lblTotalSaldo.text())

            c.save()
            QMessageBox.information(self, "Exportar", f"PDF generado:\n{ruta}")
        except Exception as ex:
            QMessageBox.critical(self, "Exportar", f"Error al exportar PDF:\n{ex}")

    def _suggest_filename(self, base: str, ext: str) -> str:
        # Si ya tenés un picker reutilizable, usalo. Aquí generamos un nombre simple.
        import os, datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre = f"{base}_{ts}.{ext}"
        return os.path.join(os.getcwd(), nombre)
