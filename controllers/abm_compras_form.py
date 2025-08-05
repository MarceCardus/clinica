from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QDateEdit, QTextEdit, QTableWidget, QTableWidgetItem, QSplitter, QGroupBox, QFormLayout,
    QMessageBox, QDialog, QListWidget
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QDate, QEvent
from utils.db import SessionLocal
from models.proveedor import Proveedor
from models.insumo import Insumo

class InsumoSelectDialog(QDialog):
    def __init__(self, insumos, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Insumo")
        self.selected = None
        layout = QVBoxLayout(self)
        self.listWidget = QListWidget()
        for insumo in insumos:
            self.listWidget.addItem(f"{insumo.idinsumo} - {insumo.nombre}")
        layout.addWidget(self.listWidget)
        self.listWidget.setCurrentRow(0)
        btn = QPushButton("Seleccionar")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
        self.listWidget.itemDoubleClicked.connect(self.accept)
        self.resize(350, 300)
    def accept(self):
        idx = self.listWidget.currentRow()
        if idx >= 0:
            self.selected = idx
            super().accept()

class ABMCompra(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compras")
        self.resize(980, 540)
        self._setup_ui()
        self.btn_eliminar.clicked.connect(self.eliminar_fila_grilla)
        self.cargar_proveedores()
        self.setup_focus()
        self.proveedor.setFocus()  # Focus inicial en proveedor


    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        title_layout = QHBoxLayout()
        icono = QLabel()
        icono.setPixmap(QIcon("imagenes/compra.png").pixmap(32,32))
        title_layout.addWidget(icono)
        title_label = QLabel("Compras")
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold; margin-left:8px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)

        splitter = QSplitter(Qt.Horizontal)

        # Panel izquierdo - Cabecera
        left_box = QGroupBox("Datos de la Compra")
        left_layout = QFormLayout()
        self.fecha = QDateEdit(QDate.currentDate())
        self.fecha.setCalendarPopup(True)
        left_layout.addRow(QLabel("Fecha:"), self.fecha)
        self.proveedor = QComboBox()
        left_layout.addRow(QLabel("Proveedor:"), self.proveedor)
        self.comprobante = QComboBox()
        self.comprobante.addItems(["Factura", "Nota de Remisión"])
        left_layout.addRow(QLabel("Tipo Comprobante:"), self.comprobante)
        self.nro_comp = QLineEdit()
        left_layout.addRow(QLabel("N° Comprobante:"), self.nro_comp)
        self.observaciones = QTextEdit()
        left_layout.addRow(QLabel("Observaciones:"), self.observaciones)
        left_box.setLayout(left_layout)
        splitter.addWidget(left_box)

        # Panel derecho - Detalle
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Buscador de insumo
        search_layout = QHBoxLayout()
        self.busca_insumo = QLineEdit()
        self.busca_insumo.setPlaceholderText("Buscar insumo")
        btn_buscar = QPushButton(QIcon("imagenes/buscar.png"), "")
        btn_buscar.setStyleSheet("""
            QPushButton {
                background-color: #e9ecef;
                border: 1px solid #ced4da;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #b6d4fe;
            }
        """)
        btn_buscar.clicked.connect(self.buscar_y_agregar_insumo)
        search_layout.addWidget(self.busca_insumo)
        search_layout.addWidget(btn_buscar)
        search_layout.addStretch()
        right_layout.addLayout(search_layout)

        # Grilla de insumos
        self.grilla = QTableWidget(0, 7)
        self.grilla.setHorizontalHeaderLabels([
            "Código", "Nombre", "Cantidad", "Precio", "IVA 10%", "Total"
        ])
        right_layout.addWidget(self.grilla)

        btns_detalle = QHBoxLayout()
        btn_agregar = QPushButton(QIcon("imagenes/agregar.png"), "Agregar")
        btn_agregar.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 4px 18px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.btn_eliminar = QPushButton(QIcon("imagenes/eliminar.png"), "Eliminar")
        self.btn_eliminar.setStyleSheet("""
            QPushButton {
                background-color: #ffc9c9;
                color: #dc3545;
                font-weight: bold;
                border-radius: 6px;
                padding: 4px 18px;
            }
            QPushButton:hover {
                background-color: #fa5252;
                color: white;
            }
        """)
        btns_detalle.addWidget(btn_agregar)
        btns_detalle.addWidget(self.btn_eliminar)
        btns_detalle.addStretch()
        right_layout.addLayout(btns_detalle)

        # Pie - totales y navegación
        pie_layout = QHBoxLayout()
        self.lbl_subtotal = QLabel("Subtotal: 0")
        self.lbl_iva = QLabel("IVA: 0")
        self.lbl_total = QLabel("<b>Total: 0</b>")
        pie_layout.addWidget(self.lbl_subtotal)
        pie_layout.addWidget(self.lbl_iva)
        pie_layout.addWidget(self.lbl_total)
        pie_layout.addStretch()

        colores_nav = """
            QPushButton {
                background-color: #007bff;
                color: #007bff;
                border-radius: 6px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #b6d4fe;
            }
        """
        for nombre, icono in [
            ("Primero", "imagenes/primero.png"),
            ("Anterior", "imagenes/anterior.png"),
            ("Siguiente", "imagenes/siguiente.png"),
            ("Último", "imagenes/ultimo.png")
        ]:
            btn = QPushButton(QIcon(icono), "")
            btn.setStyleSheet(colores_nav)
            pie_layout.addWidget(btn)

        botones_accion = [
            ("Nuevo", "imagenes/nuevo.png", "#007bff", "white"),
            ("Editar", "imagenes/editar.png", "#17a2b8", "white"),
            ("Guardar", "imagenes/guardar.png", "#28a745", "white"),
            ("Cancelar", "imagenes/cancelar.png", "#ffc9c9", "#dc3545"),
            ("Salir", "imagenes/salir.png", "#e9ecef", "#212529"),
        ]
        for nombre, icono, fondo, color in botones_accion:
            btn = QPushButton(QIcon(icono), nombre)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {fondo};
                    color: {color};
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 4px 18px;
                }}
                QPushButton:hover {{
                    background-color: #b6d4fe;
                }}
            """)
            pie_layout.addWidget(btn)

        right_layout.addLayout(pie_layout)
        splitter.addWidget(right_widget)
        splitter.setSizes([340, 800])

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def cargar_proveedores(self):
        session = SessionLocal()
        self.proveedor.clear()
        proveedores = (
            session.query(Proveedor)
            .filter_by(estado=True)
            .order_by(Proveedor.nombre)
            .all()
        )
        for prov in proveedores:
            self.proveedor.addItem(prov.nombre, prov.idproveedor)
        session.close()

    def eliminar_fila_grilla(self):
        row = self.grilla.currentRow()
        if row >= 0:
            respuesta = QMessageBox.question(
                self, "Eliminar ítem",
                "¿Seguro que desea eliminar el insumo seleccionado?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if respuesta == QMessageBox.Yes:
                self.grilla.removeRow(row)
        else:
            QMessageBox.information(self, "Atención", "Debe seleccionar una fila para eliminar.")
    

    def setup_focus(self):
        self.proveedor.installEventFilter(self)
        self.comprobante.installEventFilter(self)
        self.nro_comp.installEventFilter(self)
        self.observaciones.installEventFilter(self)
        self.busca_insumo.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if obj == self.proveedor:
                self.comprobante.setFocus()
                return True
            elif obj == self.comprobante:
                self.nro_comp.setFocus()
                return True
            elif obj == self.nro_comp:
                self.observaciones.setFocus()
                return True
            elif obj == self.observaciones:
                self.busca_insumo.setFocus()
                return True
            elif obj == self.busca_insumo:
                self.buscar_y_agregar_insumo()
                return True
        return super().eventFilter(obj, event)

    def buscar_insumos(self, texto):
        session = SessionLocal()
        query = session.query(Insumo).filter(
            Insumo.nombre.ilike(f"%{texto}%")
        ).order_by(Insumo.nombre)
        resultados = query.all()
        session.close()
        return resultados

    def buscar_y_agregar_insumo(self):
        texto = self.busca_insumo.text().strip()
        if not texto:
            return
        insumos = self.buscar_insumos(texto)
        if not insumos:
            QMessageBox.information(self, "Sin resultados", "No se encontró ningún insumo.")
        elif len(insumos) == 1:
            self.agregar_insumo_a_grilla(insumos[0])
        else:
            dlg = InsumoSelectDialog(insumos, self)
            if dlg.exec_() and dlg.selected is not None:
                self.agregar_insumo_a_grilla(insumos[dlg.selected])
        self.busca_insumo.clear()

    def agregar_insumo_a_grilla(self, insumo):
        # Evitar duplicados: buscá si ya está el código
        for row in range(self.grilla.rowCount()):
            if self.grilla.item(row, 0) and self.grilla.item(row, 0).text() == str(insumo.idinsumo):
                # Si ya existe, sumar cantidad
                cant_item = self.grilla.item(row, 2)
                cant_actual = float(cant_item.text()) if cant_item and cant_item.text() else 0
                cant_item.setText(str(cant_actual + 1))
                self.grilla.setCurrentCell(row, 2)
                return
            
        row = self.grilla.rowCount()
        self.grilla.insertRow(row)
        self.grilla.setItem(row, 0, QTableWidgetItem(str(insumo.idinsumo)))
        self.grilla.setItem(row, 1, QTableWidgetItem(insumo.nombre))
        self.grilla.setItem(row, 2, QTableWidgetItem("1"))  # cantidad default
        self.grilla.setItem(row, 3, QTableWidgetItem("0"))  # precio
        self.grilla.setItem(row, 4, QTableWidgetItem("0"))  # iva
        self.grilla.setItem(row, 5, QTableWidgetItem("0"))  # total

        # Focus y selección total en cantidad
        self.grilla.setCurrentCell(row, 2)
        self.grilla.editItem(self.grilla.item(row, 2))
        self.grilla.setFocus()
        self.grilla.item(row, 2).setSelected(True)

    def keyPressEvent(self, event):
        # Detectar si el foco está en la grilla
        if self.grilla.hasFocus():
            current_row = self.grilla.currentRow()
            current_col = self.grilla.currentColumn()
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if current_col == 2:  # Cantidad
                    self.grilla.setCurrentCell(current_row, 3)
                    self.grilla.editItem(self.grilla.item(current_row, 3))
                    self.grilla.item(current_row, 3).setSelected(True)
                    return
                elif current_col == 3:  # Precio
                    # Calcular IVA y Total
                    self.calcular_iva_total_row(current_row)
                    self.busca_insumo.setFocus()
                    return
        super().keyPressEvent(event)

    def calcular_iva_total_row(self, row):
        try:
            cantidad = float(self.grilla.item(row, 2).text())
            precio = float(self.grilla.item(row, 3).text())
            iva = precio * cantidad / 11  # Ajusta el % según corresponda
            total = (precio * cantidad) + iva
            self.grilla.setItem(row, 4, QTableWidgetItem(f"{iva:.0f}"))
            self.grilla.setItem(row, 5, QTableWidgetItem(f"{total:.0f}"))
        except Exception:
            pass
        self.actualizar_totales()    