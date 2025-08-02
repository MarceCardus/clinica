from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QFormLayout, QPushButton, QLabel, QMessageBox, QTableWidget, QTableWidgetItem
from models.encargado import Encargado
from models.pacienteEncargado import PacienteEncargado

class DialogoEncargado(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agregar Encargado")
        layout = QFormLayout(self)

        self.txt_nombre = QLineEdit(); layout.addRow("Nombre:", self.txt_nombre)
        self.txt_ci = QLineEdit(); layout.addRow("CI:", self.txt_ci)
        self.txt_edad = QLineEdit(); layout.addRow("Edad:", self.txt_edad)
        self.txt_ocupacion = QLineEdit(); layout.addRow("Ocupación:", self.txt_ocupacion)
        self.txt_telefono = QLineEdit(); layout.addRow("Teléfono:", self.txt_telefono)
        self.txt_observaciones = QLineEdit(); layout.addRow("Observaciones:", self.txt_observaciones)
        self.txt_nombre.returnPressed.connect(lambda: self.txt_ci.setFocus())
        self.txt_ci.returnPressed.connect(lambda: self.txt_edad.setFocus())
        self.txt_edad.returnPressed.connect(lambda: self.txt_ocupacion.setFocus())
        self.txt_ocupacion.returnPressed.connect(lambda: self.txt_telefono.setFocus())
        self.txt_telefono.returnPressed.connect(lambda: self.txt_observaciones.setFocus())
        self.txt_observaciones.returnPressed.connect(lambda: btn_ok.setFocus())

        botones = QHBoxLayout()
        btn_ok = QPushButton("Agregar")
        btn_cancel = QPushButton("Cancelar")
        btn_ok.clicked.connect(self.aceptar)
        btn_cancel.clicked.connect(self.reject)
        botones.addWidget(btn_ok)
        botones.addWidget(btn_cancel)
        layout.addRow(botones)

    def get_datos(self):
        return {
            "nombre": self.txt_nombre.text().strip(),
            "ci": self.txt_ci.text().strip(),
            "edad": self.txt_edad.text().strip(),
            "ocupacion": self.txt_ocupacion.text().strip(),
            "telefono": self.txt_telefono.text().strip(),
            "observaciones": self.txt_observaciones.text().strip()
        }
    
    def aceptar(self):
        nombre = self.txt_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Validación", "El nombre del encargado es obligatorio.")
            self.txt_nombre.setFocus()
            return
        # Continúa con la lógica de guardado
        self.accept()
