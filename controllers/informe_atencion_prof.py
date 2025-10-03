# controllers/informe_atencion_prof.py
from datetime import date, datetime
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QDateEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox
)
from utils.db import SessionLocal
from models.profesional import Profesional
from services.inf_produccion_prof_service import get_produccion_por_dia, get_produccion_resumen_mes
import xlsxwriter

class InformeAtencionProfesionalDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Producción real por profesional (PlanSesión)")
        self.resize(1000, 600)

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

        # Defaults fechas: mes actual
        hoy = date.today()
        self.dt_desde.setDate(QDate(hoy.year, hoy.month, 1))
        self.dt_hasta.setDate(QDate(hoy.year, hoy.month, 1).addMonths(1).addDays(-1))

        # Profesionales
        self._cargar_profesionales()

        # ---- Tabla detalle diario ----
        self.tbl = QTableWidget(self)
        self.tbl.setColumnCount(4)
        self.tbl.setHorizontalHeaderLabels(["Día", "Profesional", "Atenciones", "Pacientes únicos"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.tbl)

        # ---- Resumen mes ----
        fila2 = QHBoxLayout()
        self.btn_resumen = QPushButton("Ver resumen del mes")
        fila2.addWidget(self.btn_resumen)
        root.addLayout(fila2)

        # Señales
        self.btn_buscar.clicked.connect(self.buscar)
        self.btn_export.clicked.connect(self.exportar_excel)
        self.btn_resumen.clicked.connect(self.resumen_mes)

        # Primer load
        self.buscar()

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

    def buscar(self):
        d, h = self._rango()
        pid = self.cb_prof.currentData()

        rows = get_produccion_por_dia(d, h, pid)
        self.tbl.setRowCount(len(rows))
        for r, row in enumerate(rows):
            dia_str = row["dia"].strftime("%d/%m/%Y")
            self._set_item(r, 0, dia_str)
            self._set_item(r, 1, self._prof_label(row["idprofesional"]))
            self._set_item(r, 2, row["atenciones"])
            self._set_item(r, 3, row["pacientes_unicos"])

    def _set_item(self, r, c, v):
        it = QTableWidgetItem(str(v) if v is not None else "")
        it.setTextAlignment(Qt.AlignCenter)
        self.tbl.setItem(r, c, it)

    def exportar_excel(self):
        # colectar tabla
        rows = []
        for r in range(self.tbl.rowCount()):
            rows.append([self.tbl.item(r, c).text() if self.tbl.item(r, c) else "" for c in range(self.tbl.columnCount())])

        ts = datetime.now().strftime("%d%m%y_%H%M")
        sug = f"ProduccionProfesional__{ts}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Guardar Excel", sug, "Excel (*.xlsx)")
        if not path:
            return

        try:
            wb = xlsxwriter.Workbook(path)
            ws = wb.add_worksheet("Produccion")
            headers = ["Día", "Profesional", "Atenciones", "Pacientes únicos"]
            ws.write_row(0, 0, headers)
            for i, row in enumerate(rows, start=1):
                ws.write_row(i, 0, row)
            wb.close()
            QMessageBox.information(self, "OK", f"Exportado a:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo exportar.\n{e}")

    def resumen_mes(self):
        # Muestra un resumen rápido en un messagebox
        d, _ = self._rango()
        pid = self.cb_prof.currentData()
        data = get_produccion_resumen_mes(d.year, d.month, pid)

        if not data:
            QMessageBox.information(self, "Resumen", "Sin datos para el mes.")
            return

        # Armar texto
        lineas = []
        for r in data:
            linea = f"{self._prof_label(r['idprofesional'])}: atenciones={r['atenciones_mes']}, pacientes únicos={r['pacientes_unicos_mes']}"
            lineas.append(linea)

        QMessageBox.information(self, "Resumen mensual", "\n".join(lineas))
