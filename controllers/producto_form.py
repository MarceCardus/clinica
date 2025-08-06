from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QPushButton, QHBoxLayout, QMessageBox, QCheckBox
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
        self.setFixedSize(400, 400)  # un poco más alto por los campos extra
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

        # ----- Campos de recordatorio -----
        self.chk_requiere_recordatorio = QCheckBox("¿Requiere recordatorio?")
        self.input_dias_recordatorio = QSpinBox()
        self.input_dias_recordatorio.setRange(1, 3650)
        self.input_dias_recordatorio.setEnabled(False)
        self.input_mensaje_recordatorio = QLineEdit()
        self.input_mensaje_recordatorio.setEnabled(False)

        # Vincular enable/disable
        self.chk_requiere_recordatorio.toggled.connect(
            lambda v: [
                self.input_dias_recordatorio.setEnabled(v),
                self.input_mensaje_recordatorio.setEnabled(v)
            ]
        )

        layout.addRow("Nombre:", self.nombre)
        layout.addRow("Descripción:", self.descripcion)
        layout.addRow("Duración (hs):", self.duracion)
        layout.addRow("Precio:", self.precio)
        layout.addRow("Tipo de producto:", self.tipo_combo)
        layout.addRow("Especialidad:", self.especialidad)
        # --- Aquí los nuevos campos ---
        layout.addRow(self.chk_requiere_recordatorio)
        layout.addRow("Días para recordatorio:", self.input_dias_recordatorio)
        layout.addRow("Mensaje recordatorio:", self.input_mensaje_recordatorio)

        btns = QHBoxLayout()
        btn_guardar = QPushButton("Guardar")
        btn_cancel = QPushButton("Cancelar")
        btns.addWidget(btn_guardar)
        btns.addWidget(btn_cancel)
        layout.addRow(btns)

        btn_guardar.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        self.setMinimumSize(400, 400)
        self.setMaximumSize(400, 450)
        self.resize(400, 400)
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
        # ---------- Carga de recordatorio ----------
        self.chk_requiere_recordatorio.setChecked(bool(self.prod.requiere_recordatorio))
        self.input_dias_recordatorio.setValue(self.prod.dias_recordatorio or 1)
        self.input_mensaje_recordatorio.setText(self.prod.mensaje_recordatorio or "")
        # Habilitar/deshabilitar según estado
        self.input_dias_recordatorio.setEnabled(bool(self.prod.requiere_recordatorio))
        self.input_mensaje_recordatorio.setEnabled(bool(self.prod.requiere_recordatorio))

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

        # -------- Guardar campos de recordatorio --------
        self.prod.requiere_recordatorio = self.chk_requiere_recordatorio.isChecked()
        self.prod.dias_recordatorio = self.input_dias_recordatorio.value() if self.chk_requiere_recordatorio.isChecked() else None
        self.prod.mensaje_recordatorio = self.input_mensaje_recordatorio.text() if self.chk_requiere_recordatorio.isChecked() else None

        self.session.commit()
        if self.own_session:
            self.session.close()
        super().accept()
