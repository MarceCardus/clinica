# controllers/cambiar_password_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QCheckBox
)
from PyQt5.QtCore import Qt
from utils.db import SessionLocal
from utils.security import verify_password, hash_password
from models.usuario import Usuario

def validar_politica_password(usuario: str, old: str, new: str) -> str:
    """
    Retorna mensaje de error si no cumple, o "" si todo ok.
    Reglas simples (ajustá si querés):
      - mínimo 8 caracteres
      - no igual a la anterior
      - no igual al nombre de usuario
    """
    if len(new) < 8:
        return "La nueva contraseña debe tener al menos 8 caracteres."
    if new == old:
        return "La nueva contraseña no puede ser igual a la anterior."
    if usuario and new.lower() == usuario.lower():
        return "La nueva contraseña no puede ser igual al usuario."
    return ""

class CambiarPasswordDialog(QDialog):
    """
    Uso:
        dlg = CambiarPasswordDialog(id_usuario_logueado)
        dlg.exec_()
    """
    def __init__(self, idusuario: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cambiar contraseña")
        self.setModal(True)
        self._idusuario = idusuario
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.lbl_usuario = QLabel("")  # se completa al abrir
        form.addRow("Usuario:", self.lbl_usuario)

        self.txt_actual = QLineEdit()
        self.txt_actual.setEchoMode(QLineEdit.Password)
        form.addRow("Contraseña actual:", self.txt_actual)

        self.txt_nueva = QLineEdit()
        self.txt_nueva.setEchoMode(QLineEdit.Password)
        form.addRow("Nueva contraseña:", self.txt_nueva)

        self.txt_confirmar = QLineEdit()
        self.txt_confirmar.setEchoMode(QLineEdit.Password)
        form.addRow("Confirmar nueva:", self.txt_confirmar)

        self.chk_mostrar = QCheckBox("Mostrar contraseñas")
        self.chk_mostrar.stateChanged.connect(self._toggle_echo)
        form.addRow("", self.chk_mostrar)

        layout.addLayout(form)

        # Botones
        btns = QHBoxLayout()
        btns.addStretch()
        self.btn_guardar = QPushButton("Guardar")
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_guardar.clicked.connect(self._guardar)
        self.btn_cancelar.clicked.connect(self.reject)
        btns.addWidget(self.btn_guardar)
        btns.addWidget(self.btn_cancelar)
        layout.addLayout(btns)

        # Cargar usuario
        self._cargar_usuario()

    def _toggle_echo(self, state):
        mode = QLineEdit.Normal if state == Qt.Checked else QLineEdit.Password
        self.txt_actual.setEchoMode(mode)
        self.txt_nueva.setEchoMode(mode)
        self.txt_confirmar.setEchoMode(mode)

    def _cargar_usuario(self):
        session = SessionLocal()
        try:
            user = session.query(Usuario).get(self._idusuario)
            if not user:
                QMessageBox.critical(self, "Error", "Usuario no encontrado.")
                self.reject()
                return
            self.lbl_usuario.setText(user.usuario or "(sin nombre)")
        finally:
            session.close()

    def _guardar(self):
        actual = self.txt_actual.text().strip()
        nueva  = self.txt_nueva.text().strip()
        conf   = self.txt_confirmar.text().strip()

        if not actual or not nueva or not conf:
            QMessageBox.warning(self, "Atención", "Todos los campos son obligatorios.")
            return

        if nueva != conf:
            QMessageBox.warning(self, "Atención", "La nueva contraseña y su confirmación no coinciden.")
            return

        session = SessionLocal()
        try:
            user = session.query(Usuario).get(self._idusuario)
            if not user:
                QMessageBox.critical(self, "Error", "Usuario no encontrado.")
                return

            # Verificar contraseña actual (soporta legacy en texto plano)
            if not verify_password(actual, user.contrasena):
                QMessageBox.warning(self, "Atención", "La contraseña actual es incorrecta.")
                return

            # Política de contraseña
            msg = validar_politica_password(user.usuario or "", actual, nueva)
            if msg:
                QMessageBox.warning(self, "Atención", msg)
                return

            # Guardar SIEMPRE hasheada (migración automática a bcrypt)
            user.contrasena = hash_password(nueva)
            session.commit()

            QMessageBox.information(self, "Listo", "Contraseña actualizada correctamente.")
            self.accept()
        except Exception as ex:
            session.rollback()
            QMessageBox.critical(self, "Error", f"Ocurrió un error al actualizar: {ex}")
        finally:
            session.close()
            # limpiar buffers por seguridad
            self.txt_actual.setText("")
            self.txt_nueva.setText("")
            self.txt_confirmar.setText("")
