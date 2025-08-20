# controllers/informe_ventas_form.py
import sys
from decimal import Decimal

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QDateEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QGroupBox, QApplication, QCompleter, QSplitter, QCheckBox
)
from PyQt5.QtCore import Qt, QDate, QTime
from PyQt5.QtGui import QFont, QColor, QBrush

from utils.db import SessionLocal
from sqlalchemy import and_, func, literal, or_, case

# ====== MODELOS ======
from models.venta import Venta
from models.venta_detalle import VentaDetalle
from models.paciente import Paciente
from models.producto import Producto
from models.paquete import Paquete
from models.item import Item


def col(model, *names):
    for n in names:
        if hasattr(model, n):
            return getattr(model, n)
    return None


class VentasReportForm(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Informe de Ventas")
        self.resize(1100, 700)
        self.session = SessionLocal()

        self._build_ui()
        self._wire_events()
        self._load_filters()
        self.buscar()

    # ---------- UI ----------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # ----- Filtros -----
        filtros = QGroupBox("Filtros")
        fl = QHBoxLayout(filtros); fl.setSpacing(8)

        self.dt_desde = QDateEdit(calendarPopup=True)
        self.dt_hasta = QDateEdit(calendarPopup=True)
        hoy = QDate.currentDate()
        self.dt_desde.setDate(hoy); self.dt_hasta.setDate(hoy)
        self.dt_desde.setDisplayFormat("dd/MM/yyyy")
        self.dt_hasta.setDisplayFormat("dd/MM/yyyy")

        self.txt_cliente = QLineEdit()
        self.txt_cliente.setPlaceholderText("Cliente (escribí para buscar)")
        self.txt_cliente.setClearButtonEnabled(True)

        self.chk_mostrar_anuladas = QCheckBox("Mostrar anuladas")
        self.chk_mostrar_anuladas.setChecked(False)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_pdf = QPushButton("Exportar PDF")
        self.btn_excel = QPushButton("Exportar Excel")

        fl.addWidget(QLabel("Desde:")); fl.addWidget(self.dt_desde)
        fl.addWidget(QLabel("Hasta:")); fl.addWidget(self.dt_hasta)
        fl.addWidget(QLabel("Cliente:")); fl.addWidget(self.txt_cliente, 2)
        fl.addWidget(self.chk_mostrar_anuladas)
        fl.addWidget(self.btn_buscar); fl.addWidget(self.btn_pdf); fl.addWidget(self.btn_excel)

        # ----- Splitter maestro/detalle/resumen -----
        splitter = QSplitter(); splitter.setOrientation(Qt.Vertical)

        # +1 columna "Estado"
        self.table_master = QTableWidget(0, 7)
        self.table_master.setHorizontalHeaderLabels(
            ["ID Venta", "Fecha", "Cliente", "Factura", "Monto Total", "IVA Total", "Estado"]
        )
        self.table_master.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_master.verticalHeader().setVisible(False)
        self.table_master.setAlternatingRowColors(True)
        self.table_master.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_master.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_master.setSelectionMode(QTableWidget.SingleSelection)

        self.table_detalle = QTableWidget(0, 4)
        self.table_detalle.setHorizontalHeaderLabels(["Cantidad", "Ítem", "Precio Unitario", "Total Fila"])
        self.table_detalle.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_detalle.verticalHeader().setVisible(False)
        self.table_detalle.setAlternatingRowColors(True)
        self.table_detalle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_detalle.setSelectionBehavior(QTableWidget.SelectRows)

        # Resumen por ítem (rango completo) - SIN "Líneas (veces)"
        self.table_resumen = QTableWidget(0, 3)
        self.table_resumen.setHorizontalHeaderLabels(["Ítem", "Cantidad total", "Monto total"])
        self.table_resumen.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_resumen.verticalHeader().setVisible(False)
        self.table_resumen.setAlternatingRowColors(True)
        self.table_resumen.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_resumen.setSelectionBehavior(QTableWidget.SelectRows)

        splitter.addWidget(self.table_master)
        splitter.addWidget(self.table_detalle)
        #splitter.addWidget(self.table_resumen)
        splitter.setSizes([360, 220, 160])

        # Totales
        tot_layout = QHBoxLayout(); tot_layout.addStretch(1)
        self.lbl_total_monto = QLabel("Total Monto: 0")
        self.lbl_total_iva = QLabel("Total IVA: 0")
        f = QFont(); f.setBold(True)
        self.lbl_total_monto.setFont(f); self.lbl_total_iva.setFont(f)
        tot_layout.addWidget(self.lbl_total_monto); tot_layout.addSpacing(20); tot_layout.addWidget(self.lbl_total_iva)

        layout.addWidget(filtros)
        layout.addWidget(splitter, 1)
        layout.addLayout(tot_layout)

    def _wire_events(self):
        self.btn_buscar.clicked.connect(self.buscar)
        self.btn_pdf.clicked.connect(self.exportar_pdf)
        self.btn_excel.clicked.connect(self.exportar_excel)
        self.txt_cliente.textChanged.connect(lambda _: self.buscar())
        self.table_master.itemSelectionChanged.connect(self._on_master_changed)
        self.chk_mostrar_anuladas.stateChanged.connect(lambda _ : self.buscar())
        self.dt_desde.dateChanged.connect(lambda _ : self.buscar())
        self.dt_hasta.dateChanged.connect(lambda _ : self.buscar())

    # ---------- Carga de filtros ----------
    def _load_filters(self):
        clientes = [r[0] for r in self.session.query(Paciente.nombre).order_by(Paciente.nombre).all()]
        c = QCompleter(clientes, self)
        c.setCaseSensitivity(Qt.CaseInsensitive)
        c.setFilterMode(Qt.MatchContains)
        self.txt_cliente.setCompleter(c)

    # ---------- Helpers dinamic ----------
    def _comp_col(self):
        c = col(Venta, "nro_comprobante", "comprobante", "nrofactura", "nro_factura")
        return c if c is not None else literal("")

    def _monto_col(self):
        m = col(Venta, "montototal", "monto_total", "total")
        if m is not None:
            return m
        return (
            self.session.query(func.coalesce(func.sum(VentaDetalle.cantidad * VentaDetalle.preciounitario), 0))
            .filter(VentaDetalle.idventa == Venta.idventa)
            .correlate(Venta).scalar_subquery()
        )

    def _has_anulada_bool(self): return hasattr(Venta, "anulada")
    def _has_estado_text(self): return hasattr(Venta, "estado") or hasattr(Venta, "estadoventa")
    def _estado_col(self): return col(Venta, "estado", "estadoventa")

    def _estado_text_expr(self):
        c = self._estado_col()
        if c is not None:
            return c
        if self._has_anulada_bool():
            return case((col(Venta, "anulada") == True, literal("ANULADA")), else_=literal("Generada"))
        return literal("")

    # ---------- Búsqueda ----------
    def _filtros(self):
        desde = self.dt_desde.date().toPyDate()
        hasta = self.dt_hasta.date().toPyDate()
        cli_txt = (self.txt_cliente.text() or "").strip()

        filtros = [func.date(Venta.fecha).between(desde, hasta)]
        if cli_txt:
            filtros.append(Paciente.nombre.ilike(f"%{cli_txt}%"))

        if not self.chk_mostrar_anuladas.isChecked():
            if self._has_anulada_bool():
                filtros.append(or_(Venta.anulada.is_(False), Venta.anulada.is_(None)))
            elif self._has_estado_text():
                filtros.append(func.upper(self._estado_col()) != "ANULADA")

        return filtros

    def buscar(self):
        filtros = self._filtros()
        monto_col = self._monto_col()
        comp_col = self._comp_col()
        estado_expr = self._estado_text_expr()

        q_master = (
            self.session.query(
                Venta.idventa,
                Venta.fecha.label("fecha"),
                (func.concat(Paciente.nombre, " ", Paciente.apellido)).label("cliente"),
                comp_col.label("nro_comprobante"),
                monto_col.label("montototal"),
                (monto_col / 11).label("iva_total"),
                estado_expr.label("estado_txt"),
                (col(Venta, "anulada") if self._has_anulada_bool() else literal(None)).label("anulada_flag")
            )
            .join(Paciente, Venta.idpaciente == Paciente.idpaciente)
            .filter(and_(*filtros))
            .order_by(Venta.fecha.asc(), Venta.idventa.asc())
            .distinct()
        )
        rows = q_master.all()
        self._llenar_maestro(rows)

        if rows:
            self.table_master.selectRow(0)
            self._cargar_detalle(rows[0].idventa)
        else:
            self.table_detalle.setRowCount(0)

        # Resumen del rango
        self._cargar_resumen()

    # ---------- Exportar Excel ----------
    def exportar_excel(self):
        try:
            import pandas as pd
        except ImportError:
            QMessageBox.warning(self, "Excel", "Necesitás instalar pandas.\nSigo con CSV.")
            self._exportar_csv_simple()
            return

        filtros = self._filtros()
        monto_col = self._monto_col()
        comp_col = self._comp_col()
        estado_expr = self._estado_text_expr()

        # Maestro
        q_master = (
            self.session.query(
                Venta.idventa.label("ID Venta"),
                Venta.fecha.label("Fecha"),
                (func.concat(Paciente.nombre, " ", Paciente.apellido)).label("cliente"),
                comp_col.label("Factura"),
                monto_col.label("Monto Total"),
                (monto_col / 11).label("IVA Total"),
                estado_expr.label("Estado"),
            )
            .join(Paciente, Venta.idpaciente == Paciente.idpaciente)
            .filter(and_(*filtros))
            .order_by(Venta.fecha.asc(), Venta.idventa.asc())
            .distinct()
        )
        master_rows = q_master.all()

        # Detalle
        item_nombre = Item.nombre.label("Ítem")
        q_det = (
            self.session.query(
                VentaDetalle.idventa.label("ID Venta"),
                VentaDetalle.cantidad.label("Cantidad"),
                item_nombre,
                VentaDetalle.preciounitario.label("Precio Unitario"),
                (VentaDetalle.cantidad * VentaDetalle.preciounitario).label("Total Fila"),
            )
            .join(Venta, Venta.idventa == VentaDetalle.idventa)
            .join(Paciente, Venta.idpaciente == Paciente.idpaciente)
            .join(Item, VentaDetalle.iditem == Item.iditem)
            .filter(and_(*filtros))
            .order_by(VentaDetalle.idventa.desc(), item_nombre.asc())
        )
        det_rows = q_det.all()

        # Resumen (por Ítem) - SIN "Líneas (veces)"
        q_res = (
            self.session.query(
                item_nombre,
                func.sum(VentaDetalle.cantidad).label("Cantidad total"),
                func.sum(VentaDetalle.cantidad * VentaDetalle.preciounitario).label("Monto total"),
            )
            .join(Venta, Venta.idventa == VentaDetalle.idventa)
            .join(Paciente, Venta.idpaciente == Paciente.idpaciente)
            .join(Item, VentaDetalle.iditem == Item.iditem)
            .filter(and_(*filtros))
            .group_by(item_nombre)
            .order_by(item_nombre.asc())
        )
        res_rows = q_res.all()

        import pandas as pd
        df_master = pd.DataFrame(master_rows, columns=["ID Venta","Fecha","Cliente","Factura","Monto Total","IVA Total","Estado"])
        if not df_master.empty:
            df_master["Fecha"] = pd.to_datetime(df_master["Fecha"]).dt.strftime("%d/%m/%Y")
        df_det = pd.DataFrame(det_rows, columns=["ID Venta","Cantidad","Ítem","Precio Unitario","Total Fila"])
        df_resumen = pd.DataFrame(res_rows, columns=["Ítem","Cantidad total","Monto total"])

        # tipos numéricos
        for col in ["Monto Total","IVA Total"]:
            if col in df_master.columns: df_master[col] = pd.to_numeric(df_master[col], errors="coerce")
        for col in ["Precio Unitario","Total Fila"]:
            if col in df_det.columns: df_det[col] = pd.to_numeric(df_det[col], errors="coerce")
        if "Monto total" in df_resumen.columns:
            df_resumen["Monto total"] = pd.to_numeric(df_resumen["Monto total"], errors="coerce")

        fname = f"informe_ventas_{self._stamp()}.xlsx"
        engine = self._ensure_excel_engine()

        if engine:
            try:
                with pd.ExcelWriter(fname, engine=engine) as writer:
                    df_master.to_excel(writer, index=False, sheet_name="Ventas")
                    df_det.to_excel(writer, index=False, sheet_name="Detalle")
                    df_resumen.to_excel(writer, index=False, sheet_name="Resumen")

                    # Formato 0 decimales, miles
                    if engine == "xlsxwriter":
                        wb = writer.book
                        fmt0 = wb.add_format({'num_format': '#,##0'})
                        writer.sheets["Ventas"].set_column(4, 5, 14, fmt0)   # Monto Total, IVA Total
                        writer.sheets["Detalle"].set_column(3, 4, 14, fmt0)  # Precio Unitario, Total Fila
                        writer.sheets["Resumen"].set_column(2, 2, 14, fmt0)  # Monto total
                    else:  # openpyxl
                        ws_c = writer.sheets["Ventas"]; ws_d = writer.sheets["Detalle"]; ws_r = writer.sheets["Resumen"]
                        def apply_fmt(ws, cols):
                            for col_idx in cols:
                                for col in ws.iter_cols(min_col=col_idx+1, max_col=col_idx+1, min_row=2, max_row=ws.max_row):
                                    for c in col: c.number_format = '#,##0'
                        apply_fmt(ws_c, [4,5]); apply_fmt(ws_d, [3,4]); apply_fmt(ws_r, [2])

                QMessageBox.information(self, "Excel", f"Archivo Excel generado: {fname}")
                return
            except Exception:
                pass

        # Fallback CSV
        self._exportar_csv_simple()

    # ---------- Helpers export ----------
    def _stamp(self):
        return f"{QDate.currentDate().toString('yyyyMMdd')}_{QTime.currentTime().toString('HH_mm')}"

    def _ensure_excel_engine(self):
        try:
            import openpyxl  # noqa
            return "openpyxl"
        except Exception:
            pass
        try:
            import xlsxwriter  # noqa
            return "xlsxwriter"
        except Exception:
            pass
        # intento instalar silenciosamente
        import subprocess
        candidates = [("openpyxl", "openpyxl"), ("XlsxWriter", "xlsxwriter")]
        for pkg, eng in candidates:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return eng
            except Exception:
                continue
        return None

    def _fmt_csv_monto(self, v):
        try:
            return f"{float(v):,.0f}".replace(",", ".")
        except Exception:
            return str(v)

    def _exportar_csv_simple(self):
        import csv, os
        filtros = self._filtros()
        monto_col = self._monto_col()
        comp_col = self._comp_col()
        item_nombre = Item.nombre.label("Ítem")

        # Maestro
        master_rows = (
            self.session.query(
                Venta.idventa, Venta.fecha, Paciente.nombre, comp_col,
                monto_col.label("montototal"), (monto_col/11).label("iva_total"),
                self._estado_text_expr()
            ).join(Paciente, Venta.idpaciente == Paciente.idpaciente)
             .filter(and_(*filtros)).order_by(Venta.fecha.asc(), Venta.idventa.asc()).distinct()
        ).all()

        # Detalle
        det_rows = (
            self.session.query(
                VentaDetalle.idventa, VentaDetalle.cantidad, item_nombre,
                VentaDetalle.preciounitario, (VentaDetalle.cantidad*VentaDetalle.preciounitario).label("total_fila")
            ).join(Venta, Venta.idventa == VentaDetalle.idventa)
             .join(Item, VentaDetalle.iditem == Item.iditem)
             .filter(and_(*filtros)).order_by(VentaDetalle.idventa.desc(), item_nombre.asc())
        ).all()

        # Resumen - SIN "Líneas (veces)"
        res_rows = (
            self.session.query(
                item_nombre,
                func.sum(VentaDetalle.cantidad),
                func.sum(VentaDetalle.cantidad*VentaDetalle.preciounitario),
            ).join(Venta, Venta.idventa == VentaDetalle.idventa)
             .join(Item, VentaDetalle.iditem == Item.iditem)
             .filter(and_(*filtros)).group_by(item_nombre).order_by(item_nombre.asc())
        ).all()

        base = self._stamp()
        f1 = f"informe_ventas_{base}_ventas.csv"
        f2 = f"informe_ventas_{base}_detalle.csv"
        f3 = f"informe_ventas_{base}_resumen.csv"

        try:
            with open(f1, "w", newline="", encoding="utf-8-sig") as fp:
                w = csv.writer(fp, delimiter=';')
                w.writerow(["ID Venta","Fecha","Cliente","Factura","Monto Total","IVA Total","Estado"])
                for r in master_rows:
                    fecha_txt = r[1].strftime("%d/%m/%Y") if r[1] else ""
                    w.writerow([r[0], fecha_txt, r[2] or "", r[3] or "",
                                self._fmt_csv_monto(r[4] or 0), self._fmt_csv_monto(r[5] or 0), r[6] or ""])

            with open(f2, "w", newline="", encoding="utf-8-sig") as fp:
                w = csv.writer(fp, delimiter=';')
                w.writerow(["ID Venta","Cantidad","Ítem","Precio Unitario","Total Fila"])
                for r in det_rows:
                    w.writerow([r[0], r[1] or 0, r[2] or "",
                                self._fmt_csv_monto(r[3] or 0), self._fmt_csv_monto(r[4] or 0)])

            with open(f3, "w", newline="", encoding="utf-8-sig") as fp:
                w = csv.writer(fp, delimiter=';')
                w.writerow(["Ítem","Cantidad total","Monto total"])
                for r in res_rows:
                    w.writerow([r[0] or "", r[1] or 0, self._fmt_csv_monto(r[2] or 0)])

            QMessageBox.information(self, "Exportación",
                f"No se encontraron librerías para Excel. Se exportaron 3 CSV:\n{os.path.abspath(f1)}\n{os.path.abspath(f2)}\n{os.path.abspath(f3)}")
        except Exception as e:
            QMessageBox.critical(self, "Exportación", f"No se pudo exportar.\n{e}")

    # ---------- UI fill ----------
    def _llenar_maestro(self, rows):
        self.table_master.setRowCount(0)
        total_monto = Decimal("0"); total_iva = Decimal("0")

        def fmt(v):
            try: return f"{float(v):,.0f}".replace(",", ".")
            except Exception: return str(v)

        for r in rows:
            row = self.table_master.rowCount()
            self.table_master.insertRow(row)

            estado_txt_raw = (getattr(r, "estado_txt", "") or "")
            estado_up = estado_txt_raw.upper()
            anulada_flag = getattr(r, "anulada_flag", None)
            is_anulada = (bool(anulada_flag) if anulada_flag is not None else (estado_up == "ANULADA"))

            items = [
                QTableWidgetItem(str(r.idventa)),
                QTableWidgetItem(r.fecha.strftime("%d/%m/%Y") if r.fecha else ""),
                QTableWidgetItem(r.cliente or ""),
                QTableWidgetItem((getattr(r, "nro_comprobante", "") or "")),
                QTableWidgetItem(fmt(r.montototal)),
                QTableWidgetItem(fmt(r.iva_total)),
                QTableWidgetItem(estado_txt_raw if estado_txt_raw else ("ANULADA" if is_anulada else "Generada")),
            ]
            for i, it in enumerate(items):
                it.setTextAlignment(Qt.AlignCenter if i in (0,1,4,5,6) else Qt.AlignVCenter | Qt.AlignLeft)
                self.table_master.setItem(row, i, it)

            if is_anulada:
                red = QColor("#a40000"); bg = QColor("#ffe6e6"); f = QFont(); f.setStrikeOut(True)
                for c in range(self.table_master.columnCount()):
                    it = self.table_master.item(row, c)
                    it.setBackground(QBrush(bg)); it.setForeground(QBrush(red)); it.setFont(f)

            try:
                total_monto += Decimal(str(r.montototal or 0))
                total_iva   += Decimal(str(r.iva_total or 0))
            except Exception:
                pass

        self.lbl_total_monto.setText(f"Total Monto: {total_monto:,.0f}".replace(",", "."))
        self.lbl_total_iva.setText(f"Total IVA: {total_iva:,.0f}".replace(",", "."))

    def _on_master_changed(self):
        if not self.table_master.selectedItems():
            return
        idventa = int(self.table_master.item(self.table_master.currentRow(), 0).text())
        self._cargar_detalle(idventa)

    def _cargar_detalle(self, idventa:int):
        item_nombre = Item.nombre.label("item_nombre")
        q_det = (
            self.session.query(
                VentaDetalle.cantidad.label("cantidad"),
                item_nombre,
                VentaDetalle.preciounitario.label("preciounitario"),
                (VentaDetalle.cantidad * VentaDetalle.preciounitario).label("total_fila"),
            )
            .join(Item, VentaDetalle.iditem == Item.iditem)
            .filter(VentaDetalle.idventa == idventa)
            .order_by(item_nombre.asc())
        )
        rows = q_det.all()
        self.table_detalle.setRowCount(0)

        def fmt(v):
            try: return f"{float(v):,.0f}".replace(",", ".")
            except Exception: return str(v)

        for r in rows:
            row = self.table_detalle.rowCount()
            self.table_detalle.insertRow(row)
            items = [
                QTableWidgetItem(fmt(r.cantidad)),
                QTableWidgetItem(r.item_nombre or ""),
                QTableWidgetItem(fmt(r.preciounitario)),
                QTableWidgetItem(fmt(r.total_fila)),
            ]
            for i, it in enumerate(items):
                it.setTextAlignment(Qt.AlignCenter if i in (0,2,3) else Qt.AlignVCenter | Qt.AlignLeft)
                self.table_detalle.setItem(row, i, it)

    # ---------- Resumen en UI ----------
    def _cargar_resumen(self):
        pass

    # ---------- PDF ----------
    def exportar_pdf(self):
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
        except ImportError:
            QMessageBox.warning(self, "PDF", "Necesitás instalar reportlab:  pip install reportlab")
            return

        desde = self.dt_desde.date().toString("dd/MM/yyyy")
        hasta = self.dt_hasta.date().toString("dd/MM/yyyy")
        cli = self.txt_cliente.text().strip() or "Todos"

        filename = f"informe_ventas_{self._stamp()}.pdf"
        doc = SimpleDocTemplate(filename, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
        styles = getSampleStyleSheet()
        story = []

        import os
        logo_path = os.path.join("imagenes", "logo_grande.jpg")
        if os.path.exists(logo_path):
            try:
                story.append(Image(logo_path, width=300, height=200)); story.append(Spacer(1, 6))
            except Exception:
                pass

        story.append(Paragraph("<b>Informe de Ventas</b>", styles["Title"]))
        story.append(Paragraph(f"Rango: {desde} a {hasta} | Cliente: {cli}", styles["Normal"]))
        story.append(Spacer(1, 8))

        # Recorrer lo visible
        for r in range(self.table_master.rowCount()):
            idv = self.table_master.item(r, 0).text()
            fecha_txt = self.table_master.item(r, 1).text()
            cliente = self.table_master.item(r, 2).text()
            comp = self.table_master.item(r, 3).text()
            monto = self.table_master.item(r, 4).text()
            iva = self.table_master.item(r, 5).text()
            estado_txt = (self.table_master.item(r, 6).text() or "").upper()
            estado_html = " — <font color='red'><b>ESTADO: ANULADA</b></font>" if estado_txt == "ANULADA" else ""

            # Encabezado de la venta (más legible y separado)
            story.append(Paragraph(f"<b>N° Venta:</b> {idv}", styles["Heading3"]))
            story.append(Paragraph(f"<b>Fecha:</b> {fecha_txt}    <b>Cliente:</b> {cliente}", styles["Normal"]))
            story.append(Paragraph(f"<b>N° Factura:</b> {comp}", styles["Normal"]))
            if estado_txt == "ANULADA":
                story.append(Paragraph("<font color='red'><b>ESTADO: ANULADA</b></font>", styles["Normal"]))
            story.append(Spacer(1, 4))
            item_nombre = Item.nombre.label("item_nombre")
            det = (
                self.session.query(
                    VentaDetalle.cantidad,
                    item_nombre,
                    VentaDetalle.preciounitario,
                    (VentaDetalle.cantidad * VentaDetalle.preciounitario).label("total_fila"),
                )
                .join(Item, VentaDetalle.iditem == Item.iditem)
                .filter(VentaDetalle.idventa == int(idv))
                .order_by(item_nombre.asc())
            ).all()
            # Tabla de detalle
            data = [["Cantidad", "Ítem", "Precio Unitario", "Total Fila"]]
            def fmt(v):
                try: return f"{float(v):,.0f}".replace(",", ".")
                except: return str(v)

            total_venta = 0
            for d in det:
                data.append([fmt(d.cantidad), d.item_nombre or "", fmt(d.preciounitario), fmt(d.total_fila)])
                try:
                    total_venta += float(d.total_fila or 0)
                except Exception:
                    pass

            iva_venta = round(total_venta / 11)

            # Estilos para Paragraph
            ps_bold = ParagraphStyle("bold", parent=styles["Normal"], fontName="Helvetica-Bold")
            ps_iva = ParagraphStyle("iva", parent=styles["Normal"], textColor=colors.HexColor("#555555"))

            # Fila de total (en negrita, alineada a la derecha)
            data.append([
                "", "",
                Paragraph("Total", ps_bold),
                Paragraph(fmt(total_venta), ps_bold)
            ])
            # Fila de IVA (en gris, debajo de Total)
            data.append([
                "", "",
                Paragraph("IVA", ps_iva),
                Paragraph(fmt(iva_venta), ps_iva)
            ])

            t = Table(data, repeatRows=1, hAlign="LEFT", colWidths=[50, 220, 100, 100])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eeeeee")),
                ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
                ("ALIGN", (0,0), (-1,-1), "LEFT"),  # TODO alineado a la izquierda
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 9),
                ("BOTTOMPADDING", (0,0), (-1,0), 6),
                ("TOPPADDING", (0,0), (-1,0), 6),
                ("TOPPADDING", (0,1), (-1,-1), 2),
                ("BOTTOMPADDING", (0,1), (-1,-1), 2),
            ]))
            story.append(t)

            # Línea divisoria entre ventas
            from reportlab.platypus import HRFlowable
            story.append(Spacer(1, 6))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#bbbbbb")))
            story.append(Spacer(1, 8))

        story.append(Paragraph(self.lbl_total_monto.text(), styles["Heading3"]))
        story.append(Paragraph(self.lbl_total_iva.text(), styles["Heading3"]))

        # Resumen al final - SIN "Líneas (veces)"
        story.append(PageBreak())
        story.append(Paragraph("<b>Resumen por ítem (rango)</b>", styles["Heading2"]))
        filtros = self._filtros()
        item_nombre = Item.nombre.label("item_nombre")
        res = (
            self.session.query(
                item_nombre,
                func.sum(VentaDetalle.cantidad).label("cant_total"),
                func.sum(VentaDetalle.cantidad * VentaDetalle.preciounitario).label("monto_total"),
            )
            .join(Venta, Venta.idventa == VentaDetalle.idventa)
            .join(Item, VentaDetalle.iditem == Item.iditem)
            .filter(and_(*filtros)).group_by(item_nombre).order_by(item_nombre.asc())
        ).all()

        def fmt_m(v):
            try: return f"{float(v):,.0f}".replace(",", ".")
            except: return str(v)
        data_res = [["Ítem", "Cantidad total", "Monto total"]]
        for r in res:
            data_res.append([r[0] or "", fmt_m(r[1] or 0), fmt_m(r[2] or 0)])

        t_res = Table(data_res, repeatRows=1)
        t_res.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eeeeee")),
            ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
            ("ALIGN", (1,1), (-1,-1), "CENTER"),
        ]))
        story.append(t_res)

        try:
            doc.build(story)
            QMessageBox.information(self, "PDF", f"PDF generado: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "PDF", f"No se pudo generar el PDF.\n{e}")

    # ---------- Cierre ----------
    def closeEvent(self, e):
        try: self.session.close()
        except Exception: pass
        super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = VentasReportForm()
    w.show()
    sys.exit(app.exec_())
