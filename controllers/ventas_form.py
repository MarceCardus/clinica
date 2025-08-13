# controllers/abm_ventas_form.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QDateEdit, QTextEdit, QTableWidget, QTableWidgetItem, QSplitter, QGroupBox, QFormLayout,
    QMessageBox, QListWidget, QDialog,QSizePolicy,QHeaderView  
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QDate, QEvent
from decimal import Decimal
from sqlalchemy import select, or_
from utils.db import SessionLocal
from controllers.ventas_controller import VentasController
from models.paciente import Paciente
from models.profesional import Profesional
from models.clinica import Clinica
from models.producto import Producto
from models.paquete import Paquete
from models.venta_detalle import VentaDetalle
from models.venta import Venta


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

        self.ventas = []
        self.modo_nuevo = False
        self.idventa_actual = None
        self.idx_actual = -1

        self.setWindowTitle("Ventas")
        self.resize(980, 540)
        self._setup_ui()

        # Conectar botones
        self.btn_eliminar.clicked.connect(self.eliminar_fila_grilla)
        self.btn_guardar.clicked.connect(self.guardar_venta)
        self.btn_anular.clicked.connect(self.anular_venta_actual)
        self.btn_anular.setEnabled(False)
        self.btn_cancelar.clicked.connect(self.cancelar)
        self.btn_primero.clicked.connect(self.ir_primero)
        self.btn_anterior.clicked.connect(self.ir_anterior)
        self.btn_siguiente.clicked.connect(self.ir_siguiente)
        self.btn_ultimo.clicked.connect(self.ir_ultimo)
        self.btn_nuevo.clicked.connect(self.nuevo)
        self.btn_buscar.clicked.connect(self.buscar_y_agregar_item)

        # Cargar combos y data
        self.cargar_maestros()
        self.setup_focus()
        self.cbo_paciente.setFocus()
        self.cargar_ventas()

    # ---------- UI ----------
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
    # NUEVO: márgenes chicos y alineado arriba
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(6)
        main_layout.setAlignment(Qt.AlignTop)

        # Título
        title_layout = QHBoxLayout()
        icono = QLabel()
        icono.setPixmap(QIcon("imagenes/venta.png").pixmap(32,32))
        title_layout.addWidget(icono)
        title_label = QLabel("Ventas")
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold; margin-left:8px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.setContentsMargins(0, 0, 0, 6)
        main_layout.addLayout(title_layout, 0)       

        splitter = QSplitter(Qt.Horizontal)

        # Panel izquierdo - Cabecera
        left_box = QGroupBox("Datos de la Venta")
        left_box.setMinimumWidth(320)            # NUEVO: ancho similar a Compras
        left_box.setMaximumWidth(360)            # NUEVO: tope
        left_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        left_layout = QFormLayout()
        self.idventa = QLineEdit(); self.idventa.setReadOnly(True)
        left_layout.addRow(QLabel("ID Venta:"), self.idventa)

        self.fecha = QDateEdit(QDate.currentDate()); self.fecha.setCalendarPopup(True)
        left_layout.addRow(QLabel("Fecha:"), self.fecha)

        self.cbo_paciente = QComboBox()
        left_layout.addRow(QLabel("Paciente:"), self.cbo_paciente)

        self.cbo_profesional = QComboBox()
        left_layout.addRow(QLabel("Profesional:"), self.cbo_profesional)

        self.cbo_clinica = QComboBox()
        left_layout.addRow(QLabel("Clínica:"), self.cbo_clinica)

        self.observaciones = QTextEdit()
        self.observaciones.setFixedHeight(160)
        left_layout.addRow(QLabel("Observaciones:"), self.observaciones)

        self.lbl_estado = QLabel("Activo")
        self.lbl_estado.setStyleSheet("font-weight:bold; color: green; margin-bottom:6px;")
        left_layout.addRow(QLabel("Estado:"), self.lbl_estado)

        left_box.setLayout(left_layout)
        splitter.addWidget(left_box)

        # Panel derecho - Detalle
        right_widget = QWidget(); right_layout = QVBoxLayout(right_widget)
        right_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Buscador de producto/paquete
        search_layout = QHBoxLayout()
        self.cbo_tipo = QComboBox(); self.cbo_tipo.addItems(["producto", "paquete"])
        self.busca_item = QLineEdit(); self.busca_item.setPlaceholderText("Buscar producto o paquete")
        self.btn_buscar = QPushButton(QIcon("imagenes/buscar.png"), "")
        self.btn_buscar.setStyleSheet("""
            QPushButton { background-color: #e9ecef; border: 1px solid #ced4da; border-radius: 5px; }
            QPushButton:hover { background-color: #b6d4fe; }
        """)
        search_layout.addWidget(self.cbo_tipo)
        search_layout.addWidget(self.busca_item, 1)
        search_layout.addWidget(self.btn_buscar)
        search_layout.addStretch()
        right_layout.addLayout(search_layout)
        splitter.setHandleWidth(6)
        splitter.setStretchFactor(0, 0)          # NUEVO: cabecera no se estira
        splitter.setStretchFactor(1, 1)          # NUEVO: detalle sí se estira

        # Grilla de detalle
        self.grilla = QTableWidget(0, 6)
        self.grilla.setHorizontalHeaderLabels(["Código", "Nombre", "Tipo", "Cantidad", "Precio", "Total"])
        self.grilla.setContentsMargins(0,0,0,0)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        right_layout.addWidget(self.grilla)
        self.grilla.horizontalHeader().setStretchLastSection(True)
        self.grilla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Código
        self.grilla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)           # Nombre
        self.grilla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Tipo
        self.grilla.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Cantidad
        self.grilla.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Precio
        self.grilla.verticalHeader().setVisible(False)
        self.grilla.setAlternatingRowColors(True)
        self.grilla.setSelectionBehavior(QTableWidget.SelectRows)
        self.grilla.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        # Botones detalle
        btns_detalle = QHBoxLayout()
        self.btn_agregar = QPushButton(QIcon("imagenes/agregar.png"), "Agregar")
        self.btn_agregar.setStyleSheet("""
            QPushButton { background-color: #007bff; color: white; font-weight: bold; border-radius: 6px; padding: 4px 18px; }
            QPushButton:hover { background-color: #0056b3; }
        """)
        self.btn_agregar.clicked.connect(self._agregar_fila_manual)
        self.btn_eliminar = QPushButton(QIcon("imagenes/eliminar.png"), "Eliminar")
        self.btn_eliminar.setStyleSheet("""
            QPushButton { background-color: #ffc9c9; color: #dc3545; font-weight: bold; border-radius: 6px; padding: 4px 18px; }
            QPushButton:hover { background-color: #fa5252; color: white; }
        """)
        btns_detalle.addWidget(self.btn_agregar)
        btns_detalle.addWidget(self.btn_eliminar)
        btns_detalle.addStretch()
        right_layout.addLayout(btns_detalle)

        # Pie - totales y navegación
        pie_layout = QHBoxLayout()
        self.lbl_total = QLabel("Total: 0")
        pie_layout.addWidget(self.lbl_total)
        pie_layout.addStretch()

        self.btn_primero = QPushButton(QIcon("imagenes/primero.png"), "")
        self.btn_anterior = QPushButton(QIcon("imagenes/anterior.png"), "")
        self.btn_siguiente = QPushButton(QIcon("imagenes/siguiente.png"), "")
        self.btn_ultimo = QPushButton(QIcon("imagenes/ultimo.png"), "")
        for btn in [self.btn_primero, self.btn_anterior, self.btn_siguiente, self.btn_ultimo]:
            btn.setStyleSheet("""
                QPushButton { background-color: #007bff; color: #007bff; border-radius: 6px; padding: 4px 10px; }
                QPushButton:hover { background-color: #b6d4fe; }
            """)
            pie_layout.addWidget(btn)

        self.btn_nuevo = QPushButton(QIcon("imagenes/nuevo.png"), "Nuevo")
        self.btn_guardar = QPushButton(QIcon("imagenes/guardar.png"), "Guardar")
        self.btn_anular = QPushButton(QIcon("imagenes/eliminar.png"), "Anular")
        self.btn_cancelar = QPushButton(QIcon("imagenes/cancelar.png"), "Cancelar")

        botones = [
            (self.btn_nuevo, "#007bff", "white"),
            (self.btn_guardar, "#28a745", "white"),
            (self.btn_anular, "#dc3545", "white"),
            (self.btn_cancelar, "#ffc9c9", "#dc3545"),
        ]
        for btn, fondo, color in botones:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {fondo};
                    color: {color};
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 4px 18px;
                }}
                QPushButton:hover {{ background-color: #b6d4fe; }}
            """)
            pie_layout.addWidget(btn)

        right_layout.addLayout(pie_layout)
        splitter.addWidget(right_widget)
        splitter.setSizes([340, 800])
        self.setMinimumSize(980, 540)
        self.resize(980, 540)
        main_layout.addWidget(splitter,1)
        self.setLayout(main_layout)

    # ---------- Data maestros ----------
    def cargar_maestros(self):
        s = self.session
        self.cbo_paciente.clear()
        for p in s.execute(select(Paciente).order_by(Paciente.apellido)).scalars():
            self.cbo_paciente.addItem(f"{p.apellido}, {p.nombre}", p.idpaciente)
        self.cbo_profesional.clear()
        for pr in s.execute(select(Profesional).order_by(Profesional.apellido)).scalars():
            self.cbo_profesional.addItem(f"{pr.apellido}, {pr.nombre}", pr.idprofesional)
        self.cbo_clinica.clear()
        for c in s.execute(select(Clinica).order_by(Clinica.nombre)).scalars():
            self.cbo_clinica.addItem(c.nombre, c.idclinica)

    # ---------- Estado/limpieza ----------
    def set_campos_enabled(self, estado: bool):
        self.fecha.setEnabled(estado)
        self.cbo_paciente.setEnabled(estado)
        self.cbo_profesional.setEnabled(estado)
        self.cbo_clinica.setEnabled(estado)
        self.observaciones.setEnabled(estado)
        self.grilla.setEnabled(estado)
        self.cbo_tipo.setEnabled(estado)
        self.busca_item.setEnabled(estado)
        self.btn_buscar.setEnabled(estado)
        self.btn_agregar.setEnabled(estado)
        self.btn_eliminar.setEnabled(estado)

    def limpiar_formulario(self, editable=False):
        self.idventa.clear()
        self.fecha.setDate(QDate.currentDate())
        if self.cbo_paciente.count(): self.cbo_paciente.setCurrentIndex(0)
        if self.cbo_profesional.count(): self.cbo_profesional.setCurrentIndex(0)
        if self.cbo_clinica.count(): self.cbo_clinica.setCurrentIndex(0)
        self.observaciones.clear()
        self.grilla.setRowCount(0)
        self.lbl_total.setText("Total: 0")
        self.idventa_actual = None
        self.idx_actual = -1
        self.lbl_estado.setText("Activo"); self.lbl_estado.setStyleSheet("font-weight:bold; color: green;")
        self.set_campos_enabled(editable)
        self.btn_guardar.setEnabled(editable)
        self.btn_cancelar.setEnabled(True)
        self.btn_anular.setEnabled(False)
        self.btn_nuevo.setEnabled(not editable)

    # ---------- Carga / navegación ----------
    def cargar_ventas(self):
        ctrl = VentasController(self.session, usuario_id=self.usuario_id)
        self.ventas = ctrl.listar_ventas(solo_no_anuladas=False)
        self.idx_actual = -1
        self.limpiar_formulario(editable=False)

    def mostrar_venta(self, idx):
        if not self.ventas or idx < 0 or idx >= len(self.ventas): return
        v = self.ventas[idx]
        self.idventa_actual = v.idventa
        self.idventa.setText(str(v.idventa))
        self.fecha.setDate(QDate(v.fecha.year, v.fecha.month, v.fecha.day))
        if v.idpaciente: self.cbo_paciente.setCurrentIndex(self.cbo_paciente.findData(v.idpaciente))
        if v.idprofesional: self.cbo_profesional.setCurrentIndex(self.cbo_profesional.findData(v.idprofesional))
        if v.idclinica: self.cbo_clinica.setCurrentIndex(self.cbo_clinica.findData(v.idclinica))
        self.observaciones.setPlainText(v.observaciones or "")

        # Detalle
        self.grilla.setRowCount(0)
        dets = self.session.execute(select(VentaDetalle).where(VentaDetalle.idventa == v.idventa)).scalars().all()
        for det in dets:
            # Obtener nombre y tipo
            nombre = ""
            tipo = "producto"
            if det.idpaquete:
                tipo = "paquete(comp)"
            prod = self.session.execute(select(Producto).where(Producto.idproducto == det.idproducto)).scalar_one_or_none()
            if prod: nombre = prod.nombre

            row = self.grilla.rowCount()
            self.grilla.insertRow(row)
            self.grilla.setItem(row, 0, QTableWidgetItem(str(det.idproducto)))
            self.grilla.setItem(row, 1, QTableWidgetItem(nombre))
            self.grilla.setItem(row, 2, QTableWidgetItem(tipo))
            self.grilla.setItem(row, 3, QTableWidgetItem(f"{Decimal(det.cantidad):,.2f}".replace(",", ".")))
            self.grilla.setItem(row, 4, QTableWidgetItem(f"{Decimal(det.preciounitario):,.0f}".replace(",", ".")))
            subtotal = Decimal(det.cantidad) * Decimal(det.preciounitario) - Decimal(det.descuento or 0)
            self.grilla.setItem(row, 5, QTableWidgetItem(f"{subtotal:,.0f}".replace(",", ".")))

        self.idx_actual = idx
        self.set_campos_enabled(False)
        self.btn_guardar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.btn_anular.setEnabled(True)  # si luego agregás flag anulada, podés condicionar
        self.btn_nuevo.setEnabled(True)
        self.lbl_total.setText(f"Total: {Decimal(v.montototal or 0):,.0f}".replace(",", "."))

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

    # ---------- Búsqueda e ítems ----------
    def _agregar_fila_manual(self):
        # agrega una fila vacía por si querés completar a mano
        row = self.grilla.rowCount()
        self.grilla.insertRow(row)
        for c in range(6):
            self.grilla.setItem(row, c, QTableWidgetItem("" if c not in (3,4,5) else "0"))
        self.grilla.setCurrentCell(row, 0)
        self.grilla.editItem(self.grilla.item(row, 0))

    def buscar_y_agregar_item(self):
        texto = (self.busca_item.text() or "").strip()
        if not texto: return

        s = self.session
        resultados = []
        if self.cbo_tipo.currentText() == "producto":
            rows = s.execute(
                select(Producto).where(or_(Producto.nombre.ilike(f"%{texto}%"),
                                           Producto.descripcion.ilike(f"%{texto}%"))).limit(50)
            ).scalars().all()
            for r in rows:
                pv = getattr(r, "precio_venta", 0) or 0
                resultados.append(("producto", r.idproducto, r.nombre, Decimal(pv)))
        else:
            rows = s.execute(select(Paquete).where(Paquete.nombre.ilike(f"%{texto}%")).limit(50)).scalars().all()
            for r in rows:
                pv = getattr(r, "precio_venta", 0) or 0
                resultados.append(("paquete", r.idpaquete, r.nombre, Decimal(pv)))

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

    def agregar_item_a_grilla(self, it):
        tipo, _id, nombre, pv = it
        # Evitar duplicados: si mismo código y tipo "producto", suma cantidad
        for row in range(self.grilla.rowCount()):
            if self.grilla.item(row, 0) and self.grilla.item(row, 2):
                if self.grilla.item(row, 0).text() == str(_id) and self.grilla.item(row, 2).text().startswith("producto"):
                    # sumar cantidad
                    cant_item = self.grilla.item(row, 3)
                    cant_actual = float(cant_item.text().replace(",", ".") or 0)
                    cant_item.setText(f"{cant_actual + 1:.2f}")
                    self.calcular_total_row(row)
                    self.actualizar_total_pie()
                    self.grilla.setCurrentCell(row, 3)
                    return

        row = self.grilla.rowCount()
        self.grilla.insertRow(row)
        self.grilla.setItem(row, 0, QTableWidgetItem(str(_id)))
        self.grilla.setItem(row, 1, QTableWidgetItem(nombre))
        self.grilla.setItem(row, 2, QTableWidgetItem(tipo))
        self.grilla.setItem(row, 3, QTableWidgetItem("1.00"))
        self.grilla.setItem(row, 4, QTableWidgetItem(f"{pv:,.0f}".replace(",", ".")))
        self.grilla.setItem(row, 5, QTableWidgetItem(f"{pv:,.0f}".replace(",", ".")))

        self.grilla.setCurrentCell(row, 3)
        self.grilla.editItem(self.grilla.item(row, 3))
        self.grilla.setFocus()
        self.grilla.item(row, 3).setSelected(True)
        self.actualizar_total_pie()

    def eliminar_fila_grilla(self):
        row = self.grilla.currentRow()
        if row >= 0:
            if QMessageBox.question(self, "Eliminar ítem", "¿Eliminar la fila seleccionada?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
                self.grilla.removeRow(row)
                self.actualizar_total_pie()
        else:
            QMessageBox.information(self, "Atención", "Debe seleccionar una fila.")

    def keyPressEvent(self, event):
        if self.grilla.hasFocus():
            r = self.grilla.currentRow(); c = self.grilla.currentColumn()
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if c == 3:  # cantidad
                    self.grilla.setCurrentCell(r, 4)
                    self.grilla.editItem(self.grilla.item(r, 4))
                    self.grilla.item(r, 4).setSelected(True)
                    return
                elif c == 4:
                    self.calcular_total_row(r)
                    self.actualizar_total_pie()
                    self.busca_item.setFocus()
                    return
        super().keyPressEvent(event)

    def calcular_total_row(self, row):
        try:
            cantidad = float(self.grilla.item(row, 3).text().replace(".", "").replace(",", "."))
            precio = float(self.grilla.item(row, 4).text().replace(".", "").replace(",", "."))
            total = round(precio * cantidad)
            self.grilla.setItem(row, 5, QTableWidgetItem(f"{total:,.0f}".replace(",", ".")))
            self.grilla.setItem(row, 4, QTableWidgetItem(f"{precio:,.0f}".replace(",", ".")))
        except Exception:
            self.grilla.setItem(row, 5, QTableWidgetItem("0"))

    def actualizar_total_pie(self):
        total = 0
        for r in range(self.grilla.rowCount()):
            try:
                total += float(self.grilla.item(r, 5).text().replace(".", "").replace(",", "."))
            except Exception:
                pass
        self.lbl_total.setText(f"Total: {total:,.0f}".replace(",", "."))

    # ---------- Nuevo / Guardar / Cancelar / Anular ----------
    def nuevo(self):
        self.modo_nuevo = True
        self.limpiar_formulario(editable=True)

    def cancelar(self):
        self.modo_nuevo = False
        self.limpiar_formulario(editable=False)

    def _collect_items(self):
        items = []
        for r in range(self.grilla.rowCount()):
            tipo = self.grilla.item(r, 2).text()
            _id = int(self.grilla.item(r, 0).text())
            cant = Decimal(self.grilla.item(r, 3).text().replace(",", "."))
            precio = Decimal(self.grilla.item(r, 4).text().replace(".", "").replace(",", "."))
            if tipo == "producto":
                items.append({"tipo": "producto", "idproducto": _id, "cantidad": cant, "precio": precio, "descuento": Decimal("0")})
            else:
                items.append({"tipo": "paquete", "idpaquete": _id, "cantidad": cant, "precio": precio})
        return items

    def guardar_venta(self):
        if not self.modo_nuevo:
            QMessageBox.warning(self, "Acción inválida", "Debe presionar 'Nuevo' para registrar una nueva venta.")
            return
        if self.grilla.rowCount() == 0:
            QMessageBox.warning(self, "Sin detalle", "Debe agregar al menos un ítem.")
            return

        ctrl = VentasController(self.session, usuario_id=self.usuario_id)
        datos = {
            "fecha": self.fecha.date().toPyDate(),
            "idpaciente": self.cbo_paciente.currentData(),
            "idprofesional": self.cbo_profesional.currentData(),
            "idclinica": self.cbo_clinica.currentData(),
            "observaciones": self.observaciones.toPlainText(),
            "items": self._collect_items()
        }
        try:
            idventa = ctrl.crear_venta(datos)
            QMessageBox.information(self, "Venta", f"Venta N° {idventa} guardada correctamente.")
            self.modo_nuevo = False
            self.cargar_ventas()
            self.limpiar_formulario(editable=False)
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", str(e))

    def anular_venta_actual(self):
        if not self.idventa_actual:
            QMessageBox.warning(self, "Atención", "No hay venta cargada para anular.")
            return
        if QMessageBox.question(self, "Confirmar anulación", "¿Está seguro que desea anular esta venta?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.No:
            return
        ctrl = VentasController(self.session, usuario_id=self.usuario_id)
        try:
            ctrl.anular_venta(self.idventa_actual)
            QMessageBox.information(self, "Éxito", "Venta anulada correctamente.")
            self.cargar_ventas()
            self.limpiar_formulario(editable=False)
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", str(e))

    # ---------- Focus / Enter flow ----------
    def setup_focus(self):
        for w in [self.cbo_paciente, self.cbo_profesional, self.cbo_clinica, self.observaciones, self.busca_item]:
            w.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if obj == self.cbo_paciente:
                self.cbo_profesional.setFocus(); return True
            elif obj == self.cbo_profesional:
                self.cbo_clinica.setFocus(); return True
            elif obj == self.cbo_clinica:
                self.observaciones.setFocus(); return True
            elif obj == self.observaciones:
                self.busca_item.setFocus(); return True
            elif obj == self.busca_item:
                self.buscar_y_agregar_item(); return True
        return super().eventFilter(obj, event)

    def closeEvent(self, ev):
        try:
            self.session.close()
        finally:
            super().closeEvent(ev)
