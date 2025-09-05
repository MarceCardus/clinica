import sys, os, pathlib
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QPushButton, QTextEdit, QCheckBox,
    QMessageBox, QHeaderView, QAbstractItemView
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QSize
from sqlalchemy import func, exists
from sqlalchemy.exc import IntegrityError
from utils.db import SessionLocal
from models.aparato import Aparato

def resource_path(*parts):
    here = pathlib.Path(__file__).resolve().parent
    for p in [
        here / "imagenes" / pathlib.Path(*parts),
        pathlib.Path(os.getcwd()) / "imagenes" / pathlib.Path(*parts),
        here.parent / "imagenes" / pathlib.Path(*parts),
        pathlib.Path(getattr(sys, "_MEIPASS", "")) / "imagenes" / pathlib.Path(*parts)
    ]:
        if p and p.exists():
            return str(p)
    return ""

class ABMAparatos(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ABM de Aparatos")
        self.setMinimumWidth(900)
        self.session = SessionLocal()
        self._ui()
        self.load_data()

    def _ui(self):
        layout = QVBoxLayout(self)

        filtros = QWidget(); f = QHBoxLayout(filtros)
        self.filtro = QLineEdit(); self.filtro.setPlaceholderText("🔍 Buscar por nombre / marca / modelo…")
        self.filtro.textChanged.connect(self.load_data)
        f.addWidget(QLabel("Filtro:")); f.addWidget(self.filtro); f.addStretch()
        layout.addWidget(filtros)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["ID","Nombre","Marca","Modelo","Nº Serie","Activo","Acciones"]
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemDoubleClicked.connect(lambda *_: self.editar(self.table.currentRow()))
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        btn = QPushButton(" Agregar aparato")
        ico = resource_path("agregar.png")
        if ico: btn.setIcon(QIcon(ico))
        btn.setIconSize(QSize(48,48))
        btn.clicked.connect(self.agregar)
        h = QHBoxLayout(); h.addStretch(); h.addWidget(btn)
        layout.addLayout(h)

    def load_data(self):
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(0)
            t = (self.filtro.text() or "").strip().lower()
            q = self.session.query(Aparato)
            if t:
                like = f"%{t}%"
                q = q.filter(
                    func.lower(Aparato.nombre).like(like) |
                    func.lower(Aparato.marca).like(like) |
                    func.lower(Aparato.modelo).like(like) |
                    func.lower(Aparato.nro_serie).like(like)
                )
            rows = q.order_by(Aparato.nombre.asc()).all()
            self.table.setRowCount(len(rows))
            for r,a in enumerate(rows):
                self.table.setItem(r,0,QTableWidgetItem(str(a.idaparato)))
                self.table.setItem(r,1,QTableWidgetItem(a.nombre or ""))
                self.table.setItem(r,2,QTableWidgetItem(a.marca or ""))
                self.table.setItem(r,3,QTableWidgetItem(a.modelo or ""))
                self.table.setItem(r,4,QTableWidgetItem(a.nro_serie or ""))
                it = QTableWidgetItem("Sí" if a.activo else "No"); it.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r,5,it)

                cell = QWidget(); h = QHBoxLayout(cell); h.setContentsMargins(0,0,0,0)
                b1 = QPushButton(); ic1 = resource_path("editar.png")
                if ic1:
                    b1.setIcon(QIcon(ic1))
                else:
                    b1.setText("✏")
                b1.setFixedSize(QSize(30,26)); b1.clicked.connect(lambda _, row=r: self.editar(row))
                b2 = QPushButton(); ic2 = resource_path("eliminar.png")
                if ic2:
                    b2.setIcon(QIcon(ic2))
                else:
                    b2.setText("🗑")
                b2.setFixedSize(QSize(30,26)); b2.clicked.connect(lambda _, row=r: self.eliminar(row))
                h.addWidget(b1); h.addWidget(b2)
                self.table.setCellWidget(r,6,cell)
        finally:
            self.table.setUpdatesEnabled(True)

    def _row_id(self, row):
        it = self.table.item(row,0)
        return int(it.text()) if it and it.text().isdigit() else -1

    def agregar(self):
        dlg = FormAparato(self.session, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def editar(self, row):
        _id = self._row_id(row)
        if _id < 0: return
        a = self.session.query(Aparato).get(_id)
        if not a: return
        dlg = FormAparato(self.session, self, a)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def eliminar(self, row):
        _id = self._row_id(row)
        if _id < 0: return
        a = self.session.query(Aparato).get(_id)
        if not a: return
        if QMessageBox.question(self, "Eliminar",
            "¿Seguro que desea eliminar el aparato?",
            QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            self.session.delete(a)
            self.session.commit()
            self.load_data()
        except IntegrityError:
            self.session.rollback()
            QMessageBox.warning(self, "No se puede eliminar",
                                "Hay sesiones que referencian este aparato.")

class FormAparato(QDialog):
    def __init__(self, session, parent=None, aparato: Aparato=None):
        super().__init__(parent)
        self.session = session
        self.aparato = aparato
        self.setWindowTitle("Editar aparato" if aparato else "Agregar aparato")
        self.setMinimumWidth(520)
        self._ui()
        if self.aparato: self._cargar()

    def _ui(self):
        layout = QVBoxLayout(self)
        self.txt_nombre = QLineEdit()
        self.txt_marca  = QLineEdit()
        self.txt_modelo = QLineEdit()
        self.txt_serie  = QLineEdit()
        self.txt_desc   = QTextEdit()
        self.chk_activo = QCheckBox("Activo"); self.chk_activo.setChecked(True)

        box = QVBoxLayout()
        box.addWidget(QLabel("Nombre")); box.addWidget(self.txt_nombre)
        box.addWidget(QLabel("Marca"));  box.addWidget(self.txt_marca)
        box.addWidget(QLabel("Modelo")); box.addWidget(self.txt_modelo)
        box.addWidget(QLabel("Nº de serie")); box.addWidget(self.txt_serie)
        box.addWidget(QLabel("Descripción")); box.addWidget(self.txt_desc)
        box.addWidget(self.chk_activo)

        cont = QWidget(); cont.setLayout(box)
        layout.addWidget(cont)

        h = QHBoxLayout()
        b1 = QPushButton("Guardar"); b1.clicked.connect(self.guardar)
        b2 = QPushButton("Cancelar"); b2.clicked.connect(self.reject)
        h.addStretch(); h.addWidget(b1); h.addWidget(b2)
        layout.addLayout(h)

    def _cargar(self):
        a = self.aparato
        self.txt_nombre.setText(a.nombre or "")
        self.txt_marca.setText(a.marca or "")
        self.txt_modelo.setText(a.modelo or "")
        self.txt_serie.setText(a.nro_serie or "")
        self.txt_desc.setPlainText(a.descripcion or "")
        self.chk_activo.setChecked(bool(a.activo))

    def guardar(self):
        nombre = (self.txt_nombre.text() or "").strip()
        if not nombre:
            QMessageBox.warning(self, "Validación", "Ingrese el nombre.")
            return

        q = self.session.query(Aparato).filter(func.lower(Aparato.nombre)==nombre.lower())
        if self.aparato is not None:
            q = q.filter(Aparato.idaparato != self.aparato.idaparato)
        if self.session.query(q.exists()).scalar():
            QMessageBox.warning(self, "Validación", "Ya existe un aparato con ese nombre.")
            return

        data = dict(
            nombre=nombre,
            marca=(self.txt_marca.text() or None),
            modelo=(self.txt_modelo.text() or None),
            nro_serie=(self.txt_serie.text() or None),
            descripcion=(self.txt_desc.toPlainText() or None),
            activo=self.chk_activo.isChecked()
        )
        try:
            if self.aparato is None:
                self.session.add(Aparato(**data))
            else:
                for k,v in data.items():
                    setattr(self.aparato, k, v)
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            QMessageBox.warning(self, "Error", "No se pudo guardar.")
            return
        self.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ABMAparatos()
    w.show()
    sys.exit(app.exec_())
