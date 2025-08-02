import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel, QMessageBox
)
from PyQt5.QtCore import Qt
from utils.db import SessionLocal
# Acá cambiás por el modelo que corresponde
from models.clinica import Clinica
from PyQt5.QtGui import QIcon


class ABMClinica(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ABM de Clinica")
        self.setWindowIcon(QIcon("imagenes/logo.ico"))
        self.setGeometry(400, 150, 720, 480)
        self.setStyleSheet("""
            QMainWindow {background-color: #eaf1fb;}
            QLabel {font-size: 17px; color: #175ca4;}
            QPushButton {font-size: 16px; font-weight: bold; border-radius: 8px; padding: 6px 22px;}
            QPushButton#agregar {background: #198754; color: white;}
            QPushButton#agregar:disabled {background: #343a40; color: #bbb;}
            QPushButton#editar {background: #0d6efd; color: white;}
            QPushButton#editar:disabled {background: #343a40; color: #bbb;}
            QPushButton#eliminar {background: #dc3545; color: white;}
            QPushButton#eliminar:disabled {background: #343a40; color: #bbb;}
            QPushButton#limpiar {background: #495057; color: #fff;}
            QPushButton#limpiar:disabled {background: #343a40; color: #bbb;}
            QLineEdit {font-size: 16px; padding: 6px; border-radius: 6px;}
        """)

        main_layout = QVBoxLayout()
        widget = QWidget()
        widget.setLayout(main_layout)
        self.setCentralWidget(widget)

        # Búsqueda
        busq_layout = QHBoxLayout()
        busq_layout.addWidget(QLabel("Buscar:"))
        self.input_buscar = QLineEdit()
        self.input_buscar.setPlaceholderText("Escriba para filtrar...")
        self.input_buscar.textChanged.connect(self.filtrar_tabla)
        busq_layout.addWidget(self.input_buscar)
        main_layout.addLayout(busq_layout)

        # Tabla (ajustá columnas según la clinica)
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self.seleccionar_fila)
        main_layout.addWidget(self.table)

        # Formulario (agregá/quita campos según clinica)
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Nombre:"))
        self.input_nombre = QLineEdit()
        form_layout.addWidget(self.input_nombre)
        form_layout.addWidget(QLabel("Dirección:"))
        self.input_direccion = QLineEdit()
        form_layout.addWidget(self.input_direccion)
        form_layout.addWidget(QLabel("Teléfono:"))
        self.input_telefono = QLineEdit()
        form_layout.addWidget(self.input_telefono)
        main_layout.addLayout(form_layout)

        # Botones
        btn_layout = QHBoxLayout()
        self.btn_agregar = QPushButton("Agregar")
        self.btn_agregar.setObjectName("agregar")
        self.btn_editar = QPushButton("Editar")
        self.btn_editar.setObjectName("editar")
        self.btn_eliminar = QPushButton("Eliminar")
        self.btn_eliminar.setObjectName("eliminar")
        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_limpiar.setObjectName("limpiar")
        btn_layout.addWidget(self.btn_agregar)
        btn_layout.addWidget(self.btn_editar)
        btn_layout.addWidget(self.btn_eliminar)
        btn_layout.addWidget(self.btn_limpiar)
        main_layout.addLayout(btn_layout)

        # --- ENTER AVANZA AL SIGUIENTE ---
        self.input_nombre.keyPressEvent = self.enter_siguiente(self.input_nombre, self.input_direccion)
        self.input_direccion.keyPressEvent = self.enter_siguiente(self.input_direccion, self.input_telefono)
        self.input_telefono.keyPressEvent = self.enter_siguiente(self.input_telefono, self.btn_agregar)

        # Eventos
        self.btn_agregar.clicked.connect(self.agregar)
        self.btn_editar.clicked.connect(self.editar)
        self.btn_eliminar.clicked.connect(self.eliminar)
        self.btn_limpiar.clicked.connect(self.limpiar_formulario)

        self.clinica_seleccionada = None
        self.cargar_clinicaes()

    def cargar_clinicaes(self):
        self.table.setRowCount(0)
        session = SessionLocal()
        clinicaes = session.query(Clinica).all()
        session.close()
        for i, e in enumerate(clinicaes):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(str(e.idclinica)))
            self.table.setItem(i, 1, QTableWidgetItem(e.nombre))

    def filtrar_tabla(self):
        filtro = self.input_buscar.text().lower()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            self.table.setRowHidden(row, filtro not in item.text().lower())

    def limpiar_formulario(self):
        self.input_nombre.clear()
        self.clinica_seleccionada = None
        self.table.clearSelection()
        self.btn_agregar.setEnabled(True)
        self.btn_eliminar.setEnabled(True)
        self.btn_editar.setEnabled(False)
        self.btn_limpiar.setEnabled(True)

    def seleccionar_fila(self, row, col):
        self.clinica_seleccionada = int(self.table.item(row, 0).text())
        self.input_nombre.setText(self.table.item(row, 1).text())
        self.btn_agregar.setEnabled(False)
        self.btn_eliminar.setEnabled(True)
        self.btn_editar.setEnabled(True)
        self.btn_limpiar.setEnabled(False)

    def agregar(self):
        nombre = self.input_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Campo obligatorio", "Debe completar el nombre.")
            return
        session = SessionLocal()
        nueva = Clinica(nombre=nombre)
        session.add(nueva)
        session.commit()
        session.close()
        self.limpiar_formulario()
        self.cargar_clinicaes()
        QMessageBox.information(self, "OK", "Registro agregado.")

    def editar(self):
        if not self.clinica_seleccionada:
            QMessageBox.warning(self, "Seleccionar", "Seleccione un registro para editar.")
            return
        nombre = self.input_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Campo obligatorio", "Debe completar el nombre.")
            return
        session = SessionLocal()
        clinica = session.query(Clinica).filter_by(idclinica=self.clinica_seleccionada).first()
        if clinica:
            clinica.nombre = nombre
            session.commit()
        session.close()
        self.limpiar_formulario()
        self.cargar_clinicaes()
        QMessageBox.information(self, "OK", "Registro editado.")

    def eliminar(self):
        if not self.clinica_seleccionada:
            QMessageBox.warning(self, "Seleccionar", "Seleccione un registro para eliminar.")
            return
        session = SessionLocal()
        clinica = session.query(Clinica).filter_by(idclinica=self.clinica_seleccionada).first()
        if clinica:
            session.delete(clinica)  # Borrado físico
            session.commit()
        session.close()
        self.limpiar_formulario()
        self.cargar_clinicaes()
        QMessageBox.information(self, "OK", "Registro eliminado.")

    def enter_siguiente(self, actual, siguiente):
        def handler(event):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                        siguiente.setFocus()
            else:
                        type(actual).keyPressEvent(actual, event)
        return handler

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ABMClinica()
    win.show()
    sys.exit(app.exec_())
