from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QSpinBox, QComboBox
from models.paquete import Paquete
from models.paquete_producto import PaqueteProducto
from models.producto import Producto

class PaqueteFormDialog(QDialog):
    def __init__(self, parent=None, paquete=None, session=None):
        super().__init__(parent)
        self.setWindowTitle("Alta/Modificación de Paquete")
        self.setMinimumSize(900, 900)   # <-- AÑADÍ ESTO
        self.resize(900, 900) 
        self.session = session
        self.paquete = paquete
        self.productos_rel = []  # [(idproducto, orden, duracion)]
        self.init_ui()
        if paquete:
            self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.txt_nombre = QLineEdit()
        self.txt_descripcion = QLineEdit()
        self.spin_cant_ses = QSpinBox()
        self.spin_precio = QLineEdit()
        self.txt_obs = QLineEdit()
        layout.addWidget(QLabel("Nombre:"))
        layout.addWidget(self.txt_nombre)
        layout.addWidget(QLabel("Descripción:"))
        layout.addWidget(self.txt_descripcion)
        layout.addWidget(QLabel("Cantidad de sesiones:"))
        layout.addWidget(self.spin_cant_ses)
        layout.addWidget(QLabel("Precio total:"))
        layout.addWidget(self.spin_precio)
        layout.addWidget(QLabel("Observaciones:"))
        layout.addWidget(self.txt_obs)

        layout.addWidget(QLabel("Productos del paquete:"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Producto", "Orden", "Duración", "Eliminar"])
        layout.addWidget(self.table)

        btn_add_prod = QPushButton("Agregar producto")
        btn_add_prod.clicked.connect(self.add_producto_dialog)
        layout.addWidget(btn_add_prod)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Aceptar")
        btn_cancel = QPushButton("Cancelar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def load_data(self):
        self.txt_nombre.setText(self.paquete.nombre)
        self.txt_descripcion.setText(self.paquete.descripcion or "")
        self.spin_cant_ses.setValue(self.paquete.cantidadsesiones or 0)
        self.spin_precio.setText(str(float(self.paquete.preciototal)))
        self.txt_obs.setText(self.paquete.observaciones or "")

        productos = self.session.query(PaqueteProducto).filter_by(idpaquete=self.paquete.idpaquete).all()
        self.productos_rel = [(p.idproducto, p.sesionorden, p.duracionsesion) for p in productos]
        self.refresh_table()

    def refresh_table(self):
        self.table.setRowCount(len(self.productos_rel))
        for i, (idprod, orden, duracion) in enumerate(self.productos_rel):
            prod = self.session.query(Producto).get(idprod)
            self.table.setItem(i, 0, QTableWidgetItem(prod.nombre if prod else str(idprod)))
            self.table.setItem(i, 1, QTableWidgetItem(str(orden)))
            self.table.setItem(i, 2, QTableWidgetItem(str(duracion)))
            btn_del = QPushButton("Eliminar")
            btn_del.clicked.connect(lambda _, idx=i: self.del_producto(idx))
            self.table.setCellWidget(i, 3, btn_del)

    def add_producto_dialog(self):
        dlg = AddProductoAlPaqueteDialog(self, self.session)
        if dlg.exec_() == dlg.Accepted:
            idprod, orden, duracion = dlg.get_values()
            if any(pr[0] == idprod and pr[1] == orden for pr in self.productos_rel):
                QMessageBox.warning(self, "Duplicado", "Este producto ya está en el paquete con el mismo orden.")
                return
            self.productos_rel.append((idprod, orden, duracion))
            self.refresh_table()

    def del_producto(self, idx):
        del self.productos_rel[idx]
        self.refresh_table()

    def accept(self):
        if not self.txt_nombre.text().strip():
            QMessageBox.warning(self, "Error", "Debe ingresar un nombre.")
            return
        if not self.productos_rel:
            QMessageBox.warning(self, "Error", "El paquete debe tener al menos un producto.")
            return

        # Guardar Paquete
        if not self.paquete:
            self.paquete = Paquete()
            self.session.add(self.paquete)
        self.paquete.nombre = self.txt_nombre.text()
        self.paquete.descripcion = self.txt_descripcion.text()
        self.paquete.cantidadsesiones = self.spin_cant_ses.value()
        self.paquete.preciototal = float(self.spin_precio.text())
        self.paquete.observaciones = self.txt_obs.text()
        self.session.commit()

        # Guardar PaqueteProducto
        self.session.query(PaqueteProducto).filter_by(idpaquete=self.paquete.idpaquete).delete()
        for idprod, orden, duracion in self.productos_rel:
            rel = PaqueteProducto(
                idpaquete=self.paquete.idpaquete,
                idproducto=idprod,
                sesionorden=orden,
                duracionsesion=duracion
            )
            self.session.add(rel)
        self.session.commit()
        super().accept()

# ---- Dialogo simple para agregar producto ----
class AddProductoAlPaqueteDialog(QDialog):
    def __init__(self, parent, session):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Agregar producto al paquete")
        layout = QVBoxLayout(self)

        self.cmb_producto = QComboBox()
        self.productos = self.session.query(Producto).all()
        for p in self.productos:
            self.cmb_producto.addItem(p.nombre, p.idproducto)
        layout.addWidget(QLabel("Producto:"))
        layout.addWidget(self.cmb_producto)

        self.spin_orden = QSpinBox()
        self.spin_orden.setMinimum(1)
        layout.addWidget(QLabel("Orden en el paquete:"))
        layout.addWidget(self.spin_orden)

        self.spin_duracion = QSpinBox()
        self.spin_duracion.setMinimum(1)
        layout.addWidget(QLabel("Duración de la sesión:"))
        layout.addWidget(self.spin_duracion)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Aceptar")
        btn_cancel = QPushButton("Cancelar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def get_values(self):
        idprod = self.cmb_producto.currentData()
        orden = self.spin_orden.value()
        duracion = self.spin_duracion.value()
        return idprod, orden, duracion
