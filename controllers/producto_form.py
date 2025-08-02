from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QPushButton, QHBoxLayout, QMessageBox
)
from PyQt5.QtCore import Qt
from models.producto import Producto
from models.especialidad import Especialidad
from models.tipoproducto import TipoProducto
from utils.db import SessionLocal

class ProductoFormDialog(QDialog):
    def __init__(self, parent=None, producto=None, session=None):
        super().__init__(parent)
        self.prod = producto
        self.session = session or SessionLocal()
        self.own_session = session is None
        self.setWindowTitle("Producto" + (" – Editar" if producto else " – Nuevo"))
        self.init_ui()
        self.setFixedSize(400, 300)
        if self.prod:
            self.load_data()

    def init_ui(self):
        layout = QFormLayout(self)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.nombre = QLineEdit()
        self.descripcion = QLineEdit()
        self.duracion = QSpinBox()
        self.duracion.setRange(0, 10_000)
        self.precio = QDoubleSpinBox()
        self.precio.setRange(0, 999_999_999)
        self.precio.setDecimals(0)
        self.precio.setMinimumWidth(120)

        # Combo de Tipos de Producto
        self.tipo_combo = QComboBox()
        for tp in self.session.query(TipoProducto).order_by(TipoProducto.nombre).all():
            self.tipo_combo.addItem(tp.nombre, tp.idtipoproducto)

        # Combo de Especialidad
        self.especialidad = QComboBox()
        for e in self.session.query(Especialidad).order_by(Especialidad.nombre).all():
            self.especialidad.addItem(e.nombre, e.idespecialidad)

        layout.addRow("Nombre:", self.nombre)
        layout.addRow("Descripción:", self.descripcion)
        layout.addRow("Duración (hs):", self.duracion)
        layout.addRow("Precio:", self.precio)
        layout.addRow("Tipo de producto:", self.tipo_combo)
        layout.addRow("Especialidad:", self.especialidad)

        btns = QHBoxLayout()
        btn_guardar = QPushButton("Guardar")
        btn_cancel = QPushButton("Cancelar")
        btns.addWidget(btn_guardar)
        btns.addWidget(btn_cancel)
        layout.addRow(btns)

        btn_guardar.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        self.setMinimumSize(400, 300)      # Menor alto
        self.setMaximumSize(400, 350)      # Un poco de margen
        self.resize(400, 250)              # Tamaño inicial al abrir
        self.nombre.setFocus()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.focusNextChild()
        else:
            super().keyPressEvent(event)

    def load_data(self):
        self.nombre.setText(self.prod.nombre)
        self.descripcion.setText(self.prod.descripcion or "")
        self.duracion.setValue(self.prod.duracion or 0)
        self.precio.setValue(float(self.prod.precio))
        # Selecciona el tipo en el combo
        idx_tipo = self.tipo_combo.findData(self.prod.idtipoproducto)
        if idx_tipo >= 0:
            self.tipo_combo.setCurrentIndex(idx_tipo)
        # Selecciona la especialidad
        idx_esp = self.especialidad.findData(self.prod.idespecialidad)
        if idx_esp >= 0:
            self.especialidad.setCurrentIndex(idx_esp)

    def accept(self):
        if not self.nombre.text().strip():
            QMessageBox.warning(self, "Atención", "El campo Nombre no puede estar vacío.")
            self.nombre.setFocus()
            return

        if not self.prod:
            self.prod = Producto()
            self.session.add(self.prod)

        self.prod.nombre = self.nombre.text()
        self.prod.descripcion = self.descripcion.text()
        self.prod.duracion = self.duracion.value()
        self.prod.precio = self.precio.value()
        self.prod.idtipoproducto = self.tipo_combo.currentData()
        self.prod.idespecialidad = self.especialidad.currentData()

        self.session.commit()
        if self.own_session:
            self.session.close()
        super().accept()
