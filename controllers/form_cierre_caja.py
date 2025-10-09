# controllers/form_cierre_caja.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox)
from PyQt5.QtCore import Qt
from models.caja_chica import CajaChicaSesion
import datetime

class FormCierreCaja(QDialog):
    def __init__(self, session, usuario_id, parent=None):
        super().__init__(parent)
        self.session = session
        self.usuario_id = usuario_id
        self.caja_abierta = self.session.query(CajaChicaSesion).filter(CajaChicaSesion.estado == 'ABIERTA').first()
        self.saldo_calculado = 0

        self.setWindowTitle("Cierre de Caja (Arqueo)")
        self.setModal(True)
        self.initUI()
        self.calcular_totales()

    def initUI(self):
        self.setMinimumSize(450, 200)
        
        layout = QVBoxLayout(self)
        formLayout = QFormLayout()

        self.lbl_saldo_calculado = QLabel("Gs. 0")
        self.lbl_saldo_calculado.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.monto_real_input = QLineEdit()
        self.monto_real_input.setAlignment(Qt.AlignRight)
        self.monto_real_input.setStyleSheet("font-size: 16px; padding: 5px;")
        self.monto_real_input.textChanged.connect(self.formatear_y_recalcular)

        self.lbl_diferencia = QLabel("Gs. 0")
        # <<< CAMBIO AQUÍ: Unificamos el tamaño de letra a 16px >>>
        self.lbl_diferencia.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.observaciones_input = QLineEdit()
        
        formLayout.addRow(QLabel("<b>Saldo del Sistema (Calculado):</b>"), self.lbl_saldo_calculado)
        formLayout.addRow(QLabel("Monto Real Contado:"), self.monto_real_input)
        formLayout.addRow(QLabel("<b>Diferencia (Sobrante/Faltante):</b>"), self.lbl_diferencia)
        formLayout.addRow(QLabel("Observaciones:"), self.observaciones_input)

        self.guardar_button = QPushButton("Cerrar Caja Definitivamente")
        self.guardar_button.clicked.connect(self.accept)

        layout.addLayout(formLayout)
        layout.addWidget(self.guardar_button)

    def formatear_y_recalcular(self, texto):
        try:
            numeros = ''.join(filter(str.isdigit, texto))
            if not numeros:
                self.calcular_totales()
                return

            valor = int(numeros)
            texto_formateado = f"Gs. {valor:,}".replace(",", ".")
            
            self.monto_real_input.blockSignals(True)
            self.monto_real_input.setText(texto_formateado)
            self.monto_real_input.blockSignals(False)
        except (ValueError, TypeError):
            pass
        
        self.calcular_totales()

    def calcular_totales(self):
        total_gastos = sum(m.monto for m in self.caja_abierta.movimientos if m.tipo_movimiento in ('GASTO', 'PAGO_COMPRA'))
        self.saldo_calculado = self.caja_abierta.monto_inicial - total_gastos
        
        texto_monto_real = self.monto_real_input.text()
        numeros = ''.join(filter(str.isdigit, texto_monto_real))
        monto_real = int(numeros) if numeros else 0
        
        diferencia = monto_real - float(self.saldo_calculado)
        
        self.lbl_saldo_calculado.setText(f"Gs. {int(self.saldo_calculado):,}".replace(",", "."))
        self.lbl_diferencia.setText(f"Gs. {int(diferencia):,}".replace(",", "."))
        
        # <<< CAMBIO AQUÍ: Unificamos el tamaño de letra a 16px en todos los estilos >>>
        if diferencia > 0:
            self.lbl_diferencia.setStyleSheet("font-size: 16px; font-weight: bold; color: green;")
        elif diferencia < 0:
            self.lbl_diferencia.setStyleSheet("font-size: 16px; font-weight: bold; color: red;")
        else:
            self.lbl_diferencia.setStyleSheet("font-size: 16px; font-weight: bold;")

    def accept(self):
        reply = QMessageBox.question(self, 'Confirmación', 
                                     "¿Estás seguro de que deseas cerrar la caja? Esta acción no se puede deshacer.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                texto_monto_real = self.monto_real_input.text()
                numeros = ''.join(filter(str.isdigit, texto_monto_real))
                monto_real_final = int(numeros) if numeros else 0

                self.caja_abierta.monto_final_calculado = self.saldo_calculado
                self.caja_abierta.monto_final_real = monto_real_final
                self.caja_abierta.diferencia = monto_real_final - float(self.saldo_calculado)
                self.caja_abierta.observaciones = self.observaciones_input.text()
                self.caja_abierta.fecha_cierre = datetime.datetime.now()
                self.caja_abierta.idusuario_cierre = self.usuario_id
                self.caja_abierta.estado = 'CERRADA'
                
                self.session.commit()
                QMessageBox.information(self, "Éxito", "La caja se ha cerrado correctamente.")
                super().accept()
            except Exception as e:
                self.session.rollback()
                QMessageBox.critical(self, "Error", f"No se pudo cerrar la caja: {e}")