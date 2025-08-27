# controllers/buscar_venta_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt5.QtCore import Qt
from decimal import Decimal
from sqlalchemy import select, func, and_

from models.paciente import Paciente
from models.venta import Venta


def _fmt(n):
    try:
        return f"{int(round(Decimal(str(n) or 0))):,}".replace(",", ".")
    except Exception:
        return "0"


class BuscarVentaDialog(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.selected_idventa = None

        self.setWindowTitle("Buscar ventas")
        self.resize(820, 520)

        root = QVBoxLayout(self)

        # ---- Filtros (sin fechas) ----
        form = QFormLayout()

        self.cbo_paciente = QComboBox()
        self.cbo_paciente.setEditable(True)
        self._load_pacientes()
        form.addRow("Paciente:", self.cbo_paciente)

        self.txt_factura = QLineEdit()
        self.txt_factura.setPlaceholderText("001-001-0000001")
        form.addRow("N° Factura:", self.txt_factura)

        self.cbo_estado = QComboBox()
        self.cbo_estado.addItems(["Todos", "Cerrada", "Cobrada", "Anulada"])
        form.addRow("Estado:", self.cbo_estado)

        root.addLayout(form)

        # ---- Botón Buscar ----
        hb = QHBoxLayout()
        self.btn_filtrar = QPushButton("Buscar")
        self.btn_filtrar.clicked.connect(self._buscar)
        hb.addStretch()
        hb.addWidget(self.btn_filtrar)
        root.addLayout(hb)

        # ---- Resultados ----
        self.tab = QTableWidget(0, 6)
        self.tab.setHorizontalHeaderLabels(["ID", "Fecha", "Paciente", "Total", "Estado", "Factura"])
        self.tab.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tab.setSelectionBehavior(QTableWidget.SelectRows)
        self.tab.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tab.doubleClicked.connect(self._elegir)
        root.addWidget(self.tab)

        # ---- Botonera inferior ----
        bb = QHBoxLayout()
        self.btn_sel = QPushButton("Cargar venta seleccionada")
        self.btn_sel.clicked.connect(self._elegir)
        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.clicked.connect(self.reject)
        bb.addStretch()
        bb.addWidget(self.btn_sel)
        bb.addWidget(self.btn_cerrar)
        root.addLayout(bb)

        # primera búsqueda (trae todo)
        self._buscar()

    def _load_pacientes(self):
        self.cbo_paciente.clear()
        self.cbo_paciente.addItem("— Todos —", None)

        rows = self.session.execute(
            select(Paciente.idpaciente, Paciente.apellido, Paciente.nombre)
            .order_by(Paciente.apellido, Paciente.nombre)
        ).all()

        for pid, ap, no in rows:
            self.cbo_paciente.addItem(f"{ap}, {no}", pid)

        # autocompletar
        items = [self.cbo_paciente.itemText(i) for i in range(self.cbo_paciente.count())]
        from PyQt5.QtWidgets import QCompleter
        comp = QCompleter(items, self.cbo_paciente)
        comp.setCaseSensitivity(False)
        comp.setFilterMode(Qt.MatchContains)
        self.cbo_paciente.setCompleter(comp)

    def _buscar(self):
        self.tab.setRowCount(0)
        filtros = []

        # Paciente (opcional)
        pid = self.cbo_paciente.currentData()
        if pid:
            filtros.append(Venta.idpaciente == pid)

        # Estado (opcional)
        est = (self.cbo_estado.currentText() or "").strip().lower()
        if est != "todos":
            filtros.append(func.lower(func.coalesce(Venta.estadoventa, "")) == est)

        # N° Factura (opcional)
        fac = (self.txt_factura.text() or "").strip()
        if fac:
            filtros.append(Venta.nro_factura.ilike(f"%{fac}%"))

        q = (
            select(
                Venta.idventa,
                Venta.fecha,
                func.coalesce(Paciente.apellido, "") + ", " + func.coalesce(Paciente.nombre, ""),
                Venta.montototal,
                Venta.estadoventa,
                Venta.nro_factura,
            )
            .join(Paciente, Paciente.idpaciente == Venta.idpaciente, isouter=True)
            .where(and_(*filtros))  # si está vacío, trae todo
            .order_by(Venta.fecha.desc(), Venta.idventa.desc())
            .limit(500)
        )

        rows = self.session.execute(q).all()

        for rid, fecha, paciente, total, estado, factura in rows:
            r = self.tab.rowCount()
            self.tab.insertRow(r)
            self.tab.setItem(r, 0, QTableWidgetItem(str(rid)))
            self.tab.setItem(r, 1, QTableWidgetItem(fecha.strftime("%d/%m/%Y") if fecha else ""))
            self.tab.setItem(r, 2, QTableWidgetItem(paciente or ""))
            self.tab.setItem(r, 3, QTableWidgetItem(_fmt(total)))
            self.tab.setItem(r, 4, QTableWidgetItem(estado or ""))
            self.tab.setItem(r, 5, QTableWidgetItem(factura or ""))

        if not rows:
            QMessageBox.information(self, "Búsqueda", "No se encontraron ventas.")

    def _elegir(self):
        r = self.tab.currentRow()
        if r < 0:
            QMessageBox.warning(self, "Atención", "Seleccioná una venta de la tabla.")
            return
        self.selected_idventa = int(self.tab.item(r, 0).text())
        self.accept()
