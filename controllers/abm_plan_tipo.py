# controllers/abm_plan_tipo.py
import sys, os, pathlib
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QPushButton, QTextEdit, QSpinBox, QCheckBox,
    QMessageBox, QHeaderView, QAbstractItemView
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QSize

from utils.db import SessionLocal
from sqlalchemy import exists, func
from sqlalchemy.exc import IntegrityError

from models.plan_tipo import PlanTipo
try:
    from models.item import Item
except Exception:
    Item = None
try:
    from models.plan_sesiones import PlanSesiones
except Exception:
    PlanSesiones = None


def resource_path(*parts):
    candidates = []
    here = pathlib.Path(__file__).resolve().parent
    candidates += [
        here / "imagenes" / pathlib.Path(*parts),
        pathlib.Path(os.getcwd()) / "imagenes" / pathlib.Path(*parts),
        here.parent / "imagenes" / pathlib.Path(*parts),
    ]
    if hasattr(sys, "_MEIPASS"):
        candidates.append(pathlib.Path(sys._MEIPASS) / "imagenes" / pathlib.Path(*parts))
    for p in candidates:
        if p.exists():
            return str(p)
    return ""


class ABMPlanTipo(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ABM de Tipos de Plan")
        self.setMinimumWidth(860)
        self.session = SessionLocal()
        self._init_ui()
        self.load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        filtros = QWidget(); f = QHBoxLayout(filtros)
        self.filtro_nombre = QLineEdit()
        self.filtro_nombre.setPlaceholderText("🔍 Buscar por nombre…")
        self.filtro_nombre.textChanged.connect(self.load_data)
        f.addWidget(QLabel("Filtro:"))
        f.addWidget(self.filtro_nombre, stretch=2)
        f.addStretch()
        layout.addWidget(filtros)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Sesiones por defecto", "Req. masaje",
            "Req. aparato", "Activo", "Acciones"
        ])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemDoubleClicked.connect(lambda *_: self.abrir_dialogo_editar(self.table.currentRow()))

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setStretchLastSection(False)
        self.table.setWordWrap(False)
        layout.addWidget(self.table)

        self.btn_agregar = QPushButton(" Agregar tipo de plan")
        ico_add = resource_path("agregar.png")
        if ico_add: self.btn_agregar.setIcon(QIcon(ico_add))
        self.btn_agregar.setIconSize(QSize(50, 50))
        self.btn_agregar.clicked.connect(self.abrir_dialogo_agregar)
        h = QHBoxLayout(); h.addStretch(); h.addWidget(self.btn_agregar)
        layout.addLayout(h)

    def load_data(self):
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(0)
            texto = (self.filtro_nombre.text() or "").strip().lower()

            q = self.session.query(PlanTipo)
            if texto:
                q = q.filter(func.lower(PlanTipo.nombre).like(f"%{texto}%"))

            rows = q.order_by(PlanTipo.nombre.asc()).all()
            self.table.setRowCount(len(rows))

            for r, pt in enumerate(rows):
                id_fijo = pt.idplantipo
                self.table.setItem(r, 0, QTableWidgetItem(str(pt.idplantipo)))
                self.table.setItem(r, 1, QTableWidgetItem(pt.nombre or ""))
                self.table.setItem(r, 2, QTableWidgetItem(str(pt.sesiones_por_defecto or 0)))

                def yn(v):
                    it = QTableWidgetItem("Sí" if v else "No")
                    it.setTextAlignment(Qt.AlignCenter)
                    return it

                self.table.setItem(r, 3, yn(bool(pt.requiere_masaje)))
                self.table.setItem(r, 4, yn(bool(pt.requiere_aparato)))
                self.table.setItem(r, 5, yn(bool(pt.activo)))

                cell = QWidget(); h = QHBoxLayout(cell); h.setContentsMargins(0,0,0,0)
                btn_editar = QPushButton(); ico = resource_path("editar.png")
                if ico: btn_editar.setIcon(QIcon(ico))
                else:   btn_editar.setText("✏")
                btn_editar.setFixedSize(QSize(30,26)); btn_editar.setIconSize(QSize(18,18))
                btn_editar.setToolTip("Editar")
                btn_editar.clicked.connect(lambda _, _id=id_fijo: self._abrir_editar_por_id(_id))
                btn_editar.setFocusPolicy(Qt.NoFocus)

                btn_del = QPushButton(); ico = resource_path("eliminar.png")
                if ico: btn_del.setIcon(QIcon(ico))
                else:   btn_del.setText("🗑")
                btn_del.setFixedSize(QSize(30,26)); btn_del.setIconSize(QSize(18,18))
                btn_del.setToolTip("Eliminar")
                btn_del.clicked.connect(lambda _, _id=id_fijo: self._eliminar_por_id(_id))
                btn_del.setFocusPolicy(Qt.NoFocus)

                h.addWidget(btn_editar); h.addWidget(btn_del)
                cell.setLayout(h)
                self.table.setCellWidget(r, 6, cell)

            self.table.resizeRowsToContents()
            last = self.table.columnCount() - 1
            self.table.setColumnWidth(last, max(90, self.table.columnWidth(last)))
        finally:
            self.table.setUpdatesEnabled(True)

    def _row_id(self, row):
        it = self.table.item(row, 0)
        if not it or not it.text().isdigit():
            return -1
        return int(it.text())

    def _row_by_id(self, _id: int) -> int:
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it and it.text().isdigit() and int(it.text()) == _id:
                return r
        return -1

    def _abrir_editar_por_id(self, _id: int):
        row = self._row_by_id(_id)
        if row >= 0:
            self.abrir_dialogo_editar(row)

    def _eliminar_por_id(self, _id: int):
        row = self._row_by_id(_id)
        if row >= 0:
            self.eliminar(row)

    def abrir_dialogo_agregar(self):
        dlg = FormPlanTipo(self.session, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def abrir_dialogo_editar(self, row):
        if row < 0: return
        _id = self._row_id(row)
        pt = self.session.query(PlanTipo).get(_id)
        if not pt: return
        dlg = FormPlanTipo(self.session, parent=self, plan_tipo=pt)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def _referenciado(self, idplantipo: int) -> bool:
        s = self.session
        usado_item = s.query(exists().where(Item.idplantipo == idplantipo)).scalar() if Item else False
        usado_plan = s.query(exists().where(PlanSesiones.idplantipo == idplantipo)).scalar() if PlanSesiones else False
        return bool(usado_item or usado_plan)

    def eliminar(self, row):
        if row < 0 or row >= self.table.rowCount(): return
        _id = self._row_id(row)
        if QMessageBox.question(self, "Eliminar",
                                "¿Seguro que desea eliminar este tipo de plan?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return

        pt = self.session.query(PlanTipo).get(_id)
        if not pt: return

        if self._referenciado(_id):
            QMessageBox.warning(self, "No se puede eliminar",
                                "Este tipo de plan está referenciado por Ítems y/o Planes de pacientes.")
            return

        try:
            self.session.delete(pt)
            self.session.commit()
            self.load_data()
        except IntegrityError:
            self.session.rollback()
            QMessageBox.warning(self, "No se puede eliminar",
                                "La base de datos impidió la eliminación por referencias existentes.")


class FormPlanTipo(QDialog):
    def __init__(self, session, parent=None, plan_tipo: PlanTipo=None):
        super().__init__(parent)
        self.session = session
        self.plan_tipo = plan_tipo
        self.setWindowTitle("Editar Tipo de Plan" if plan_tipo else "Agregar Tipo de Plan")
        self.setMinimumWidth(520)
        self._init_ui()
        if self.plan_tipo:
            self._cargar()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.txt_nombre = QLineEdit()
        self.sp_sesiones = QSpinBox(); self.sp_sesiones.setRange(1, 999)
        self.chk_masaje  = QCheckBox("Requiere masaje")
        self.chk_aparato = QCheckBox("Requiere aparato")
        self.chk_activo  = QCheckBox("Activo"); self.chk_activo.setChecked(True)

        box = QVBoxLayout()
        box.addWidget(QLabel("Nombre")); box.addWidget(self.txt_nombre)
        box.addWidget(QLabel("Sesiones por defecto")); box.addWidget(self.sp_sesiones)
        box.addWidget(self.chk_masaje); box.addWidget(self.chk_aparato); box.addWidget(self.chk_activo)

        cont = QWidget(); cont.setLayout(box)
        layout.addWidget(cont)

        btns = QHBoxLayout()
        self.btn_guardar = QPushButton("Guardar"); self.btn_guardar.clicked.connect(self.guardar)
        self.btn_cancelar = QPushButton("Cancelar"); self.btn_cancelar.clicked.connect(self.reject)
        btns.addStretch(); btns.addWidget(self.btn_guardar); btns.addWidget(self.btn_cancelar)
        layout.addLayout(btns)

    def _cargar(self):
        pt = self.plan_tipo
        self.txt_nombre.setText(pt.nombre or "")
        self.sp_sesiones.setValue(int(pt.sesiones_por_defecto or 1))
        self.chk_masaje.setChecked(bool(pt.requiere_masaje))
        self.chk_aparato.setChecked(bool(pt.requiere_aparato))
        self.chk_activo.setChecked(bool(pt.activo))

    def guardar(self):
        nombre = (self.txt_nombre.text() or "").strip()
        if not nombre:
            QMessageBox.warning(self, "Validación", "Debe ingresar el nombre.")
            return

        q = self.session.query(PlanTipo).filter(func.lower(PlanTipo.nombre) == nombre.lower())
        if self.plan_tipo is not None:
            q = q.filter(PlanTipo.idplantipo != self.plan_tipo.idplantipo)
        if self.session.query(q.exists()).scalar():
            QMessageBox.warning(self, "Validación", "Ya existe un tipo de plan con ese nombre.")
            return

        data = dict(
            nombre=nombre,
            sesiones_por_defecto=int(self.sp_sesiones.value()),
            requiere_masaje=self.chk_masaje.isChecked(),
            requiere_aparato=self.chk_aparato.isChecked(),
            activo=self.chk_activo.isChecked(),
        )

        try:
            if self.plan_tipo is None:
                self.session.add(PlanTipo(**data))
            else:
                for k, v in data.items():
                    setattr(self.plan_tipo, k, v)
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            QMessageBox.warning(self, "Error", "No se pudo guardar (conflicto en la base).")
            return

        self.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ABMPlanTipo()
    w.show()
    sys.exit(app.exec_())
