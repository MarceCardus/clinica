# controllers/form_registrar_gasto.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit,
                             QPushButton, QMessageBox, QComboBox) # QSpinBox ya no se usa para el monto
from PyQt5.QtCore import Qt
from models.caja_chica import CajaChicaMovimiento, CajaChicaSesion
from models.compra import Compra
from models.proveedor import Proveedor

class FormRegistrarGasto(QDialog):
    def __init__(self, session, usuario_id, parent=None):
        super().__init__(parent)
        self.session = session
        self.usuario_id = usuario_id
        self.caja_abierta = self.session.query(CajaChicaSesion).filter(CajaChicaSesion.estado == 'ABIERTA').first()

        self.setWindowTitle("Registrar Gasto de Caja Chica")
        self.setModal(True)
        self.setMinimumWidth(550)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        formLayout = QFormLayout()

        self.tipo_gasto_combo = QComboBox()
        self.tipo_gasto_combo.addItems(["Gastos Varios", "Pago de Compra"])
        self.tipo_gasto_combo.currentIndexChanged.connect(self.actualizar_ui_por_tipo)

        self.proveedor_label = QLabel("Filtrar por Proveedor:")
        self.proveedor_combo = QComboBox()
        self.proveedor_combo.currentIndexChanged.connect(self.cargar_compras_pendientes)

        self.compra_label = QLabel("Seleccionar Compra:")
        self.compra_selector = QComboBox()
        self.compra_selector.currentIndexChanged.connect(self.cargar_datos_compra)
        
        self.descripcion_input = QLineEdit()
        
        # --- CAMBIO 1: Reemplazamos QSpinBox por QLineEdit ---
        self.monto_input = QLineEdit()
        self.monto_input.setAlignment(Qt.AlignRight)
        self.monto_input.setStyleSheet("font-size: 16px; padding: 5px;")
        self.monto_input.textChanged.connect(self.formatear_monto)

        formLayout.addRow(QLabel("Tipo de Gasto:"), self.tipo_gasto_combo)
        formLayout.addRow(self.proveedor_label, self.proveedor_combo)
        formLayout.addRow(self.compra_label, self.compra_selector)
        formLayout.addRow(QLabel("Descripción:"), self.descripcion_input)
        formLayout.addRow(QLabel("Monto:"), self.monto_input)

        self.guardar_button = QPushButton("Guardar Gasto")
        self.guardar_button.clicked.connect(self.accept)

        layout.addLayout(formLayout)
        layout.addWidget(self.guardar_button)
        
        self.actualizar_ui_por_tipo()

    # --- CAMBIO 2: Agregamos la función para formatear el monto en tiempo real ---
    def formatear_monto(self, texto):
        try:
            numeros = ''.join(filter(str.isdigit, texto))
            if not numeros:
                return
            valor = int(numeros)
            texto_formateado = f"Gs. {valor:,}".replace(",", ".")
            
            self.monto_input.blockSignals(True)
            self.monto_input.setText(texto_formateado)
            self.monto_input.blockSignals(False)
        except (ValueError, TypeError):
            pass

    def actualizar_ui_por_tipo(self):
        es_pago_compra = self.tipo_gasto_combo.currentText() == "Pago de Compra"
        
        self.proveedor_label.setVisible(es_pago_compra)
        self.proveedor_combo.setVisible(es_pago_compra)
        self.compra_label.setVisible(es_pago_compra)
        self.compra_selector.setVisible(es_pago_compra)
        
        self.descripcion_input.setReadOnly(es_pago_compra)
        # --- CAMBIO 3: Ajustamos el campo de monto (ahora es QLineEdit) ---
        self.monto_input.setReadOnly(es_pago_compra)
        
        if es_pago_compra:
            self.cargar_proveedores()
        else:
            self.descripcion_input.clear()
            self.monto_input.setText("")

    def cargar_proveedores(self):
        self.proveedor_combo.blockSignals(True)
        self.proveedor_combo.clear()
        
        subquery_pagadas = self.session.query(CajaChicaMovimiento.idcompra).filter(CajaChicaMovimiento.idcompra.isnot(None))
        proveedores = self.session.query(Proveedor).join(Compra).filter(
            Compra.condicion_compra == 'CONTADO',
            Compra.anulada == False,
            ~Compra.idcompra.in_(subquery_pagadas)
        ).distinct().order_by(Proveedor.nombre).all()

        self.proveedor_combo.addItem("Todos los proveedores", None)
        for prov in proveedores:
            self.proveedor_combo.addItem(prov.nombre, prov.idproveedor)
        
        self.proveedor_combo.blockSignals(False)
        self.cargar_compras_pendientes()

    def cargar_compras_pendientes(self):
        self.compra_selector.clear()
        
        id_proveedor_seleccionado = self.proveedor_combo.currentData()
        
        subquery_pagadas = self.session.query(CajaChicaMovimiento.idcompra).filter(CajaChicaMovimiento.idcompra.isnot(None))
        query_compras = self.session.query(Compra).filter(
            Compra.condicion_compra == 'CONTADO',
            Compra.anulada == False,
            ~Compra.idcompra.in_(subquery_pagadas)
        )
        
        if id_proveedor_seleccionado:
            query_compras = query_compras.filter(Compra.idproveedor == id_proveedor_seleccionado)
            
        compras = query_compras.order_by(Compra.fecha.desc()).all()
        
        self.compra_selector.addItem("Seleccione una compra...", None)
        for compra in compras:
            monto_formateado = f"{int(compra.montototal):,}".replace(",", ".")
            texto = f"ID:{compra.idcompra} | {compra.nro_comprobante or 'S/N'} | Gs. {monto_formateado}"
            self.compra_selector.addItem(texto, compra.idcompra)

    def cargar_datos_compra(self):
        id_compra = self.compra_selector.currentData()
        if id_compra:
            compra = self.session.query(Compra).get(id_compra)
            self.descripcion_input.setText(f"Pago Compra ID {compra.idcompra} - Factura {compra.nro_comprobante}")
            # --- CAMBIO 4: Usamos setText en lugar de setValue ---
            self.monto_input.setText(str(int(compra.montototal)))
        else:
            self.descripcion_input.clear()
            self.monto_input.setText("")

    def accept(self):
        # --- CAMBIO 5: Obtenemos el valor del QLineEdit ---
        texto_monto = self.monto_input.text()
        numeros = ''.join(filter(str.isdigit, texto_monto))
        monto = int(numeros) if numeros else 0
        
        descripcion = self.descripcion_input.text().strip()
        tipo_seleccionado = self.tipo_gasto_combo.currentText()
        id_compra_seleccionada = None
        tipo_movimiento_enum = 'GASTO'

        if monto <= 0 and tipo_seleccionado == 'Gastos Varios':
            QMessageBox.warning(self, "Error", "El monto debe ser mayor a cero.")
            return
        if not descripcion:
            QMessageBox.warning(self, "Error", "La descripción no puede estar vacía.")
            return

        if tipo_seleccionado == "Pago de Compra":
            id_compra_seleccionada = self.compra_selector.currentData()
            if not id_compra_seleccionada:
                QMessageBox.warning(self, "Error", "Debe seleccionar una compra para pagar.")
                return
            tipo_movimiento_enum = 'PAGO_COMPRA'

        try:
            nuevo_movimiento = CajaChicaMovimiento(
                idcajachica=self.caja_abierta.idcajachica,
                tipo_movimiento=tipo_movimiento_enum,
                descripcion=descripcion,
                monto=monto,
                idcompra=id_compra_seleccionada,
                idusuario_registro=self.usuario_id
            )
            self.session.add(nuevo_movimiento)
            self.session.commit()
            QMessageBox.information(self, "Éxito", "Gasto registrado correctamente.")
            super().accept()
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo registrar el gasto: {e}")