# controllers/form_ver_estado_caja.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton)
from PyQt5.QtCore import Qt
from models.caja_chica import CajaChicaSesion

class FormVerEstadoCaja(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.caja_abierta = self.session.query(CajaChicaSesion).filter(CajaChicaSesion.estado == 'ABIERTA').first()

        self.setWindowTitle("Estado Actual de Caja Chica")
        self.setMinimumSize(700, 500)
        self.initUI()
        self.cargar_datos()

    def initUI(self):
        layout = QVBoxLayout(self)
        formLayout = QFormLayout()

        self.lbl_monto_inicial = QLabel("Gs. 0")
        self.lbl_total_gastos = QLabel("Gs. 0")
        self.lbl_saldo_calculado = QLabel("Gs. 0")
        
        # Aumentamos el tamaño de la fuente para mejor legibilidad
        label_style = "font-size: 14px;"
        self.lbl_monto_inicial.setStyleSheet(label_style)
        self.lbl_total_gastos.setStyleSheet(label_style)
        self.lbl_saldo_calculado.setStyleSheet("font-weight: bold; font-size: 16px;")

        formLayout.addRow(QLabel("Monto Inicial:"), self.lbl_monto_inicial)
        formLayout.addRow(QLabel("Total Gastos y Pagos:"), self.lbl_total_gastos)
        formLayout.addRow(QLabel("<b>Saldo Actual Calculado:</b>"), self.lbl_saldo_calculado)

        self.tabla_movimientos = QTableWidget()
        self.tabla_movimientos.setColumnCount(4)
        self.tabla_movimientos.setHorizontalHeaderLabels(["Fecha y Hora", "Descripción", "Tipo", "Monto"])
        self.tabla_movimientos.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabla_movimientos.setEditTriggers(QTableWidget.NoEditTriggers)

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.close)

        layout.addLayout(formLayout)
        layout.addWidget(self.tabla_movimientos)
        layout.addWidget(btn_cerrar)

    def cargar_datos(self):
        total_gastos = 0
        self.tabla_movimientos.setRowCount(0)

        for mov in self.caja_abierta.movimientos:
            row = self.tabla_movimientos.rowCount()
            self.tabla_movimientos.insertRow(row)
            
            fecha_hora = mov.fecha_hora.strftime('%d/%m/%Y %H:%M:%S')
            
            # --- CAMBIO 1: Formateamos el monto para la tabla ---
            monto_formateado = f"Gs. {int(mov.monto):,}".replace(",", ".")
            monto_item = QTableWidgetItem(monto_formateado)
            monto_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            self.tabla_movimientos.setItem(row, 0, QTableWidgetItem(fecha_hora))
            self.tabla_movimientos.setItem(row, 1, QTableWidgetItem(mov.descripcion))
            self.tabla_movimientos.setItem(row, 2, QTableWidgetItem(mov.tipo_movimiento))
            self.tabla_movimientos.setItem(row, 3, monto_item)
            
            if mov.tipo_movimiento in ('GASTO', 'PAGO_COMPRA'):
                total_gastos += mov.monto

        monto_inicial = self.caja_abierta.monto_inicial
        saldo_calculado = monto_inicial - total_gastos

        # --- CAMBIO 2: Formateamos los montos para las etiquetas de resumen ---
        self.lbl_monto_inicial.setText(f"Gs. {int(monto_inicial):,}".replace(",", "."))
        self.lbl_total_gastos.setText(f"Gs. {int(total_gastos):,}".replace(",", "."))
        self.lbl_saldo_calculado.setText(f"Gs. {int(saldo_calculado):,}".replace(",", "."))