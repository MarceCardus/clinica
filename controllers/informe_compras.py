import sys
from decimal import Decimal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QDateEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QGroupBox, QApplication, QCompleter, QCheckBox, QSplitter
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QColor, QBrush

from utils.db import SessionLocal
from sqlalchemy import func, and_, or_

# ====== MODELOS ======
from models.compra import Compra
from models.compra_detalle import CompraDetalle
from models.proveedor import Proveedor
from models.item import Item


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
        self.chk_mostrar_anuladas.setChecked(False)

        fl.addWidget(QLabel("Desde:")); fl.addWidget(self.dt_desde)
        fl.addWidget(QLabel("Hasta:")); fl.addWidget(self.dt_hasta)
        fl.addWidget(QLabel("Proveedor:")); fl.addWidget(self.txt_proveedor, 2)
        fl.addWidget(QLabel("Tipo de ítem:")); fl.addWidget(self.cbo_tipo, 1)
        fl.addWidget(self.chk_mostrar_anuladas)
        fl.addWidget(self.btn_buscar)
        fl.addWidget(self.btn_pdf)
        fl.addWidget(self.btn_excel)

        # ----- Splitter maestro/detalle/resumen -----
        splitter = QSplitter()
        splitter.setOrientation(Qt.Vertical)

        # Maestro
        self.table_master = QTableWidget(0, 7)
        self.table_master.setHorizontalHeaderLabels([
            "ID Compra", "Fecha", "Proveedor", "Comprobante", "Monto Total", "IVA Total", "Estado"
        ])
        self.table_master.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_master.verticalHeader().setVisible(False)
        self.table_master.setAlternatingRowColors(True)
        self.table_master.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_master.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_master.setSelectionMode(QTableWidget.SingleSelection)

        # Detalle
        self.table_detalle = QTableWidget(0, 4)
        self.table_detalle.setHorizontalHeaderLabels([
            "Cantidad", "Ítem", "Precio Unitario", "Total Fila"
        ])
        self.table_detalle.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_detalle.verticalHeader().setVisible(False)
        self.table_detalle.setAlternatingRowColors(True)
        self.table_detalle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_detalle.setSelectionBehavior(QTableWidget.SelectRows)

        
        splitter.addWidget(self.table_master)
        splitter.addWidget(self.table_detalle)
        splitter.setSizes([360, 220])

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

    def _filtros_actuales(self):
        desde = self.dt_desde.date().toPyDate()
        hasta = self.dt_hasta.date().toPyDate()
        prov_txt = (self.txt_proveedor.text() or "").strip()
        tipo_val = self.cbo_tipo.currentData()

        filtros = [Compra.fecha.between(desde, hasta)]
        if not self.chk_mostrar_anuladas.isChecked():
            filtros.append(or_(Compra.anulada.is_(False), Compra.anulada.is_(None)))
        if prov_txt:
            filtros.append(Proveedor.nombre.ilike(f"%{prov_txt}%"))
        return filtros, tipo_val

    def buscar(self):
        filtros, tipo_val = self._filtros_actuales()

        # Maestro
        q_master = (
            self.session.query(
                Compra.idcompra,
                Compra.fecha.label("fecha"),
                Proveedor.nombre.label("proveedor"),
                Compra.nro_comprobante.label("nro_comprobante"),
                Compra.montototal.label("montototal"),
                (Compra.montototal / 11).label("iva_total"),
                Compra.anulada.label("anulada"),
            )
            .join(Proveedor, Compra.idproveedor == Proveedor.idproveedor)
            .filter(and_(*filtros))
            .order_by(Compra.fecha.asc(), Compra.idcompra.asc())
            .distinct()
        )
        rows = q_master.all()
        self._llenar_maestro(rows)

        if rows:
            self.table_master.selectRow(0)
            self._cargar_detalle(rows[0].idcompra)
        else:
            self.table_detalle.setRowCount(0)

        
    def exportar_excel(self):
        # Intentar usar pandas; si no está, hacer fallback a CSV
        try:
            import pandas as pd
        except ImportError:
            self._exportar_csv_simple()
            return

        filtros, tipo_val = self._filtros_actuales()

        # Maestro
        q_master = (
            self.session.query(
                Compra.idcompra.label("ID Compra"),
                Compra.fecha.label("Fecha"),
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

        # Detalle
        q_det = (
            self.session.query(
                CompraDetalle.idcompra.label("ID Compra"),
                CompraDetalle.cantidad.label("Cantidad"),
                Item.nombre.label("Ítem"),
                CompraDetalle.preciounitario.label("Precio Unitario"),
                (CompraDetalle.cantidad * CompraDetalle.preciounitario).label("Total Fila"),
            )
            .join(Compra, Compra.idcompra == CompraDetalle.idcompra)
            .join(Proveedor, Compra.idproveedor == Proveedor.idproveedor)
            .join(Item, CompraDetalle.iditem == Item.iditem)
            .filter(and_(*filtros))
            .order_by(CompraDetalle.idcompra.desc(), Item.nombre.asc())
        )
        if tipo_val:
            q_det = q_det.filter(Item.tipo == tipo_val)
        det_rows = q_det.all()

        # Resumen
        q_res = (
            self.session.query(
                Item.nombre.label("Ítem"),
                func.sum(CompraDetalle.cantidad).label("Cantidad total"),
                func.sum(CompraDetalle.cantidad * CompraDetalle.preciounitario).label("Monto total")
            )
            .join(Compra, Compra.idcompra == CompraDetalle.idcompra)
            .join(Proveedor, Compra.idproveedor == Proveedor.idproveedor)
            .join(Item, CompraDetalle.iditem == Item.iditem)
            .filter(and_(*filtros))
            .group_by(Item.nombre)
            .order_by(Item.nombre.asc())
        )
        if tipo_val:
            q_res = q_res.filter(Item.tipo == tipo_val)
        res_rows = q_res.all()

        import pandas as pd
        df_master = pd.DataFrame(
            master_rows,
            columns=["ID Compra", "Fecha", "Proveedor", "Comprobante", "Monto Total", "IVA Total", "anulada"]
        )
        df_master["Estado"] = df_master["anulada"].map(lambda v: "ANULADA" if bool(v) else "Generada")
        df_master = df_master.drop(columns=["anulada"])
        if not df_master.empty:
            df_master["Fecha"] = pd.to_datetime(df_master["Fecha"]).dt.strftime("%d/%m/%Y")

        df_det = pd.DataFrame(det_rows, columns=["ID Compra", "Cantidad", "Ítem", "Precio Unitario", "Total Fila"])
        df_resumen = pd.DataFrame(res_rows, columns=["Ítem", "Cantidad total", "Monto total"])

        # Tipos numéricos
        for col in ["Monto Total", "IVA Total"]:
            if col in df_master.columns:
                df_master[col] = pd.to_numeric(df_master[col], errors="coerce")
        for col in ["Precio Unitario", "Total Fila"]:
            if col in df_det.columns:
                df_det[col] = pd.to_numeric(df_det[col], errors="coerce")
        if "Monto total" in df_resumen.columns:
            df_resumen["Monto total"] = pd.to_numeric(df_resumen["Monto total"], errors="coerce")

        fname = f"informe_compras_{self._stamp()}.xlsx"

        # Asegurar engine (con auto-instalación silenciosa)
        engine = self._ensure_excel_engine()

        if engine:
            try:
                with pd.ExcelWriter(fname, engine=engine) as writer:
                    # Escribir
                    df_master.to_excel(writer, index=False, sheet_name="Compras")
                    df_det.to_excel(writer, index=False, sheet_name="Detalle")
                    df_resumen.to_excel(writer, index=False, sheet_name="Resumen")

                    # Formato miles con 0 decimales
                    if engine == "xlsxwriter":
                        wb  = writer.book
                        fmt0 = wb.add_format({'num_format': '#,##0'})
                        ws_c = writer.sheets["Compras"]
                        ws_d = writer.sheets["Detalle"]
                        ws_r = writer.sheets["Resumen"]
                        ws_c.set_column(4, 5, 14, fmt0)   # Monto Total, IVA Total
                        ws_d.set_column(3, 4, 14, fmt0)   # Precio Unitario, Total Fila
                        ws_r.set_column(2, 2, 14, fmt0)   # Monto total
                    else:  # openpyxl
                        ws_c = writer.sheets["Compras"]
                        ws_d = writer.sheets["Detalle"]
                        ws_r = writer.sheets["Resumen"]
                        def apply_fmt(ws, cols):
                            for col_idx in cols:
                                for cell in ws.iter_cols(min_col=col_idx+1, max_col=col_idx+1,
                                                        min_row=2, max_row=ws.max_row):
                                    for c in cell:
                                        c.number_format = '#,##0'
                        apply_fmt(ws_c, [4,5])
                        apply_fmt(ws_d, [3,4])
                        apply_fmt(ws_r, [2])

                QMessageBox.information(self, "Excel", f"Archivo Excel generado: {fname}\nEngine: {engine}")
                return
            except Exception:
                pass  # si algo falla, cae a CSV

        # Fallback CSV
        self._exportar_csv_simple()

    def _stamp(self):
        # Ej.: 20250817_06_12
        from PyQt5.QtCore import QDate, QTime
        return f"{QDate.currentDate().toString('yyyyMMdd')}_{QTime.currentTime().toString('HH_mm')}"

    def _exportar_csv_simple(self, extra_msg: str = ""):
        """
        Exporta 3 CSV (Compras, Detalle, Resumen) cuando faltan dependencias
        para Excel. No requiere pandas/openpyxl/xlsxwriter.
        """
        import csv, os
        filtros, tipo_val = self._filtros_actuales()

        # Maestro
        q_master = (
            self.session.query(
                Compra.idcompra,
                Compra.fecha,
                Proveedor.nombre,
                Compra.nro_comprobante,
                Compra.montototal,
                (Compra.montototal / 11).label("iva_total"),
                Compra.anulada,
            )
            .join(Proveedor, Compra.idproveedor == Proveedor.idproveedor)
            .filter(and_(*filtros))
            .order_by(Compra.fecha.asc(), Compra.idcompra.asc())
            .distinct()
        )
        master_rows = q_master.all()

        # Detalle
        q_det = (
            self.session.query(
                CompraDetalle.idcompra,
                CompraDetalle.cantidad,
                Item.nombre,
                CompraDetalle.preciounitario,
                (CompraDetalle.cantidad * CompraDetalle.preciounitario).label("total_fila"),
            )
            .join(Compra, Compra.idcompra == CompraDetalle.idcompra)
            .join(Proveedor, Compra.idproveedor == Proveedor.idproveedor)
            .join(Item, CompraDetalle.iditem == Item.iditem)
            .filter(and_(*filtros))
            .order_by(CompraDetalle.idcompra.desc(), Item.nombre.asc())
        )
        if tipo_val:
            q_det = q_det.filter(Item.tipo == tipo_val)
        det_rows = q_det.all()

        # Resumen
        q_res = (
            self.session.query(
                Item.nombre.label("item"),
                func.sum(CompraDetalle.cantidad).label("cant_total"),
                func.sum(CompraDetalle.cantidad * CompraDetalle.preciounitario).label("monto_total")
            )
            .join(Compra, Compra.idcompra == CompraDetalle.idcompra)
            .join(Proveedor, Compra.idproveedor == Proveedor.idproveedor)
            .join(Item, CompraDetalle.iditem == Item.iditem)
            .filter(and_(*filtros))
            .group_by(Item.nombre)
            .order_by(Item.nombre.asc())
        )
        if tipo_val:
            q_res = q_res.filter(Item.tipo == tipo_val)
        res_rows = q_res.all()

        base = self._stamp()
        f1 = f"informe_compras_{base}_compras.csv"
        f2 = f"informe_compras_{base}_detalle.csv"
        f3 = f"informe_compras_{base}_resumen.csv"

        try:
            with open(f1, "w", newline="", encoding="utf-8-sig") as fp:
                w = csv.writer(fp, delimiter=';')
                w.writerow(["ID Compra","Fecha","Proveedor","Comprobante","Monto Total","IVA Total","Estado"])
                for r in master_rows:
                    estado = "ANULADA" if bool(r.anulada) else "Generada"
                    fecha_txt = r.fecha.strftime("%d/%m/%Y") if r.fecha else ""
                    w.writerow([r.idcompra, fecha_txt, r[2] or "", r.nro_comprobante or "", self._fmt_csv_monto(r.montototal or 0), self._fmt_csv_monto(r.iva_total or 0), estado])

            with open(f2, "w", newline="", encoding="utf-8-sig") as fp:
                w = csv.writer(fp, delimiter=';')
                w.writerow(["ID Compra","Cantidad","Ítem","Precio Unitario","Total Fila"])
                for r in det_rows:
                    w.writerow([r.idcompra, r.cantidad or 0, r.nombre or "", self._fmt_csv_monto(r.preciounitario or 0), self._fmt_csv_monto(r.total_fila or 0)])

            with open(f3, "w", newline="", encoding="utf-8-sig") as fp:
                w = csv.writer(fp, delimiter=';')
                w.writerow(["Ítem","Cantidad total","Monto total"])
                for r in res_rows:
                    w.writerow([r.nombre or "", r.cant_total or 0, self._fmt_csv_monto(r.monto_total or 0)])
            QMessageBox.information(
                self, "Exportación",
                "No se encontraron librerías para Excel (openpyxl/xlsxwriter). "
                "Se exportaron 3 archivos CSV (separados por ';'):\n\n"
                f"• {os.path.abspath(f1)}\n• {os.path.abspath(f2)}\n• {os.path.abspath(f3)}\n"
                "Tip: Podés abrirlos en Excel sin problemas." + (extra_msg or "")
            )
        except Exception as e:
            QMessageBox.critical(self, "Exportación", f"No se pudo exportar.\n{e}" + (extra_msg or ""))

    def _fmt_csv_monto(self, v):
        try:
            # redondeo 0 decimales y separador de miles con '.'
            return f"{float(v):,.0f}".replace(",", ".")
        except Exception:
            return str(v)


    def _llenar_maestro(self, rows):
        self.table_master.setRowCount(0)
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
                QTableWidgetItem(estado_txt),
            ]
            for i, it in enumerate(items):
                it.setTextAlignment(Qt.AlignCenter if i in (0,1,4,5,6) else Qt.AlignVCenter | Qt.AlignLeft)
                self.table_master.setItem(row, i, it)

            if anul:
                red = QColor("#a40000")
                bg  = QColor("#ffe6e6")
                f = QFont(); f.setStrikeOut(True)
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
        sel = self.table_master.selectedItems()
        if not sel:
            return
        idcompra = int(self.table_master.item(self.table_master.currentRow(), 0).text())
        self._cargar_detalle(idcompra)

    def _cargar_detalle(self, idcompra: int):
        q = (
            self.session.query(
                CompraDetalle.cantidad,
                Item.nombre,
                CompraDetalle.preciounitario,
                CompraDetalle.iva,
                CompraDetalle.lote,
                CompraDetalle.fechavencimiento,
                CompraDetalle.observaciones,
                (CompraDetalle.cantidad * CompraDetalle.preciounitario).label("total_fila"),
            )
            .join(Item, CompraDetalle.iditem == Item.iditem)
            .filter(CompraDetalle.idcompra == idcompra)
            .order_by(Item.nombre.asc())
        )
        rows = q.all()
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
                QTableWidgetItem(r.nombre or ""),
                QTableWidgetItem(fmt(r.preciounitario)),
                QTableWidgetItem(fmt(r.total_fila)),
            ]
            for i, it in enumerate(items):
                it.setTextAlignment(Qt.AlignCenter if i in (0,2,3) else Qt.AlignVCenter | Qt.AlignLeft)
                self.table_detalle.setItem(row, i, it)

    def _cargar_resumen(self):
        desde = self.dt_desde.date().toPyDate()
        hasta = self.dt_hasta.date().toPyDate()
        prov_txt = (self.txt_proveedor.text() or "").strip()
        tipo_val = self.cbo_tipo.currentData()

        filtros = [Compra.fecha.between(desde, hasta)]
        if not self.chk_mostrar_anuladas.isChecked():
            filtros.append(or_(Compra.anulada.is_(False), Compra.anulada.is_(None)))
        if prov_txt:
            filtros.append(Proveedor.nombre.ilike(f"%{prov_txt}%"))

        q = (
            self.session.query(
                Item.nombre.label("item"),
                func.sum(CompraDetalle.cantidad).label("cant_total"),
                func.sum(CompraDetalle.cantidad * CompraDetalle.preciounitario).label("monto_total")
            )
            .join(Compra, Compra.idcompra == CompraDetalle.idcompra)
            .join(Proveedor, Compra.idproveedor == Proveedor.idproveedor)
            .join(Item, CompraDetalle.iditem == Item.iditem)
            .filter(and_(*filtros))
            .group_by(Item.nombre)
            .order_by(Item.nombre.asc())
        )
        if tipo_val:
            q = q.filter(Item.tipo == tipo_val)

        rows = q.all()

        def fmt_m(n):
            try:
                return f"{float(n):,.0f}".replace(",", ".")
            except Exception:
                return str(n)

        self.table_resumen.setRowCount(0)
        total_cant = 0
        total_monto = 0
        for r in rows:
            row = self.table_resumen.rowCount()
            self.table_resumen.insertRow(row)
            items = [
                QTableWidgetItem(r.item or ""),
                QTableWidgetItem(fmt_m(r.cant_total or 0)),
                QTableWidgetItem(fmt_m(r.monto_total or 0)),
            ]
            total_cant += r.cant_total or 0
            total_monto += r.monto_total or 0
            for i, it in enumerate(items):
                it.setTextAlignment(Qt.AlignCenter if i in (1,2) else Qt.AlignVCenter | Qt.AlignLeft)
                self.table_resumen.setItem(row, i, it)
        # Fila de totales
        if rows:
            row = self.table_resumen.rowCount()
            self.table_resumen.insertRow(row)
            items = [
                QTableWidgetItem("TOTAL"),
                QTableWidgetItem(fmt_m(total_cant)),
                QTableWidgetItem(fmt_m(total_monto)),
            ]
            for i, it in enumerate(items):
                it.setFont(QFont("Arial", weight=QFont.Bold))
                it.setTextAlignment(Qt.AlignCenter if i in (1,2) else Qt.AlignVCenter | Qt.AlignLeft)
                self.table_resumen.setItem(row, i, it)

    def _ensure_excel_engine(self):
        """
        Devuelve 'openpyxl' o 'xlsxwriter' si están disponibles.
        Si no, intenta instalarlos automáticamente con pip y devuelve el que logró instalar.
        Si nada funciona, devuelve None.
        """
        try:
            import openpyxl  # noqa: F401
            return "openpyxl"
        except Exception:
            pass
        try:
            import xlsxwriter  # noqa: F401
            return "xlsxwriter"
        except Exception:
            pass

        # Intento de instalación automática
        import subprocess, sys
        candidates = [("openpyxl", "openpyxl"), ("XlsxWriter", "xlsxwriter")]
        for pkg, eng in candidates:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return eng
            except Exception:
                continue
        return None

    def exportar_pdf(self):
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
            )
        except ImportError:
            QMessageBox.warning(self, "PDF", "Necesitás instalar reportlab:  pip install reportlab")
            return

        desde = self.dt_desde.date().toString("dd/MM/yyyy")
        hasta = self.dt_hasta.date().toString("dd/MM/yyyy")
        prov = self.txt_proveedor.text().strip() or "Todos"
        tipo = self.cbo_tipo.currentText()

        filename = f"informe_compras_{self._stamp()}.pdf"
        doc = SimpleDocTemplate(
            filename, pagesize=landscape(A4),
            leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20
        )
        styles = getSampleStyleSheet()

        story = []

        # LOGO (opcional)
        import os
        logo_path = os.path.join("imagenes", "logo_grande.jpg")
        if os.path.exists(logo_path):
            try:
                img = Image(logo_path, width=300, height=200)
                story.append(img); story.append(Spacer(1, 6))
            except Exception:
                pass

        # Título + filtros
        story.append(Paragraph("<b>Informe de Compras</b>", styles["Title"]))
        story.append(Paragraph(f"Rango: {desde} a {hasta} | Proveedor: {prov} | Tipo: {tipo}", styles["Normal"]))
        story.append(Spacer(1, 8))

        # Recorremos compras visibles del maestro
        for r in range(self.table_master.rowCount()):
            idc = self.table_master.item(r, 0).text()
            fecha_txt = self.table_master.item(r, 1).text()
            proveedor = self.table_master.item(r, 2).text()
            comp = self.table_master.item(r, 3).text()
            monto = self.table_master.item(r, 4).text()
            iva = self.table_master.item(r, 5).text()
            anulada = (self.table_master.item(r, 6).text().upper() == "ANULADA")
            estado_html = " — <font color='red'><b>ESTADO: ANULADA</b></font>" if anulada else ""
            # Estética alineada y por línea como informe de ventas
            story.append(Paragraph(f"<b>N° Compra:</b> {idc}", styles["Heading3"]))
            story.append(Paragraph(f"<b>Fecha:</b> {fecha_txt}", styles["Normal"]))
            story.append(Paragraph(f"<b>N° Factura:</b> {comp}", styles["Normal"]))
            story.append(Paragraph(f"<b>Proveedor:</b> {proveedor}", styles["Normal"]))
            if anulada:
                story.append(Paragraph("<font color='red'><b>ESTADO: ANULADA</b></font>", styles["Normal"]))
            story.append(Spacer(1, 4))

            # Detalle desde DB (respeta filtro de tipo)
            tipo_val = self.cbo_tipo.currentData()
            q = (
                self.session.query(
                    CompraDetalle.cantidad,
                    Item.nombre,
                    CompraDetalle.preciounitario,
                    (CompraDetalle.cantidad * CompraDetalle.preciounitario).label("total_fila"),
                )
                .join(Item, CompraDetalle.iditem == Item.iditem)
                .filter(CompraDetalle.idcompra == int(idc))
                .order_by(Item.nombre.asc())
            )
            if tipo_val:
                q = q.filter(Item.tipo == tipo_val)
            det = q.all()

            data = [["Cantidad", "Ítem", "Precio Unitario", "Total Fila"]]
            def fmt(v):
                try: return f"{float(v):,.0f}".replace(",", ".")
                except: return str(v)
            total_fila = 0
            for d in det:
                row = [
                    fmt(d.cantidad),
                    d.nombre or "",
                    fmt(d.preciounitario),
                    fmt(d.total_fila),
                ]
                data.append(row)
                total_fila += float(d.total_fila or 0)

            # Fila Total
            data.append([
                "",
                "",
                Paragraph("<b>Total:</b>", styles["Normal"]),
                Paragraph(f"<b>{fmt(total_fila)}</b>", styles["Normal"]),
            ])
            # Fila IVA
            iva_val = total_fila / 11 if total_fila else 0
            data.append([
                "",
                "",
                Paragraph("<b>IVA:</b>", styles["Normal"]),
                Paragraph(f"<b>{fmt(iva_val)}</b>", styles["Normal"]),
            ])

            t = Table(
                data,
                repeatRows=1,
                colWidths=[50, 200, 80, 80],
                hAlign="LEFT"
            )
            t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eeeeee")),
                ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTNAME", (0,-2), (-1,-1), "Helvetica-Bold"),  # Total/IVA bold
                ("BACKGROUND", (0,-2), (-1,-2), colors.whitesmoke),
                ("BACKGROUND", (0,-1), (-1,-1), colors.whitesmoke),
            ]))
            story.append(t); story.append(Spacer(1, 6))

        story.append(Paragraph(self.lbl_total_monto.text(), styles["Heading3"]))
        story.append(Paragraph(self.lbl_total_iva.text(), styles["Heading3"]))
        story.append(PageBreak())   
        # ====== Resumen al final ======
        filtros, tipo_val = self._filtros_actuales()
        q_res = (
            self.session.query(
                Item.nombre.label("item"),
                func.sum(CompraDetalle.cantidad).label("cant_total"),
                func.sum(CompraDetalle.cantidad * CompraDetalle.preciounitario).label("monto_total")
            )
            .join(Compra, Compra.idcompra == CompraDetalle.idcompra)
            .join(Proveedor, Compra.idproveedor == Proveedor.idproveedor)
            .join(Item, CompraDetalle.iditem == Item.iditem)
            .filter(and_(*filtros))
            .group_by(Item.nombre)
            .order_by(Item.nombre.asc())
        )
        if tipo_val:
            q_res = q_res.filter(Item.tipo == tipo_val)
        res = q_res.all()

        from reportlab.lib import colors
        from reportlab.platypus import Table, TableStyle
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Resumen por ítem (rango)</b>", styles["Heading2"]))

        data_res = [["Ítem", "Cantidad total", "Monto total"]]
        def fmt_m(v):
            try: return f"{float(v):,.0f}".replace(",", ".")
            except: return str(v)
        for r in res:
            data_res.append([r.item or "", fmt_m(r.cant_total or 0), fmt_m(r.monto_total or 0)])

        t_res = Table(data_res, repeatRows=1, hAlign="LEFT")
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
    w = ComprasReportForm()
    w.show()
    sys.exit(app.exec_())
