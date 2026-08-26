# -*- coding: utf-8 -*-
"""
Panel "Agenda del día" (pantalla de inicio / index).

Se muestra como ventana principal al abrir el sistema y da un vistazo rápido de
los turnos del día. Permite:
  * navegar a días anteriores / siguientes con flechas (arranca en "Hoy"),
  * cambiar el estado de cada turno sin abrir el ABM de citas.
Se refresca solo cada pocos minutos.
"""
from datetime import datetime, date, time, timedelta

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QFrame,
    QMessageBox
)

from utils.db import SessionLocal
from models.agenda import Cita


# Estados posibles de un turno (flujo típico de consultorio)
ESTADOS = ["Programada", "Confirmada", "Atendida", "Cancelada", "Ausente"]

# Paleta por estado: (fondo fila, color acento)
ESTILO_ESTADO = {
    "programada": ("#FFF7E6", "#B45309"),   # ámbar
    "confirmada": ("#E7F8EF", "#047857"),   # verde
    "atendida":   ("#E8F1FE", "#1D4ED8"),   # azul
    "realizado":  ("#E8F1FE", "#1D4ED8"),
    "cancelada":  ("#FDECEC", "#B91C1C"),   # rojo
    "anulada":    ("#FDECEC", "#B91C1C"),
    "ausente":    ("#F4ECFB", "#7C3AED"),   # violeta
}
ESTILO_DEFAULT = ("#FFFFFF", "#374151")

ESTADOS_CERRADOS = {"atendida", "realizado", "cancelada", "anulada", "ausente"}

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


class PanelAgendaHoy(QWidget):
    contenido_actualizado = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cargando = False
        self.fecha = date.today()
        self._build_ui()
        self.refrescar()

        self._timer = QTimer(self)
        self._timer.setInterval(3 * 60 * 1000)
        self._timer.timeout.connect(self.refrescar)
        self._timer.start()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # Stylesheet propio del panel: contiene los estilos y neutraliza el
        # fondo que el tema global aplica a todos los QWidget/QLabel.
        self.setStyleSheet("""
            #cardAgenda { background: #FFFFFF; border: 1px solid #F3D3E1;
                          border-radius: 14px; }
            #headerAgenda { background: #BE185D;
                            border-top-left-radius: 14px;
                            border-top-right-radius: 14px; }
            #headerAgenda QPushButton {
                background: #FFFFFF; color: #BE185D; font-weight: bold;
                border: none; border-radius: 8px; padding: 6px 12px;
            }
            #headerAgenda QPushButton:hover { background: #FCE7F3; }
            #navBtn { padding: 4px 10px; font-size: 15px; }
        """)
        # Estilos inline en los labels (ganan al tema global QWidget{background})
        est_titulo = "color:#FFFFFF; background:transparent; font-size:18px; font-weight:bold;"
        est_fecha = "color:#FFFFFF; background:transparent; font-size:14px; font-weight:bold;"
        est_resumen = "color:#FBCFE8; background:transparent; font-size:12px;"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 14)

        self.card = QFrame()
        self.card.setObjectName("cardAgenda")
        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(0, 0, 0, 0)
        card_lay.setSpacing(0)

        # --- Encabezado ---
        header = QFrame()
        header.setObjectName("headerAgenda")
        head = QVBoxLayout(header)
        head.setContentsMargins(16, 10, 12, 10)
        head.setSpacing(4)

        fila1 = QHBoxLayout()
        fila1.setSpacing(8)

        lbl_titulo = QLabel("📅  Agenda del día")
        lbl_titulo.setStyleSheet(est_titulo)
        fila1.addWidget(lbl_titulo)

        fila1.addSpacing(16)

        self.btn_prev = QPushButton("◀")
        self.btn_prev.setObjectName("navBtn")
        self.btn_prev.setCursor(Qt.PointingHandCursor)
        self.btn_prev.setToolTip("Día anterior")
        self.btn_prev.clicked.connect(lambda: self._mover_dia(-1))
        fila1.addWidget(self.btn_prev)

        self.lbl_fecha = QLabel("")
        self.lbl_fecha.setStyleSheet(est_fecha)
        self.lbl_fecha.setAlignment(Qt.AlignCenter)
        self.lbl_fecha.setMinimumWidth(230)
        fila1.addWidget(self.lbl_fecha)

        self.btn_next = QPushButton("▶")
        self.btn_next.setObjectName("navBtn")
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.setToolTip("Día siguiente")
        self.btn_next.clicked.connect(lambda: self._mover_dia(1))
        fila1.addWidget(self.btn_next)

        self.btn_hoy = QPushButton("Hoy")
        self.btn_hoy.setCursor(Qt.PointingHandCursor)
        self.btn_hoy.clicked.connect(self._ir_hoy)
        fila1.addWidget(self.btn_hoy)

        fila1.addStretch()

        self.btn_refrescar = QPushButton("↻  Actualizar")
        self.btn_refrescar.setCursor(Qt.PointingHandCursor)
        self.btn_refrescar.clicked.connect(self.refrescar)
        fila1.addWidget(self.btn_refrescar)

        head.addLayout(fila1)

        self.lbl_resumen = QLabel("")
        self.lbl_resumen.setStyleSheet(est_resumen)
        head.addWidget(self.lbl_resumen)

        card_lay.addWidget(header)

        # --- Tabla ---
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(
            ["Hora", "Paciente", "Profesional", "Servicio", "Estado"]
        )
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.setShowGrid(False)
        self.tabla.setFocusPolicy(Qt.NoFocus)
        self.tabla.verticalHeader().setDefaultSectionSize(36)
        self.tabla.setFrameShape(QFrame.NoFrame)
        self.tabla.setStyleSheet(
            "QTableWidget { background: #FFFFFF; border: none; }"
            "QTableWidget::item { padding: 2px 8px;"
            " border-bottom: 1px solid #F5E6EE; }"
            "QTableWidget::item:selected { background: #FCE7F3; color: #111827; }"
            "QHeaderView::section { background: #FDF2F8; color: #9D174D;"
            " font-weight: bold; border: none; border-bottom: 2px solid #F3D3E1;"
            " padding: 8px 10px; }"
        )
        hdr = self.tabla.horizontalHeader()
        hdr.setHighlightSections(False)
        # Hora y Estado con ancho fijo; el resto se estira para llenar la ventana
        # (y acompaña al redimensionar).
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        self.tabla.setColumnWidth(0, 90)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)
        self.tabla.setColumnWidth(4, 175)
        card_lay.addWidget(self.tabla)

        outer.addWidget(self.card)

    # ------------------------------------------------------- navegación
    def _mover_dia(self, delta):
        self.fecha = self.fecha + timedelta(days=delta)
        self.refrescar()

    def _ir_hoy(self):
        self.fecha = date.today()
        self.refrescar()

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _nombre_persona(obj):
        if obj is None:
            return "—"
        nombre = getattr(obj, "nombre", "") or ""
        apellido = getattr(obj, "apellido", "") or ""
        return f"{apellido} {nombre}".strip() or "—"

    @staticmethod
    def _servicio(cita):
        if getattr(cita, "item", None) is not None:
            return cita.item.nombre or "—"
        if getattr(cita, "plan_tipo", None) is not None:
            return getattr(cita.plan_tipo, "nombre", None) or "Plan"
        if getattr(cita, "producto", None) is not None:
            return getattr(cita.producto, "nombre", None) or "—"
        return "—"

    def _combo_estado(self, idcita, estado):
        cb = QComboBox()
        opciones = list(ESTADOS)
        if estado and estado not in opciones:
            opciones.insert(0, estado)
        cb.addItems(opciones)
        cb.setCurrentText(estado or "Programada")
        cb.setProperty("idcita", idcita)
        cb.setCursor(Qt.PointingHandCursor)
        self._pintar_combo(cb, estado)
        cb.currentTextChanged.connect(
            lambda nuevo, c=cb: self._cambiar_estado(c, nuevo)
        )
        return cb

    @staticmethod
    def _pintar_combo(cb, estado):
        _, acento = ESTILO_ESTADO.get((estado or "").lower(), ESTILO_DEFAULT)
        cb.setStyleSheet(
            "QComboBox { border: 1px solid %s; border-radius: 8px;"
            " padding: 2px 6px; color: %s; font-weight: bold;"
            " background: #FFFFFF; }"
            "QComboBox::drop-down { border: none; width: 16px; }"
            "QComboBox QAbstractItemView { selection-background-color: #FCE7F3;"
            " selection-color: #111827; }" % (acento, acento)
        )

    def _pintar_fila(self, row, estado):
        fondo, _ = ESTILO_ESTADO.get((estado or "").lower(), ESTILO_DEFAULT)
        brush = QBrush(QColor(fondo))
        for col in range(4):
            it = self.tabla.item(row, col)
            if it is not None:
                it.setBackground(brush)

    # ----------------------------------------------------------- refrescar
    def refrescar(self):
        self._cargando = True
        inicio = datetime.combine(self.fecha, time.min)
        fin = inicio + timedelta(days=1)

        s = SessionLocal()
        try:
            citas = (
                s.query(Cita)
                .filter(Cita.fecha_inicio >= inicio, Cita.fecha_inicio < fin)
                .order_by(Cita.fecha_inicio)
                .all()
            )
            datos = [(
                c.idcita,
                c.fecha_inicio.strftime("%H:%M"),
                self._nombre_persona(c.paciente),
                self._nombre_persona(c.profesional),
                self._servicio(c),
                (c.estado or "").strip() or "Programada",
            ) for c in citas]
        finally:
            s.close()

        self.tabla.setRowCount(len(datos))
        pendientes = 0
        for i, (idcita, hora, pac, prof, serv, estado) in enumerate(datos):
            if estado.lower() not in ESTADOS_CERRADOS:
                pendientes += 1

            it_hora = QTableWidgetItem(hora)
            it_hora.setTextAlignment(Qt.AlignCenter)
            f = it_hora.font(); f.setBold(True); it_hora.setFont(f)
            self.tabla.setItem(i, 0, it_hora)
            self.tabla.setItem(i, 1, QTableWidgetItem(pac))
            self.tabla.setItem(i, 2, QTableWidgetItem(prof))
            self.tabla.setItem(i, 3, QTableWidgetItem(serv))
            self.tabla.setCellWidget(i, 4, self._combo_estado(idcita, estado))
            self._pintar_fila(i, estado)

        # Etiqueta de fecha (con día de la semana)
        es_hoy = self.fecha == date.today()
        texto_fecha = f"{DIAS[self.fecha.weekday()]} {self.fecha.strftime('%d/%m/%Y')}"
        if es_hoy:
            texto_fecha += "  ·  Hoy"
        self.lbl_fecha.setText(texto_fecha)
        self.btn_hoy.setEnabled(not es_hoy)

        actualizado = datetime.now().strftime("%H:%M")
        if not datos:
            self.lbl_resumen.setText(
                f"Sin turnos para este día   (actualizado {actualizado})"
            )
        else:
            self.lbl_resumen.setText(
                f"{len(datos)} turno(s)  ·  {pendientes} pendiente(s)"
                f"   (actualizado {actualizado})"
            )

        self._cargando = False
        self.contenido_actualizado.emit()

    # ------------------------------------------------------- cambiar estado
    def _cambiar_estado(self, combo, nuevo):
        if self._cargando:
            return
        idcita = combo.property("idcita")
        if idcita is None:
            return
        s = SessionLocal()
        try:
            cita = s.query(Cita).get(idcita)
            if cita is None:
                return
            cita.estado = nuevo
            s.commit()
        except Exception as e:
            s.rollback()
            QMessageBox.critical(self, "Agenda del día",
                                 f"No se pudo cambiar el estado:\n{e}")
            return
        finally:
            s.close()

        self._pintar_combo(combo, nuevo)
        row = self._fila_de_combo(combo)
        if row is not None:
            self._pintar_fila(row, nuevo)

    def _fila_de_combo(self, combo):
        for r in range(self.tabla.rowCount()):
            if self.tabla.cellWidget(r, 4) is combo:
                return r
        return None

    # ------------------------------------------------- tamaño sugerido
    def ancho_preferido(self):
        # Ancho amplio por defecto; el contenedor lo limita al área disponible.
        return 1250

    def alto_preferido(self):
        filas = max(self.tabla.rowCount(), 3)
        alto_filas = 36 * min(filas, 22)      # hasta 22 filas sin scroll
        return 96 + 40 + alto_filas + 14 * 2 + 8
