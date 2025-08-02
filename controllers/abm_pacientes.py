import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from utils.db import SessionLocal
from models.paciente import Paciente
from models.barrio import Barrio
from models.ciudad import Ciudad
from models.departamento import Departamento

from sqlalchemy.orm import joinedload

class PacienteForm(QMainWindow):
    def __init__(self, usuario_id):
        super().__init__()
        self.usuario_id = usuario_id

        self.setWindowTitle("Gestión de Pacientes")

        # --- Layout principal ---
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # --- Buscador arriba ---
        buscador_layout = QHBoxLayout()
        buscador_layout.addWidget(QLabel("Buscar:"))
        self.input_buscar = QLineEdit()
        self.input_buscar.setPlaceholderText("Escriba para filtrar...")
        self.input_buscar.textChanged.connect(self.filtrar_pacientes)
        buscador_layout.addWidget(self.input_buscar)
        buscador_layout.addStretch()
        layout.addLayout(buscador_layout)

        # --- Grilla de pacientes ---
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Apellido", "CI", "Teléfono",
            "Ciudad", "Estado", "Editar", "Eliminar", "Historial", "Fotos"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # --- Botón "Agregar" abajo a la derecha ---
        footer = QHBoxLayout()
        footer.addStretch()
        self.btn_agregar = QPushButton("Agregar Paciente")
        self.btn_agregar.setIcon(QIcon("imagenes/agregar.png"))
        self.btn_agregar.setFixedHeight(36)
        self.btn_agregar.clicked.connect(self.agregar_paciente)
        footer.addWidget(self.btn_agregar)
        layout.addLayout(footer)

        self.setCentralWidget(central)

        # --- Cargar pacientes ---
        self.pacientes = []
        self.cargar_pacientes()

    def cargar_pacientes(self):
        self.pacientes = []
        self.table.setRowCount(0)
        session = SessionLocal()
        query = (
            session.query(Paciente)
            .options(joinedload(Paciente.barrio).joinedload(Barrio.ciudad))
            .order_by(Paciente.apellido.asc(), Paciente.nombre.asc())  # <- AQUÍ EL CAMBIO
            .all()
        )
        for i, pac in enumerate(query):
            self.pacientes.append(pac)
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(str(pac.idpaciente)))
            self.table.setItem(i, 1, QTableWidgetItem(pac.nombre))
            self.table.setItem(i, 2, QTableWidgetItem(pac.apellido))
            self.table.setItem(i, 3, QTableWidgetItem(pac.ci_pasaporte))
            self.table.setItem(i, 4, QTableWidgetItem(pac.telefono or ""))
            ciudad = pac.barrio.ciudad.nombre if pac.barrio and pac.barrio.ciudad else ""
            self.table.setItem(i, 5, QTableWidgetItem(ciudad))
            self.table.setItem(i, 6, QTableWidgetItem("Activo" if pac.estado else "Inactivo"))
            # Botón Editar
            btn_editar = QPushButton(); btn_editar.setIcon(QIcon("imagenes/editar.png"))
            btn_editar.setToolTip("Editar paciente")
            btn_editar.clicked.connect(lambda _, pid=pac.idpaciente: self.editar_paciente(pid))
            self.table.setCellWidget(i, 7, btn_editar)
            # Botón Eliminar
            btn_eliminar = QPushButton(); btn_eliminar.setIcon(QIcon("imagenes/eliminar.png"))
            btn_eliminar.setToolTip("Eliminar (desactivar)")
            btn_eliminar.clicked.connect(lambda _, pid=pac.idpaciente: self.eliminar_paciente(pid))
            self.table.setCellWidget(i, 8, btn_eliminar)
            # Botón Historial
            btn_historial = QPushButton(); btn_historial.setIcon(QIcon("imagenes/historial.png"))
            btn_historial.setToolTip("Ver ficha clínica")
            btn_historial.clicked.connect(lambda _, pid=pac.idpaciente: self.ver_historial(pid))
            self.table.setCellWidget(i, 9, btn_historial)
            # Botón Fotos
            btn_fotos = QPushButton(); btn_fotos.setIcon(QIcon("imagenes/fotos.png"))
            btn_fotos.setToolTip("Ver fotos")
            btn_fotos.clicked.connect(lambda _, pid=pac.idpaciente: self.abrir_fotos(pid))
            self.table.setCellWidget(i, 10, btn_fotos)
        session.close()

    def ver_historial(self, idpaciente):
        from controllers.fichaClinica import FichaClinicaForm
        dlg = FichaClinicaForm(idpaciente=idpaciente, parent=self, solo_control=True)
        dlg.exec_()

    def filtrar_pacientes(self):
        texto = self.input_buscar.text().strip().lower()
        self.table.setRowCount(0)
        for pac in self.pacientes:
            campos = [
                str(pac.idpaciente), pac.nombre.lower(), pac.apellido.lower(),
                (pac.ci_pasaporte or "").lower(), (pac.telefono or "").lower(),
                (pac.barrio.ciudad.nombre.lower() if pac.barrio and pac.barrio.ciudad else "")
            ]
            if any(texto in c for c in campos):
                i = self.table.rowCount()
                self.table.insertRow(i)
                self.table.setItem(i, 0, QTableWidgetItem(str(pac.idpaciente)))
                self.table.setItem(i, 1, QTableWidgetItem(pac.nombre))
                self.table.setItem(i, 2, QTableWidgetItem(pac.apellido))
                self.table.setItem(i, 3, QTableWidgetItem(pac.ci_pasaporte))
                self.table.setItem(i, 4, QTableWidgetItem(pac.telefono or ""))
                ciudad = pac.barrio.ciudad.nombre if pac.barrio and pac.barrio.ciudad else ""
                self.table.setItem(i, 5, QTableWidgetItem(ciudad))
                self.table.setItem(i, 6, QTableWidgetItem("Activo" if pac.estado else "Inactivo"))
                # Botón Editar
                btn_editar = QPushButton(); btn_editar.setIcon(QIcon("imagenes/editar.png"))
                btn_editar.clicked.connect(lambda _, pid=pac.idpaciente: self.editar_paciente(pid))
                self.table.setCellWidget(i, 7, btn_editar)
                # Botón Eliminar
                btn_eliminar = QPushButton(); btn_eliminar.setIcon(QIcon("imagenes/eliminar.png"))
                btn_eliminar.clicked.connect(lambda _, pid=pac.idpaciente: self.eliminar_paciente(pid))
                self.table.setCellWidget(i, 8, btn_eliminar)
                # Botón Historial
                btn_historial = QPushButton(); btn_historial.setIcon(QIcon("imagenes/historial.png"))
                btn_historial.clicked.connect(lambda _, pid=pac.idpaciente: self.ver_ficha_clinica(pid))
                self.table.setCellWidget(i, 9, btn_historial)
                # Botón Fotos
                btn_fotos = QPushButton(); btn_fotos.setIcon(QIcon("imagenes/fotos.png"))
                btn_fotos.clicked.connect(lambda _, pid=pac.idpaciente: self.abrir_fotos(pid))
                self.table.setCellWidget(i, 10, btn_fotos)

    def agregar_paciente(self):
        from controllers.fichaClinica import FichaClinicaForm
        dlg = FichaClinicaForm(idpaciente=None, parent=self)  # O no pasar idpaciente
        if dlg.exec_():
            self.cargar_pacientes()

    def editar_paciente(self, idpaciente):
        from controllers.fichaClinica import FichaClinicaForm
        dlg = FichaClinicaForm(idpaciente=idpaciente, parent=self, solo_control=False)
        if dlg.exec_():
            self.cargar_pacientes()

    def eliminar_paciente(self, idpaciente):
        reply = QMessageBox.question(self, "Confirmar", "¿Desea desactivar este paciente?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No:
            return
        session = SessionLocal()
        pac = session.query(Paciente).filter_by(idpaciente=idpaciente).first()
        if pac:
            pac.estado = False
            session.commit()
        session.close()
        self.cargar_pacientes()

    def ver_ficha_clinica(self, idpaciente):
        from controllers.fichaClinica import FichaClinicaForm
        dlg = FichaClinicaForm(idpaciente=idpaciente, parent=self)
        dlg.exec_()  # Sólo ver, no hace falta recargar la grilla

    def abrir_fotos(self, idpaciente):
        from controllers.abm_fotoavance import FotosAvanceDialog
        dlg = FotosAvanceDialog(idpaciente, usuario_id=self.usuario_id)
        dlg.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = PacienteForm(usuario_id=1)
    ventana.showMaximized()
    sys.exit(app.exec_())
