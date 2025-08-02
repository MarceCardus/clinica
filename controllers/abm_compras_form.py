from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QDateEdit, QTextEdit, QTableWidget, QSplitter, QGroupBox, QFormLayout
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QDate, QEvent
from utils.db import SessionLocal
from models.proveedor import Proveedor

class ABMCompra(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compras")
        self.resize(980, 540)
        self._setup_ui()
        self.cargar_proveedores()
        self.setup_focus()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        title_layout = QHBoxLayout()
        icono = QLabel()
        icono.setPixmap(QIcon("imagenes/compra.png").pixmap(32,32))
        title_layout.addWidget(icono)
        title_label = QLabel("ABM de Compras")
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
        search_layout.addWidget(self.busca_insumo)
        search_layout.addWidget(btn_buscar)
        search_layout.addStretch()
        right_layout.addLayout(search_layout)

        # Grilla de insumos
        self.grilla = QTableWidget(0, 7)
        self.grilla.setHorizontalHeaderLabels([
            "Código", "Nombre", "Cantidad", "Unidad", "Precio", "IVA", "Total"
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
        btn_eliminar = QPushButton(QIcon("imagenes/eliminar.png"), "Eliminar")
        btn_eliminar.setStyleSheet("""
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
        btns_detalle.addWidget(btn_eliminar)
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

        # Botones navegación (azul claro)
        colores_nav = """
            QPushButton {
                background-color: #e3f0ff;
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

        # Botones acción
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

    def setup_focus(self):
        self.proveedor.setFocus()
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
                # Aquí puedes llamar a la lógica de búsqueda y agregado de insumo
                print("Buscar insumo por texto o lanzar selección")
                return True
        return super().eventFilter(obj, event)
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QDateEdit, QTextEdit, QTableWidget, QSplitter, QGroupBox, QFormLayout
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QDate, QEvent
from utils.db import SessionLocal
from models.proveedor import Proveedor

class ABMCompra(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compras")
        self.resize(980, 540)
        self._setup_ui()
        self.cargar_proveedores()
        self.setup_focus()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        title_layout = QHBoxLayout()
        icono = QLabel()
        icono.setPixmap(QIcon("imagenes/compra.png").pixmap(32,32))
        title_layout.addWidget(icono)
        title_label = QLabel("ABM de Compras")
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
        search_layout.addWidget(self.busca_insumo)
        search_layout.addWidget(btn_buscar)
        search_layout.addStretch()
        right_layout.addLayout(search_layout)

        # Grilla de insumos
        self.grilla = QTableWidget(0, 7)
        self.grilla.setHorizontalHeaderLabels([
            "Código", "Nombre", "Cantidad", "Unidad", "Precio", "IVA", "Total"
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
        btn_eliminar = QPushButton(QIcon("imagenes/eliminar.png"), "Eliminar")
        btn_eliminar.setStyleSheet("""
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
        btns_detalle.addWidget(btn_eliminar)
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

        # Botones navegación (azul claro)
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

        # Botones acción
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

    def setup_focus(self):
        self.proveedor.setFocus()
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
                # Aquí puedes llamar a la lógica de búsqueda y agregado de insumo
                print("Buscar insumo por texto o lanzar selección")
                return True
        return super().eventFilter(obj, event)
