import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel, QMessageBox, QTextEdit, QComboBox
)
from utils.db import SessionLocal
from models.profesional import Profesional
from models.agenda import Cita
from PyQt5.QtCore import Qt

class ABMProfesionales(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ABM de Profesionales")
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
        self.setGeometry(400, 150, 720, 480)
        self.setMinimumSize(720, 480)
        self.resize(720, 480)
        self.setCentralWidget(widget)

        # --- Búsqueda ---
        busq_layout = QHBoxLayout()
        busq_layout.addWidget(QLabel("Buscar:"))
        self.input_buscar = QLineEdit()
        self.input_buscar.setPlaceholderText("Filtrar profesionales...")
        self.input_buscar.textChanged.connect(self.filtrar_tabla)
        busq_layout.addWidget(self.input_buscar)
        main_layout.addLayout(busq_layout)

        # --- Tabla: Nombre completo + Documento ---
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Nombre Completo", "Documento", "Teléfono", "ID"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self.seleccionar_fila)
        self.table.setColumnHidden(3, True)  # Oculta la columna de ID

        from PyQt5.QtWidgets import QHeaderView
        # >>> Estas líneas son las nuevas para distribuir bien el espacio:
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Nombre Completo
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Documento
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Teléfono
        self.table.setMinimumHeight(200)  # Opcional, para que se vea menos apretado
        self.table.resizeColumnsToContents()  # Puedes dejarlo o quitarlo, según el resultado visual
        main_layout.addWidget(self.table)

        # --- Formulario (campos del modelo) ---
        form1 = QHBoxLayout()
        form2 = QHBoxLayout()
        form1.addWidget(QLabel("Nombre:"))
        self.input_nombre = QLineEdit()
        form1.addWidget(self.input_nombre)
        form1.addWidget(QLabel("Apellido:"))
        self.input_apellido = QLineEdit()
        form1.addWidget(self.input_apellido)
        form1.addWidget(QLabel("Documento:"))
        self.input_documento = QLineEdit()
        form1.addWidget(self.input_documento)
        form2.addWidget(QLabel("Matrícula:"))
        self.input_matricula = QLineEdit()
        form2.addWidget(self.input_matricula)
        form2.addWidget(QLabel("Teléfono:"))
        self.input_telefono = QLineEdit()
        form2.addWidget(self.input_telefono)
        form2.addWidget(QLabel("Email:"))
        self.input_email = QLineEdit()
        form2.addWidget(self.input_email)
        form2.addWidget(QLabel("Dirección:"))
        self.input_direccion = QLineEdit()
        form2.addWidget(self.input_direccion)
        main_layout.addLayout(form1)
        main_layout.addLayout(form2)

        # Observaciones
        obs_layout = QHBoxLayout()
        obs_layout.addWidget(QLabel("Observaciones:"))
        self.input_observaciones = QLineEdit()
        obs_layout.addWidget(self.input_observaciones)
        main_layout.addLayout(obs_layout)

        # Combo de estado
        estado_layout = QHBoxLayout()
        estado_layout.addWidget(QLabel("Estado:"))
        self.cbo_estado = QComboBox()
        self.cbo_estado.addItems(["Activo", "Inactivo"])
        estado_layout.addWidget(self.cbo_estado)
        main_layout.addLayout(estado_layout)

        # --- Botones ---
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
        self.input_nombre.keyPressEvent = self.enter_siguiente(self.input_nombre, self.input_apellido)
        self.input_apellido.keyPressEvent = self.enter_siguiente(self.input_apellido, self.input_documento)
        self.input_documento.keyPressEvent = self.enter_siguiente(self.input_documento, self.input_matricula)
        self.input_matricula.keyPressEvent = self.enter_siguiente(self.input_matricula, self.input_telefono)
        self.input_telefono.keyPressEvent = self.enter_siguiente(self.input_telefono, self.input_email)
        self.input_email.keyPressEvent = self.enter_siguiente(self.input_email, self.input_direccion)
        self.input_direccion.keyPressEvent = self.enter_siguiente(self.input_direccion, self.input_observaciones)
        self.input_observaciones.keyPressEvent = self.enter_siguiente(self.input_observaciones, self.btn_agregar)
        
        # --- Eventos ---
        self.btn_agregar.clicked.connect(self.agregar)
        self.btn_editar.clicked.connect(self.editar)
        self.btn_eliminar.clicked.connect(self.eliminar)
        self.btn_limpiar.clicked.connect(self.limpiar_formulario)

        self.profesional_seleccionado = None
        self.cargar_profesionales()

    def cargar_profesionales(self):
        self.table.setRowCount(0)
        session = SessionLocal()
        profesionales = session.query(Profesional).filter_by(estado=True).all()  # Solo activos
        session.close()
        for i, p in enumerate(profesionales):
            nombre_completo = f"{p.nombre} {p.apellido}".strip()
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(nombre_completo))
            self.table.setItem(i, 1, QTableWidgetItem(p.documento or ""))
            self.table.setItem(i, 2, QTableWidgetItem(p.telefono or ""))
            self.table.setItem(i, 3, QTableWidgetItem(str(p.idprofesional)))  # ID en columna 3

    def filtrar_tabla(self):
        filtro = self.input_buscar.text().lower()
        for row in range(self.table.rowCount()):
            visible = False
            for col in range(2):
                item = self.table.item(row, col)
                if filtro in (item.text() or "").lower():
                    visible = True
                    break
            self.table.setRowHidden(row, not visible)

    def limpiar_formulario(self):
        self.input_nombre.clear()
        self.input_apellido.clear()
        self.input_documento.clear()
        self.input_matricula.clear()
        self.input_telefono.clear()
        self.input_email.clear()
        self.input_direccion.clear()
        self.input_observaciones.clear()
        self.profesional_seleccionado = None
        self.table.clearSelection()
        self.btn_agregar.setEnabled(True)
        self.btn_eliminar.setEnabled(True)
        self.btn_editar.setEnabled(False)
        self.btn_limpiar.setEnabled(True)

    def seleccionar_fila(self, row, col):
        profesional_id_item = self.table.item(row, 3)
        if profesional_id_item is None:
            return
        profesional_id = int(profesional_id_item.text())
        session = SessionLocal()
        profesional = session.query(Profesional).filter_by(idprofesional=profesional_id).first()
        session.close()
        if profesional:
            self.profesional_seleccionado = profesional.idprofesional
            self.input_nombre.setText(profesional.nombre)
            self.input_apellido.setText(profesional.apellido)
            self.input_documento.setText(profesional.documento or "")
            self.input_matricula.setText(profesional.matricula or "")
            self.input_telefono.setText(profesional.telefono or "")
            self.input_email.setText(profesional.email or "")
            self.input_direccion.setText(profesional.direccion or "")
            self.input_observaciones.setText(profesional.observaciones or "")
            self.cbo_estado.setCurrentIndex(0 if profesional.estado else 1)
            self.btn_agregar.setEnabled(False)
            self.btn_eliminar.setEnabled(True)
            self.btn_editar.setEnabled(True)
            self.btn_limpiar.setEnabled(False)

    def agregar(self):
        nombre = self.input_nombre.text().strip()
        apellido = self.input_apellido.text().strip()
        documento = self.input_documento.text().strip()
        matricula = self.input_matricula.text().strip()
        telefono = self.input_telefono.text().strip()
        email = self.input_email.text().strip()
        direccion = self.input_direccion.text().strip()
        observaciones = self.input_observaciones.text().strip()
        estado = self.cbo_estado.currentText()  # Obtener el estado del combo
        if not nombre or not apellido:
            QMessageBox.warning(self, "Campos obligatorios", "Debe completar nombre y apellido.")
            return
        session = SessionLocal()
        nuevo = Profesional(
            nombre=nombre,
            apellido=apellido,
            documento=documento,
            matricula=matricula,
            telefono=telefono,
            email=email,
            direccion=direccion,
            observaciones=observaciones,
            estado=estado
        )
        session.add(nuevo)
        session.commit()
        session.close()
        self.limpiar_formulario()
        self.cargar_profesionales()
        QMessageBox.information(self, "OK", "Profesional agregado.")

    def editar(self):
        if not self.profesional_seleccionado:
            QMessageBox.warning(self, "Seleccionar", "Seleccione un profesional para editar.")
            return
        nombre = self.input_nombre.text().strip()
        apellido = self.input_apellido.text().strip()
        documento = self.input_documento.text().strip()
        matricula = self.input_matricula.text().strip()
        telefono = self.input_telefono.text().strip()
        email = self.input_email.text().strip()
        direccion = self.input_direccion.text().strip()
        observaciones = self.input_observaciones.text().strip()
        estado = self.cbo_estado.currentText()  # Obtener el estado del combo
        if not nombre or not apellido:
            QMessageBox.warning(self, "Campos obligatorios", "Debe completar nombre y apellido.")
            return
        session = SessionLocal()
        profesional = session.query(Profesional).filter_by(idprofesional=self.profesional_seleccionado).first()
        if profesional:
            profesional.nombre = nombre
            profesional.apellido = apellido
            profesional.documento = documento
            profesional.matricula = matricula
            profesional.telefono = telefono
            profesional.email = email
            profesional.direccion = direccion
            profesional.observaciones = observaciones
            profesional.estado = (estado == "Activo")  # Actualizar estado
            session.commit()
        session.close()
        self.limpiar_formulario()
        self.cargar_profesionales()
        QMessageBox.information(self, "OK", "Profesional editado.")

    def eliminar(self):
        if not self.profesional_seleccionado:
            QMessageBox.warning(self, "Seleccionar", "Seleccione un profesional para eliminar.")
            return
        session = SessionLocal()
        profesional = session.query(Profesional).filter_by(idprofesional=self.profesional_seleccionado).first()
        if profesional:
            profesional.estado = False
            session.commit()
        session.close()
        self.limpiar_formulario()
        self.cargar_profesionales()
        QMessageBox.information(self, "OK", "Profesional eliminado (lógico).")

        
    def enter_siguiente(self, actual, siguiente):
        def handler(event):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                    siguiente.setFocus()
            else:
                    type(actual).keyPressEvent(actual, event)
        return handler

       
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ABMProfesionales()
    win.show()
    sys.exit(app.exec_())
