# controllers/visor_graficos.py
# -*- coding: utf-8 -*-
from datetime import date, datetime
from typing import Dict

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QDateEdit,
    QCheckBox, QPushButton, QFileDialog, QMessageBox, QTabWidget, QWidget
)

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from utils.db import SessionLocal
from services.graficos_informe import (
    fig_ventas_linea, fig_metodos_pago_donut, fig_cobros_apilados, guardar_png
)

class VisorGraficosDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Visor de Gráficos del Informe")
        self.resize(1100, 700)

        # --------- Filtros
        filtros = QGridLayout()
        filtros.addWidget(QLabel("Desde:"), 0, 0)
        self.dt_desde = QDateEdit(QDate.currentDate().addMonths(-3))
        self.dt_desde.setCalendarPopup(True)
        filtros.addWidget(self.dt_desde, 0, 1)

        filtros.addWidget(QLabel("Hasta:"), 0, 2)
        self.dt_hasta = QDateEdit(QDate.currentDate())
        self.dt_hasta.setCalendarPopup(True)
        filtros.addWidget(self.dt_hasta, 0, 3)

        self.chk_linea = QCheckBox("Evolución de Ventas")
        self.chk_donut = QCheckBox("Método de Pago (Donut)")
        self.chk_apiladas = QCheckBox("Cobrados vs Pendientes")
        for i, w in enumerate([self.chk_linea, self.chk_donut, self.chk_apiladas], start=1):
            w.setChecked(True if i <= 3 else False)
            filtros.addWidget(w, 1, i-1)

        self.btn_generar = QPushButton("Generar")
        self.btn_guardar = QPushButton("Guardar seleccionados…")

        fila_btns = QHBoxLayout()
        fila_btns.addStretch(1)
        fila_btns.addWidget(self.btn_generar)
        fila_btns.addWidget(self.btn_guardar)

        top = QVBoxLayout()
        top.addLayout(filtros)
        top.addLayout(fila_btns)

        # --------- Área de visualización (tabs)
        self.tabs = QTabWidget()
        self._tab_map: Dict[str, QWidget] = {}

        def _make_tab(nombre: str):
            w = QWidget()
            lay = QVBoxLayout(w)
            self.tabs.addTab(w, nombre)
            self._tab_map[nombre] = w

        _make_tab("Ventas (línea)")
        _make_tab("Métodos (donut)")
        _make_tab("Cobros (apiladas)")

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.tabs)

        # eventos
        self.btn_generar.clicked.connect(self._generar)
        self.btn_guardar.clicked.connect(self._guardar)

        # holders de figuras/canvas
        self._figs: Dict[str, object] = {}
        self._canvases: Dict[str, FigureCanvas] = {}

    # Util: limpia un tab y agrega un canvas con fig
    def _set_tab_figure(self, tab_key: str, fig):
        w = self._tab_map[tab_key]
        # limpiar
        while w.layout().count():
            item = w.layout().takeAt(0)
            cw = item.widget()
            if cw:
                cw.setParent(None)
        canvas = FigureCanvas(fig)
        w.layout().addWidget(canvas)
        self._canvases[tab_key] = canvas
        self._figs[tab_key] = fig

    def _generar(self):
        d1 = self.dt_desde.date().toPyDate()
        d2 = self.dt_hasta.date().toPyDate()
        if d1 > d2:
            QMessageBox.warning(self, "Rango inválido", "La fecha 'Desde' no puede ser mayor que 'Hasta'.")
            return

        session = SessionLocal()
        try:
            if self.chk_linea.isChecked():
                fig = fig_ventas_linea(session, d1, d2)
                self._set_tab_figure("Ventas (línea)", fig)

            if self.chk_donut.isChecked():
                fig = fig_metodos_pago_donut(session, d1, d2)
                self._set_tab_figure("Métodos (donut)", fig)

            if self.chk_apiladas.isChecked():
                fig = fig_cobros_apilados(session, d1, d2)
                self._set_tab_figure("Cobros (apiladas)", fig)

            # cambiar a la primera pestaña que tenga gráfico
            for name in ["Ventas (línea)", "Métodos (donut)", "Cobros (apiladas)"]:
                if name in self._figs:
                    self.tabs.setCurrentIndex(list(self._tab_map.keys()).index(name))
                    break
        except Exception as e:
            QMessageBox.critical(self, "Error al generar", str(e))
        finally:
            session.close()

    def _guardar(self):
        # verifica qué tabs tienen figura y estaban seleccionados
        seleccion = []
        if self.chk_linea.isChecked() and "Ventas (línea)" in self._figs:
            seleccion.append(("Ventas (línea)", "ventas_linea"))
        if self.chk_donut.isChecked() and "Métodos (donut)" in self._figs:
            seleccion.append(("Métodos (donut)", "metodos_pago_donut"))
        if self.chk_apiladas.isChecked() and "Cobros (apiladas)" in self._figs:
            seleccion.append(("Cobros (apiladas)", "cobros_apilados"))

        if not seleccion:
            QMessageBox.information(self, "Nada para guardar", "No hay gráficos generados/seleccionados.")
            return

        carpeta = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de destino")
        if not carpeta:
            return

        timestamp = datetime.now().strftime("%d%m%y_%H%M")
        try:
            for tab_name, base in seleccion:
                fig = self._figs[tab_name]
                nombre = f"{base}_{timestamp}"
                guardar_png(fig, carpeta, nombre)
            QMessageBox.information(self, "Listo", "Archivos PNG guardados correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))
