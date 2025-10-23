from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QDateEdit, QTextEdit, QTableWidget, QTableWidgetItem, QSplitter, QGroupBox, QFormLayout,
    QMessageBox, QListWidget, QDialog, QCompleter, QShortcut, QAbstractItemView
)
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtCore import Qt, QDate, QEvent, QTimer
from decimal import Decimal
from sqlalchemy import select, or_,func
from sqlalchemy.orm import joinedload
from utils.db import SessionLocal
from controllers.ventas_controller import VentasController
from models.paciente import Paciente
from models.profesional import Profesional
from models.clinica import Clinica
from models.venta_detalle import VentaDetalle
from models.venta import Venta
from controllers.buscar_venta_dialog import BuscarVentaDialog
# === impresión TXT (preimpreso) ===
from printing.factura_txt import render_factura_txt, DEFAULT_LAYOUT
from services.venta_consumo_service import (
    confirmar_venta_generar_consumo,
    anular_venta_revertir_consumo,
)
from typing import Optional,ContextManager, Any
import os, datetime
from contextlib import nullcontext
# ====== NUEVO: imports tolerantes de Cobro y CobroVenta ======
try:
    from models.cobro import Cobro
except Exception:
    Cobro = None

try:
    from models.cobro_venta import CobroVenta
except Exception:
    CobroVenta = None
# =============================================================


# --- Diálogo de selección genérico (producto o paquete)
class ItemSelectDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar ítem")
        self.selected = None
        layout = QVBoxLayout(self)
        self.listWidget = QListWidget()
        for it in items:
            # it: (tipo, id, nombre, precio)
            tipo, _id, nombre, pv = it
            pref = "P" if tipo == "producto" else "Q"
            self.listWidget.addItem(f"{pref}{_id} - {nombre} - {pv:,.0f}".replace(",", "."))
        layout.addWidget(self.listWidget)
        self.listWidget.setCurrentRow(0)
        btn = QPushButton("Seleccionar")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
        self.listWidget.itemDoubleClicked.connect(self.accept)
        self.resize(420, 330)

    def accept(self):
        idx = self.listWidget.currentRow()
        if idx >= 0:
            self.selected = idx
            super().accept()


class ABMVenta(QWidget):
    def __init__(self, usuario_id=None, parent=None):
        super().__init__(parent)
        self.usuario_id = usuario_id
        self.session = SessionLocal()
        self._detalle_ids = []
        self.ventas = []
        self.modo_nuevo = False
        self.idventa_actual = None
        self.idx_actual = -1

        self.setWindowTitle("Ventas")
        self.resize(980, 540)      # <<< igual que Compras

        self._setup_ui()
        self.btn_planes.clicked.connect(self.abrir_planes_paciente)
        self.btn_buscar_venta.clicked.connect(self.abrir_buscador_venta)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.abrir_buscador_venta)  # <<< crea los widgets
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self._on_guardar_click)
        self.grilla.itemChanged.connect(self._on_item_changed)
        # --- Conexiones (después del setup) ---
        self.btn_eliminar.clicked.connect(self.eliminar_fila_grilla)
        self.btn_guardar.clicked.connect(self._on_guardar_click)
        self.btn_anular.clicked.connect(self.anular_venta_actual)
        self.btn_imprimir.clicked.connect(self._on_imprimir_clicked)
        self.btn_anular.setEnabled(False)
        self.btn_primero.clicked.connect(self.ir_primero)
        self.btn_anterior.clicked.connect(self.ir_anterior)
        self.btn_siguiente.clicked.connect(self.ir_siguiente)
        self.btn_ultimo.clicked.connect(self.ir_ultimo)
        self.btn_nuevo.clicked.connect(self.nuevo)
        self.btn_buscar.clicked.connect(self.buscar_y_agregar_item)

        # Datos
        self.cargar_maestros()
        self.setup_focus()
        self.cbo_paciente.setFocus()
        self.cargar_ventas()
        self.modo_edicion = False
        self._update_buttons_state()
    
    def _txn_ctx(self) -> ContextManager[Any]:
        return self.session.begin() if not self.session.in_transaction() else nullcontext()
    
    def _safe_rb(self):
        try:
            self._safe_rb()
        except Exception:
            pass
    def _detalle_id_seleccionado(self) -> Optional[int]:
        r = self.grilla.currentRow()
        if r < 0:
            return None
        try:
            return int(self._detalle_ids[r])
        except Exception:
            return None

    def abrir_planes_paciente(self):
        if not self.modo_edicion:
            QMessageBox.information(self, "Planes", "Para gestionar los planes, primero presioná Editar.")
            return
        if not self.idventa_actual:
            QMessageBox.information(self, "Planes", "No hay una venta cargada.")
            return

        pid = self.cbo_paciente.currentData()
        if not pid:
            QMessageBox.information(self, "Planes", "Seleccione un paciente primero.")
            return

        idvd = self._detalle_id_seleccionado()
        if not idvd:
            QMessageBox.information(self, "Planes", "Seleccioná una línea de la venta (el procedimiento).")
            return

        iditem_proc = self.session.execute(
            select(VentaDetalle.iditem).where(VentaDetalle.idventadet == idvd)
        ).scalar()

        try:
            from controllers.planes_paciente import PlanesPaciente
            dlg = PlanesPaciente(
                self,
                idpaciente=pid,
                ctx_venta={"idventadet": idvd, "iditem_procedimiento": iditem_proc}
            )
            dlg.exec_()
        except Exception as e:
            QMessageBox.information(self, "Planes", f"No se pudo abrir el panel de planes.\n{e}")

    def _mask_vacia(self, txt: str) -> bool:
        return ((txt or "").replace("_", "").replace("-", "").strip() == "")

    def _pintar_estado(self, v: Venta):
        est = (getattr(v, "estadoventa", "") or "").strip().lower()
        anulada = getattr(v, "anulada", False)

        if est == "anulada" or anulada:
            self.lbl_estado.setText("Anulada")
            self.lbl_estado.setStyleSheet("font-weight:bold; color:#dc3545; margin-bottom:6px;")
            self.btn_anular.setEnabled(False)
            self.set_campos_enabled(False)

        elif est in ("cerrada", "cerrado"):
            self.lbl_estado.setText("Generada")
            self.lbl_estado.setStyleSheet("font-weight:bold; color:#0d6efd; margin-bottom:6px;")
            self.btn_anular.setEnabled(True)
            self.set_campos_enabled(False)

        else:
            self.lbl_estado.setText("Cobrada")
            self.lbl_estado.setStyleSheet("font-weight:bold; color: green; margin-bottom:6px;")
            self.btn_anular.setEnabled(True)

    def _enable_search_on_combobox(self, combo: QComboBox):
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        items = [combo.itemText(i) for i in range(combo.count())]
        comp = QCompleter(items, combo)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        combo.setCompleter(comp)

    def _venta_tiene_cobros_activos(self, idventa: int) -> bool:
        # Si no existen los modelos, asumimos que no hay cobros activos
        if Cobro is None or CobroVenta is None:
            return False

        row = self.session.execute(
            select(1)
            .select_from(CobroVenta)
            .join(Cobro, Cobro.idcobro == CobroVenta.idcobro)
            .where(
                CobroVenta.idventa == int(idventa),
                or_(Cobro.estado.is_(None), func.lower(func.trim(Cobro.estado)) != "anulado")
            )
            .limit(1)
        ).first()
        return bool(row)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        title_layout = QHBoxLayout()
        icono = QLabel(); icono.setPixmap(QIcon("imagenes/venta.png").pixmap(32, 32))
        title_layout.addWidget(icono)
        title_label = QLabel("Ventas")
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold; margin-left:8px;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()
        self.btn_imprimir = QPushButton(QIcon("imagenes/imprimir.png"), " Imprimir")
        self.btn_imprimir.setToolTip("Imprimir factura (TXT)")
        self.btn_imprimir.setCursor(Qt.PointingHandCursor)
        self.btn_imprimir.setStyleSheet("""
        QPushButton { 
            background-color: #198754; 
            color: white; 
            font-weight: bold;
            border-radius: 6px; 
            padding: 5px 15px; 
        }
        QPushButton:hover:!disabled { background-color: #20c997; }
        QPushButton:disabled { background-color: #e9ecef; color: #6c757d; }
        """)
        title_layout.addWidget(self.btn_imprimir)
        main_layout.addLayout(title_layout)

        splitter = QSplitter(Qt.Horizontal)
        left_box = QGroupBox("Datos de la Venta")
        left_layout = QFormLayout()
        self.idventa = QLineEdit(); self.idventa.setReadOnly(True)
        left_layout.addRow(QLabel("ID Venta:"), self.idventa)
        self.fecha = QDateEdit(QDate.currentDate()); self.fecha.setCalendarPopup(True)
        left_layout.addRow(QLabel("Fecha:"), self.fecha)
        self.txt_nro_factura = QLineEdit()
        self.txt_nro_factura.setInputMask("000-000-0000000;_")  # 001-001-0000001
        left_layout.addRow(QLabel("N° Factura:"), self.txt_nro_factura)
        self.cbo_paciente = QComboBox(); left_layout.addRow(QLabel("Paciente:"), self.cbo_paciente)
        self.cbo_profesional = QComboBox(); left_layout.addRow(QLabel("Profesional:"), self.cbo_profesional)
        self.cbo_clinica = QComboBox(); left_layout.addRow(QLabel("Clínica:"), self.cbo_clinica)
        self.observaciones = QTextEdit(); left_layout.addRow(QLabel("Observaciones:"), self.observaciones)
        self.btn_planes = QPushButton("Planes…")
        self.btn_planes.setStyleSheet("""
        QPushButton { background-color: #276ef1; color: white; font-weight: bold;
                      border-radius: 6px; padding: 4px 12px; }
        QPushButton:hover:!disabled { background-color: #5181f3; }
        QPushButton:disabled { background-color: #e9ecef; color: #6c757d; }
        """)
        left_layout.addRow(QLabel(""), self.btn_planes)
        self.lbl_estado = QLabel("Activo")
        self.lbl_estado.setStyleSheet("font-weight:bold; color: green; margin-bottom:6px;")
        left_layout.addRow(QLabel("Estado:"), self.lbl_estado)
        left_box.setLayout(left_layout)
        splitter.addWidget(left_box)

        right_widget = QWidget(); right_layout = QVBoxLayout(right_widget)
        search_layout = QHBoxLayout()
        self.cbo_tipo = QComboBox(); self.cbo_tipo.addItems(["producto", "paquete"])
        self.busca_item = QLineEdit(); self.busca_item.setPlaceholderText("Buscar producto o paquete")
        self.btn_buscar = QPushButton(QIcon("imagenes/buscar.png"), "")
        search_layout.addWidget(self.cbo_tipo)
        search_layout.addWidget(self.busca_item)
        search_layout.addWidget(self.btn_buscar)
        right_layout.addLayout(search_layout)

        self.grilla = QTableWidget(0, 6)
        self.grilla.setHorizontalHeaderLabels(["Código", "Nombre", "Cantidad", "Precio", "Total", "IVA 10%"])
        right_layout.addWidget(self.grilla)

        btns_detalle = QHBoxLayout()
        self.btn_eliminar = QPushButton(QIcon("imagenes/eliminar.png"), "Eliminar")
        btns_detalle.addWidget(self.btn_eliminar)
        self.lbl_total = QLabel("Total: 0      IVA10: 0")
        btns_detalle.addStretch()
        btns_detalle.addWidget(self.lbl_total)
        right_layout.addLayout(btns_detalle)

        pie_layout = QHBoxLayout()
        self.btn_buscar_venta = QPushButton(QIcon("imagenes/buscar.png"), "Buscar")
        self.btn_buscar_venta.setStyleSheet("""
            QPushButton { background-color: #0d6efd; color: white; font-weight: bold;
                          border-radius: 6px; padding: 4px 12px; }
            QPushButton:hover:!disabled { background-color: #b6d4fe; color: #0d6efd; }
            QPushButton:disabled { background-color: #e9ecef; color: #6c757d; }
        """)
        pie_layout.addWidget(self.btn_buscar_venta)
        self.btn_primero   = QPushButton(QIcon("imagenes/primero.png"), "")
        self.btn_anterior  = QPushButton(QIcon("imagenes/anterior.png"), "")
        self.btn_siguiente = QPushButton(QIcon("imagenes/siguiente.png"), "")
        self.btn_ultimo    = QPushButton(QIcon("imagenes/ultimo.png"), "")
        for btn in [self.btn_primero, self.btn_anterior, self.btn_siguiente, self.btn_ultimo]:
            btn.setStyleSheet("""
            QPushButton { background-color: #007bff; color: #007bff;
                          border-radius: 6px; padding: 4px 10px; }
            QPushButton:hover:!disabled { background-color: #b6d4fe; }
            QPushButton:disabled { background-color: #e9ecef; color: #6c757d; }
            """)

        for b in [self.btn_primero, self.btn_anterior, self.btn_siguiente, self.btn_ultimo]:
            pie_layout.addWidget(b)
        self.btn_nuevo    = QPushButton(QIcon("imagenes/nuevo.png"), "Nuevo")
        self.btn_guardar  = QPushButton(QIcon("imagenes/guardar.png"), "Guardar")
        self.btn_anular   = QPushButton(QIcon("imagenes/eliminar.png"), "Anular")
        self.btn_editar   = QPushButton(QIcon("imagenes/editar.png"), "Editar")
        self.btn_editar.setStyleSheet("""
        QPushButton { background-color: #fd7e14; color: white; font-weight: bold;
                      border-radius: 6px; padding: 4px 18px; }
        QPushButton:hover:!disabled { background-color: #ffb37a; }
        QPushButton:disabled { background-color: #e9ecef; color: #6c757d; }
        """)
        self.btn_editar.clicked.connect(self.editar_actual)
        for btn, fondo in [(self.btn_nuevo, "#007bff"),
                           (self.btn_guardar, "#28a745"),
                           (self.btn_anular, "#dc3545")]:
            self.set_btn_style(btn, fondo)
        for b in [self.btn_nuevo, self.btn_editar, self.btn_guardar, self.btn_anular]:
            pie_layout.addWidget(b)
        right_layout.addLayout(pie_layout)
        splitter.addWidget(right_widget)
        splitter.setSizes([340, 800])

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def set_btn_style(self, btn: QPushButton, fondo: str):
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {fondo};
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 4px 18px;
            }}
            QPushButton:hover:!disabled {{ background-color: #b6d4fe; color: #0d6efd; }}
            QPushButton:disabled {{ background-color: #e9ecef; color: #6c757d; }}
        """)

    def _on_item_changed(self, item):
        r, c = item.row(), item.column()
        if c in (2, 3):
            if not self.grilla.item(r, 2) or not self.grilla.item(r, 3):
                return
            if (self.grilla.item(r, 2).text() or "").strip() == "" or \
               (self.grilla.item(r, 3).text() or "").strip() == "":
                return
            self.grilla.blockSignals(True)
            self.calcular_total_row(r)
            self.actualizar_total_pie()
            self.grilla.blockSignals(False)

    def _update_buttons_state(self):
        has_loaded = self.idventa_actual is not None
        modo_ed = getattr(self, "modo_edicion", False)
        modo_nuevo = getattr(self, "modo_nuevo", False)
        self.btn_planes.setEnabled(modo_ed and has_loaded)

        if modo_nuevo:
            self.btn_guardar.setEnabled(True)
            self.btn_nuevo.setEnabled(False)
            self.btn_editar.setEnabled(False)
            self.btn_anular.setEnabled(False)
            self._toggle_nav(False)
        elif modo_ed:
            self.btn_guardar.setEnabled(True)
            self.btn_nuevo.setEnabled(False)
            self.btn_editar.setEnabled(False)
            self.btn_anular.setEnabled(False)
            self._toggle_nav(False)
        else:
            self.btn_guardar.setEnabled(False)
            self.btn_nuevo.setEnabled(True)
            self.btn_editar.setEnabled(has_loaded)
            self.btn_anular.setEnabled(has_loaded)
            self._toggle_nav(True)
        self.btn_imprimir.setEnabled(has_loaded and not (modo_nuevo or modo_ed))

    def agregar_item_a_grilla(self, it):
        tipo, _id, nombre, pv = it
        for row in range(self.grilla.rowCount()):
            cod = self.grilla.item(row, 0)
            if cod and cod.text() == str(_id):
                self.grilla.blockSignals(True)
                cant_item = self.grilla.item(row, 2)
                if not cant_item:
                    cant_item = QTableWidgetItem("0")
                    self.grilla.setItem(row, 2, cant_item)
                try:
                    cant_actual = int((cant_item.text() or "0").replace(".", "").replace(",", ""))
                except Exception:
                    cant_actual = 0
                cant_item.setText(str(cant_actual + 1))
                self.calcular_total_row(row)
                self.grilla.blockSignals(False)
                self.actualizar_total_pie()
                self.grilla.setCurrentCell(row, 2)
                self.grilla.editItem(self.grilla.item(row, 2))
                QTimer.singleShot(0, self._select_all_in_current_editor)
                return

        self.grilla.blockSignals(True)
        row = self.grilla.rowCount()
        self.grilla.insertRow(row)
        cod_item = QTableWidgetItem(str(_id))
        cod_item.setData(Qt.UserRole, tipo)
        self.grilla.setItem(row, 0, cod_item)
        self.grilla.setItem(row, 1, QTableWidgetItem(nombre))
        self.grilla.setItem(row, 2, QTableWidgetItem("1"))
        self.grilla.setItem(row, 3, QTableWidgetItem(f"{pv:,.0f}".replace(",", ".")))
        total = int(round(float(pv)))
        iva = round(total / 11)
        self.grilla.setItem(row, 4, QTableWidgetItem(f"{total:,.0f}".replace(",", ".")))
        self.grilla.setItem(row, 5, QTableWidgetItem(f"{iva:,.0f}".replace(",", ".")))
        self.grilla.blockSignals(False)
        self.actualizar_total_pie()
        self.grilla.setCurrentCell(row, 2)
        self.grilla.editItem(self.grilla.item(row, 2))

    def _select_all_in_current_editor(self):
        from PyQt5.QtWidgets import QApplication, QLineEdit, QSpinBox, QDoubleSpinBox
        w = QApplication.focusWidget()
        if isinstance(w, (QLineEdit,)):
            w.selectAll()
        elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
            w.lineEdit().selectAll()

    def cargar_maestros(self):
        s = self.session
        self.cbo_paciente.clear()
        for p in s.execute(select(Paciente).order_by(Paciente.apellido)).scalars():
            self.cbo_paciente.addItem(f"{p.apellido}, {p.nombre}", p.idpaciente)
        self._enable_search_on_combobox(self.cbo_paciente)
        self.cbo_profesional.clear()
        for pr in s.execute(select(Profesional).where(Profesional.estado.is_(True)).order_by(Profesional.apellido)).scalars():
            self.cbo_profesional.addItem(f"{pr.apellido}, {pr.nombre}", pr.idprofesional)
        self.cbo_clinica.clear()
        for c in s.execute(select(Clinica).order_by(Clinica.nombre)).scalars():
            self.cbo_clinica.addItem(c.nombre, c.idclinica)

    def set_campos_enabled(self, estado: bool):
        self.fecha.setEnabled(estado)
        self.txt_nro_factura.setEnabled(estado)
        self.cbo_paciente.setEnabled(estado)
        self.cbo_profesional.setEnabled(estado)
        self.cbo_clinica.setEnabled(estado)
        self.observaciones.setEnabled(estado)
        self.grilla.setEnabled(estado)
        self.cbo_tipo.setEnabled(estado)
        self.busca_item.setEnabled(estado)
        self.btn_buscar.setEnabled(estado)
        self.btn_eliminar.setEnabled(estado)

    def limpiar_formulario(self, editable=False):
        self.idventa.clear()
        self.fecha.setDate(QDate.currentDate())
        if self.cbo_paciente.count(): self.cbo_paciente.setCurrentIndex(0)
        if self.cbo_profesional.count(): self.cbo_profesional.setCurrentIndex(0)
        if self.cbo_clinica.count(): self.cbo_clinica.setCurrentIndex(0)
        self.txt_nro_factura.clear()
        self.observaciones.clear()
        self.grilla.setRowCount(0)
        self.lbl_total.setText("Total: 0      IVA10: 0")
        self.idventa_actual = None
        self.idx_actual = -1
        self.lbl_estado.setText("Activo")
        self.lbl_estado.setStyleSheet("font-weight:bold; color: green;")
        self._update_buttons_state()
        self._detalle_ids = []
        self.set_campos_enabled(editable)
        self.btn_guardar.setEnabled(editable)
        self.btn_anular.setEnabled(False)
        self.btn_nuevo.setEnabled(not editable)
        self.btn_editar.setEnabled(False)
        self._toggle_nav(not editable)

    def eliminar_fila_grilla(self):
        row = self.grilla.currentRow()
        if row < 0:
            QMessageBox.information(self, "Atención", "Debe seleccionar una fila.")
            return
        if QMessageBox.question(
            self, "Eliminar ítem", "¿Eliminar la fila seleccionada?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) == QMessageBox.No:
            return
        self.grilla.removeRow(row)
        self.actualizar_total_pie()
        if self.grilla.rowCount() > 0:
            self.grilla.setCurrentCell(min(row, self.grilla.rowCount() - 1), 0)

    def cancelar(self):
        self.modo_nuevo = False
        self.limpiar_formulario(editable=False)

    def cargar_ventas(self):
        ctrl = VentasController(self.session, usuario_id=self.usuario_id)
        self.ventas = ctrl.listar_ventas(solo_no_anuladas=False)
        self.idx_actual = -1
        self.limpiar_formulario(editable=False)

    def mostrar_venta(self, idx):
        from sqlalchemy import select
        from models.item import Item
        if not self.ventas or idx < 0 or idx >= len(self.ventas):
            return
        v = self.ventas[idx]
        self.idventa_actual = v.idventa
        self.idventa.setText(str(v.idventa))
        self.fecha.setDate(QDate(v.fecha.year, v.fecha.month, v.fecha.day))
        if v.idpaciente:
            self.cbo_paciente.setCurrentIndex(self.cbo_paciente.findData(v.idpaciente))
        if v.idprofesional:
            self.cbo_profesional.setCurrentIndex(self.cbo_profesional.findData(v.idprofesional))
        if v.idclinica:
            self.cbo_clinica.setCurrentIndex(self.cbo_clinica.findData(v.idclinica))
        self.observaciones.setPlainText(v.observaciones or "")
        nf = getattr(v, "nro_factura", None)
        self.txt_nro_factura.setText(nf if nf else "")

        det_rows = self.session.execute(
            select(
                VentaDetalle.idventadet, VentaDetalle.iditem, VentaDetalle.cantidad,
                VentaDetalle.preciounitario, VentaDetalle.descuento,
            ).where(VentaDetalle.idventa == v.idventa)
        ).all()
        iditems = [r[1] for r in det_rows if r[1] is not None]
        items_map = {}
        if iditems:
            it_rows = self.session.execute(
                select(Item.iditem, Item.nombre).where(Item.iditem.in_(iditems))
            ).all()
            for iid, nom in it_rows:
                items_map[iid] = (str(iid), (nom or ""))

        self.grilla.blockSignals(True)
        self.grilla.setRowCount(0)
        self._detalle_ids = []
        for (idventadet, iditem, cant, pu, desc) in det_rows:
            codigo, nombre = items_map.get(iditem, ("", ""))
            try: cant = int(Decimal(str(cant or 0)))
            except Exception: cant = 0
            try: pu = int(Decimal(str(pu or 0)))
            except Exception: pu = 0
            try: desc = Decimal(str(desc or 0))
            except Exception: desc = Decimal("0")
            subtotal = (Decimal(pu) * Decimal(cant)) - desc
            try: sub_i = int(subtotal)
            except Exception: sub_i = 0
            iva_i = round(sub_i / 11)
            row = self.grilla.rowCount()
            self.grilla.insertRow(row)
            self.grilla.setItem(row, 0, QTableWidgetItem(codigo))
            self.grilla.setItem(row, 1, QTableWidgetItem(nombre))
            self.grilla.setItem(row, 2, QTableWidgetItem(str(cant)))
            self.grilla.setItem(row, 3, QTableWidgetItem(f"{pu:,.0f}".replace(",", ".")))
            self.grilla.setItem(row, 4, QTableWidgetItem(f"{sub_i:,.0f}".replace(",", ".")))
            self.grilla.setItem(row, 5, QTableWidgetItem(f"{iva_i:,.0f}".replace(",", ".")))
            self._detalle_ids.append(int(idventadet))

        self.idx_actual = idx
        self.set_campos_enabled(False)
        self.btn_guardar.setEnabled(False)
        self.btn_anular.setEnabled(True)
        self.btn_nuevo.setEnabled(True)
        self.set_modo_edicion_minima(False)
        self.actualizar_total_pie()
        self._pintar_estado(v)
        self._update_buttons_state()
        self.grilla.blockSignals(False)

    def ir_primero(self):
        if self.ventas: self.mostrar_venta(0)

    def ir_anterior(self):
        if self.ventas and self.idx_actual > 0:
            self.mostrar_venta(self.idx_actual - 1)

    def ir_siguiente(self):
        if self.ventas and self.idx_actual < len(self.ventas) - 1:
            self.mostrar_venta(self.idx_actual + 1)

    def ir_ultimo(self):
        if self.ventas: self.mostrar_venta(len(self.ventas) - 1)

    def buscar_y_agregar_item(self):
        from models.item import Item, ItemTipo
        texto = (self.busca_item.text() or "").strip()
        if not texto:
            return
        s = self.session
        self._safe_rb()
        want = (self.cbo_tipo.currentText() or "").strip().lower()
        tipo_ci = func.lower(func.trim(ItemTipo.nombre))
        if want == "producto":
            tipo_pred = tipo_ci.in_(["producto", "ambos"])
        else:
            tipo_pred = tipo_ci.in_(["paquete", "ambos"])
        rows = s.execute(
            select(Item).join(ItemTipo, ItemTipo.iditemtipo == Item.iditemtipo)
            .where(tipo_pred, Item.nombre.ilike(f"%{texto}%"))
            .limit(50)
        ).scalars().all()
        resultados = []
        for r in rows:
            pv = getattr(r, "precio_venta", None)
            if pv is None:
                pv = getattr(r, "precio", 0)
            t = want
            tipo_attr = getattr(r, "tipo", None)
            if isinstance(tipo_attr, str):
                t = (tipo_attr or "").strip().lower() or t
            elif tipo_attr is not None:
                tnom = (getattr(tipo_attr, "nombre", "") or "").strip().lower()
                if tnom in ("producto", "paquete"):
                    t = tnom
            resultados.append((t, r.iditem, r.nombre, Decimal(pv or 0)))
        if not resultados and want == "paquete":
            try:
                from models.paquete import Paquete
                packs = s.execute(
                    select(Paquete).where(Paquete.nombre.ilike(f"%{texto}%")).limit(50)
                ).scalars().all()
                for p in packs:
                    pv = getattr(p, "precio_venta", 0) or 0
                    resultados.append(("paquete", p.idpaquete, p.nombre, Decimal(pv)))
            except Exception:
                pass
        if not resultados:
            QMessageBox.information(self, "Sin resultados", "No se encontró ningún ítem.")
            return
        if len(resultados) == 1:
            self.agregar_item_a_grilla(resultados[0])
        else:
            dlg = ItemSelectDialog(resultados, self)
            if dlg.exec_() and dlg.selected is not None:
                self.agregar_item_a_grilla(resultados[dlg.selected])
        self.busca_item.clear()

    def guardar_venta(self):
        if not self.modo_nuevo:
            QMessageBox.warning(self, "Acción inválida", "Debe presionar 'Nuevo' para registrar una nueva venta.")
            return
        if self.grilla.rowCount() == 0:
            QMessageBox.warning(self, "Sin detalle", "Debe agregar al menos un ítem.")
            return
        if self.cbo_paciente.currentIndex() < 0 or self.cbo_paciente.currentData() is None:
            QMessageBox.warning(self, "Paciente", "Debe seleccionar un paciente.")
            self.cbo_paciente.setFocus()
            return
        if self.cbo_clinica.currentIndex() < 0 or self.cbo_clinica.currentData() is None:
            QMessageBox.warning(self, "Clínica", "Debe seleccionar una clínica.")
            self.cbo_clinica.setFocus()
            return

        nro = (self.txt_nro_factura.text() or "").strip()
        if self._mask_vacia(nro):
            nro = None
        else:
            if not self.txt_nro_factura.hasAcceptableInput():
                QMessageBox.warning(self, "N° Factura", "Formato inválido. Usá 001-001-0000001.")
                return

        ctrl = VentasController(self.session, usuario_id=self.usuario_id)
        datos = {
            "fecha": self.fecha.date().toPyDate(), "nro_factura": nro,
            "idpaciente": self.cbo_paciente.currentData(), "idprofesional": self.cbo_profesional.currentData(),
            "idclinica": self.cbo_clinica.currentData(), "observaciones": self.observaciones.toPlainText(),
            "items": self._collect_items()
        }
        try:
            # 1) Crear la venta (tu controller suele commitear aquí)
            idventa = ctrl.crear_venta(datos)

            # 2) Generar consumo (stock/procedimiento)
            consumo_ok = True
            try:
                with self._txn_ctx():
                    confirmar_venta_generar_consumo(self.session, idventa)
            except Exception as ex:
                consumo_ok = False
                self._safe_rb()
                QMessageBox.warning(self, "Atención",
                    f"La venta N° {idventa} se guardó, pero no se pudo generar el consumo.\n\n{ex}")

            if consumo_ok:
                QMessageBox.information(self, "Venta", f"Venta N° {idventa} guardada correctamente.")
            else:
                QMessageBox.information(self, "Venta", f"Venta N° {idventa} guardada (consumo pendiente).")


            # --- (opcional) Impresión como ya tenías ---
            resp = QMessageBox.question(
                self, "Imprimir", "¿Desea imprimir la factura ahora?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if resp == QMessageBox.Yes:
                venta = self._cargar_venta_completa_para_print(idventa)
                if venta:
                    try:
                        path = self._generar_txt_factura(venta)
                        from printing.factura_txt import print_file_by_name
                        print_file_by_name(path, "ELX350")
                    except Exception as ex:
                        QMessageBox.critical(self, "Error de Impresión", f"No se pudo enviar a la impresora:\n\n{ex}")

            self.modo_nuevo = False
            self.cargar_ventas()
            self.limpiar_formulario(editable=False)
            self._update_buttons_state()

        except Exception as e:
            self._safe_rb()
            QMessageBox.critical(self, "Error", str(e))

    def anular_venta_actual(self):
        if not self.idventa_actual:
            QMessageBox.warning(self, "Atención", "No hay venta cargada para anular.")
            return
        if self._venta_tiene_cobros_activos(self.idventa_actual):
            QMessageBox.warning(
                self, "No permitido",
                "La venta tiene cobros asociados.\nPrimero anulá los cobros y luego intentá anular la venta."
            )
            return
        if QMessageBox.question(
            self, "Confirmar anulación", "¿Está seguro que desea anular esta venta?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) == QMessageBox.No:
            return

        ctrl = VentasController(self.session, usuario_id=self.usuario_id)
        try:
            # 1) Anular estado
            ctrl.anular_venta(self.idventa_actual)

            # 2) Revertir consumos con begin/nullcontext
            try:
                with self._txn_ctx():
                    anular_venta_revertir_consumo(self.session, self.idventa_actual)
            except Exception as ex:
                self._safe_rb()
                QMessageBox.warning(self, "Atención",
                    "La venta se marcó como ANULADA, pero no se pudo revertir el consumo de stock/procedimiento.\n\n" + str(ex))

            QMessageBox.information(self, "Éxito", "Venta anulada correctamente.")
            self.cargar_ventas()
            self.limpiar_formulario(editable=False)
            self._update_buttons_state()

        except Exception as e:
            self._safe_rb()
            QMessageBox.critical(self, "Error", str(e)) 

    def setup_focus(self):
        for w in [self.txt_nro_factura, self.cbo_paciente, self.cbo_profesional,
                self.cbo_clinica, self.observaciones, self.busca_item]:
            w.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if obj == self.txt_nro_factura: self.cbo_paciente.setFocus(); return True
            elif obj == self.cbo_paciente: self.cbo_profesional.setFocus(); return True
            elif obj == self.cbo_profesional: self.cbo_clinica.setFocus(); return True
            elif obj == self.cbo_clinica: self.observaciones.setFocus(); return True
            elif obj == self.observaciones: self.busca_item.setFocus(); return True
            elif obj == self.busca_item: self.buscar_y_agregar_item(); return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if self.grilla.hasFocus() and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            r, c = self.grilla.currentRow(), self.grilla.currentColumn()
            if c == 2:
                self.grilla.setCurrentCell(r, 3)
                self.grilla.editItem(self.grilla.item(r, 3))
                return
            elif c == 3:
                self.calcular_total_row(r)
                self.actualizar_total_pie()
                self.busca_item.setFocus()
                return
        super().keyPressEvent(event)

    def closeEvent(self, ev):
        try: self.session.close()
        finally: super().closeEvent(ev)

    def nuevo(self):
        self.modo_nuevo = True
        self.limpiar_formulario(editable=True)
        idx = -1
        for i in range(self.cbo_profesional.count()):
            if "daisy" in (self.cbo_profesional.itemText(i) or "").lower():
                idx = i; break
        if idx < 0:
            idx = self.cbo_profesional.findData(1)
        if idx >= 0:
            self.cbo_profesional.setCurrentIndex(idx)
        self.txt_nro_factura.setFocus()
        self._update_buttons_state()

    def calcular_total_row(self, row: int):
        try:
            txt_cant = (self.grilla.item(row, 2).text() or "").strip()
            txt_prec = (self.grilla.item(row, 3).text() or "").strip()
            cantidad = int((txt_cant.replace(".", "").replace(",", "")) or "0")
            precio   = int((txt_prec.replace(".", "").replace(",", "")) or "0")
            total = round(precio * cantidad)
            iva10 = round(total / 11)
            self.grilla.setItem(row, 2, QTableWidgetItem(str(cantidad)))
            self.grilla.setItem(row, 3, QTableWidgetItem(f"{precio:,.0f}".replace(",", ".")))
            self.grilla.setItem(row, 4, QTableWidgetItem(f"{total:,.0f}".replace(",", ".")))
            self.grilla.setItem(row, 5, QTableWidgetItem(f"{iva10:,.0f}".replace(",", ".")))
        except Exception:
            self.grilla.setItem(row, 4, QTableWidgetItem("0"))
            self.grilla.setItem(row, 5, QTableWidgetItem("0"))

    def actualizar_total_pie(self):
        total, total_iva = 0, 0
        for r in range(self.grilla.rowCount()):
            try:
                v_total = (self.grilla.item(r, 4).text() if self.grilla.item(r, 4) else "0")
                v_iva   = (self.grilla.item(r, 5).text() if self.grilla.item(r, 5) else "0")
                total += float(v_total.replace(".", "").replace(",", "."))
                total_iva += float(v_iva.replace(".", "").replace(",", "."))
            except Exception:
                pass
        self.lbl_total.setText(f"Total: {total:,.0f}      IVA10: {int(round(total_iva)):,.0f}".replace(",", "."))

    def editar_actual(self):
        if self.modo_nuevo:
            QMessageBox.information(self, "Editar", "Estás creando una venta nueva. Guardala o cancelá antes de editar otra.")
            return
        if not self.idventa_actual:
            QMessageBox.information(self, "Editar", "Primero seleccioná una venta (o usá Buscar venta).")
            return
        v = next((x for x in self.ventas if x.idventa == self.idventa_actual), None)
        if v and (getattr(v, "estadoventa", "").lower() == "anulada" or getattr(v, "anulada", False)):
            QMessageBox.warning(self, "Editar", "La venta está anulada; no se puede editar.")
            return
        self.set_modo_edicion_minima(True)
        self.txt_nro_factura.setFocus()

    def _on_guardar_click(self):
        if self.modo_edicion:
            self.guardar_cambios_minimos()
        else:
            self.guardar_venta()

    def guardar_cambios_minimos(self):
        if not self.idventa_actual:
            QMessageBox.warning(self, "Guardar", "No hay venta cargada.")
            return
        nro = (self.txt_nro_factura.text() or "").strip()
        if self._mask_vacia(nro):
            nro = None
        else:
            if not self.txt_nro_factura.hasAcceptableInput():
                QMessageBox.warning(self, "N° Factura", "Formato inválido. Usá 001-001-0000001.")
                return
        try:
            v = self.session.get(Venta, int(self.idventa_actual))
            if not v:
                QMessageBox.warning(self, "Guardar", "Venta no encontrada.")
                return
            v.nro_factura = nro
            v.observaciones = self.observaciones.toPlainText()
            self.session.commit()
            QMessageBox.information(self, "Venta", "Cambios guardados correctamente.")
            cur_id = v.idventa
            self.cargar_ventas()
            self.cargar_venta_por_id(cur_id)
            self.set_modo_edicion_minima(False)
        except Exception as e:
            self._safe_rb()
            QMessageBox.critical(self, "Error", f"Ocurrió un error al guardar: {e}")

    def _collect_items(self):
        items = []
        for r in range(self.grilla.rowCount()):
            iditem_txt = (self.grilla.item(r, 0).text() or "0")
            try: iditem = int(iditem_txt)
            except Exception: continue
            tipo = self.grilla.item(r, 0).data(Qt.UserRole) or "producto"
            txt_cant = (self.grilla.item(r, 2).text() or "").strip()
            txt_prec = (self.grilla.item(r, 3).text() or "").strip()
            cantidad = int((txt_cant.replace(".", "").replace(",", "")) or "0")
            precio   = int((txt_prec.replace(".", "").replace(",", "")) or "0")
            if iditem and cantidad > 0:
                if tipo == "paquete":
                    items.append({
                        "idpaquete": iditem, "cantidad": Decimal(cantidad),
                        "precio": Decimal(precio),
                    })
                else:
                    items.append({
                        "iditem": iditem, "cantidad": Decimal(cantidad),
                        "precio": Decimal(precio), "descuento": Decimal("0"),
                    })
        return items

    def set_modo_edicion_minima(self, on: bool):
        self.modo_edicion = on
        if on:
            self.set_campos_enabled(False)
            self.grilla.setEnabled(True)
            self.grilla.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.grilla.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.grilla.setSelectionMode(QAbstractItemView.SingleSelection)
            self.txt_nro_factura.setEnabled(True)
            self.observaciones.setEnabled(True)
            self.btn_guardar.setEnabled(True)
        else:
            self.set_campos_enabled(self.modo_nuevo)
            self.grilla.setEditTriggers(
                QAbstractItemView.AllEditTriggers if self.modo_nuevo else QAbstractItemView.NoEditTriggers
            )
            self.btn_guardar.setEnabled(self.modo_nuevo)
        self._update_buttons_state()

    def abrir_buscador_venta(self):
        dlg = BuscarVentaDialog(self.session, self)
        if dlg.exec_() == QDialog.Accepted and dlg.selected_idventa:
            self.cargar_venta_por_id(dlg.selected_idventa)

    def _toggle_nav(self, on: bool):
        for b in (self.btn_buscar_venta, self.btn_primero, self.btn_anterior, self.btn_siguiente, self.btn_ultimo):
            b.setEnabled(on)

    def cargar_venta_por_id(self, idventa: int):
        for i, v in enumerate(self.ventas or []):
            if int(v.idventa) == int(idventa):
                self.mostrar_venta(i)
                return
        self.cargar_ventas()
        for i, v in enumerate(self.ventas or []):
            if int(v.idventa) == int(idventa):
                self.mostrar_venta(i)
                return
        v = self.session.execute(select(Venta).where(Venta.idventa == int(idventa))).scalar_one_or_none()
        if v:
            (self.ventas or []).append(v)
            self.mostrar_venta(len(self.ventas) - 1)
        else:
            QMessageBox.warning(self, "Venta", "No se encontró la venta seleccionada.")

    # =========================
    #   IMPRESIÓN – HELPERS
    # =========================
    def _cargar_venta_completa_para_print(self, idventa: int):
        """Trae la venta con paciente y detalles+item para poder renderizar."""
        try:
            v = (
                self.session.query(Venta)
                .options(
                    joinedload(Venta.paciente),
                    joinedload(Venta.detalles).joinedload(VentaDetalle.item),
                )
                .filter(Venta.idventa == int(idventa))
                .one_or_none()
            )
            return v
        except Exception as e:
            try: self._safe_rb()
            except Exception: pass
            print("Error load venta:", e)
            return None

    def _generar_txt_factura(self, venta):
        """Genera el TXT en una carpeta local. Devuelve la ruta."""
        carpeta_salida = r"C:\consultorio\facturas_txt"
        os.makedirs(carpeta_salida, exist_ok=True)
        suf = venta.nro_factura or f"ID{venta.idventa}"
        suf = suf.replace("/", "-") # Reemplazar caracteres invalidos para nombres de archivo
        tstamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"FAC_{suf}_{tstamp}.txt"
        path = os.path.join(carpeta_salida, nombre_archivo)
        txt = render_factura_txt(venta, DEFAULT_LAYOUT)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(txt)
        return path

    def _on_imprimir_clicked(self):
        """Imprime la venta actualmente mostrada (modo lectura)."""
        if not self.idventa_actual:
            QMessageBox.information(self, "Imprimir", "No hay una venta cargada para imprimir.")
            return
        if self._mask_vacia(self.txt_nro_factura.text() or ""):
            if QMessageBox.question(
                self, "Sin N° de factura",
                "Esta venta no tiene N° de factura. ¿Desea imprimir de todos modos?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            ) == QMessageBox.No:
                return
        venta = self._cargar_venta_completa_para_print(self.idventa_actual)
        if not venta:
            QMessageBox.warning(self, "Imprimir", "No se pudo cargar la venta completa.")
            return
        try:
            path = self._generar_txt_factura(venta)
            
            # --- Envío a Impresora (MÉTODO DEFINITIVO POR NOMBRE) ---
            from printing.factura_txt import print_file_by_name
            print_file_by_name(path, "ELX350")

            
        except Exception as ex:
            QMessageBox.critical(self, "Error de Impresión", f"No se pudo enviar a la impresora:\n\n{ex}")