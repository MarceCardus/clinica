# controllers/informe_ventas_form.py
import sys
from decimal import Decimal

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QDateEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QGroupBox, QApplication, QCompleter, QSplitter
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont

from utils.db import SessionLocal
from sqlalchemy import and_, func, literal

# ====== MODELOS ======
from models.venta import Venta
from models.venta_detalle import VentaDetalle
from models.paciente import Paciente
# Si no usás Paquete, podés comentar su import y las outerjoin a Paquete
from models.producto import Producto
from models.paquete import Paquete


def col(model, *names):
    """Devuelve la 1ª columna existente en el modelo, o None si no hay coincidencia."""
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
        self.buscar()  # primera carga

    # ---------- UI ----------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # ----- Filtros -----
        filtros = QGroupBox("Filtros")
        fl = QHBoxLayout(filtros)
        fl.setSpacing(8)

        self.dt_desde = QDateEdit(calendarPopup=True)
        self.dt_hasta = QDateEdit(calendarPopup=True)
        hoy = QDate.currentDate()
        self.dt_desde.setDate(hoy)   # ambos hoy
        self.dt_hasta.setDate(hoy)
        self.dt_desde.setDisplayFormat("dd/MM/yyyy")
        self.dt_hasta.setDisplayFormat("dd/MM/yyyy")

        self.txt_cliente = QLineEdit()
        self.txt_cliente.setPlaceholderText("Cliente (escribí para buscar)")
        self.txt_cliente.setClearButtonEnabled(True)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_pdf = QPushButton("Exportar PDF")
        self.btn_excel = QPushButton("Exportar Excel")

        fl.addWidget(QLabel("Desde:")); fl.addWidget(self.dt_desde)
        fl.addWidget(QLabel("Hasta:")); fl.addWidget(self.dt_hasta)
        fl.addWidget(QLabel("Cliente:")); fl.addWidget(self.txt_cliente, 2)
        fl.addWidget(self.btn_buscar); fl.addWidget(self.btn_pdf); fl.addWidget(self.btn_excel)

        # ----- Splitter maestro/detalle -----
        splitter = QSplitter(); splitter.setOrientation(Qt.Vertical)

        self.table_master = QTableWidget(0, 6)
        self.table_master.setHorizontalHeaderLabels([
            "ID Venta", "Fecha", "Cliente", "Comprobante", "Monto Total", "IVA Total"
        ])
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

        splitter.addWidget(self.table_master); splitter.addWidget(self.table_detalle)
        splitter.setSizes([420, 280])

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

    # ---------- Carga de filtros ----------
    def _load_filters(self):
        clientes = [r[0] for r in self.session.query(Paciente.nombre).order_by(Paciente.nombre).all()]
        c = QCompleter(clientes, self); c.setCaseSensitivity(Qt.CaseInsensitive); c.setFilterMode(Qt.MatchContains)
        self.txt_cliente.setCompleter(c)

    # ---------- Helpers de columnas dinámicas ----------
    def _comp_col(self):
        # intenta varios nombres; si no existe, usa literal vacío
        c = col(Venta, "nro_comprobante", "comprobante", "nrofactura", "nro_factura")
        return c if c is not None else literal("")

    def _monto_col(self):
        m = col(Venta, "montototal", "monto_total", "total")
        if m is not None:
            return m
        # calcular desde el detalle si no hay columna de total en la cabecera
        return (
            self.session.query(func.coalesce(func.sum(VentaDetalle.cantidad * VentaDetalle.preciounitario), 0))
            .filter(VentaDetalle.idventa == Venta.idventa)
            .correlate(Venta)
            .scalar_subquery()
        )

    # ---------- Búsqueda ----------
    def buscar(self):
        desde = self.dt_desde.date().toPyDate()
        hasta = self.dt_hasta.date().toPyDate()
        cli_txt = (self.txt_cliente.text() or "").strip()

        filtros = [func.date(Venta.fecha).between(desde, hasta)]
        if cli_txt:
            filtros.append(Paciente.nombre.ilike(f"%{cli_txt}%"))

        monto_col = self._monto_col()
        comp_col = self._comp_col()

        q_master = (
            self.session.query(
                Venta.idventa,
                Venta.fecha.label("fecha"),
                Paciente.nombre.label("cliente"),
                comp_col.label("nro_comprobante"),
                monto_col.label("montototal"),
                (monto_col / 11).label("iva_total"),
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

    def exportar_excel(self):
        try:
            import pandas as pd
        except ImportError:
            QMessageBox.warning(self, "Excel", "Necesitás instalar pandas y openpyxl:\n\npip install pandas openpyxl")
            return

        desde = self.dt_desde.date().toPyDate()
        hasta = self.dt_hasta.date().toPyDate()
        cli_txt = (self.txt_cliente.text() or "").strip()

        filtros = [func.date(Venta.fecha).between(desde, hasta)]
        if cli_txt:
            filtros.append(Paciente.nombre.ilike(f"%{cli_txt}%"))

        monto_col = self._monto_col()
        comp_col = self._comp_col()

        q_master = (
            self.session.query(
                Venta.idventa.label("ID Venta"),
                Venta.fecha.label("Fecha"),
                Paciente.nombre.label("Cliente"),
                comp_col.label("Comprobante"),
                monto_col.label("Monto Total"),
                (monto_col / 11).label("IVA Total"),
            )
            .join(Paciente, Venta.idpaciente == Paciente.idpaciente)
            .filter(and_(*filtros))
            .order_by(Venta.fecha.asc(), Venta.idventa.asc())
            .distinct()
        )
        master_rows = q_master.all()

        item_nombre = func.coalesce(Producto.nombre, Paquete.nombre).label("item_nombre")
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
            .outerjoin(Producto, VentaDetalle.idproducto == Producto.idproducto)
            .outerjoin(Paquete, VentaDetalle.idpaquete == Paquete.idpaquete)
            .filter(and_(*filtros))
            .order_by(VentaDetalle.idventa.desc(), item_nombre.asc())
        )
        det_rows = q_det.all()

        import pandas as pd
        df_master = pd.DataFrame(master_rows, columns=["ID Venta", "Fecha", "Cliente", "Comprobante", "Monto Total", "IVA Total"])
        df_det = pd.DataFrame(det_rows, columns=["ID Venta", "Cantidad", "item_nombre", "Precio Unitario", "Total Fila"]).rename(columns={"item_nombre": "Ítem"})

        fname = f"informe_ventas_{QDate.currentDate().toString('yyyyMMdd')}.xlsx"
        try:
            with pd.ExcelWriter(fname, engine="openpyxl") as writer:
                df_master["Fecha"] = pd.to_datetime(df_master["Fecha"]).dt.strftime("%d/%m/%Y")
                df_master.to_excel(writer, index=False, sheet_name="Ventas")
                df_det.to_excel(writer, index=False, sheet_name="Detalle")
            QMessageBox.information(self, "Excel", f"Archivo Excel generado: {fname}")
        except Exception as e:
            QMessageBox.critical(self, "Excel", f"No se pudo generar el Excel.\n{e}")

    def _llenar_maestro(self, rows):
        self.table_master.setRowCount(0)
        total_monto = Decimal("0"); total_iva = Decimal("0")

        def fmt(v):
            try: return f"{float(v):,.0f}".replace(",", ".")
            except Exception: return str(v)

        for r in rows:
            row = self.table_master.rowCount()
            self.table_master.insertRow(row)
            items = [
                QTableWidgetItem(str(r.idventa)),
                QTableWidgetItem(r.fecha.strftime("%d/%m/%Y") if r.fecha else ""),
                QTableWidgetItem(r.cliente or ""),
                QTableWidgetItem((r.nro_comprobante or "") if hasattr(r, "nro_comprobante") else ""),
                QTableWidgetItem(fmt(r.montototal)),
                QTableWidgetItem(fmt(r.iva_total)),
            ]
            for i, it in enumerate(items):
                it.setTextAlignment(Qt.AlignCenter if i in (0,1,4,5) else Qt.AlignVCenter | Qt.AlignLeft)
                self.table_master.setItem(row, i, it)

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
        item_nombre = func.coalesce(Producto.nombre, Paquete.nombre).label("item_nombre")
        q_det = (
            self.session.query(
                VentaDetalle.cantidad.label("cantidad"),
                item_nombre,
                VentaDetalle.preciounitario.label("preciounitario"),
                (VentaDetalle.cantidad * VentaDetalle.preciounitario).label("total_fila"),
            )
            .outerjoin(Producto, VentaDetalle.idproducto == Producto.idproducto)
            .outerjoin(Paquete, VentaDetalle.idpaquete == Paquete.idpaquete)
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

    def exportar_pdf(self):
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        except ImportError:
            QMessageBox.warning(self, "PDF", "Necesitás instalar reportlab:  pip install reportlab")
            return

        desde = self.dt_desde.date().toString("dd/MM/yyyy")
        hasta = self.dt_hasta.date().toString("dd/MM/yyyy")
        cli = self.txt_cliente.text().strip() or "Todos"

        filename = f"informe_ventas_{QDate.currentDate().toString('yyyyMMdd')}.pdf"
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

            story.append(Paragraph(
                f"<b>#{idv}</b> — {fecha_txt} — {cliente}<br/>"
                f"N° Comprobante: <b>{comp}</b> — Total: <b>{monto}</b> — IVA: <b>{iva}</b>",
                styles["Heading3"]
            ))
            story.append(Spacer(1, 8))

            item_nombre = func.coalesce(Producto.nombre, Paquete.nombre).label("item_nombre")
            det = (
                self.session.query(
                    VentaDetalle.cantidad,
                    item_nombre,
                    VentaDetalle.preciounitario,
                    (VentaDetalle.cantidad * VentaDetalle.preciounitario).label("total_fila"),
                )
                .outerjoin(Producto, VentaDetalle.idproducto == Producto.idproducto)
                .outerjoin(Paquete, VentaDetalle.idpaquete == Paquete.idpaquete)
                .filter(VentaDetalle.idventa == int(idv))
                .order_by(item_nombre.asc())
            ).all()

            data = [["Cantidad", "Ítem", "Precio Unitario", "Total Fila"]]
            for d in det:
                def fmt(v):
                    try: return f"{float(v):,.0f}".replace(",", ".")
                    except: return str(v)
                data.append([fmt(d.cantidad), d.item_nombre or "", fmt(d.preciounitario), fmt(d.total_fila)])

            t = Table(data, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eeeeee")),
                ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
                ("ALIGN", (0,1), (0,-1), "CENTER"),
                ("ALIGN", (2,1), (3,-1), "CENTER"),
            ]))
            story.append(t); story.append(Spacer(1, 6))

        story.append(Paragraph(self.lbl_total_monto.text(), styles["Heading3"]))
        story.append(Paragraph(self.lbl_total_iva.text(), styles["Heading3"]))

        try:
            doc.build(story)
            QMessageBox.information(self, "PDF", f"PDF generado: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "PDF", f"No se pudo generar el PDF.\n{e}")

    def closeEvent(self, e):
        try: self.session.close()
        except Exception: pass
        super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = VentasReportForm()
    w.show()
    sys.exit(app.exec_())
