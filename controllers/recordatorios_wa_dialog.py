# -*- coding: utf-8 -*-
# controllers/recordatorios_wa_dialog.py
#
# Panel de "Recordatorios WhatsApp" con dos pestañas:
#   1. Pacientes    → un recordatorio individual por turno de mañana.
#   2. Profesionales → un resumen del día para cada profesional.
#
# No usa Selenium: abre https://web.whatsapp.com/send con el mensaje ya
# escrito y el operador aprieta Enter para enviar.

from PyQt5.QtWidgets import (
    QDialog, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDateEdit, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QProgressBar, QMessageBox, QAbstractItemView,
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor

from utils.db import SessionLocal
from services.whatsapp import (
    citas_para_recordar, resumen_por_profesional,
    construir_mensaje, construir_mensaje_profesional,
    abrir_whatsapp,
    PLANTILLA_DEFECTO, PLANTILLA_PROFESIONAL_DEFECTO,
)

# Estados de envío por fila
PENDIENTE = "Pendiente"
ABIERTO   = "Abierto (enviá con Enter)"
ENVIADO   = "✓ Enviado"
OMITIDO   = "Omitido"
SIN_TEL   = "✗ Sin teléfono válido"

_COLORES = {
    ENVIADO:   QColor("#DCFCE7"),
    ABIERTO:   QColor("#FEF9C3"),
    OMITIDO:   QColor("#FEE2E2"),
    SIN_TEL:   QColor("#F3F4F6"),
    PENDIENTE: QColor("#FFFFFF"),
}


def _btn_style(base, hover, pressed):
    return f"""
        QPushButton {{
            background-color: {base}; color: white; border: none;
            border-radius: 10px; padding: 10px 16px; font-weight: 600;
        }}
        QPushButton:hover {{ background-color: {hover}; }}
        QPushButton:pressed {{ background-color: {pressed}; }}
        QPushButton:disabled {{ background-color: #BDBDBD; color: #EEEEEE; }}
    """


def _pintar_fila(tabla, row, estado):
    col = _COLORES.get(estado, QColor("#FFFFFF"))
    for c in range(tabla.columnCount()):
        cell = tabla.item(row, c)
        if cell is not None:
            cell.setBackground(col)


# ---------------------------------------------------------------------------
# Panel base con la lógica común (tabla + envío secuencial + plantilla).
# ---------------------------------------------------------------------------
class _BaseTab(QWidget):
    """Los que heredan definen:
        COLUMNAS               → nombres de las columnas 1..N (checkbox aparte)
        AYUDA_PLANTILLA        → texto de ayuda arriba del cuadro plantilla
        PLANTILLA_INICIAL      → texto por defecto
        ETIQUETA_ITEM          → "turno" / "profesional" (para textos)
        FILTRO_ESTADOS_LABEL   → texto del checkbox de filtro
    y sobreescriben _cargar_datos, _valores_fila, _construir_mensaje.
    """
    COLUMNAS: list[str] = []
    AYUDA_PLANTILLA = ""
    PLANTILLA_INICIAL = ""
    ETIQUETA_ITEM = "elemento"
    FILTRO_ESTADOS_LABEL = "Sólo turnos Programados"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: list[dict] = []
        self._idx_actual = -1
        self._fecha_actual = None

        root = QVBoxLayout(self)

        # --- Barra superior: fecha + filtro + cargar ---
        top = QHBoxLayout()
        top.addWidget(QLabel("Fecha:"))
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd-MM-yyyy")
        self.date.setDate(QDate.currentDate().addDays(1))
        top.addWidget(self.date)

        self.chk_solo_prog = QCheckBox(self.FILTRO_ESTADOS_LABEL)
        self.chk_solo_prog.setChecked(True)
        top.addWidget(self.chk_solo_prog)

        self.chk_desktop = QCheckBox("Usar WhatsApp Desktop (misma ventana)")
        self.chk_desktop.setChecked(True)
        self.chk_desktop.setToolTip(
            "Si está tildado, abre la app de WhatsApp para Windows y cada envío "
            "cambia el chat en la misma ventana. Si no, usa WhatsApp Web en el "
            "navegador (una pestaña por envío).")
        top.addWidget(self.chk_desktop)

        top.addStretch(1)
        self.btn_cargar = QPushButton("🔄 Cargar")
        self.btn_cargar.setStyleSheet(_btn_style("#455A64", "#37474F", "#263238"))
        self.btn_cargar.setCursor(Qt.PointingHandCursor)
        self.btn_cargar.clicked.connect(self.cargar)
        top.addWidget(self.btn_cargar)
        root.addLayout(top)

        # --- Tabla ---
        n_cols = 1 + len(self.COLUMNAS) + 1  # checkbox + datos + estado
        self.tabla = QTableWidget(0, n_cols)
        headers = ["Enviar"] + list(self.COLUMNAS) + ["Estado"]
        self.tabla.setHorizontalHeaderLabels(headers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        hdr = self.tabla.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for i in range(1, 1 + len(self.COLUMNAS)):
            hdr.setSectionResizeMode(i, QHeaderView.Stretch)
        hdr.setSectionResizeMode(n_cols - 1, QHeaderView.ResizeToContents)
        self.tabla.itemSelectionChanged.connect(self._refrescar_preview)
        self.tabla.cellDoubleClicked.connect(self._on_double_click)
        # La tabla es lo principal: le damos altura mínima y el mayor peso
        # de estiramiento para que muestre varias filas sin scroll y ocupe
        # más espacio que el cuadro editable / la vista previa.
        self.tabla.setMinimumHeight(260)
        root.addWidget(self.tabla, 5)

        # --- Plantilla editable ---
        root.addWidget(QLabel(self.AYUDA_PLANTILLA))
        self.txt_plantilla = QTextEdit()
        self.txt_plantilla.setPlainText(self.PLANTILLA_INICIAL)
        self.txt_plantilla.setMaximumHeight(110)
        self.txt_plantilla.textChanged.connect(self._refrescar_preview)
        root.addWidget(self.txt_plantilla, 0)

        # --- Vista previa ---
        self.lbl_preview = QLabel(
            f"— seleccioná un {self.ETIQUETA_ITEM} para ver el mensaje —")
        self.lbl_preview.setWordWrap(True)
        self.lbl_preview.setStyleSheet(
            "background:#FDF2F8; border:1px solid #F9A8D4; border-radius:8px;"
            "padding:8px; color:#831843;")
        self.lbl_preview.setMinimumHeight(70)
        self.lbl_preview.setMaximumHeight(150)
        self.lbl_preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self.lbl_preview, 0)

        # --- Progreso ---
        self.progress = QProgressBar()
        self.progress.setFormat("Enviados %v / %m")
        root.addWidget(self.progress)

        # --- Acciones ---
        acciones = QHBoxLayout()
        self.btn_marcar_todos = QPushButton("Marcar / desmarcar todos")
        self.btn_marcar_todos.setStyleSheet(_btn_style("#455A64", "#37474F", "#263238"))
        self.btn_marcar_todos.setCursor(Qt.PointingHandCursor)
        self.btn_marcar_todos.clicked.connect(self._toggle_todos)
        acciones.addWidget(self.btn_marcar_todos)

        acciones.addStretch(1)

        self.btn_saltar = QPushButton("Saltar este")
        self.btn_saltar.setStyleSheet(_btn_style("#FB8C00", "#F57C00", "#EF6C00"))
        self.btn_saltar.setCursor(Qt.PointingHandCursor)
        self.btn_saltar.clicked.connect(self.saltar_actual)
        self.btn_saltar.setEnabled(False)
        acciones.addWidget(self.btn_saltar)

        self.btn_enviar = QPushButton("▶  Iniciar envío")
        self.btn_enviar.setStyleSheet(_btn_style("#2E7D32", "#1B5E20", "#1B5E20"))
        self.btn_enviar.setCursor(Qt.PointingHandCursor)
        self.btn_enviar.setMinimumWidth(240)
        self.btn_enviar.clicked.connect(self.enviar_siguiente)
        self.btn_enviar.setEnabled(False)
        acciones.addWidget(self.btn_enviar)
        root.addLayout(acciones)

        ayuda = QLabel(
            "Cómo funciona: <b>Iniciar envío</b> abre el chat con el mensaje. "
            "<b>Enter</b> en WhatsApp para enviar. Volvé y apretá <b>Siguiente</b>.")
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color:#6B7280; font-size:12px;")
        root.addWidget(ayuda)

        self.cargar()

    # ---- A implementar por la subclase --------------------------------
    def _cargar_datos(self, session, fecha, solo_prog):
        raise NotImplementedError

    def _valores_fila(self, it) -> tuple:
        raise NotImplementedError

    def _construir_mensaje(self, it) -> str:
        raise NotImplementedError

    # ---- Carga --------------------------------------------------------
    def cargar(self):
        self._fecha_actual = self.date.date().toPyDate()
        s = SessionLocal()
        try:
            self.items = self._cargar_datos(
                s, self._fecha_actual, self.chk_solo_prog.isChecked())
        except Exception as e:
            QMessageBox.critical(self, "Recordatorios",
                                 f"No se pudieron cargar los datos.\n{e}")
            self.items = []
        finally:
            s.close()

        for it in self.items:
            it["_estado_envio"] = PENDIENTE if it["valido"] else SIN_TEL
            it["_enviar"] = bool(it["valido"])

        self._idx_actual = -1
        self._poblar_tabla()
        self._reset_flujo()

        if not self.items:
            QMessageBox.information(
                self, "Recordatorios",
                "No hay datos para esa fecha con el filtro elegido.")

    def _poblar_tabla(self):
        self.tabla.setRowCount(0)
        estado_col = 1 + len(self.COLUMNAS)
        for it in self.items:
            r = self.tabla.rowCount()
            self.tabla.insertRow(r)

            chk = QTableWidgetItem()
            chk.setFlags((Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                         if it["valido"] else Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if it["_enviar"] else Qt.Unchecked)
            self.tabla.setItem(r, 0, chk)

            for i, val in enumerate(self._valores_fila(it), start=1):
                self.tabla.setItem(r, i, QTableWidgetItem(str(val)))

            self.tabla.setItem(r, estado_col, QTableWidgetItem(it["_estado_envio"]))
            _pintar_fila(self.tabla, r, it["_estado_envio"])
        self._actualizar_progreso()

    # ---- Preview -------------------------------------------------------
    def _refrescar_preview(self):
        r = self.tabla.currentRow()
        if 0 <= r < len(self.items):
            self.lbl_preview.setText(self._construir_mensaje(self.items[r]))
        else:
            self.lbl_preview.setText(
                f"— seleccioná un {self.ETIQUETA_ITEM} para ver el mensaje —")

    def _on_double_click(self, row, _col):
        if 0 <= row < len(self.items):
            self._abrir_chat(self.items[row])

    # ---- Envío secuencial ---------------------------------------------
    def _reset_flujo(self):
        hay = any(it["_enviar"] and it["valido"] for it in self.items)
        self.btn_enviar.setEnabled(hay)
        self.btn_enviar.setText("▶  Iniciar envío")
        self.btn_saltar.setEnabled(False)

    def _sync_checks(self):
        for r, it in enumerate(self.items):
            box = self.tabla.item(r, 0)
            if box is not None and it["valido"]:
                it["_enviar"] = (box.checkState() == Qt.Checked)

    def _proxima_fila(self, desde: int) -> int:
        for r in range(desde + 1, len(self.items)):
            it = self.items[r]
            if (it["_enviar"] and it["valido"]
                    and it["_estado_envio"] not in (ENVIADO, OMITIDO)):
                return r
        return -1

    def enviar_siguiente(self):
        self._sync_checks()
        if 0 <= self._idx_actual < len(self.items):
            it = self.items[self._idx_actual]
            if it["_estado_envio"] == ABIERTO:
                it["_estado_envio"] = ENVIADO
        self._continuar(self._proxima_fila(self._idx_actual))

    def saltar_actual(self):
        if 0 <= self._idx_actual < len(self.items):
            self.items[self._idx_actual]["_estado_envio"] = OMITIDO
        self._sync_checks()
        self._continuar(self._proxima_fila(self._idx_actual))

    def _continuar(self, nxt: int):
        estado_col = 1 + len(self.COLUMNAS)
        # Refrescar visualmente todo
        for r, it in enumerate(self.items):
            cell = self.tabla.item(r, estado_col)
            if cell is not None:
                cell.setText(it["_estado_envio"])
            _pintar_fila(self.tabla, r, it["_estado_envio"])
        self._actualizar_progreso()

        if nxt == -1:
            self._idx_actual = -1
            self.btn_enviar.setText("▶  Iniciar envío")
            hay = any(it["_enviar"] and it["valido"]
                      and it["_estado_envio"] not in (ENVIADO, OMITIDO)
                      for it in self.items)
            self.btn_enviar.setEnabled(hay)
            self.btn_saltar.setEnabled(False)
            enviados = sum(1 for it in self.items if it["_estado_envio"] == ENVIADO)
            QMessageBox.information(
                self, "Recordatorios",
                f"No quedan más envíos.\nEnviados: {enviados}")
            return

        self._idx_actual = nxt
        self._abrir_chat(self.items[nxt])
        self.items[nxt]["_estado_envio"] = ABIERTO
        self.tabla.selectRow(nxt)
        cell = self.tabla.item(nxt, estado_col)
        if cell is not None:
            cell.setText(ABIERTO)
        _pintar_fila(self.tabla, nxt, ABIERTO)
        self.btn_enviar.setText("✓ Enviado — Siguiente  ▶")
        self.btn_saltar.setEnabled(True)

    def _abrir_chat(self, it):
        try:
            abrir_whatsapp(
                it["telefono_norm"], self._construir_mensaje(it),
                preferir_desktop=self.chk_desktop.isChecked())
        except Exception as e:
            QMessageBox.warning(self, "Recordatorios",
                                f"No se pudo abrir WhatsApp.\n{e}")

    def _toggle_todos(self):
        marcar = any(it["valido"] and not it["_enviar"] for it in self.items)
        for r, it in enumerate(self.items):
            if not it["valido"]:
                continue
            it["_enviar"] = marcar
            box = self.tabla.item(r, 0)
            if box is not None:
                box.setCheckState(Qt.Checked if marcar else Qt.Unchecked)
        self._reset_flujo()

    def _actualizar_progreso(self):
        total = sum(1 for it in self.items if it["_enviar"] and it["valido"])
        enviados = sum(1 for it in self.items if it["_estado_envio"] == ENVIADO)
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(enviados)


# ---------------------------------------------------------------------------
# Pestaña 1: recordatorios individuales a pacientes.
# ---------------------------------------------------------------------------
class _PacientesTab(_BaseTab):
    COLUMNAS = ["Paciente", "Teléfono", "Hora", "Profesional"]
    AYUDA_PLANTILLA = (
        "Mensaje al paciente (editable). Placeholders: "
        "{tratamiento} {emoji} {nombre} {apellido} {hora} {clinica}   "
        "— {emoji} = 🌸 mujer / 👔 hombre")
    PLANTILLA_INICIAL = PLANTILLA_DEFECTO
    ETIQUETA_ITEM = "turno"
    FILTRO_ESTADOS_LABEL = "Sólo turnos Programados (sin confirmar)"

    def _cargar_datos(self, session, fecha, solo_prog):
        estados = ("Programada",) if solo_prog else ()
        return citas_para_recordar(session, fecha, estados=estados)

    def _valores_fila(self, it):
        return (
            f"{it['apellido']}, {it['nombre']}".strip(", "),
            it["telefono"] or "—",
            it["hora"],
            it["profesional"],
        )

    def _construir_mensaje(self, it):
        return construir_mensaje(
            it["nombre"], it["apellido"], it["sexo"], it["hora"],
            plantilla=self.txt_plantilla.toPlainText() or PLANTILLA_DEFECTO,
        )


# ---------------------------------------------------------------------------
# Pestaña 2: resumen del día a cada profesional.
# ---------------------------------------------------------------------------
class _ProfesionalesTab(_BaseTab):
    COLUMNAS = ["Profesional", "Teléfono", "Pacientes", "Horario"]
    AYUDA_PLANTILLA = (
        "Mensaje al profesional (editable). Placeholders: "
        "{tratamiento} {nombre} {apellido} {fecha} {cantidad} {pacientes} {clinica}   "
        "— {tratamiento} = Dra./Lic./… según el nombre")
    PLANTILLA_INICIAL = PLANTILLA_PROFESIONAL_DEFECTO
    ETIQUETA_ITEM = "profesional"
    FILTRO_ESTADOS_LABEL = "Sólo turnos Programados"

    def _cargar_datos(self, session, fecha, solo_prog):
        estados = ("Programada",) if solo_prog else ()
        return resumen_por_profesional(session, fecha, estados=estados)

    def _valores_fila(self, it):
        pacs = it["pacientes"]
        rango = f"{pacs[0]['hora']} - {pacs[-1]['hora']}" if pacs else "—"
        return (
            f"{it['apellido']}, {it['nombre']}".strip(", "),
            it["telefono"] or "—",
            str(len(pacs)),
            rango,
        )

    def _construir_mensaje(self, it):
        return construir_mensaje_profesional(
            it["nombre"], it["apellido"],
            self._fecha_actual or self.date.date().toPyDate(),
            it["pacientes"],
            plantilla=self.txt_plantilla.toPlainText() or PLANTILLA_PROFESIONAL_DEFECTO,
        )


# ---------------------------------------------------------------------------
# Diálogo contenedor con las dos pestañas.
# ---------------------------------------------------------------------------
class RecordatoriosWADialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recordatorios de WhatsApp")
        self.resize(1000, 820)

        root = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                background: #FDF2F8; color: #831843;
                padding: 10px 20px; margin-right: 4px;
                border-top-left-radius: 8px; border-top-right-radius: 8px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #DB2777; color: white;
            }
            QTabWidget::pane { border: 1px solid #F9A8D4; border-radius: 6px; }
        """)

        self.tab_pac = _PacientesTab(self)
        self.tab_prof = _ProfesionalesTab(self)
        self.tabs.addTab(self.tab_pac,  "🌸  Recordatorios a Pacientes")
        self.tabs.addTab(self.tab_prof, "🩺  Resumen a Profesionales")
        root.addWidget(self.tabs)
