# controllers/form_apertura_caja.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox) # Se cambió QSpinBox por QLineEdit
from PyQt5.QtCore import Qt
from models.caja_chica import CajaChicaSesion

class FormAperturaCaja(QDialog):
    def __init__(self, session, usuario_id, parent=None):
        super().__init__(parent)
        self.session = session
        self.usuario_id = usuario_id
        
        self.setWindowTitle("Apertura de Caja Chica")
        self.setModal(True)
        self.initUI()

    def initUI(self):
        # 2. Hacemos la ventana más grande
        self.setMinimumSize(400, 150)
        
        layout = QVBoxLayout(self)
        formLayout = QFormLayout()

        # 1. Usamos QLineEdit en lugar de QSpinBox para controlar el formato
        self.monto_inicial_input = QLineEdit()
        self.monto_inicial_input.setAlignment(Qt.AlignRight)
        self.monto_inicial_input.setStyleSheet("font-size: 18px; padding: 5px;")
        
        # Conectamos la señal de cambio de texto a nuestra función de formato
        self.monto_inicial_input.textChanged.connect(self.formatear_monto)
        
        formLayout.addRow(QLabel("Monto Inicial:"), self.monto_inicial_input)
        
        self.guardar_button = QPushButton("Abrir Caja")
        self.guardar_button.clicked.connect(self.accept)
        
        layout.addLayout(formLayout)
        layout.addWidget(self.guardar_button)

    def formatear_monto(self, texto):
        # Esta es la función clave que se ejecuta cada vez que escribís algo
        try:
            # Quitamos el prefijo y los puntos para obtener solo los números
            numeros = ''.join(filter(str.isdigit, texto))
            
            if not numeros:
                # Si el campo está vacío, no hacemos nada
                return

            valor = int(numeros)
            
            # Formateamos el número con separadores de miles (punto)
            texto_formateado = f"Gs. {valor:,}".replace(",", ".")

            # Bloqueamos las señales temporalmente para evitar un bucle infinito
            self.monto_inicial_input.blockSignals(True)
            self.monto_inicial_input.setText(texto_formateado)
            self.monto_inicial_input.blockSignals(False)

        except ValueError:
            # En caso de algún error, no hacemos nada
            pass

    def accept(self):
        # 3. Ajustamos cómo se obtiene el valor desde el QLineEdit
        texto_monto = self.monto_inicial_input.text()
        numeros = ''.join(filter(str.isdigit, texto_monto))
        
        if not numeros:
            QMessageBox.warning(self, "Valor Inválido", "Debe ingresar un monto inicial.")
            return

        monto = int(numeros)
        
        if monto <= 0:
            QMessageBox.warning(self, "Valor Inválido", "El monto inicial debe ser mayor a cero.")
            return

        caja_abierta = self.session.query(CajaChicaSesion).filter(CajaChicaSesion.estado == 'ABIERTA').first()
        if caja_abierta:
            QMessageBox.warning(self, "Error", "Ya existe una sesión de caja abierta. Debe cerrarla primero.")
            return
        
        try:
            nueva_sesion = CajaChicaSesion(
                monto_inicial=monto,
                idusuario_apertura=self.usuario_id,
                estado='ABIERTA'
            )
            self.session.add(nueva_sesion)
            self.session.commit()
            
            # Usamos el mismo formato para el mensaje de éxito
            monto_formateado = f"{monto:,}".replace(",", ".")
            QMessageBox.information(self, "Éxito", f"Caja abierta con un monto inicial de Gs. {monto_formateado}")
            super().accept()
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo abrir la caja: {e}")