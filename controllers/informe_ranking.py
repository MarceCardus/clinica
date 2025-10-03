# controllers/informe_ranking.py
from datetime import datetime, date
from decimal import Decimal

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QComboBox,
    QFileDialog, QMessageBox, QCheckBox
)

import pandas as pd

from utils.db import SessionLocal
from services.ranking_service import (
    top_pacientes_por_monto, top_items_por_cantidad, bottom_items_por_cantidad
)


class InformeRankingDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Informe de Rankings (Ventas)")
        self.resize(980, 580)

        lay = QVBoxLayout(self)

        # --- Filtros
        f1 = QHBoxLayout()
        f1.addWidget(QLabel("Desde:"))
        self.dp_desde = QDateEdit(self)
        self.dp_desde.setCalendarPopup(True)
        self.dp_desde.setDate(QDate.currentDate().addYears(-1))
        f1.addWidget(self.dp_desde)

        f1.addWidget(QLabel("Hasta:"))
        self.dp_hasta = QDateEdit(self)
        self.dp_hasta.setCalendarPopup(True)
        self.dp_hasta.setDate(QDate.currentDate())
        f1.addWidget(self.dp_hasta)

        f1.addWidget(QLabel("Límite (Top N):"))
        self.sp_limit = QSpinBox(self)
        self.sp_limit.setRange(1, 1000)
        self.sp_limit.setValue(10)
        f1.addWidget(self.sp_limit)

        f1.addWidget(QLabel("Ranking:"))
        self.cbo_tipo = QComboBox(self)
        self.cbo_tipo.addItems([
            "Top Pacientes por Monto",
            "Top Items por Cantidad",
            "Bottom Items por Cantidad (incluye 0)"
        ])
        f1.addWidget(self.cbo_tipo)

        # Checkboxes
        self.chk_ignorar_estado = QCheckBox("Ignorar estado de venta")
        self.chk_incluir_inactivos = QCheckBox("Incluir ítems inactivos")
        f1.addWidget(self.chk_ignorar_estado)
        f1.addWidget(self.chk_incluir_inactivos)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_exportar = QPushButton("Exportar a Excel")
        self.btn_cerrar = QPushButton("Cerrar")

        f1.addWidget(self.btn_buscar)
        f1.addWidget(self.btn_exportar)
        f1.addStretch()
        f1.addWidget(self.btn_cerrar)
        lay.addLayout(f1)

        # --- Tabla
        self.tbl = QTableWidget(self)
        self.tbl.setColumnCount(0)
        self.tbl.setRowCount(0)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setAlternatingRowColors(True)
        lay.addWidget(self.tbl)

        # Eventos
        self.btn_buscar.clicked.connect(self._buscar)
        self.btn_exportar.clicked.connect(self._exportar)
        self.btn_cerrar.clicked.connect(self.close)

        self._buscar()

    def _get_dates(self):
        d = self.dp_desde.date()
        h = self.dp_hasta.date()
        return date(d.year(), d.month(), d.day()), date(h.year(), h.month(), h.day())

    def _buscar(self):
        s = SessionLocal()
        try:
            desde, hasta = self._get_dates()
            limit = int(self.sp_limit.value())
            tipo = self.cbo_tipo.currentText()
            ignorar_estado = self.chk_ignorar_estado.isChecked()
            incluir_inactivos = self.chk_incluir_inactivos.isChecked()

            s.rollback()

            if tipo == "Top Pacientes por Monto":
                rows = top_pacientes_por_monto(s, desde, hasta, limit, ignorar_estado=ignorar_estado)
                self._poblar_top_pacientes(rows)
            elif tipo == "Top Items por Cantidad":
                rows = top_items_por_cantidad(s, desde, hasta, limit, ignorar_estado=ignorar_estado, incluir_inactivos=incluir_inactivos)
                self._poblar_top_items(rows)
            else:
                rows = bottom_items_por_cantidad(s, desde, hasta, limit, incluir_cero=True, ignorar_estado=ignorar_estado, incluir_inactivos=incluir_inactivos)
                self._poblar_bottom_items(rows)

            if self.tbl.rowCount() == 0:
                QMessageBox.information(self, "Ranking", "No se encontraron registros para el rango/criterios seleccionados.")

        except Exception as ex:
            s.rollback()
            from traceback import format_exc
            QMessageBox.critical(self, "Error", f"Ocurrió un error al buscar:\n{ex}\n\n{format_exc()}")
        finally:
            s.close()

    # Pobladores de tablas
    def _poblar_top_pacientes(self, rows):
        headers = ["#", "ID Paciente", "Paciente", "Monto Total (Gs.)", "Cantidad de Ventas"]
        self._set_headers(headers, len(rows))
        for i, r in enumerate(rows, start=1):
            self._set_row(i, [i, r[0], r[1], int(r[2] or 0), r[3] or 0])

    def _poblar_top_items(self, rows):
        headers = ["#", "ID Item", "Item", "Cantidad Total", "Monto Estimado (Gs.)"]
        self._set_headers(headers, len(rows))
        for i, r in enumerate(rows, start=1):
            self._set_row(i, [i, r[0], r[1], r[2] or 0, int(r[3] or 0)])

    def _poblar_bottom_items(self, rows):
        headers = ["#", "ID Item", "Item", "Cantidad Total"]
        self._set_headers(headers, len(rows))
        for i, r in enumerate(rows, start=1):
            self._set_row(i, [i, r[0], r[1], r[2] or 0])

    # Helpers tabla
    def _set_headers(self, headers, nrows):
        self.tbl.setColumnCount(len(headers))
        self.tbl.setHorizontalHeaderLabels(headers)
        self.tbl.setRowCount(nrows)

    def _set_row(self, idx, values):
        for col, val in enumerate(values):
            if col == 0:  # #
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(Qt.AlignCenter)
            elif isinstance(val, (Decimal, float, int)):
                # formatear como entero con separador de miles
                s = f"{int(val):,}".replace(",", ".")
                it = QTableWidgetItem(s)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            else:
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            it.setFlags(it.flags() ^ Qt.ItemIsEditable)
            self.tbl.setItem(idx-1, col, it)

    def _exportar(self):
        if self.tbl.rowCount() == 0:
            QMessageBox.information(self, "Exportar", "No hay datos para exportar.")
            return
        tipo = self.cbo_tipo.currentText()
        dts = datetime.now()
        fname_sug = f"ranking_{self._slug(tipo)}_{dts.strftime('%Y-%m-%d_%H%M')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Guardar Excel", fname_sug, "Excel (*.xlsx)")
        if not path:
            return

        cols = [self.tbl.horizontalHeaderItem(c).text() for c in range(self.tbl.columnCount())]
        data = []
        for r in range(self.tbl.rowCount()):
            fila = []
            for c in range(self.tbl.columnCount()):
                it = self.tbl.item(r, c)
                if it:
                    txt = it.text().replace(".", "")  # quitar separadores al exportar, si querés crudo
                    fila.append(txt)
                else:
                    fila.append("")
            data.append(fila)
        df = pd.DataFrame(data, columns=cols)

        try:
            with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
                sheet = "Ranking"
                df.to_excel(writer, sheet_name=sheet, index=False)
                wb = writer.book
                ws = writer.sheets[sheet]
                titulo = f"{tipo} — generado {dts.strftime('%d/%m/%y %H:%M')}"
                ws.write(0, 0, titulo, wb.add_format({"bold": True, "font_size": 12}))
            QMessageBox.information(self, "Exportar", f"Archivo exportado:\n{path}")
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"No se pudo exportar:\n{ex}")

    def _slug(self, s: str) -> str:
        return (
            s.lower()
             .replace(" ", "_")
             .replace("(", "").replace(")", "")
             .replace("á","a").replace("é","e").replace("í","i")
             .replace("ó","o").replace("ú","u").replace("ñ","n")
        )
