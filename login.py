# login.py
import models
import models.usuario_actual

from models.tipoproducto import TipoProducto
from models.producto import Producto
from models.item import Item
from models.plan_tipo import PlanTipo
from sqlalchemy.orm import configure_mappers, class_mapper
configure_mappers()            # dispara el mapeo
class_mapper(TipoProducto)
class_mapper(Producto)
class_mapper(Item)
class_mapper(PlanTipo)
from PyQt5.QtWidgets import (
    QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox
)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt, QEvent

from models.usuario import Usuario
from utils.db import SessionLocal
from utils.security import verify_password, hash_password, needs_rehash


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ingreso al sistema - Margaritte")
        self.setWindowIcon(QIcon("imagenes/logo2.ico"))
        self.setFixedSize(420, 280)
        self.setStyleSheet("""
            QDialog {
                background-color: #eaf1fb;
                border-radius: 18px;
            }
            QLabel {
                color: #175ca4;
                font-size: 16px;
            }
            QLineEdit {
                font-size: 16px;
                padding: 8px;
                border-radius: 8px;
                border: 1px solid #b5cbe8;
            }
            QPushButton {
                background-color: #175ca4;
                color: white;
                font-size: 17px;
                font-weight: bold;
                border-radius: 10px;
                padding: 10px 0;
            }
            QPushButton:hover {
                background-color: #4688ce;
            }
        """)

        layout = QVBoxLayout()
        lbl_title = QLabel("Sistema de Consultorio")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setFont(QFont("Arial", 22, QFont.Bold))
        lbl_title.setStyleSheet("color: #175ca4; margin-bottom: 18px;")
        layout.addWidget(lbl_title)

        layout.addWidget(QLabel("Usuario:"))
        self.input_usuario = QLineEdit()
        self.input_usuario.setPlaceholderText("Ingrese su usuario...")
        layout.addWidget(self.input_usuario)

        layout.addWidget(QLabel("Contraseña:"))
        self.input_password = QLineEdit()
        self.input_password.setEchoMode(QLineEdit.Password)
        self.input_password.setPlaceholderText("Ingrese su contraseña...")
        layout.addWidget(self.input_password)

        btns = QHBoxLayout()
        self.btn_login = QPushButton("Ingresar")
        self.btn_login.clicked.connect(self.login)
        btns.addStretch()
        btns.addWidget(self.btn_login)
        btns.addStretch()
        layout.addLayout(btns)

        self.setLayout(layout)
        self.rol = None
        self.usuario_actual = None

        # ENTER para iniciar sesión
        self.input_usuario.returnPressed.connect(self.login)
        self.input_password.returnPressed.connect(self.login)

    def login(self):
        usuario = self.input_usuario.text().strip()
        password = self.input_password.text().strip()

        if not usuario or not password:
            QMessageBox.warning(self, "Atención", "Complete usuario y contraseña.")
            return

        session = SessionLocal()
        try:
            # Buscar solo por usuario ACTIVO
            user = (
                session.query(Usuario)
                .filter(Usuario.usuario == usuario, Usuario.estado == True)
                .first()
            )

            # Verificar hash/legacy
            if not user or not verify_password(password, user.contrasena):
                QMessageBox.warning(self, "Error", "Usuario o contraseña incorrectos")
                return

            # Migración/rehash automático si corresponde (p.ej., venía en texto plano)
            if needs_rehash(user.contrasena):
                user.contrasena = hash_password(password)
                session.commit()

            # Éxito: devolver objeto Usuario y rol
            self.rol = user.rol
            self.usuario_actual = user  # Guarda el objeto Usuario
            models.usuario_actual.usuario_id = user.idusuario  # ¡IMPORTANTE!
            self.accept()

        except Exception as ex:
            session.rollback()
            QMessageBox.critical(self, "Error", f"Ocurrió un problema durante el inicio de sesión:\n{ex}")
        finally:
            session.close()
