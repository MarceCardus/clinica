import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel, QMessageBox
)
from utils.db import SessionLocal
from models.proveedor import Proveedor
from PyQt5.QtCore import Qt

class ABMProveedor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ABM de Proveedores")
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
        self.input_buscar.setPlaceholderText("Filtrar proveedores...")
        self.input_buscar.textChanged.connect(self.filtrar_tabla)
        busq_layout.addWidget(self.input_buscar)
        main_layout.addLayout(busq_layout)

        # Tabla
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "Teléfono", "RUC", "Email", "Dirección", "Contacto Alt."])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self.seleccionar_fila)
        main_layout.addWidget(self.table)

        # Formulario - Dos filas
        form_layout1 = QHBoxLayout()
        form_layout2 = QHBoxLayout()
        form_layout1.addWidget(QLabel("Nombre:"))
        self.input_nombre = QLineEdit()
        form_layout1.addWidget(self.input_nombre)
        form_layout1.addWidget(QLabel("Teléfono:"))
        self.input_telefono = QLineEdit()
        form_layout1.addWidget(self.input_telefono)
        form_layout1.addWidget(QLabel("RUC:"))
        self.input_ruc = QLineEdit()
        form_layout1.addWidget(self.input_ruc)
        form_layout2.addWidget(QLabel("Email:"))
        self.input_email = QLineEdit()
        form_layout2.addWidget(self.input_email)
        form_layout2.addWidget(QLabel("Dirección:"))
        self.input_direccion = QLineEdit()
        form_layout2.addWidget(self.input_direccion)
        form_layout2.addWidget(QLabel("Contacto alt.:"))
        self.input_contacto_alt = QLineEdit()
        form_layout2.addWidget(self.input_contacto_alt)
        main_layout.addLayout(form_layout1)
        main_layout.addLayout(form_layout2)

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
        self.input_nombre.keyPressEvent = self.enter_siguiente(self.input_nombre, self.input_telefono)
        self.input_telefono.keyPressEvent = self.enter_siguiente(self.input_telefono, self.input_ruc)
        self.input_ruc.keyPressEvent = self.enter_siguiente(self.input_ruc, self.input_email)
        self.input_email.keyPressEvent = self.enter_siguiente(self.input_email, self.input_direccion)
        self.input_direccion.keyPressEvent = self.enter_siguiente(self.input_direccion, self.input_contacto_alt)
        self.input_contacto_alt.keyPressEvent = self.enter_siguiente(self.input_contacto_alt, self.btn_agregar)

        # Eventos
        self.btn_agregar.clicked.connect(self.agregar)
        self.btn_editar.clicked.connect(self.editar)
        self.btn_eliminar.clicked.connect(self.eliminar)
        self.btn_limpiar.clicked.connect(self.limpiar_formulario)

        self.proveedor_seleccionado = None
        self.cargar_proveedores()

    def cargar_proveedores(self):
        self.table.setRowCount(0)
        session = SessionLocal()
        proveedores = session.query(Proveedor).filter_by(estado=True).all()  # Solo activos
        session.close()
        for i, p in enumerate(proveedores):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(str(p.idproveedor)))
            self.table.setItem(i, 1, QTableWidgetItem(p.nombre))
            self.table.setItem(i, 2, QTableWidgetItem(p.telefono or ""))
            self.table.setItem(i, 3, QTableWidgetItem(p.ruc or ""))
            self.table.setItem(i, 4, QTableWidgetItem(p.email or ""))
            self.table.setItem(i, 5, QTableWidgetItem(p.direccion or ""))

    def filtrar_tabla(self):
        filtro = self.input_buscar.text().lower()
        for row in range(self.table.rowCount()):
            visible = False
            for col in range(1, 7):  # Buscar en todas las columnas menos ID
                item = self.table.item(row, col)
                if filtro in (item.text() or "").lower():
                    visible = True
                    break
            self.table.setRowHidden(row, not visible)

    def limpiar_formulario(self):
        self.input_nombre.clear()
        self.input_telefono.clear()
        self.input_ruc.clear()
        self.input_email.clear()
        self.input_direccion.clear()
        self.input_contacto_alt.clear()
        self.proveedor_seleccionado = None
        self.table.clearSelection()
        self.btn_agregar.setEnabled(True)
        self.btn_eliminar.setEnabled(True)
        self.btn_editar.setEnabled(False)
        self.btn_limpiar.setEnabled(True)

    def seleccionar_fila(self, row, col):
        self.proveedor_seleccionado = int(self.table.item(row, 0).text())
        self.input_nombre.setText(self.table.item(row, 1).text())
        self.input_telefono.setText(self.table.item(row, 2).text())
        self.input_ruc.setText(self.table.item(row, 3).text())
        self.input_email.setText(self.table.item(row, 4).text())
        self.input_direccion.setText(self.table.item(row, 5).text())
        self.btn_agregar.setEnabled(False)
        self.btn_eliminar.setEnabled(True)
        self.btn_editar.setEnabled(True)
        self.btn_limpiar.setEnabled(False)
       
    def agregar(self):
        nombre = self.input_nombre.text().strip()
        telefono = self.input_telefono.text().strip()
        ruc = self.input_ruc.text().strip()
        email = self.input_email.text().strip()
        direccion = self.input_direccion.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Campo obligatorio", "Debe completar el nombre.")
            return
        session = SessionLocal()
        nuevo = Proveedor(
            nombre=nombre,
            telefono=telefono,
            ruc=ruc,
            email=email,
            direccion=direccion,
            estado=True
        )
        session.add(nuevo)
        session.commit()
        session.close()
        self.limpiar_formulario()
        self.cargar_proveedores()
        QMessageBox.information(self, "OK", "Proveedor agregado.")

    def editar(self):
        if not self.proveedor_seleccionado:
            QMessageBox.warning(self, "Seleccionar", "Seleccione un proveedor para editar.")
            return
        nombre = self.input_nombre.text().strip()
        telefono = self.input_telefono.text().strip()
        ruc = self.input_ruc.text().strip()
        email = self.input_email.text().strip()
        direccion = self.input_direccion.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Campo obligatorio", "Debe completar el nombre.")
            return
        session = SessionLocal()
        prov = session.query(Proveedor).filter_by(idproveedor=self.proveedor_seleccionado).first()
        if prov:
            prov.nombre = nombre
            prov.telefono = telefono
            prov.ruc = ruc
            prov.email = email
            prov.direccion = direccion
            session.commit()
        session.close()
        self.limpiar_formulario()
        self.cargar_proveedores()
        QMessageBox.information(self, "OK", "Proveedor editado.")

    def eliminar(self):
        if not self.proveedor_seleccionado:
            QMessageBox.warning(self, "Seleccionar", "Seleccione un proveedor para eliminar.")
            return
        session = SessionLocal()
        prov = session.query(Proveedor).filter_by(idproveedor=self.proveedor_seleccionado).first()
        if prov:
            prov.estado = False  # Baja lógica
            session.commit()
        session.close()
        self.limpiar_formulario()
        self.cargar_proveedores()
        QMessageBox.information(self, "OK", "Proveedor eliminado (lógico).")

    def enter_siguiente(self, actual, siguiente):
        def handler(event):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                        siguiente.setFocus()
            else:
                        type(actual).keyPressEvent(actual, event)
        return handler

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ABMProveedor()
    win.show()
    sys.exit(app.exec_())
