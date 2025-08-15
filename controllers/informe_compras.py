import sys
from decimal import Decimal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QDateEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QGroupBox, QApplication, QCompleter, QCheckBox
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QColor, QBrush

from utils.db import SessionLocal
from sqlalchemy import func, and_, or_

# ====== MODELOS ======
from models.compra import Compra
from models.compra_detalle import CompraDetalle
from models.proveedor import Proveedor
from models.insumo import Insumo


# Reemplazá la clase ComprasReportForm por esta versión

class ComprasReportForm(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Informe de Compras")
        self.resize(1100, 700)
        self.session = SessionLocal()

        self._build_ui()
        self._wire_events()
        self._load_filters()
        self.buscar()  # primera carga

    # ---------- UI ----------
    def _build_ui(self):
        from PyQt5.QtWidgets import QSplitter
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
        self.dt_desde.setDate(hoy)
        self.dt_hasta.setDate(hoy)
        self.dt_desde.setDisplayFormat("dd/MM/yyyy")
        self.dt_hasta.setDisplayFormat("dd/MM/yyyy")
        
        self.txt_proveedor = QLineEdit()
        self.txt_proveedor.setPlaceholderText("Proveedor (escribí para buscar)")
        self.txt_proveedor.setClearButtonEnabled(True)

        self.cbo_tipo = QComboBox()
        self.cbo_tipo.setEditable(False)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_pdf = QPushButton("Exportar PDF")
        self.btn_excel = QPushButton("Exportar Excel")
        self.chk_mostrar_anuladas = QCheckBox("Mostrar anuladas")
        self.chk_mostrar_anuladas.setChecked(False)  # por defecto NO muestra anuladas

        fl.addWidget(QLabel("Desde:")); fl.addWidget(self.dt_desde)
        fl.addWidget(QLabel("Hasta:")); fl.addWidget(self.dt_hasta)
        fl.addWidget(QLabel("Proveedor:")); fl.addWidget(self.txt_proveedor, 2)
        fl.addWidget(QLabel("Tipo de insumo:")); fl.addWidget(self.cbo_tipo, 1)
        fl.addWidget(self.chk_mostrar_anuladas)
        fl.addWidget(self.btn_buscar)
        fl.addWidget(self.btn_pdf)
        fl.addWidget(self.btn_excel)

        # ----- Splitter maestro/detalle -----
        splitter = QSplitter()
        splitter.setOrientation(Qt.Vertical)

        # Maestro (cabecera de compra)
        self.table_master = QTableWidget(0, 7)
        self.table_master.setHorizontalHeaderLabels([
            "ID Compra", "Fecha", "Proveedor", "Comprobante", "Monto Total", "IVA Total", "Estado"  # <-- nueva
        ])
        self.table_master.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_master.verticalHeader().setVisible(False)
        self.table_master.setAlternatingRowColors(True)
        self.table_master.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_master.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_master.setSelectionMode(QTableWidget.SingleSelection)

        # Detalle (items de la compra seleccionada)
        self.table_detalle = QTableWidget(0, 4)
        self.table_detalle.setHorizontalHeaderLabels([
            "Cantidad", "Insumo", "Precio Unitario", "Total Fila"
        ])
        self.table_detalle.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_detalle.verticalHeader().setVisible(False)
        self.table_detalle.setAlternatingRowColors(True)
        self.table_detalle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_detalle.setSelectionBehavior(QTableWidget.SelectRows)

        splitter.addWidget(self.table_master)
        splitter.addWidget(self.table_detalle)
        splitter.setSizes([420, 280])  # proporción inicial

        # Totales
        tot_layout = QHBoxLayout()
        tot_layout.addStretch(1)
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
        self.txt_proveedor.textChanged.connect(self._auto_buscar_on_type)
        # cuando cambio la selección de maestro, cargo detalle
        self.table_master.itemSelectionChanged.connect(self._on_master_changed)
        self.btn_excel.clicked.connect(self.exportar_excel)
        self.chk_mostrar_anuladas.stateChanged.connect(lambda _ : self.buscar())
        self.dt_desde.dateChanged.connect(lambda _ : self.buscar())
        self.dt_hasta.dateChanged.connect(lambda _ : self.buscar())

    # ---------- Carga de filtros ----------
    def _load_filters(self):
        proveedores = [r[0] for r in self.session.query(Proveedor.nombre).order_by(Proveedor.nombre).all()]
        c = QCompleter(proveedores, self)
        c.setCaseSensitivity(Qt.CaseInsensitive)
        c.setFilterMode(Qt.MatchContains)
        self.txt_proveedor.setCompleter(c)

        self.cbo_tipo.clear()
        self.cbo_tipo.addItem("Todos", None)
        for t in ['MEDICAMENTO', 'DESCARTABLE', 'REACTIVO', 'ANTIBIOTICO', 'VARIOS']:
            self.cbo_tipo.addItem(t, t)

    # ---------- Búsqueda ----------
    def _auto_buscar_on_type(self, _):
        self.buscar()

    def buscar(self):
        desde = self.dt_desde.date().toPyDate()
        hasta = self.dt_hasta.date().toPyDate()
        prov_txt = (self.txt_proveedor.text() or "").strip()

        # ⚠️ CAMBIAR si tu campo no es Compra.fecha
        filtros = [Compra.fecha.between(desde, hasta)]

        # Si NO está marcado el checkbox, excluimos anuladas
        if not self.chk_mostrar_anuladas.isChecked():
            filtros.append(or_(Compra.anulada.is_(False), Compra.anulada.is_(None)))

        # Proveedor
        if prov_txt:
            filtros.append(Proveedor.nombre.ilike(f"%{prov_txt}%"))

        # Tipo de insumo
        tipo = self.cbo_tipo.currentData()
        if tipo:
            sub = (
                self.session.query(CompraDetalle.idcompra)
                .join(Insumo, CompraDetalle.idinsumo == Insumo.idinsumo)
                .filter(CompraDetalle.idcompra == Compra.idcompra, Insumo.tipo == tipo)
            ).exists()
            filtros.append(sub)

        # Maestro: 1 fila por compra
        q_master = (
            self.session.query(
                Compra.idcompra,
                Compra.fecha.label("fecha"),  # <-- CAMBIÁ si tu campo se llama distinto
                Proveedor.nombre.label("proveedor"),
                Compra.nro_comprobante.label("nro_comprobante"),
                Compra.montototal.label("montototal"),
                (Compra.montototal / 11).label("iva_total"),
                Compra.anulada.label("anulada"),
            )
            .join(Proveedor, Compra.idproveedor == Proveedor.idproveedor)
            .filter(and_(*filtros))
            .order_by(Compra.fecha.asc(), Compra.idcompra.asc())  # orden: fecha, luego id
            .distinct()
        )
        rows = q_master.all()
        self._llenar_maestro(rows)

        # si hay al menos una compra, seleccionar la primera para cargar su detalle
        if rows:
            self.table_master.selectRow(0)
            self._cargar_detalle(rows[0].idcompra)
        else:
            self.table_detalle.setRowCount(0)

    def exportar_excel(self):
        try:
            import pandas as pd
        except ImportError:
            QMessageBox.warning(self, "Excel", "Necesitás instalar pandas y openpyxl:\n\npip install pandas openpyxl")
            return

        # Filtros actuales
        desde = self.dt_desde.date().toPyDate()
        hasta = self.dt_hasta.date().toPyDate()
        prov_txt = (self.txt_proveedor.text() or "").strip()
        tipo_val = self.cbo_tipo.currentData()

        # ⚠️ CAMBIAR si tu campo no es Compra.fecha
        filtros = [Compra.fecha.between(desde, hasta)]
        if not self.chk_mostrar_anuladas.isChecked():
            filtros.append(or_(Compra.anulada.is_(False), Compra.anulada.is_(None)))

        if prov_txt:
            filtros.append(Proveedor.nombre.ilike(f"%{prov_txt}%"))

        if tipo_val:
            sub = (
                self.session.query(CompraDetalle.idcompra)
                .join(Insumo, CompraDetalle.idinsumo == Insumo.idinsumo)
                .filter(CompraDetalle.idcompra == Compra.idcompra, Insumo.tipo == tipo_val)
            ).exists()
            filtros.append(sub)

        # Maestro
        q_master = (
            self.session.query(
                Compra.idcompra,
                Compra.fecha.label("Fecha"),  # <-- CAMBIÁ si se llama distinto
                Proveedor.nombre.label("Proveedor"),
                Compra.nro_comprobante.label("Comprobante"),
                Compra.montototal.label("Monto Total"),
                (Compra.montototal / 11).label("IVA Total"),
                Compra.anulada.label("anulada"),
            )
            .join(Proveedor, Compra.idproveedor == Proveedor.idproveedor)
            .filter(and_(*filtros))
            .order_by(Compra.fecha.asc(), Compra.idcompra.asc())
            .distinct()
        )
        master_rows = q_master.all()


        # Detalle (con filtro opcional por tipo)
        q_det = (
            self.session.query(
                CompraDetalle.idcompra.label("ID Compra"),
                CompraDetalle.cantidad.label("Cantidad"),
                Insumo.nombre.label("Insumo"),
                CompraDetalle.preciounitario.label("Precio Unitario"),
                (CompraDetalle.cantidad * CompraDetalle.preciounitario).label("Total Fila"),
            )
            .join(Compra, Compra.idcompra == CompraDetalle.idcompra)
            .join(Proveedor, Compra.idproveedor == Proveedor.idproveedor)
            .join(Insumo, CompraDetalle.idinsumo == Insumo.idinsumo)
            .filter(and_(*filtros))
            .order_by(CompraDetalle.idcompra.desc(), Insumo.nombre.asc())
        )
        if tipo_val:
            q_det = q_det.filter(Insumo.tipo == tipo_val)

        det_rows = q_det.all()

        # DataFrames
        import pandas as pd
        df_master = pd.DataFrame(
            master_rows,
            columns=["ID Compra", "Fecha", "Proveedor", "Comprobante", "Monto Total", "IVA Total", "anulada"]
        )
        # transformar bool -> texto
        df_master["Estado"] = df_master["anulada"].map(lambda v: "ANULADA" if bool(v) else "Generada")
        df_master = df_master.drop(columns=["anulada"])
        df_det = pd.DataFrame(det_rows, columns=["ID Compra", "Cantidad", "Insumo", "Precio Unitario", "Total Fila"])

        # Exportar
        fname = f"informe_compras_{QDate.currentDate().toString('yyyyMMdd')}.xlsx"
        try:
            with pd.ExcelWriter(fname, engine="openpyxl") as writer:
                df_master["Fecha"] = pd.to_datetime(df_master["Fecha"]).dt.strftime("%d/%m/%Y")
                df_master.to_excel(writer, index=False, sheet_name="Compras")
                df_det.to_excel(writer, index=False, sheet_name="Detalle")
            QMessageBox.information(self, "Excel", f"Archivo Excel generado: {fname}")
        except Exception as e:
            QMessageBox.critical(self, "Excel", f"No se pudo generar el Excel.\n{e}")


    def _llenar_maestro(self, rows):
        self.table_master.setRowCount(0)
        from decimal import Decimal
        total_monto = Decimal("0")
        total_iva = Decimal("0")

        def fmt(v):
            try:
                return f"{float(v):,.0f}".replace(",", ".")
            except Exception:
                return str(v)

        for r in rows:
            row = self.table_master.rowCount()
            self.table_master.insertRow(row)
            anul = bool(getattr(r, "anulada", False))
            estado_txt = "ANULADA" if anul else "Generado"
            items = [
                QTableWidgetItem(str(r.idcompra)),
                QTableWidgetItem(r.fecha.strftime("%d/%m/%Y") if r.fecha else ""),
                QTableWidgetItem(r.proveedor or ""),
                QTableWidgetItem(r.nro_comprobante or ""),
                QTableWidgetItem(fmt(r.montototal)),
                QTableWidgetItem(fmt(r.iva_total)),
                QTableWidgetItem(estado_txt),  # <-- nueva col
            ]
            for i, it in enumerate(items):
                it.setTextAlignment(Qt.AlignCenter if i in (0,1,4,5,6) else Qt.AlignVCenter | Qt.AlignLeft)
                self.table_master.setItem(row, i, it)

            # Si está ANULADA, resaltar toda la fila
            if anul:
                red = QColor("#a40000")
                bg  = QColor("#ffe6e6")
                f = QFont(); f.setStrikeOut(True)  # tachado
                for c in range(self.table_master.columnCount()):
                    it = self.table_master.item(row, c)
                    it.setBackground(QBrush(bg))
                    it.setForeground(QBrush(red))
                    it.setFont(f)

            # acumular totales (una vez por fila)
            try:
                total_monto += Decimal(str(r.montototal or 0))
                total_iva   += Decimal(str(r.iva_total or 0))
            except Exception:
                pass

        self.lbl_total_monto.setText(f"Total Monto: {total_monto:,.0f}".replace(",", "."))
        self.lbl_total_iva.setText(f"Total IVA: {total_iva:,.0f}".replace(",", "."))

    def _on_master_changed(self):
        sel = self.table_master.selectedItems()
        if not sel:
            return
        idcompra = int(self.table_master.item(self.table_master.currentRow(), 0).text())
        self._cargar_detalle(idcompra)

    def _cargar_detalle(self, idcompra: int):
        # aplicamos además el filtro de tipo si el usuario eligió uno
        tipo = self.cbo_tipo.currentData()

        q_det = (
            self.session.query(
                CompraDetalle.cantidad.label("cantidad"),
                Insumo.nombre.label("insumo"),
                CompraDetalle.preciounitario.label("preciounitario"),
                (CompraDetalle.cantidad * CompraDetalle.preciounitario).label("total_fila"),
            )
            .join(Insumo, CompraDetalle.idinsumo == Insumo.idinsumo)
            .filter(CompraDetalle.idcompra == idcompra)
            .order_by(Insumo.nombre.asc())
        )
        if tipo:
            q_det = q_det.filter(Insumo.tipo == tipo)

        rows = q_det.all()
        self.table_detalle.setRowCount(0)

        def fmt(v):
            try:
                return f"{float(v):,.0f}".replace(",", ".")
            except Exception:
                return str(v)

        for r in rows:
            row = self.table_detalle.rowCount()
            self.table_detalle.insertRow(row)
            items = [
                QTableWidgetItem(fmt(r.cantidad)),
                QTableWidgetItem(r.insumo or ""),
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
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        except ImportError:
            QMessageBox.warning(self, "PDF", "Necesitás instalar reportlab:  pip install reportlab")
            return

        desde = self.dt_desde.date().toString("dd/MM/yyyy")
        hasta = self.dt_hasta.date().toString("dd/MM/yyyy")
        prov = self.txt_proveedor.text().strip() or "Todos"
        tipo = self.cbo_tipo.currentText()

        filename = f"informe_compras_{QDate.currentDate().toString('yyyyMMdd')}.pdf"
        doc = SimpleDocTemplate(
            filename, pagesize=landscape(A4),
            leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20
        )
        styles = getSampleStyleSheet()

        story = []

        # --- LOGO (opcional) ---
        import os
        logo_path = os.path.join("imagenes", "logo_grande.jpg")  # ajustá si es .jpg/.ico
        if os.path.exists(logo_path):
            try:
                img = Image(logo_path, width=300, height=200)  # escalado simple
                story.append(img)
                story.append(Spacer(1, 6))
            except Exception:
                pass  # si falla, seguimos sin logo

        # Título + filtros
        title = Paragraph("<b>Informe de Compras</b>", styles["Title"])
        story.append(title)
        story.append(Paragraph(f"Rango: {desde} a {hasta} | Proveedor: {prov} | Tipo: {tipo}", styles["Normal"]))
        story.append(Spacer(1, 8))

        # ---- Recorremos cada compra visible en la tabla maestro ----
        for r in range(self.table_master.rowCount()):
            idc = self.table_master.item(r, 0).text()
            fecha_txt = self.table_master.item(r, 1).text()
            proveedor = self.table_master.item(r, 2).text()
            comp = self.table_master.item(r, 3).text()
            monto = self.table_master.item(r, 4).text()
            iva = self.table_master.item(r, 5).text()
            anulada = (self.table_master.item(r, 6).text().upper() == "ANULADA")
            estado_html = " — <font color='red'><b>ESTADO: ANULADA</b></font>" if anulada else ""
            story.append(Paragraph(
                f"<b>#{idc}</b> — {fecha_txt} — {proveedor}<br/>"
                f"N° Factura: <b>{comp}</b> — Total: <b>{monto}</b> — IVA: <b>{iva}</b>{estado_html}",
                styles["Heading3"]
            ))
            story.append(Spacer(1, 8))

            # detalle desde DB (para no depender de selección)
            tipo_val = self.cbo_tipo.currentData()
            q = (
                self.session.query(
                    CompraDetalle.cantidad,
                    Insumo.nombre,
                    CompraDetalle.preciounitario,
                    (CompraDetalle.cantidad * CompraDetalle.preciounitario).label("total_fila"),
                )
                .join(Insumo, CompraDetalle.idinsumo == Insumo.idinsumo)
                .filter(CompraDetalle.idcompra == int(idc))
                .order_by(Insumo.nombre.asc())
            )
            if tipo_val:
                q = q.filter(Insumo.tipo == tipo_val)
            det = q.all()

            data = [["Cantidad", "Insumo", "Precio Unitario", "Total Fila"]]
            for d in det:
                def fmt(v):
                    try: return f"{float(v):,.0f}".replace(",", ".")
                    except: return str(v)
                data.append([fmt(d.cantidad), d.nombre or "", fmt(d.preciounitario), fmt(d.total_fila)])

            t = Table(data, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eeeeee")),
                ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
                ("ALIGN", (0,1), (0,-1), "CENTER"),
                ("ALIGN", (2,1), (3,-1), "CENTER"),
            ]))
            story.append(t)
            story.append(Spacer(1, 6))

        story.append(Paragraph(self.lbl_total_monto.text(), styles["Heading3"]))
        story.append(Paragraph(self.lbl_total_iva.text(), styles["Heading3"]))

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

# ---- Ejecutar suelto para pruebas ----
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ComprasReportForm()
    w.show()
    sys.exit(app.exec_())
