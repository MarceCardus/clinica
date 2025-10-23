import sys, os, pathlib
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QWidget, QLabel, QLineEdit, QComboBox, QMessageBox, QTextEdit,
    QCheckBox, QTabWidget, QSpinBox, QDoubleSpinBox, QHeaderView, QAbstractItemView
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QSize, QLocale

from utils.db import SessionLocal
from sqlalchemy import exists, or_
from sqlalchemy.exc import IntegrityError

# MODELOS
from models.item import Item, ItemTipo
from models.tipoproducto import TipoProducto
from models.especialidad import Especialidad
from models.compra_detalle import CompraDetalle
from models.venta_detalle  import VentaDetalle
from models.plan_tipo import PlanTipo
from models.item_composicion import ItemComposicion  # <<--- NUEVO

# --- util rutas de icono (con fallback) ---
def resource_path(*parts):
    candidates = []
    here = pathlib.Path(__file__).resolve().parent
    candidates.append(here / "imagenes" / pathlib.Path(*parts))
    candidates.append(pathlib.Path(os.getcwd()) / "imagenes" / pathlib.Path(*parts))
    candidates.append(here.parent / "imagenes" / pathlib.Path(*parts))
    if hasattr(sys, "_MEIPASS"):
        candidates.append(pathlib.Path(sys._MEIPASS) / "imagenes" / pathlib.Path(*parts))
    for p in candidates:
        if p.exists():
            return str(p)
    return ""


class ABMItems(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ABM de Ítems")
        self.setMinimumWidth(950)
        self.session = SessionLocal()
        self.init_ui()
        self.load_tipos()
        self.load_data()

    # ---------- UI ----------
    def init_ui(self):
        layout = QVBoxLayout(self)

        # Filtros
        filtros = QWidget(); f = QHBoxLayout(filtros)
        self.filtro_nombre = QLineEdit()
        self.filtro_nombre.setPlaceholderText("🔍 Buscar por nombre o descripción…")
        self.filtro_nombre.textChanged.connect(self.load_data)

        self.filtro_tipo = QComboBox()
        self.filtro_tipo.addItem("")  # Todos
        self.filtro_tipo.currentIndexChanged.connect(self.load_data)

        self.chk_inactivos = QCheckBox("Ver inactivos")
        self.chk_inactivos.stateChanged.connect(self.load_data)

        f.addWidget(QLabel("Filtro:"))
        f.addWidget(self.filtro_nombre, stretch=2)
        f.addWidget(QLabel("Tipo:"))
        f.addWidget(self.filtro_tipo, stretch=1)
        f.addStretch()
        f.addWidget(self.chk_inactivos)
        layout.addWidget(filtros)

        # Grilla (12 columnas)
        self.table = QTableWidget(0, 12)
        self.table.setHorizontalHeaderLabels([
            "ID","Nombre","Tipo","Precio de Venta","Tipo de Producto","Especialidad",
            "Tipo de Insumo","Uso Interno","Uso Procedimiento","Genera Stock","Activo","Acciones"
        ])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setStretchLastSection(False)
        hdr.setMinimumSectionSize(60)
        self.table.setWordWrap(False)

        self.table.itemDoubleClicked.connect(lambda *_: self.abrir_dialogo_editar(self.table.currentRow()))
        self.table.setAlternatingRowColors(True)

        fm = self.table.fontMetrics()
        self.table.verticalHeader().setDefaultSectionSize(int(fm.height() * 1.9))
        layout.addWidget(self.table)

        # Botón agregar
        self.btn_agregar = QPushButton(" Agregar ítem")
        ico_add = resource_path("agregar.png")
        if ico_add: self.btn_agregar.setIcon(QIcon(ico_add))
        self.btn_agregar.setIconSize(QSize(50, 50))
        self.btn_agregar.clicked.connect(self.abrir_dialogo_agregar)

        h = QHBoxLayout(); h.addStretch(); h.addWidget(self.btn_agregar)
        layout.addLayout(h)
        self.setLayout(layout)

    def _selected_id(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        return int(self.table.item(r, 0).text())

    def _select_row_by_id(self, iditem, col=None):
        if iditem is None:
            return
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it and it.text().isdigit() and int(it.text()) == iditem:
                self.table.setCurrentCell(r, col if col is not None else 1)
                self.table.scrollToItem(self.table.item(r, 1), self.table.PositionAtCenter)
                break

    def _save_view_state(self):
        return {
            "vpos": self.table.verticalScrollBar().value(),
            "hpos": self.table.horizontalScrollBar().value(),
            "id": self._selected_id(),
            "col": self.table.currentColumn(),
        }

    def _restore_view_state(self, state):
        if not state:
            return
        self._select_row_by_id(state.get("id"), state.get("col"))
        self.table.verticalScrollBar().setValue(state.get("vpos", 0))
        self.table.horizontalScrollBar().setValue(state.get("hpos", 0))

    def _fmt_precio(self, v):
        try:
            n = int(v or 0)
            return f"{n:,}".replace(",", ".")
        except Exception:
            return str(v or "0")

    def _auto_fit_columns(self):
        self.table.resizeColumnsToContents()
        fm = self.table.fontMetrics()
        adv = getattr(fm, "horizontalAdvance", fm.width)
        maxw = adv(self.table.horizontalHeaderItem(1).text())
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 1)
            if it:
                w = adv(it.text())
                if w > maxw:
                    maxw = w
        padding = 40
        ancho = max(220, min(maxw + padding, 480))
        self.table.setColumnWidth(1, ancho)
        last = self.table.columnCount() - 1
        self.table.setColumnWidth(last, max(90, self.table.columnWidth(last)))

    # ---------- Data ----------
    def load_tipos(self):
        self._tipos = self.session.query(ItemTipo).order_by(ItemTipo.nombre).all()
        cur = self.filtro_tipo.currentText()
        self.filtro_tipo.blockSignals(True)
        self.filtro_tipo.clear(); self.filtro_tipo.addItem("")
        for t in self._tipos: self.filtro_tipo.addItem(t.nombre)
        ix = self.filtro_tipo.findText(cur)
        self.filtro_tipo.setCurrentIndex(ix if ix != -1 else 0)
        self.filtro_tipo.blockSignals(False)

    def load_data(self):
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(0)
            texto = (self.filtro_nombre.text() or "").strip().lower()
            nombre_tipo = (self.filtro_tipo.currentText() or "").strip()
            ver_inactivos = self.chk_inactivos.isChecked()

            q = (self.session.query(
                    Item,
                    ItemTipo.nombre.label("tipo_general"),
                    TipoProducto.nombre.label("tipo_producto"),
                    Especialidad.nombre.label("especialidad")
                )
                .join(ItemTipo, Item.iditemtipo == ItemTipo.iditemtipo)
                .outerjoin(TipoProducto, Item.idtipoproducto == TipoProducto.idtipoproducto)
                .outerjoin(Especialidad, Item.idespecialidad == Especialidad.idespecialidad)
            )

            if texto:
                q = q.filter(or_(Item.nombre.ilike(f"%{texto}%"), Item.descripcion.ilike(f"%{texto}%")))
            if nombre_tipo:
                q = q.filter(ItemTipo.nombre == nombre_tipo)
            if not ver_inactivos:
                q = q.filter(Item.activo == True)

            rows = q.order_by(Item.nombre.asc()).all()
            self.table.setRowCount(len(rows))

            for r, (it, tipo_general, tipo_producto, especialidad) in enumerate(rows):
                id_fijo = it.iditem
                self.table.setItem(r, 0, QTableWidgetItem(str(it.iditem)))
                self.table.setItem(r, 1, QTableWidgetItem(it.nombre or ""))
                self.table.setItem(r, 2, QTableWidgetItem(tipo_general or ""))

                it_precio = QTableWidgetItem(self._fmt_precio(it.precio_venta))
                it_precio.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, 3, it_precio)

                self.table.setItem(r, 4, QTableWidgetItem(tipo_producto or ""))
                self.table.setItem(r, 5, QTableWidgetItem(especialidad or ""))
                self.table.setItem(r, 6, QTableWidgetItem(it.tipo_insumo or ""))

                it_uso_int = QTableWidgetItem("Sí" if it.uso_interno else "No")
                it_uso_int.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, 7, it_uso_int)

                it_uso_proc = QTableWidgetItem("Sí" if it.uso_procedimiento else "No")
                it_uso_proc.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, 8, it_uso_proc)

                it_gen = QTableWidgetItem("Sí" if getattr(it, "genera_stock", True) else "No")
                it_gen.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, 9, it_gen)

                it_activo = QTableWidgetItem("Sí" if it.activo else "No")
                it_activo.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, 10, it_activo)

                cell = QWidget(); h = QHBoxLayout(cell); h.setContentsMargins(0,0,0,0)
                btn_editar = QPushButton(); ico = resource_path("editar.png")
                if ico: btn_editar.setIcon(QIcon(ico))
                else:   btn_editar.setText("✏")
                btn_editar.setFixedSize(QSize(30,26)); btn_editar.setIconSize(QSize(18,18))
                btn_editar.setToolTip("Editar")
                btn_editar.clicked.connect(lambda _, _id=id_fijo: self._abrir_editar_por_id(_id))
                btn_editar.setFocusPolicy(Qt.NoFocus)

                btn_del = QPushButton(); ico = resource_path("eliminar.png")
                if ico: btn_del.setIcon(QIcon(ico))
                else:   btn_del.setText("🗑")
                btn_del.setFixedSize(QSize(30,26)); btn_del.setIconSize(QSize(18,18))
                btn_del.setToolTip("Eliminar")
                btn_del.clicked.connect(lambda _, _id=id_fijo: self._eliminar_por_id(_id))
                btn_del.setFocusPolicy(Qt.NoFocus)

                h.addWidget(btn_editar); h.addWidget(btn_del)
                cell.setLayout(h)
                self.table.setCellWidget(r, 11, cell)

            self.table.resizeRowsToContents()
            self._auto_fit_columns()
        finally:
            self.table.setSortingEnabled(True)
            self.table.setUpdatesEnabled(True)

    def _row_id(self, row):
        it = self.table.item(row, 0)
        if not it or not it.text().isdigit():
            return -1
        return int(it.text())

    def _row_by_id(self, iditem: int) -> int:
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it and it.text().isdigit() and int(it.text()) == iditem:
                return r
        return -1

    def _abrir_editar_por_id(self, iditem: int):
        row = self._row_by_id(iditem)
        if row >= 0:
            self.abrir_dialogo_editar(row)

    def _eliminar_por_id(self, iditem: int):
        row = self._row_by_id(iditem)
        if row >= 0:
            self.eliminar_item(row)

    # ---------- CRUD ----------
    def abrir_dialogo_agregar(self):
        state = self._save_view_state()
        dlg = FormularioItem(self.session, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.load_tipos()
                self.load_data()
            finally:
                QApplication.restoreOverrideCursor()
            self._restore_view_state(state)

    def abrir_dialogo_editar(self, row):
        if row < 0:
            return
        iditem = self._row_id(row)
        it = self.session.query(Item).get(iditem)
        if not it:
            return
        state = self._save_view_state()
        dlg = FormularioItem(self.session, parent=self, item=it)
        if dlg.exec_() == QDialog.Accepted:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.load_data()
            finally:
                QApplication.restoreOverrideCursor()
            self._restore_view_state(state)

    def _esta_referenciado(self, iditem:int) -> bool:
        s = self.session
        usado_en_compra = s.query(exists().where(CompraDetalle.iditem == iditem)).scalar()
        usado_en_venta  = s.query(exists().where(VentaDetalle.iditem == iditem)).scalar()
        return bool(usado_en_compra or usado_en_venta)

    def eliminar_item(self, row):
        if row < 0 or row >= self.table.rowCount():
            return
        iditem = self._row_id(row)

        next_sel_id = None
        if self.table.rowCount() > 1:
            if row < self.table.rowCount() - 1:
                nxt = self.table.item(row + 1, 0)
            else:
                nxt = self.table.item(row - 1, 0)
            if nxt and nxt.text().isdigit():
                next_sel_id = int(nxt.text())

        if QMessageBox.question(self, "Eliminar", "¿Seguro que desea eliminar este ítem?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return

        it = self.session.query(Item).get(iditem)
        if not it:
            return

        if self._esta_referenciado(iditem):
            QMessageBox.warning(self, "No se puede eliminar",
                                "Este ítem ya fue utilizado o está mapeado.\n"
                                "Sugerencia: marcá el ítem como INACTIVO para bloquear su uso.")
            return

        state = self._save_view_state()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.session.delete(it)
            self.session.commit()
            self.load_data()
        except IntegrityError:
            self.session.rollback()
            QMessageBox.warning(self, "No se puede eliminar",
                                "El ítem está referenciado por otros registros.")
        finally:
            QApplication.restoreOverrideCursor()

        if next_sel_id is not None:
            self._select_row_by_id(next_sel_id, state.get("col"))
            self.table.verticalScrollBar().setValue(state.get("vpos", 0))
            self.table.horizontalScrollBar().setValue(state.get("hpos", 0))
        else:
            self._restore_view_state(state)


# ------------ FORM MODAL ------------
class FormularioItem(QDialog):
    TIPOS_INSUMO = ["Medicamento", "Descartable", "Reactivo", "Limpieza", "Cafetería","Varios"]

    def __init__(self, session, parent=None, item: Item=None):
        super().__init__(parent)
        self.session = session
        self.item = item
        self.setWindowTitle("Editar Ítem" if item else "Agregar Ítem")
        self.setMinimumWidth(720)
        self._locale = QLocale(QLocale.Spanish, QLocale.Paraguay)
        self.init_ui()
        self.load_combos()
        if self.item:
            self.cargar_datos()
            self._cargar_composicion()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # --- Comunes (encabezado) ---
        self.txt_nombre = QLineEdit()

        # Código de barra
        self.txt_codigo = QLineEdit()
        self.txt_codigo.setPlaceholderText("Escaneá o escribí el código…")
        self.txt_codigo.setClearButtonEnabled(True)
        self.txt_codigo.setMaxLength(64)

        self.cbo_tipo_general = QComboBox()
        self.txt_descripcion = QTextEdit()
        self.chk_activo = QCheckBox("Activo"); self.chk_activo.setChecked(True)

        self.chk_genera_stock = QCheckBox("Genera stock")
        self.chk_genera_stock.setChecked(True)

        # Tabs
        self.tabs = QTabWidget()

        # === Tab Producto ===
        tab_prod = QWidget(); lp = QVBoxLayout(tab_prod)
        self.sp_precio = QSpinBox()
        self.sp_precio.setLocale(self._locale)
        self.sp_precio.setGroupSeparatorShown(True)
        self.sp_precio.setRange(0, 1_000_000_000)
        self.sp_precio.setSingleStep(1)

        self.cbo_tipoproducto = QComboBox()
        self.cbo_especialidad = QComboBox()
        self.chk_requiere = QCheckBox("Requiere recordatorio")
        self.sp_dias = QSpinBox(); self.sp_dias.setRange(0, 365)
        self.txt_msg = QLineEdit()

        lp.addWidget(QLabel("Precio de venta")); lp.addWidget(self.sp_precio)
        lp.addWidget(QLabel("Tipo de producto")); lp.addWidget(self.cbo_tipoproducto)
        lp.addWidget(QLabel("Especialidad")); lp.addWidget(self.cbo_especialidad)
        lp.addWidget(self.chk_requiere)
        lp.addWidget(QLabel("Días recordatorio")); lp.addWidget(self.sp_dias)
        lp.addWidget(QLabel("Mensaje recordatorio")); lp.addWidget(self.txt_msg)
        tab_prod.setLayout(lp)

        # === Tab Insumo ===
        tab_ins = QWidget(); li = QVBoxLayout(tab_ins)
        self.txt_unidad = QLineEdit()
        self.cbo_tipo_insumo = QComboBox(); self.cbo_tipo_insumo.addItems(self.TIPOS_INSUMO)
        self.sp_stock_min = QDoubleSpinBox(); self.sp_stock_min.setLocale(self._locale)
        self.sp_stock_min.setDecimals(2); self.sp_stock_min.setMaximum(1e9)

        self.chk_uso_interno = QCheckBox("Uso interno")
        self.chk_uso_proc = QCheckBox("Uso procedimiento")

        li.addWidget(QLabel("Unidad")); li.addWidget(self.txt_unidad)
        li.addWidget(QLabel("Tipo de insumo")); li.addWidget(self.cbo_tipo_insumo)
        li.addWidget(QLabel("Stock mínimo")); li.addWidget(self.sp_stock_min)
        li.addWidget(self.chk_uso_interno); li.addWidget(self.chk_uso_proc)
        tab_ins.setLayout(li)

        # === Tab Composición (NUEVA) ===
        tab_comp = QWidget(); lc = QVBoxLayout(tab_comp)

        # fila alta rápida
        barra = QHBoxLayout()
        self.cbo_insumo = QComboBox()
        self.sp_cantidad_comp = QDoubleSpinBox()
        self.sp_cantidad_comp.setDecimals(3)
        self.sp_cantidad_comp.setRange(0.001, 1_000_000)
        self.sp_cantidad_comp.setValue(1.000)
        btn_add_comp = QPushButton("Agregar")
        btn_add_comp.clicked.connect(self._agregar_insumo_composicion)

        barra.addWidget(QLabel("Insumo / componente"))
        barra.addWidget(self.cbo_insumo, 2)
        barra.addWidget(QLabel("Cantidad"))
        barra.addWidget(self.sp_cantidad_comp)
        barra.addWidget(btn_add_comp)
        lc.addLayout(barra)

        # tabla composición
        self.tbl_comp = QTableWidget(0, 4)
        self.tbl_comp.setHorizontalHeaderLabels(["ID", "Nombre", "Cantidad", "Acciones"])
        self.tbl_comp.verticalHeader().setVisible(False)
        self.tbl_comp.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_comp.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_comp.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tbl_comp.horizontalHeader().setStretchLastSection(False)
        lc.addWidget(self.tbl_comp)
        tab_comp.setLayout(lc)

        self.tabs.addTab(tab_prod, "Producto")
        self.tabs.addTab(tab_ins, "Insumo")
        self.tabs.addTab(tab_comp, "Composición")

        # Header comunes
        head = QVBoxLayout()
        head.addWidget(QLabel("Nombre")); head.addWidget(self.txt_nombre)
        head.addWidget(QLabel("Código de barra")); head.addWidget(self.txt_codigo)
        head.addWidget(QLabel("Tipo (GENERAL)")); head.addWidget(self.cbo_tipo_general)
        head.addWidget(QLabel("Descripción")); head.addWidget(self.txt_descripcion)
        head.addWidget(self.chk_genera_stock)
        head.addWidget(self.chk_activo)

        cont = QWidget(); cont.setLayout(head)
        layout.addWidget(cont)
        layout.addWidget(self.tabs)

        # Botones
        btns = QHBoxLayout()
        self.btn_guardar = QPushButton("Guardar")
        self.btn_guardar.clicked.connect(self.guardar)
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.clicked.connect(self.reject)
        btns.addStretch(); btns.addWidget(self.btn_guardar); btns.addWidget(self.btn_cancelar)
        layout.addLayout(btns)

        self.cbo_tipo_general.currentIndexChanged.connect(self._toggle_tabs_by_tipo)

    # Combos
    def load_combos(self):
        # ItemTipo
        self.cbo_tipo_general.clear()
        for t in self.session.query(ItemTipo).order_by(ItemTipo.nombre).all():
            self.cbo_tipo_general.addItem(t.nombre, t.iditemtipo)

        # TipoProducto
        self.cbo_tipoproducto.clear()
        for tp in self.session.query(TipoProducto).order_by(TipoProducto.nombre).all():
            self.cbo_tipoproducto.addItem(tp.nombre, tp.idtipoproducto)

        # Especialidad
        self.cbo_especialidad.clear()
        for e in self.session.query(Especialidad).order_by(Especialidad.nombre).all():
            self.cbo_especialidad.addItem(e.nombre, e.idespecialidad)

        # Insumos disponibles para Composición (solo activos, que muevan stock o uso_procedimiento)
        self._poblar_combo_insumo()

        self._toggle_tabs_by_tipo()

    def _poblar_combo_insumo(self):
        self.cbo_insumo.clear()
        q = (self.session.query(Item)
             .filter(Item.activo == True)
             .filter(or_(Item.genera_stock == True, Item.uso_procedimiento == True))
             .order_by(Item.nombre.asc()))
        # Si estoy editando, evito que el padre se elija como su propio componente
        if self.item:
            q = q.filter(Item.iditem != self.item.iditem)
        for it in q.all():
            self.cbo_insumo.addItem(f"{it.nombre}", it.iditem)

    def _toggle_tabs_by_tipo(self):
        txt = (self.cbo_tipo_general.currentText() or "").upper()
        self.tabs.setTabEnabled(0, txt in ("PRODUCTO", "AMBOS"))
        self.tabs.setTabEnabled(1, txt in ("INSUMO", "AMBOS"))
        # Composición: útil para SERVICIO / PRODUCTO / AMBOS
        self.tabs.setTabEnabled(2, txt in ("SERVICIO", "PRODUCTO", "AMBOS"))

        if txt == "PRODUCTO" and not (self.chk_uso_interno.isChecked() or self.chk_uso_proc.isChecked()):
            self.chk_uso_proc.setChecked(True)

        if txt == "SERVICIO":
            self.chk_genera_stock.setChecked(False)
            self.chk_genera_stock.setEnabled(False)
        else:
            self.chk_genera_stock.setEnabled(True)

    def cargar_datos(self):
        it = self.item
        self.txt_nombre.setText(it.nombre or "")
        self.txt_codigo.setText(it.codigo_barra or "")
        self.txt_descripcion.setPlainText(it.descripcion or "")
        self.chk_activo.setChecked(bool(it.activo))
        self.chk_genera_stock.setChecked(bool(getattr(it, "genera_stock", True)))

        if it.tipo:
            ix = self.cbo_tipo_general.findText(it.tipo.nombre, Qt.MatchFixedString)
            self.cbo_tipo_general.setCurrentIndex(ix if ix != -1 else 0)

        if it.precio_venta is not None: self.sp_precio.setValue(int(it.precio_venta))
        if it.idtipoproducto:
            ix = self.cbo_tipoproducto.findData(it.idtipoproducto)
            if ix != -1: self.cbo_tipoproducto.setCurrentIndex(ix)
        if it.idespecialidad:
            ix = self.cbo_especialidad.findData(it.idespecialidad)
            if ix != -1: self.cbo_especialidad.setCurrentIndex(ix)
        self.chk_requiere.setChecked(bool(it.requiere_recordatorio))
        self.sp_dias.setValue(int(it.dias_recordatorio or 0))
        self.txt_msg.setText(it.mensaje_recordatorio or "")

        self.txt_unidad.setText(it.unidad or "")
        if it.tipo_insumo:
            ix = self.cbo_tipo_insumo.findText(it.tipo_insumo, Qt.MatchFixedString)
            if ix != -1: self.cbo_tipo_insumo.setCurrentIndex(ix)
        if it.stock_minimo is not None: self.sp_stock_min.setValue(float(it.stock_minimo))

        self.chk_uso_interno.setChecked(bool(it.uso_interno))
        self.chk_uso_proc.setChecked(bool(it.uso_procedimiento))

    # ----------- COMPOSICIÓN (UI) -----------
    def _agregar_insumo_composicion(self):
        insumo_id = self.cbo_insumo.currentData()
        if insumo_id is None:
            return
        if self.item and insumo_id == self.item.iditem:
            QMessageBox.warning(self, "Composición", "El ítem no puede componerse de sí mismo.")
            return

        # Si ya existe, sumo cantidades
        for r in range(self.tbl_comp.rowCount()):
            rid = int(self.tbl_comp.item(r, 0).text())
            if rid == insumo_id:
                sp: QDoubleSpinBox = self.tbl_comp.cellWidget(r, 2)
                sp.setValue(sp.value() + float(self.sp_cantidad_comp.value()))
                return

        it = self.session.query(Item).get(insumo_id)
        if not it:
            return

        r = self.tbl_comp.rowCount()
        self.tbl_comp.insertRow(r)
        self.tbl_comp.setItem(r, 0, QTableWidgetItem(str(insumo_id)))
        self.tbl_comp.setItem(r, 1, QTableWidgetItem(it.nombre))

        sp = QDoubleSpinBox()
        sp.setDecimals(3); sp.setRange(0.001, 1_000_000); sp.setValue(float(self.sp_cantidad_comp.value()))
        self.tbl_comp.setCellWidget(r, 2, sp)

        btn = QPushButton("Quitar")
        btn.clicked.connect(lambda *_: self._quitar_fila_composicion(r))
        self.tbl_comp.setCellWidget(r, 3, btn)

    def _quitar_fila_composicion(self, row):
        if 0 <= row < self.tbl_comp.rowCount():
            self.tbl_comp.removeRow(row)

    def _cargar_composicion(self):
        """Carga desde DB a la tabla si estoy editando un ítem existente."""
        self.tbl_comp.setRowCount(0)
        if not self.item:
            return
        comps = (self.session.query(ItemComposicion)
                 .filter(ItemComposicion.iditem_padre == self.item.iditem)
                 .all())
        for c in comps:
            r = self.tbl_comp.rowCount()
            self.tbl_comp.insertRow(r)
            self.tbl_comp.setItem(r, 0, QTableWidgetItem(str(c.iditem_insumo)))
            self.tbl_comp.setItem(r, 1, QTableWidgetItem(c.insumo.nombre if c.insumo else str(c.iditem_insumo)))

            sp = QDoubleSpinBox()
            sp.setDecimals(3); sp.setRange(0.001, 1_000_000); sp.setValue(float(c.cantidad or 1))
            self.tbl_comp.setCellWidget(r, 2, sp)

            btn = QPushButton("Quitar")
            # Corregido:
            btn.clicked.connect(lambda _, _r=r: self._quitar_fila_composicion(_r))
            self.tbl_comp.setCellWidget(r, 3, btn)

    def _recoger_composicion_ui(self):
        """Devuelve lista de dicts con {iditem_insumo, cantidad} desde la tabla UI."""
        out = []
        for r in range(self.tbl_comp.rowCount()):
            iid = int(self.tbl_comp.item(r, 0).text())
            sp: QDoubleSpinBox = self.tbl_comp.cellWidget(r, 2)
            out.append({"iditem_insumo": iid, "cantidad": float(sp.value())})
        return out

    def _sync_composicion_db(self, iditem_padre: int):
        """Sincroniza DB con lo que hay en la UI (delete + insert)."""
        lista = self._recoger_composicion_ui()
        # Eliminar existentes
        self.session.query(ItemComposicion).filter(ItemComposicion.iditem_padre == iditem_padre).delete(synchronize_session=False)
        # Insertar nuevos
        for row in lista:
            if row["iditem_insumo"] == iditem_padre:
                continue
            self.session.add(ItemComposicion(
                iditem_padre=iditem_padre,
                iditem_insumo=row["iditem_insumo"],
                cantidad=row["cantidad"] or 1
            ))

    # ----------- GUARDAR -----------
    def guardar(self):
        nombre = (self.txt_nombre.text() or "").strip()
        if not nombre:
            QMessageBox.warning(self, "Validación", "Debe ingresar el nombre.")
            return
        iditemtipo = self.cbo_tipo_general.currentData()
        if not iditemtipo:
            QMessageBox.warning(self, "Validación", "Debe seleccionar el tipo general.")
            return

        codigo = (self.txt_codigo.text() or "").strip() or None
        if codigo:
            q = self.session.query(Item).filter(Item.codigo_barra == codigo)
            if self.item is not None:
                q = q.filter(Item.iditem != self.item.iditem)
            if self.session.query(q.exists()).scalar():
                QMessageBox.warning(self, "Validación", "Ya existe otro ítem con ese código de barra.")
                return

        precio = int(self.sp_precio.value())
        idtp = self.cbo_tipoproducto.currentData()
        idesp = self.cbo_especialidad.currentData()
        req = self.chk_requiere.isChecked()
        dias = int(self.sp_dias.value())
        msg  = (self.txt_msg.text() or "").strip() or None

        unidad = (self.txt_unidad.text() or "").strip() or None
        tin = self.cbo_tipo_insumo.currentText()
        stock_min = self.sp_stock_min.value()

        uso_int = self.chk_uso_interno.isChecked()
        uso_proc = self.chk_uso_proc.isChecked()

        categoria = None
        if uso_int and uso_proc: categoria = "AMBOS"
        elif uso_int:            categoria = "CONSUMO_INTERNO"
        elif uso_proc:           categoria = "USO_PROCEDIMIENTO"

        tipo_general = (self.cbo_tipo_general.currentText() or "").upper()
        if tipo_general == "PRODUCTO":
            unidad = tin = None; stock_min = None
            if not (uso_int or uso_proc): uso_proc = True
        elif tipo_general == "INSUMO":
            precio = 0; idtp = None; idesp = None; req = False; dias = 0; msg = None
        elif tipo_general == "SERVICIO":
            self.chk_genera_stock.setChecked(False)

        data = dict(
            nombre=nombre,
            codigo_barra=codigo,
            descripcion=(self.txt_descripcion.toPlainText() or None),
            activo=self.chk_activo.isChecked(),
            iditemtipo=iditemtipo,

            precio_venta=precio,
            idtipoproducto=idtp,
            idespecialidad=idesp,
            requiere_recordatorio=req,
            dias_recordatorio=dias,
            mensaje_recordatorio=msg,

            unidad=unidad,
            categoria=categoria,
            tipo_insumo=tin,
            stock_minimo=stock_min,
            uso_interno=uso_int,
            uso_procedimiento=uso_proc,

            genera_stock=self.chk_genera_stock.isChecked(),
        )

        try:
            if self.item is None:
                it = Item(**data)
                self.session.add(it)
                self.session.flush()  # obtener id para composición
                self._sync_composicion_db(it.iditem)
            else:
                for k, v in data.items():
                    setattr(self.item, k, v)
                self._sync_composicion_db(self.item.iditem)

            self.session.commit()
        except IntegrityError as e:
            self.session.rollback()
            QMessageBox.warning(self, "Error", f"No se pudo guardar. {str(e.orig) if hasattr(e, 'orig') else ''}")
            return

        self.accept()

    def closeEvent(self, e):
        try:
            self.session.close()
        finally:
            super().closeEvent(e)
