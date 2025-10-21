# controllers/informe_detalle_prof.py

from datetime import date, datetime
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QDateEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox
)
import xlsxwriter

from utils.db import SessionLocal
from models.profesional import Profesional
from services.inf_produccion_prof_service import get_produccion_detallado

class InformeDetalleProfesionalDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detalle de atenciones por profesional (PlanSesión)")
        self.resize(1100, 620)

        root = QVBoxLayout(self)

        # ---- Filtros ----
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Desde:"))
        self.dt_desde = QDateEdit(self); self.dt_desde.setCalendarPopup(True); self.dt_desde.setDisplayFormat("dd/MM/yyyy")
        fila.addWidget(self.dt_desde)

        fila.addWidget(QLabel("Hasta:"))
        self.dt_hasta = QDateEdit(self); self.dt_hasta.setCalendarPopup(True); self.dt_hasta.setDisplayFormat("dd/MM/yyyy")
        fila.addWidget(self.dt_hasta)

        fila.addWidget(QLabel("Profesional:"))
        self.cb_prof = QComboBox(self)
        fila.addWidget(self.cb_prof)

        self.btn_buscar = QPushButton("Buscar")
        fila.addWidget(self.btn_buscar)

        self.btn_export = QPushButton("Exportar Excel")
        fila.addWidget(self.btn_export)

        root.addLayout(fila)

        # Defaults: mes actual
        hoy = date.today()
        self.dt_desde.setDate(QDate(hoy.year, hoy.month, 1))
        self.dt_hasta.setDate(QDate(hoy.year, hoy.month, 1).addMonths(1).addDays(-1))

        # Profesionales
        self._cargar_profesionales()

        # ---- Tabla ----
        self.tbl = QTableWidget(self)
        self.tbl.setColumnCount(5)
        self.tbl.setHorizontalHeaderLabels(["Fecha", "Profesional", "Paciente", "Procedimiento", "Observaciones"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Fecha
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Profesional
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Paciente
        self.tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Procedimiento
        self.tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)          # Observaciones
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.tbl)

        # ---- Señales ----
        self.btn_buscar.clicked.connect(self.buscar)
        self.btn_export.clicked.connect(self.exportar_excel)

        # Primer load
        self.buscar()

    # -------- helpers ----------
    def _cargar_profesionales(self):
        s = SessionLocal()
        try:
            self.cb_prof.clear()
            self.cb_prof.addItem("Todos", None)
            for p in s.query(Profesional).filter_by(estado=True).order_by(Profesional.apellido, Profesional.nombre).all():
                self.cb_prof.addItem(f"{p.apellido}, {p.nombre}", p.idprofesional)
        finally:
            s.close()

    def _rango(self):
        d = self.dt_desde.date().toPyDate()
        h = self.dt_hasta.date().toPyDate()
        if h < d:
            d, h = h, d
        return d, h

    def _prof_label(self, pid):
        if pid is None:
            return "Todos"
        idx = self.cb_prof.findData(pid)
        return self.cb_prof.itemText(idx) if idx >= 0 else str(pid)

    def _set_item(self, r, c, v, align_center=False):
        it = QTableWidgetItem("" if v is None else str(v))
        it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        it.setTextAlignment(Qt.AlignCenter if align_center else Qt.AlignLeft)
        self.tbl.setItem(r, c, it)

    # -------- acciones ----------
    def buscar(self):
        d, h = self._rango()
        pid = self.cb_prof.currentData()

        rows = get_produccion_detallado(d, h, pid)
        self.tbl.setRowCount(len(rows))

        for r, row in enumerate(rows):
            fecha_str = row["fecha"].strftime("%d/%m/%Y") if hasattr(row["fecha"], "strftime") else str(row["fecha"])
            self._set_item(r, 0, fecha_str, align_center=True)
            self._set_item(r, 1, row["profesional"])
            self._set_item(r, 2, row["paciente"])
            self._set_item(r, 3, row["procedimiento"])
            self._set_item(r, 4, row["observaciones"])

    def exportar_excel(self):
        # Recolectar
        rows = []
        for r in range(self.tbl.rowCount()):
            rows.append([self.tbl.item(r, c).text() if self.tbl.item(r, c) else "" for c in range(self.tbl.columnCount())])

        ts = datetime.now().strftime("%d%m%y_%H%M")
        sug = f"DetalleAtenciones_{ts}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Guardar Excel", sug, "Excel (*.xlsx)")
        if not path:
            return

        try:
            wb = xlsxwriter.Workbook(path)
            ws = wb.add_worksheet("Detalle")
            headers = ["Fecha", "Profesional", "Paciente", "Procedimiento", "Observaciones"]
            ws.write_row(0, 0, headers)
            for i, row in enumerate(rows, start=1):
                ws.write_row(i, 0, row)
            wb.close()
            QMessageBox.information(self, "OK", f"Exportado a:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo exportar.\n{e}")
