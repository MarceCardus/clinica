from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize
from .producto_form import ProductoFormDialog
from models.producto import Producto
from utils.db import SessionLocal
from sqlalchemy.orm import joinedload
from sqlalchemy import text

class ABMProducto(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ABM de Productos")
        
        self.init_ui()
        self.load_data()
        
    def init_ui(self):
        layout = QVBoxLayout(self)

        # — Grilla con 8 columnas (incluye Editar y Eliminar) —
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Descripción", "Duración",
            "Precio", "Tipo", "Requiere rec.", "Días rec.", "Editar", "Eliminar"
        ])

        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # — Botón Agregar abajo —
        btn_layout = QHBoxLayout()
        btn_add = QPushButton()
        btn_add.setIcon(QIcon("imagenes/agregar.png"))
        btn_add.setIconSize(QSize(80,80))
        btn_add.setFlat(True)
        btn_add.setToolTip("Agregar producto")
        btn_add.clicked.connect(self.add_producto)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_add)
        layout.addLayout(btn_layout)

    def load_data(self):
        
        session = SessionLocal()
        prods = session.query(Producto).options(joinedload(Producto.tipoproducto)).all()
        session.close()

        self.table.setRowCount(len(prods))
        for i, p in enumerate(prods):
            # columnas de datos
            self.table.setItem(i, 0, QTableWidgetItem(str(p.idproducto)))
            self.table.setItem(i, 1, QTableWidgetItem(p.nombre))
            self.table.setItem(i, 2, QTableWidgetItem(p.descripcion or ""))
            self.table.setItem(i, 3, QTableWidgetItem(str(p.duracion or "")))
            self.table.setItem(i, 4, QTableWidgetItem(f"{p.precio:,.0f}".replace(',', '.')))
            self.table.setItem(i, 5, QTableWidgetItem(p.tipoproducto.nombre if p.tipoproducto else ""))
            self.table.setItem(i, 6, QTableWidgetItem("Sí" if p.requiere_recordatorio else "No"))
            self.table.setItem(i, 7, QTableWidgetItem(str(p.dias_recordatorio or "")))
            # botón Editar
            btn_e = QPushButton()
            btn_e.setIcon(QIcon("imagenes/editar.png"))
            btn_e.setIconSize(QSize(24,24))
            btn_e.setFlat(True)
            btn_e.clicked.connect(lambda _, pid=p.idproducto: self.edit_producto(pid))
            self.table.setCellWidget(i, 8, btn_e)

            # botón Eliminar
            btn_d = QPushButton()
            btn_d.setIcon(QIcon("imagenes/eliminar.png"))
            btn_d.setIconSize(QSize(24,24))
            btn_d.setFlat(True)
            btn_d.clicked.connect(lambda _, pid=p.idproducto: self.delete_producto(pid))
            self.table.setCellWidget(i, 9, btn_d)

    def add_producto(self):
        session = SessionLocal()
        dlg = ProductoFormDialog(self, None, session)
        if dlg.exec_() == dlg.Accepted:
            session.close()
            self.load_data()
        else:
            session.close()

    def edit_producto(self, prod_id):
        session = SessionLocal()
        prod = session.query(Producto).get(prod_id)
        dlg = ProductoFormDialog(self, prod, session)
        if dlg.exec_() == dlg.Accepted:
            session.close()
            self.load_data()
        else:
            session.close()

    def delete_producto(self, prod_id):
        if QMessageBox.question(
            self, "Confirmar", "¿Eliminar este producto?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        session = SessionLocal()
        # Verifica en ventas
        tiene_ventas = session.execute(
            text("SELECT 1 FROM ventadetalle WHERE idproducto = :pid LIMIT 1"),
            {'pid': prod_id}
        ).first() is not None
        # Verifica en citas
        tiene_citas = session.execute(
            text("SELECT 1 FROM cita WHERE idproducto = :pid LIMIT 1"),
            {'pid': prod_id}
        ).first() is not None

        if tiene_ventas or tiene_citas:
            session.close()
            QMessageBox.warning(
                self, "No permitido",
                "No se puede eliminar el producto porque ya fue utilizado en ventas o citas."
            )
            return

        # Si no tiene usos, elimina normalmente
        prod = session.query(Producto).filter_by(idproducto=prod_id).first()
        if prod:
            session.delete(prod)
            session.commit()
        session.close()
        self.cargar_productos()
        QMessageBox.information(self, "OK", "Producto eliminado.")

        session = SessionLocal()
        prod = session.query(Producto).get(prod_id)
        session.delete(prod)
        session.commit()
        session.close()
        self.load_data()
