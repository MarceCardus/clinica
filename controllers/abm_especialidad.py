import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel, QMessageBox
)
from PyQt5.QtCore import Qt
from utils.db import SessionLocal
from models.especialidad import Especialidad
from PyQt5.QtCore import Qt

class ABMEspecialidad(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ABM de Especialidades")
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
        self.input_buscar.setPlaceholderText("Escriba para filtrar especialidades...")
        self.input_buscar.textChanged.connect(self.filtrar_tabla)
        busq_layout.addWidget(self.input_buscar)
        main_layout.addLayout(busq_layout)

        # Tabla
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self.seleccionar_especialidad)
        main_layout.addWidget(self.table)

        # Formulario simple
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Nombre:"))
        self.input_nombre = QLineEdit()
        self.input_nombre.setPlaceholderText("Nombre de la especialidad")
        form_layout.addWidget(self.input_nombre)
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
        self.input_nombre.keyPressEvent = self.enter_siguiente(self.input_nombre, self.btn_agregar)

        # Eventos
        self.btn_agregar.clicked.connect(self.agregar)
        self.btn_editar.clicked.connect(self.editar)
        self.btn_eliminar.clicked.connect(self.eliminar)
        self.btn_limpiar.clicked.connect(self.limpiar_formulario)

        self.especialidad_seleccionada = None
        self.cargar_especialidades()

    def cargar_especialidades(self):
        self.table.setRowCount(0)
        session = SessionLocal()
        especialidades = session.query(Especialidad).all()
        session.close()
        for i, esp in enumerate(especialidades):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(str(esp.idespecialidad)))
            self.table.setItem(i, 1, QTableWidgetItem(esp.nombre))

    def filtrar_tabla(self):
        filtro = self.input_buscar.text().lower()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            self.table.setRowHidden(row, filtro not in item.text().lower())

    def limpiar_formulario(self):
        self.input_nombre.clear()
        self.especialidad_seleccionada = None
        self.table.clearSelection()
        self.btn_agregar.setEnabled(True)
        self.btn_eliminar.setEnabled(True)
        self.btn_editar.setEnabled(False)
        self.btn_limpiar.setEnabled(True)

    def seleccionar_especialidad(self, row, col):
        self.especialidad_seleccionada = int(self.table.item(row, 0).text())
        self.input_nombre.setText(self.table.item(row, 1).text())
        self.btn_agregar.setEnabled(False)
        self.btn_eliminar.setEnabled(True)
        self.btn_editar.setEnabled(True)
        self.btn_limpiar.setEnabled(True)

    def agregar(self):
        nombre = self.input_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Campo obligatorio", "Debe completar el nombre.")
            return
        session = SessionLocal()
        nueva = Especialidad(nombre=nombre)
        session.add(nueva)
        session.commit()
        session.close()
        self.limpiar_formulario()
        self.cargar_especialidades()
        QMessageBox.information(self, "OK", "Especialidad agregada.")

    def editar(self):
        if not self.especialidad_seleccionada:
            QMessageBox.warning(self, "Seleccionar", "Seleccione una especialidad para editar.")
            return
        nombre = self.input_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Campo obligatorio", "Debe completar el nombre.")
            return
        session = SessionLocal()
        esp = session.query(Especialidad).filter_by(idespecialidad=self.especialidad_seleccionada).first()
        if esp:
            esp.nombre = nombre
            session.commit()
        session.close()
        self.limpiar_formulario()
        self.cargar_especialidades()
        QMessageBox.information(self, "OK", "Especialidad editada.")

    def eliminar(self):
        if not self.especialidad_seleccionada:
            QMessageBox.warning(self, "Seleccionar", "Seleccione una especialidad para eliminar.")
            return

        session = SessionLocal()
        # IMPORTANTE: Importá el modelo Producto si no lo tenés ya
        from models.producto import Producto

        # Chequeo si hay productos asociados
        count = session.query(Producto).filter_by(idespecialidad=self.especialidad_seleccionada).count()
        if count > 0:
            session.close()
            QMessageBox.critical(self, "No permitido", 
                "No se puede eliminar la especialidad porque tiene productos asociados.")
            return

        esp = session.query(Especialidad).filter_by(idespecialidad=self.especialidad_seleccionada).first()
        if esp:
            session.delete(esp)  # Borrado físico (NO lógico)
            session.commit()
        session.close()
        self.limpiar_formulario()
        self.cargar_especialidades()
        QMessageBox.information(self, "OK", "Especialidad eliminada.")


    def enter_siguiente(self, actual, siguiente):
        def handler(event):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                        siguiente.setFocus()
            else:
                        type(actual).keyPressEvent(actual, event)
        return handler

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ABMEspecialidad()
    win.show()
    sys.exit(app.exec_())
