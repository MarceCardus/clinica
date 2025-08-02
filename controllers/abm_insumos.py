import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QWidget, QLabel, QLineEdit, QComboBox, QMessageBox
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
from utils.db import SessionLocal
from models.insumo import Insumo

ICON_PATH = os.path.join(os.path.dirname(__file__), 'icons')

TIPOS = [
    "MEDICAMENTO",
    "DESCARTABLE",
    "REACTIVO",
    "ANTIBIOTICO"
]
CATEGORIAS = [
    "CONSUMO_INTERNO",
    "USO_PROCEDIMIENTO"
]

class ABMInsumos(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ABM de Insumos")
        self.setMinimumWidth(600)
        self.session = SessionLocal()
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Filtros
        filtro_widget = QWidget()
        filtro_layout = QHBoxLayout(filtro_widget)
        self.filtro_nombre = QLineEdit()
        self.filtro_nombre.setPlaceholderText("🔍 Buscar por nombre...")
        self.filtro_nombre.textChanged.connect(self.load_data)
        self.filtro_tipo = QComboBox()
        self.filtro_tipo.addItem("")  # Todos
        self.filtro_tipo.addItems(TIPOS)
        self.filtro_tipo.setPlaceholderText("Filtrar por tipo")
        self.filtro_tipo.currentIndexChanged.connect(self.load_data)
        filtro_layout.addWidget(QLabel("Filtro:"))
        filtro_layout.addWidget(self.filtro_nombre)
        filtro_layout.addWidget(self.filtro_tipo)
        filtro_layout.addStretch()
        layout.addWidget(filtro_widget)

        # Grilla de Insumos
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Tipo", "Categoría", "Unidad", "Acciones"
        ])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # Botón agregar insumo
        self.btn_agregar = QPushButton(" Agregar insumo")
        self.btn_agregar.setIcon(QIcon(os.path.join(ICON_PATH, "add.png")))
        self.btn_agregar.setStyleSheet(
            "QPushButton { background-color: #198754; color: white; font-size: 16px; border-radius: 24px; padding: 12px 32px; }"
        )
        self.btn_agregar.clicked.connect(self.abrir_dialogo_agregar)

        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(self.btn_agregar)
        layout.addLayout(hbox)

        self.setLayout(layout)

    def load_data(self):
        self.table.setRowCount(0)
        nombre_filtro = self.filtro_nombre.text().strip().lower()
        tipo_filtro = self.filtro_tipo.currentText().strip().upper()

        insumos = self.session.query(Insumo).all()
        insumos = [
            i for i in insumos
            if (nombre_filtro in i.nombre.lower())
            and (tipo_filtro == "" or tipo_filtro == (i.tipo or "").upper())
        ]

        for insumo in insumos:
            row_pos = self.table.rowCount()
            self.table.insertRow(row_pos)
            self.table.setItem(row_pos, 0, QTableWidgetItem(str(insumo.idinsumo)))
            self.table.setItem(row_pos, 1, QTableWidgetItem(insumo.nombre or ""))
            self.table.setItem(row_pos, 2, QTableWidgetItem(insumo.tipo or ""))
            self.table.setItem(row_pos, 3, QTableWidgetItem(insumo.categoria or ""))
            self.table.setItem(row_pos, 4, QTableWidgetItem(insumo.unidad or ""))
            # Acciones
            widget = QWidget()
            h = QHBoxLayout(widget)
            btn_editar = QPushButton()
            btn_editar.setIcon(QIcon(os.path.join(ICON_PATH, "edit.png")))
            btn_editar.setToolTip("Editar")
            btn_editar.clicked.connect(lambda _, row=row_pos: self.abrir_dialogo_editar(row))
            btn_eliminar = QPushButton()
            btn_eliminar.setIcon(QIcon(os.path.join(ICON_PATH, "delete.png")))
            btn_eliminar.setToolTip("Eliminar")
            btn_eliminar.clicked.connect(lambda _, row=row_pos: self.eliminar_insumo(row))
            h.addWidget(btn_editar)
            h.addWidget(btn_eliminar)
            h.setContentsMargins(0,0,0,0)
            widget.setLayout(h)
            self.table.setCellWidget(row_pos, 5, widget)

    def abrir_dialogo_agregar(self):
        dialogo = FormularioInsumo(self.session, self)
        if dialogo.exec_() == QDialog.Accepted:
            self.load_data()

    def abrir_dialogo_editar(self, row):
        idinsumo = int(self.table.item(row, 0).text())
        insumo = self.session.query(Insumo).filter_by(idinsumo=idinsumo).first()
        dialogo = FormularioInsumo(self.session, self, insumo)
        if dialogo.exec_() == QDialog.Accepted:
            self.load_data()

    def eliminar_insumo(self, row):
        idinsumo = int(self.table.item(row, 0).text())
        if QMessageBox.question(self, "Eliminar", "¿Está seguro que desea eliminar este insumo?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            insumo = self.session.query(Insumo).filter_by(idinsumo=idinsumo).first()
            if insumo:
                self.session.delete(insumo)
                self.session.commit()
                self.load_data()

# --------- FORMULARIO MODAL DE INSUMO ---------
class FormularioInsumo(QDialog):
    def __init__(self, session, parent=None, insumo=None):
        super().__init__(parent)
        self.session = session
        self.insumo = insumo
        self.setWindowTitle("Editar Insumo" if insumo else "Agregar Insumo")
        self.setMinimumWidth(350)
        self.init_ui()
        if self.insumo:
            self.cargar_datos()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form_widget = QWidget()
        form_layout = QHBoxLayout()
        form_grid = QVBoxLayout()

        self.input_nombre = QLineEdit()
        self.input_tipo = QComboBox()
        self.input_tipo.addItems(TIPOS)
        self.input_categoria = QComboBox()
        self.input_categoria.addItems(CATEGORIAS)
        self.input_unidad = QLineEdit()

        # Layout sencillo y compacto
        grid = QVBoxLayout()
        grid.addWidget(QLabel("Nombre"));      grid.addWidget(self.input_nombre)
        grid.addWidget(QLabel("Tipo"));        grid.addWidget(self.input_tipo)
        grid.addWidget(QLabel("Categoría"));   grid.addWidget(self.input_categoria)
        grid.addWidget(QLabel("Unidad"));      grid.addWidget(self.input_unidad)
        form_widget.setLayout(grid)
        layout.addWidget(form_widget)

        botones = QHBoxLayout()
        self.btn_guardar = QPushButton("Guardar")
        self.btn_guardar.setIcon(QIcon(os.path.join(ICON_PATH, "save.png")))
        self.btn_guardar.clicked.connect(self.guardar)
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.clicked.connect(self.reject)
        botones.addStretch()
        botones.addWidget(self.btn_guardar)
        botones.addWidget(self.btn_cancelar)
        layout.addLayout(botones)

    def cargar_datos(self):
        self.input_nombre.setText(self.insumo.nombre or "")
        idx_tipo = self.input_tipo.findText(self.insumo.tipo or TIPOS[0])
        self.input_tipo.setCurrentIndex(idx_tipo if idx_tipo != -1 else 0)
        idx_categoria = self.input_categoria.findText(self.insumo.categoria or CATEGORIAS[0])
        self.input_categoria.setCurrentIndex(idx_categoria if idx_categoria != -1 else 0)
        self.input_unidad.setText(self.insumo.unidad or "")

    def guardar(self):
        nombre = self.input_nombre.text().strip()
        tipo = self.input_tipo.currentText()
        categoria = self.input_categoria.currentText()
        unidad = self.input_unidad.text().strip()

        if not nombre:
            QMessageBox.warning(self, "Error", "Debe ingresar un nombre para el insumo.")
            return

        if self.insumo is None:
            nuevo = Insumo(
                nombre=nombre,
                tipo=tipo,
                categoria=categoria,
                unidad=unidad
            )
            self.session.add(nuevo)
        else:
            self.insumo.nombre = nombre
            self.insumo.tipo = tipo
            self.insumo.categoria = categoria
            self.insumo.unidad = unidad

        self.session.commit()
        self.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ABMInsumos()
    window.show()
    sys.exit(app.exec_())
