
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize
from models.paquete import Paquete
from utils.db import SessionLocal
from controllers.PaqueteForm import PaqueteFormDialog

class ABMPaquete(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ABM de Paquetes")
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 7 columnas (ID, Nombre, Descripción, Cant. Sesiones, Precio Total, Editar, Eliminar)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Descripción", "Cant. Sesiones", "Precio Total", "Editar", "Eliminar"
        ])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton()
        btn_add.setIcon(QIcon("imagenes/agregar.png"))
        btn_add.setIconSize(QSize(80, 80))
        btn_add.setFlat(True)
        btn_add.setToolTip("Agregar paquete")
        btn_add.clicked.connect(self.add_paquete)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_add)
        layout.addLayout(btn_layout)

    def load_data(self):
        session = SessionLocal()
        paquetes = session.query(Paquete).all()
        session.close()

        self.table.setRowCount(len(paquetes))
        for i, p in enumerate(paquetes):
            self.table.setItem(i, 0, QTableWidgetItem(str(p.idpaquete)))
            self.table.setItem(i, 1, QTableWidgetItem(p.nombre))
            self.table.setItem(i, 2, QTableWidgetItem(p.descripcion or ""))
            self.table.setItem(i, 3, QTableWidgetItem(str(p.cantidadsesiones or "")))
            self.table.setItem(i, 4, QTableWidgetItem(f"{float(p.preciototal):.2f}"))

            # Botón Editar
            btn_e = QPushButton()
            btn_e.setIcon(QIcon("imagenes/editar.png"))
            btn_e.setIconSize(QSize(24, 24))
            btn_e.setFlat(True)
            btn_e.clicked.connect(lambda _, pid=p.idpaquete: self.edit_paquete(pid))
            self.table.setCellWidget(i, 5, btn_e)

            # Botón Eliminar
            btn_d = QPushButton()
            btn_d.setIcon(QIcon("imagenes/eliminar.png"))
            btn_d.setIconSize(QSize(24, 24))
            btn_d.setFlat(True)
            btn_d.clicked.connect(lambda _, pid=p.idpaquete: self.delete_paquete(pid))
            self.table.setCellWidget(i, 6, btn_d)

    def add_paquete(self):
        session = SessionLocal()
        dlg = PaqueteFormDialog(self, None, session)
        if dlg.exec_() == dlg.Accepted:
            session.close()
            self.load_data()
        else:
            session.close()

    def edit_paquete(self, paquete_id):
        session = SessionLocal()
        paquete = session.query(Paquete).get(paquete_id)
        dlg = PaqueteFormDialog(self, paquete, session)
        if dlg.exec_() == dlg.Accepted:
            session.close()
            self.load_data()
        else:
            session.close()

    def delete_paquete(self, paquete_id):
        if QMessageBox.question(
            self, "Confirmar", "¿Eliminar este paquete (y todas sus relaciones con productos)?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        session = SessionLocal()
        paquete = session.query(Paquete).get(paquete_id)
        if paquete:
            session.delete(paquete)
            session.commit()
        session.close()
        self.load_data()
