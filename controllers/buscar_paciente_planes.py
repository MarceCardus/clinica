# controllers/buscar_paciente_planes.py
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox
)
from utils.db import SessionLocal
from services.patient_picker import PatientPicker   # ya lo usás en ABM Turnos
from controllers.planes_paciente import PlanesPaciente

class BuscarPacientePlanesDlg(QDialog):
    """
    Lanzador independiente para gestionar Planes/Sesiones de un paciente,
    sin pasar por Ventas. Usa PatientPicker para buscar y abrir PlanesPaciente.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Planes y sesiones — Buscar paciente")
        self.resize(600, 140)

        self.session = SessionLocal()   # solo para el picker/autocomplete
        root = QVBoxLayout(self)

        # Título
        root.addWidget(QLabel("Buscar paciente:"))

        # Buscador (nombre, CI, tel, etc. según tengas en tu PatientPicker)
        self.ppaciente = PatientPicker(self.session, placeholder="Escribí nombre, CI o teléfono…")
        root.addWidget(self.ppaciente)

        # Botones
        hb = QHBoxLayout()
        self.btn_abrir = QPushButton("Abrir planes…")
        self.btn_cerrar = QPushButton("Cerrar")
        hb.addStretch()
        hb.addWidget(self.btn_abrir)
        hb.addWidget(self.btn_cerrar)
        root.addLayout(hb)

        # Eventos
        self.btn_cerrar.clicked.connect(self.reject)
        self.btn_abrir.clicked.connect(self.abrir_planes)

        # Enter/Return abre directo si hay selección
        self.ppaciente.input.returnPressed.connect(self.abrir_planes)

    def abrir_planes(self):
        pid = self.ppaciente.current_id()
        if not pid:
            QMessageBox.information(self, "Planes", "Elegí un paciente de la lista.")
            return
        dlg = PlanesPaciente(self, idpaciente=int(pid))  # sesión propia interna
        dlg.exec_()

    def closeEvent(self, e):
        try:
            if self.session:
                self.session.close()
        finally:
            super().closeEvent(e)
