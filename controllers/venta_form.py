from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QComboBox,
    QDateEdit, QTextEdit, QTableWidget, QTableWidgetItem, QPushButton,
    QHBoxLayout, QMessageBox, QSpinBox, QDoubleSpinBox
)
from PyQt5.QtCore import QDate
from decimal import Decimal
from models.venta import Venta
from models.venta_detalle import VentaDetalle
from models.venta_cuota import VentaCuota


class VentaForm(QDialog):
    def __init__(self, session, pacientes, profesionales, clinicas, productos, paquetes, parent=None):
        super().__init__(parent)
        self.session = session
        self.productos = productos
        self.paquetes = paquetes

        self.setWindowTitle("Registrar Venta")
        self.setMinimumWidth(900)
        layout = QVBoxLayout(self)

        # --- Cabecera Venta ---
        form_layout = QFormLayout()
        self.fecha_edit = QDateEdit(QDate.currentDate())
        self.fecha_edit.setCalendarPopup(True)
        form_layout.addRow("Fecha:", self.fecha_edit)

        self.paciente_combo = QComboBox()
        for p in pacientes:
            self.paciente_combo.addItem(p.nombre, p.idpaciente)
        form_layout.addRow("Paciente:", self.paciente_combo)

        self.prof_combo = QComboBox()
        for p in profesionales:
             self.prof_combo.addItem(p.nombre, p.idprofesional)
        form_layout.addRow("Profesional:", self.prof_combo)

        self.clinica_combo = QComboBox()
        for c in clinicas:
            self.clinica_combo.addItem(c.nombre, c.idclinica)
        form_layout.addRow("Clínica:", self.clinica_combo)

        self.txt_nro_factura = QLineEdit()
        form_layout.addRow("N° Factura:", self.txt_nro_factura)

        self.monto_total_edit = QLineEdit("0.00")
        self.monto_total_edit.setReadOnly(True)
        form_layout.addRow("Monto Total:", self.monto_total_edit)

        self.obs_edit = QTextEdit()
        form_layout.addRow("Observaciones:", self.obs_edit)
        layout.addLayout(form_layout)

        # --- Detalle de Venta ---
        self.detalle_table = QTableWidget(0, 5)
        self.detalle_table.setHorizontalHeaderLabels(
            ["Tipo", "Producto/Paquete", "Cantidad", "Precio Unitario", "Descuento"]
        )
        layout.addWidget(QLabel("Detalle de Venta:"))
        layout.addWidget(self.detalle_table)

        add_item_btn = QPushButton("Agregar ítem")
        add_item_btn.clicked.connect(self.agregar_item)
        layout.addWidget(add_item_btn)

        # --- Cuotas ---
        self.cuotas_table = QTableWidget(0, 5)
        self.cuotas_table.setHorizontalHeaderLabels(
            ["N° Cuota", "Fecha Vencimiento", "Monto", "Estado", "Observaciones"]
        )
        layout.addWidget(QLabel("Cuotas de Venta:"))
        layout.addWidget(self.cuotas_table)

        add_cuota_btn = QPushButton("Agregar cuota")
        add_cuota_btn.clicked.connect(self.agregar_cuota)
        layout.addWidget(add_cuota_btn)

        # --- Guardar/Cancelar ---
        btns = QHBoxLayout()
        save_btn = QPushButton("Guardar Venta")
        save_btn.clicked.connect(self.guardar_venta)
        btns.addWidget(save_btn)
        btns.addWidget(QPushButton("Cancelar", self, clicked=self.reject))
        layout.addLayout(btns)

    def agregar_item(self):
        row = self.detalle_table.rowCount()
        self.detalle_table.insertRow(row)

        tipo_combo = QComboBox()
        tipo_combo.addItems(["Producto", "Paquete"])
        self.detalle_table.setCellWidget(row, 0, tipo_combo)

        prod_combo = QComboBox()
        # Productos primero, luego paquetes
        for p in self.productos:
            prod_combo.addItem(p.nombre, ("Producto", p.idproducto))
        for p in self.paquetes:
            prod_combo.addItem(p.nombre, ("Paquete", p.idpaquete))
        self.detalle_table.setCellWidget(row, 1, prod_combo)

        cantidad = QSpinBox()
        cantidad.setMinimum(1)
        cantidad.setValue(1)
        cantidad.valueChanged.connect(self.actualizar_monto_total)
        self.detalle_table.setCellWidget(row, 2, cantidad)

        precio = QDoubleSpinBox()
        precio.setDecimals(2)
        precio.setMaximum(999999)
        precio.setValue(0.00)
        precio.valueChanged.connect(self.actualizar_monto_total)
        self.detalle_table.setCellWidget(row, 3, precio)

        descuento = QDoubleSpinBox()
        descuento.setDecimals(2)
        descuento.setMaximum(99999)
        descuento.setValue(0.00)
        descuento.valueChanged.connect(self.actualizar_monto_total)
        self.detalle_table.setCellWidget(row, 4, descuento)

        self.actualizar_monto_total()

    def agregar_cuota(self):
        row = self.cuotas_table.rowCount()
        self.cuotas_table.insertRow(row)
        self.cuotas_table.setItem(row, 0, QTableWidgetItem(str(row+1)))
        fecha_edit = QDateEdit(QDate.currentDate())
        fecha_edit.setCalendarPopup(True)
        self.cuotas_table.setCellWidget(row, 1, fecha_edit)
        monto = QDoubleSpinBox()
        monto.setDecimals(2)
        monto.setMaximum(999999)
        monto.setValue(0.00)
        self.cuotas_table.setCellWidget(row, 2, monto)
        estado = QComboBox()
        estado.addItems(["Pendiente", "Pagado"])
        self.cuotas_table.setCellWidget(row, 3, estado)
        self.cuotas_table.setItem(row, 4, QTableWidgetItem(""))

    def actualizar_monto_total(self):
        total = 0
        for row in range(self.detalle_table.rowCount()):
            cantidad = self.detalle_table.cellWidget(row, 2).value()
            precio = self.detalle_table.cellWidget(row, 3).value()
            descuento = self.detalle_table.cellWidget(row, 4).value()
            total += (precio * cantidad) - descuento
        self.monto_total_edit.setText(f"{total:.2f}")

    def guardar_venta(self):
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy import select
        from decimal import Decimal
        from models.item import Item  # <-- usamos Item unificado

        try:
            self.session.begin()

            obj_venta = Venta(
                fecha=self.fecha_edit.date().toPyDate(),
                idpaciente=self.paciente_combo.currentData(),
                idprofesional=self.prof_combo.currentData(),
                idclinica=self.clinica_combo.currentData(),
                montototal=Decimal(self.monto_total_edit.text() or "0"),
                estadoventa="PENDIENTE",
                nro_factura=(self.txt_nro_factura.text() or "").strip(),
                observaciones=self.obs_edit.toPlainText()
            )
            self.session.add(obj_venta)
            self.session.flush()  # ya tenemos obj_venta.idventa

            # --- Detalles (SIEMPRE con iditem) ---
            for row in range(self.detalle_table.rowCount()):
                tipo_combo_txt = self.detalle_table.cellWidget(row, 0).currentText()  # "Producto" | "Paquete"
                prod_combo = self.detalle_table.cellWidget(row, 1)
                tipo_sel, id_sel = prod_combo.currentData()  # ("Producto"|"Paquete", id)
                cantidad  = self.detalle_table.cellWidget(row, 2).value()
                precio    = self.detalle_table.cellWidget(row, 3).value()
                descuento = self.detalle_table.cellWidget(row, 4).value()

                iditem = None

                if tipo_sel == "Producto":
                    # Aceptamos sólo Items cuyo tipo sea 'producto' o 'ambos'
                    iditem = int(id_sel)
                    it_tipo = (self.session.execute(
                        select(Item.tipo).where(Item.iditem == iditem)
                    ).scalar_one_or_none() or "").lower()
                    if it_tipo not in ("producto", "ambos"):
                        raise ValueError("El ítem seleccionado no es de tipo 'producto' ni 'ambos'.")

                else:  # "Paquete"
                    # Opción simple: guardar una línea por paquete (Item tipo 'paquete').
                    # Ajustá el criterio si tu Item de paquete se identifica distinto.
                    iditem = self.session.execute(
                        select(Item.iditem).where(
                            Item.iditem == int(id_sel),            # fallback: mismo id
                            Item.tipo.in_(["paquete", "ambos"])
                        )
                    ).scalar_one_or_none()
                    if iditem is None:
                        # alternativa: por referencia "PAQ:<id>"
                        iditem = self.session.execute(
                            select(Item.iditem).where(
                                Item.tipo.in_(["paquete", "ambos"]),
                                getattr(Item, "referencia", None) == f"PAQ:{int(id_sel)}"  # ignora si no existe el campo
                            )
                        ).scalar_one_or_none()
                    if iditem is None:
                        raise ValueError("No existe un Item de tipo 'paquete' que represente este paquete.")

                det = VentaDetalle(
                    idventa=obj_venta.idventa,
                    iditem=int(iditem),
                    cantidad=Decimal(str(cantidad)),
                    preciounitario=Decimal(str(precio)),
                    descuento=Decimal(str(descuento))
                )
                self.session.add(det)

            # --- Cuotas ---
            for row in range(self.cuotas_table.rowCount()):
                numerocuota = int(self.cuotas_table.item(row, 0).text())
                fechavencimiento = self.cuotas_table.cellWidget(row, 1).date().toPyDate()
                montocuota = self.cuotas_table.cellWidget(row, 2).value()
                estadocuota = self.cuotas_table.cellWidget(row, 3).currentText()
                obs_item = self.cuotas_table.item(row, 4)
                obs = obs_item.text() if obs_item else ""

                cuota = VentaCuota(
                    idventa=obj_venta.idventa,
                    numerocuota=numerocuota,
                    fechavencimiento=fechavencimiento,
                    montocuota=Decimal(str(montocuota)),
                    estadocuota=estadocuota,
                    fechapago=None,
                    idcobro=None,
                    observaciones=obs
                )
                self.session.add(cuota)

            self.session.commit()
            QMessageBox.information(self, "Venta", "Venta guardada correctamente.")
            self.accept()

        except SQLAlchemyError as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"Ocurrió un error: {e}")
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"Ocurrió un error inesperado: {e}")
