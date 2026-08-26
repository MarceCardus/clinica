# controllers/abm_turnos.py
import sys
from datetime import datetime, time, timedelta

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QComboBox, QDateTimeEdit,
    QSpinBox, QTextEdit, QMessageBox, QTabWidget, QInputDialog, QTimeEdit, QDialog, QDialogButtonBox, QAction, QSizePolicy,
    QCompleter, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QDateTime, QEvent, QLocale, QTime
from sqlalchemy import func
from utils.db import SessionLocal
from controllers.planes_paciente import PlanesPaciente
# Modelos
from models.agenda      import Cita
from models.paciente    import Paciente
from models.profesional import Profesional

# Item/Plan
from models.item        import Item, ItemTipo
from models.plan_tipo   import PlanTipo

# Calendarios
from controllers.week_calendar import WeekCalendar, DayCalendar, MonthCalendar
from controllers.circular_time_picker import CircularTimePicker
from services.agenda_plan_linker import AgendaPlanLinker
from services.patient_picker import PatientPicker

COLORS = [
    "#66cdaa", "#f8d74e", "#d066d6", "#F472B6", "#f06666",
    "#3E697B", "#07DCFC", "#fcf9f9", "#09f81d"
]

class CustomDateTimeEdit(QDateTimeEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setLocale(QLocale(QLocale.Spanish, QLocale.Spain))
        self.setDisplayFormat("dd-MM-yyyy HH:mm")
        self.setDateTime(QDateTime.currentDateTime())


class ReagendarTurnoDialog(QDialog):
    def __init__(self, fecha_hora_actual, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reagendar Turno")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Selecciona la nueva fecha:"))
        self.date_edit = QDateTimeEdit(self)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(fecha_hora_actual.date())
        self.date_edit.setDisplayFormat("dd-MM-yyyy")
        layout.addWidget(self.date_edit)

        layout.addWidget(QLabel("Selecciona la nueva hora:"))
        self.time_edit = QTimeEdit(self)
        self.time_edit.setTime(fecha_hora_actual.time())
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setMinimumTime(QTime(5, 0))
        self.time_edit.setMaximumTime(QTime(21, 0))
        layout.addWidget(self.time_edit)

        self.time_edit.timeChanged.connect(self.ajustar_minutos_a_10)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def ajustar_minutos_a_10(self, qtime):
        minutos = (qtime.minute() // 10) * 10
        if qtime.minute() != minutos:
            self.time_edit.blockSignals(True)
            self.time_edit.setTime(QTime(qtime.hour(), minutos))
            self.time_edit.blockSignals(False)

    def get_datetime(self):
        fecha = self.date_edit.date()
        hora = self.time_edit.time()
        return QDateTime(fecha, hora).toPyDateTime()


class CitaForm(QMainWindow):
    ENABLED_CSS  = ""
    DISABLED_CSS = (
        "QComboBox{background:#a0a0a0; color:#202020; border:1px solid #707070;}"
        "QComboBox::drop-down{background:#8c8c8c; border-left:1px solid #707070;}"
    )
    def __init__(self, usuario_id):
        super().__init__()
        self.usuario_id = usuario_id
        self.cita_seleccionada = None

        self.setWindowTitle("ABM de Citas")
        self.resize(1200, 800)
        cw = QWidget(); self.setCentralWidget(cw)
        main = QVBoxLayout(cw)

        # Profesionales activos
        s = SessionLocal()
        self.profes = [(p.idprofesional, f"{p.nombre} {p.apellido}")
                       for p in s.query(Profesional).filter_by(estado=True).order_by(Profesional.apellido)]
        self.color_por_profesional = {pid: COLORS[i % len(COLORS)] for i, (pid, _) in enumerate(self.profes)}
        s.close()

        def _style_button(btn, base="#DB2777", hover="#BE185D", pressed="#9D174D",
                          text="#FFFFFF", radius=10, pad_v=10, pad_h=16):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(38)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {base};
                    color: {text};
                    border: none;
                    border-radius: {radius}px;
                    padding: {pad_v}px {pad_h}px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {hover};
                }}
                QPushButton:pressed {{
                    background-color: {pressed};
                }}
                QPushButton:disabled {{
                    background-color: #BDBDBD;
                    color: #EEEEEE;
                }}
            """)

        # Vistas
        self.tabs = QTabWidget()
        self.day_view   = DayCalendar(self.profes, self.color_por_profesional, parent=self, form_parent=self)
        self.week_view  = WeekCalendar(self.profes, self.color_por_profesional, parent=self, form_parent=self)
        self.month_view = MonthCalendar()
        self.tabs.addTab(self.day_view,   "Día")
        self.tabs.addTab(self.week_view,  "Semana")
        self.tabs.addTab(self.month_view, "Mes")
        main.addWidget(self.tabs)

        # ---------- Formulario inferior ----------
        form = QGridLayout(); r = 0

        form.addWidget(QLabel("Paciente:"), r, 0)
        self.ppaciente = PatientPicker(SessionLocal(), placeholder="Buscar paciente (nombre, CI, tel)…")
        form.addWidget(self.ppaciente, r, 1)

        form.addWidget(QLabel("Profesional:"), r, 2)
        self.cb_pro = QComboBox()
        for pid, nombre in self.profes:
            self.cb_pro.addItem(nombre, pid)
        form.addWidget(self.cb_pro, r, 3)

        r += 1
        form.addWidget(QLabel("Tipo:"), r, 0)
        self.cb_tipo = QComboBox(); self.cb_tipo.addItems(["Item (Producto)", "Plan de sesiones"])
        form.addWidget(self.cb_tipo, r, 1)

        form.addWidget(QLabel("Item/Producto:"), r, 2)
        self.cb_item = QComboBox(); self.cb_item.setObjectName("cb_item")
        self._setup_item_search()
        form.addWidget(self.cb_item, r, 3)

        r += 1
        form.addWidget(QLabel("Zonas del turno:"), r, 0)
        zonas_box = QWidget()
        zonas_lay = QHBoxLayout(zonas_box); zonas_lay.setContentsMargins(0, 0, 0, 0)
        self.lst_zonas = QListWidget()
        self.lst_zonas.setMaximumHeight(70)
        self.lst_zonas.setSelectionMode(QListWidget.SingleSelection)
        self.lst_zonas.setToolTip("Elegí un item arriba para agregarlo. Doble clic para quitar.")
        self.lst_zonas.itemDoubleClicked.connect(lambda _it: self._remove_zona_selected())
        self.btn_quitar_zona = QPushButton("Quitar")
        self.btn_quitar_zona.clicked.connect(self._remove_zona_selected)
        zonas_lay.addWidget(self.lst_zonas, 1)
        zonas_lay.addWidget(self.btn_quitar_zona)
        form.addWidget(zonas_box, r, 1, 1, 3)

        r += 1
        form.addWidget(QLabel("Plan:"), r, 0)
        self.cb_plan = QComboBox(); self.cb_plan.setObjectName("cb_plan")
        form.addWidget(self.cb_plan, r, 1)

        form.addWidget(QLabel("Fecha y Hora:"), r, 2)
        self.dt_inicio = CustomDateTimeEdit()
        form.addWidget(self.dt_inicio, r, 3)

        r += 1
        form.addWidget(QLabel("Duración (min):"), r, 0)
        self.sp_dur = QSpinBox(); self.sp_dur.setRange(5, 480); self.sp_dur.setValue(30)
        form.addWidget(self.sp_dur, r, 1)

        form.addWidget(QLabel("Observaciones:"), r, 2)
        self.txt_obs = QTextEdit(); self.txt_obs.setMaximumHeight(60)
        form.addWidget(self.txt_obs, r, 3)

        main.addLayout(form)

        # Botones
        btns = QHBoxLayout()
        self.btn_dictar = QPushButton("🎤 Dictar")
        self.btn_save  = QPushButton("Guardar")
        self.btn_edit  = QPushButton("Editar")
        self.btn_del   = QPushButton("Eliminar")
        self.btn_clear = QPushButton("Limpiar")
        self.btn_planes = QPushButton("Planes")
        for b in (self.btn_dictar, self.btn_save, self.btn_edit, self.btn_del, self.btn_clear, self.btn_planes):
            btns.addWidget(b)
        main.addLayout(btns)

        AZUL   = ("#DB2777", "#BE185D", "#9D174D")
        NARAN  = ("#FB8C00", "#F57C00", "#EF6C00")
        ROJO   = ("#D32F2F", "#C62828", "#B71C1C")
        GRIS   = ("#455A64", "#37474F", "#263238")
        VERDE  = ("#2E7D32", "#1B5E20", "#1B5E20")
        VIOLET = ("#7C3AED", "#6D28D9", "#5B21B6")

        btns.setSpacing(12)
        _style_button(self.btn_dictar, *VIOLET)
        _style_button(self.btn_save,   *AZUL)
        _style_button(self.btn_edit,   *NARAN)
        _style_button(self.btn_del,    *ROJO)
        _style_button(self.btn_clear,  *GRIS)
        _style_button(self.btn_planes, *VERDE)

        # Señales
        self.btn_save.clicked.connect(self.guardar_cita)
        self.btn_edit.clicked.connect(self.editar_cita)
        self.btn_del.clicked.connect(self.eliminar_cita)
        self.btn_clear.clicked.connect(self.limpiar_formulario)
        self.cb_tipo.currentIndexChanged.connect(self._toggle_tipo)
        self.btn_planes.clicked.connect(self._abrir_planes_paciente)
        self.btn_dictar.clicked.connect(self._dictar_turno)

        self._cargar_combos()
        self._toggle_tipo()
        self._cargar_citas()

        # Reordenar items segun el profesional elegido (despues de la carga inicial)
        self.cb_pro.currentIndexChanged.connect(self._on_prof_changed)
        # Autocompletar la duracion al elegir el item
        self.cb_item.currentIndexChanged.connect(self._on_item_changed)

        for w in (self.cb_pro, self.cb_tipo, self.cb_item, self.cb_plan,
                  self.dt_inicio, self.sp_dur, self.txt_obs,
                  self.btn_save, self.btn_edit, self.btn_del, self.btn_clear):
            w.installEventFilter(self)

    # ---------------- Utilidades ----------------
    def _toggle_tipo(self):
        es_item = (self.cb_tipo.currentIndex() == 0)

        self.cb_item.setEnabled(es_item)
        self.cb_item.setCursor(Qt.ArrowCursor if es_item else Qt.ForbiddenCursor)
        self.cb_item.setStyleSheet(self.ENABLED_CSS if es_item else self.DISABLED_CSS)

        # Lista de zonas: solo aplica en modo Item.
        if hasattr(self, "lst_zonas"):
            self.lst_zonas.setEnabled(es_item)
            self.btn_quitar_zona.setEnabled(es_item)
            if not es_item:
                self._clear_zonas()

        self.cb_plan.setEnabled(not es_item)
        self.cb_plan.setCursor(Qt.ArrowCursor if not es_item else Qt.ForbiddenCursor)
        self.cb_plan.setStyleSheet(self.ENABLED_CSS if not es_item else self.DISABLED_CSS)

        if es_item:
            if self.cb_plan.currentIndex() != 0:
                self.cb_plan.setCurrentIndex(0)
        else:
            if self.cb_item.currentIndex() != 0:
                self.cb_item.setCurrentIndex(0)

    def _setup_item_search(self):
        """Convierte el combo de items en un buscador con autocompletado."""
        self.cb_item.setEditable(True)
        self.cb_item.setInsertPolicy(QComboBox.NoInsert)
        le = self.cb_item.lineEdit()
        le.setPlaceholderText("Escribí para buscar item…")
        comp = self.cb_item.completer()
        comp.setCompletionMode(QCompleter.PopupCompletion)
        comp.setFilterMode(Qt.MatchContains)   # busca por cualquier parte del nombre
        comp.setCaseSensitivity(Qt.CaseInsensitive)

    def _current_prof_id(self):
        return self.cb_pro.currentData()

    def _items_frecuentes(self, s, prof_id, limite=5):
        """IDs de los items más agendados por este profesional (de más a menos)."""
        if not prof_id:
            return []
        rows = (s.query(Cita.iditem, func.count().label("n"))
                  .filter(Cita.idprofesional == prof_id, Cita.iditem.isnot(None))
                  .group_by(Cita.iditem)
                  .order_by(func.count().desc())
                  .limit(limite)
                  .all())
        return [r[0] for r in rows]

    def _poblar_cb_item(self, prof_id=None):
        """Llena el combo de items: primero los frecuentes del profesional, luego todos."""
        s = SessionLocal()
        try:
            it_producto = (s.query(ItemTipo)
                            .filter(func.lower(ItemTipo.nombre) == func.lower("PRODUCTO"))
                            .first())
            q_items = s.query(Item).filter(Item.activo.is_(True))
            if it_producto:
                q_items = q_items.filter(Item.iditemtipo == it_producto.iditemtipo)

            items = [(it.nombre, it.iditem)
                     for it in q_items.order_by(Item.nombre.asc()).all()]
            nombre_por_id = {iid: nom for nom, iid in items}
            frec_ids = [i for i in self._items_frecuentes(s, prof_id) if i in nombre_por_id]
        finally:
            s.close()

        self.cb_item.blockSignals(True)
        self.cb_item.clear()
        self.cb_item.addItem("Seleccionar Item", None)
        if frec_ids:
            for iid in frec_ids:
                self.cb_item.addItem(f"★ {nombre_por_id[iid]}", iid)
            self.cb_item.insertSeparator(self.cb_item.count())
        for nom, iid in items:
            self.cb_item.addItem(nom, iid)
        self.cb_item.setCurrentIndex(0)
        self.cb_item.blockSignals(False)

    def _on_prof_changed(self, *_):
        # Al cambiar de profesional, reordenamos los items por sus frecuentes.
        self._poblar_cb_item(self._current_prof_id())

    def _duracion_sugerida(self, item_id):
        """Duracion mas usada (moda) para este item en el historial de citas."""
        if not item_id:
            return None
        s = SessionLocal()
        try:
            row = (s.query(Cita.duracion, func.count().label("n"))
                     .filter(Cita.iditem == item_id, Cita.duracion.isnot(None))
                     .group_by(Cita.duracion)
                     .order_by(func.count().desc())
                     .first())
            return int(row[0]) if row and row[0] else None
        finally:
            s.close()

    def _on_item_changed(self, *_):
        # Al elegir un item en el combo, lo agregamos como zona del turno.
        iid = self.cb_item.currentData()
        if iid is None:
            return
        nombre = self.cb_item.currentText().lstrip("★ ").strip()
        primera = (self.lst_zonas.count() == 0)
        agregada = self._add_zona(iid, nombre)
        # La duracion sugerida solo la fijamos con la primera zona (es editable).
        if agregada and primera:
            dur = self._duracion_sugerida(iid)
            if dur:
                self.sp_dur.setValue(dur)
        # Reseteamos el combo para poder elegir la siguiente zona.
        self.cb_item.blockSignals(True)
        self.cb_item.setCurrentIndex(0)
        if self.cb_item.lineEdit() is not None:
            self.cb_item.lineEdit().clear()
        self.cb_item.blockSignals(False)

    # ---------------- Zonas del turno ----------------
    def _zonas_ids(self):
        return [self.lst_zonas.item(i).data(Qt.UserRole)
                for i in range(self.lst_zonas.count())]

    def _add_zona(self, iid, nombre):
        """Agrega una zona si no está ya en la lista. Devuelve True si la agregó."""
        if iid is None or iid in self._zonas_ids():
            return False
        it = QListWidgetItem(nombre)
        it.setData(Qt.UserRole, iid)
        self.lst_zonas.addItem(it)
        return True

    def _remove_zona_selected(self):
        row = self.lst_zonas.currentRow()
        if row >= 0:
            self.lst_zonas.takeItem(row)

    def _clear_zonas(self):
        self.lst_zonas.clear()

    def _set_zonas(self, pares):
        """pares: lista de (iditem, nombre). El primero será la zona principal."""
        self._clear_zonas()
        for iid, nombre in pares:
            self._add_zona(iid, nombre)

    def _cargar_combos(self):
        self._poblar_cb_item(self._current_prof_id())

        s = SessionLocal()
        try:
            self.cb_plan.blockSignals(True)
            self.cb_plan.clear()
            self.cb_plan.addItem("Seleccionar Plan", None)

            for pl in (s.query(PlanTipo)
                        .filter(PlanTipo.activo.is_(True))
                        .order_by(PlanTipo.nombre.asc())
                        .all()):
                self.cb_plan.addItem(pl.nombre, pl.idplantipo)
            self.cb_plan.blockSignals(False)
        finally:
            s.close()

    def _cargar_citas(self):
        self.day_view.clear_events()
        self.week_view.clear_events()

        # Rango visible = unión de la semana (week_view) y el día (day_view).
        # Evita traer toda la tabla cita en cada navegación (saturaba la red/BD).
        desde = min(self.day_view.start_date, self.week_view.start_date)
        hasta = max(
            self.day_view.start_date + timedelta(days=1),
            self.week_view.start_date + timedelta(days=7),
        )
        inicio = datetime.combine(desde, time.min)
        fin = datetime.combine(hasta, time.min)

        s = SessionLocal()
        citas = (s.query(Cita)
                   .filter(Cita.fecha_inicio >= inicio,
                           Cita.fecha_inicio < fin)
                   .all())
        self.day_view.add_eventos_batch(citas)
        self.week_view.add_eventos_batch(citas)
        s.close()
        self.month_view._on_date_changed()

    def _selected_paciente_id(self):
        return self.ppaciente.current_id()

    def _set_cita_refs(self, c, item_id=None, plan_id=None):
        if hasattr(c, "iditem"): c.iditem = None
        if hasattr(c, "idplantipo"): c.idplantipo = None
        if item_id and hasattr(c, "iditem"): c.iditem = item_id
        if plan_id and hasattr(c, "idplantipo"): c.idplantipo = plan_id

    # ---------------- Acciones ----------------

    def seleccionar_cita_por_id(self, cita_id):
        if isinstance(cita_id, list):
            if len(cita_id) == 1:
                cita_id = cita_id[0]
            elif len(cita_id) > 1:
                s = SessionLocal()
                opciones, id_map = [], []
                for cid in cita_id:
                    c = s.query(Cita).get(cid)
                    if c and c.paciente:
                        opciones.append(f"{c.paciente.nombre} {c.paciente.apellido} - {c.fecha_inicio.strftime('%d/%m %H:%M')} (ID {cid})")
                    else:
                        opciones.append(f"ID {cid}")
                    id_map.append(cid)
                s.close()
                idx, ok = QInputDialog.getItem(self, "Turnos en este horario", "Seleccione el turno:", opciones, 0, False)
                if ok and idx:
                    for op, cid in zip(opciones, id_map):
                        if op == idx:
                            cita_id = cid
                            break
                else:
                    return
            else:
                return

        if cita_id is None:
            return

        s = SessionLocal()
        c = s.query(Cita).get(cita_id)
        # Capturamos las zonas (item principal primero) antes de cerrar la sesión.
        zonas_pares = []
        if c:
            principal = getattr(c, "iditem", None)
            if principal and c.item:
                zonas_pares.append((principal, c.item.nombre))
            for it in (c.zonas or []):
                if it.iditem != principal:
                    zonas_pares.append((it.iditem, it.nombre))
        s.close()
        if not c:
            QMessageBox.warning(self, "Error", "No se encontró la cita.")
            return

        self.cita_seleccionada = cita_id

        if c.paciente:
            display = f"{c.paciente.apellido or ''}, {c.paciente.nombre or ''}".strip(", ")
            try:
                self.ppaciente.set_current(int(c.idpaciente), display_text=display)
            except Exception:
                pass

        if c.idprofesional:
            idx_pro = self.cb_pro.findData(c.idprofesional)
            if idx_pro >= 0:
                self.cb_pro.setCurrentIndex(idx_pro)

        item_id = getattr(c, "iditem", None) or getattr(c, "idproducto", None)
        plan_id = getattr(c, "idplantipo", None)

        if item_id:
            self.cb_tipo.setCurrentIndex(0); self._toggle_tipo()
            self._set_zonas(zonas_pares)
        elif plan_id:
            self.cb_tipo.setCurrentIndex(1); self._toggle_tipo()
            idx_pl = self.cb_plan.findData(plan_id)
            if idx_pl >= 0: self.cb_plan.setCurrentIndex(idx_pl)

        self.dt_inicio.setDateTime(QDateTime(c.fecha_inicio))
        self.sp_dur.setValue(c.duracion or 30)
        self.txt_obs.setPlainText(c.observaciones or "")

    def editar_cita(self):
        if not self.cita_seleccionada:
            QMessageBox.warning(self, "Atención", "Selecciona un turno de la grilla para editar.")
            return

        s = SessionLocal()
        c = s.query(Cita).get(self.cita_seleccionada)
        if not c:
            s.close()
            QMessageBox.warning(self, "Error", "No se encontró la cita.")
            return

        dlg = ReagendarTurnoDialog(QDateTime(c.fecha_inicio), self)
        if dlg.exec_() != QDialog.Accepted:
            s.close(); return
        nueva_fecha_hora = dlg.get_datetime()

        pid = self._selected_paciente_id()
        if not pid:
            s.close()
            QMessageBox.warning(self, "Error", "Debes seleccionar un paciente.")
            return

        es_item = (self.cb_tipo.currentIndex() == 0)
        zonas   = self._zonas_ids() if es_item else []
        item_id = zonas[0] if zonas else None
        plan_id = self.cb_plan.currentData() if not es_item else None

        if (es_item and not zonas) or ((not es_item) and not plan_id):
            s.close()
            QMessageBox.warning(self, "Error",
                                "Agregá al menos una zona (item) o seleccioná un Plan.")
            return

        c.idpaciente    = int(pid)
        c.idprofesional = self.cb_pro.currentData()
        self._set_cita_refs(c, item_id=item_id, plan_id=plan_id)
        self._sync_zonas_cita(s, c, zonas)
        c.fecha_inicio  = nueva_fecha_hora
        c.duracion      = self.sp_dur.value()
        c.observaciones = self.txt_obs.toPlainText().strip()

        AgendaPlanLinker.on_cita_creada_o_editada(s, c)

        s.commit(); s.close()
        self.limpiar_formulario(); self._cargar_citas()
        QMessageBox.information(self, "Ok", "Turno actualizado.")

    def eliminar_cita(self):
        if not self.cita_seleccionada:
            QMessageBox.warning(self, "Atención", "Selecciona un turno de la grilla para eliminar.")
            return
        if QMessageBox.question(self, "Confirmar", "¿Eliminar este turno?") != QMessageBox.Yes:
            return
        s = SessionLocal()
        c = s.query(Cita).get(self.cita_seleccionada)
        if c:
            AgendaPlanLinker.on_cita_cancelada_o_eliminada(s, c)
            s.delete(c); s.commit()
        s.close()
        self.limpiar_formulario(); self._cargar_citas()
        QMessageBox.information(self, "Ok", "Turno eliminado.")

    def limpiar_formulario(self, _checked=False, keep_context=False):
        self.cita_seleccionada = None
        try: self.ppaciente.set_current(None, "")
        except Exception: pass

        if keep_context and getattr(self, "_last_prof_id", None) is not None:
            # Mantener profesional e item del ultimo turno (carga en serie)
            idx_pro = self.cb_pro.findData(self._last_prof_id)
            if idx_pro >= 0:
                self.cb_pro.setCurrentIndex(idx_pro)   # dispara _poblar_cb_item
            self.cb_tipo.setCurrentIndex(0); self._toggle_tipo()
            self._clear_zonas()
            if getattr(self, "_last_item_id", None):
                idx_it = self.cb_item.findData(self._last_item_id)
                if idx_it >= 0:
                    nombre = self.cb_item.itemText(idx_it).lstrip("★ ").strip()
                    self._add_zona(self._last_item_id, nombre)
        else:
            if self.cb_pro.count(): self.cb_pro.setCurrentIndex(0)
            self.cb_tipo.setCurrentIndex(0); self._toggle_tipo()
            self.cb_item.setCurrentIndex(0)
            self._clear_zonas()

        self.cb_plan.setCurrentIndex(0)
        self.dt_inicio.setDateTime(QDateTime.currentDateTime())
        if not keep_context:
            # con keep_context la duracion la fija _on_item_changed al reponer el item
            self.sp_dur.setValue(30)
        self.txt_obs.clear()

    def _recordar_contexto(self, prof_id, item_id):
        self._last_prof_id = prof_id
        self._last_item_id = item_id

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Down):
                self.focusNextChild(); return True
            if event.key() == Qt.Key_Up:
                self.focusPreviousChild(); return True
        return super().eventFilter(obj, event)

    def _validar_form_cita(self):
        """Valida el formulario. Devuelve (pid, item_id, plan_id, fecha, zonas) o
        None (mostrando el aviso correspondiente). `zonas` es la lista de iditem
        del turno; `item_id` es la primera (zona principal)."""
        pid = self._selected_paciente_id()
        if not pid:
            QMessageBox.warning(self, "Error", "Debes seleccionar un paciente.")
            return None

        es_item = (self.cb_tipo.currentIndex() == 0)
        zonas   = self._zonas_ids() if es_item else []
        item_id = zonas[0] if zonas else None
        plan_id = self.cb_plan.currentData() if not es_item else None

        if es_item and not zonas:
            QMessageBox.warning(self, "Error", "Agregá al menos una zona (item) al turno.")
            return None
        if (not es_item) and not plan_id:
            QMessageBox.warning(self, "Error", "Selecciona un Plan.")
            return None

        fecha = self.dt_inicio.dateTime().toPyDateTime()
        return int(pid), item_id, plan_id, fecha, zonas

    def _sync_zonas_cita(self, s, cita, zonas):
        """Sincroniza las zonas (items) del turno en la tabla puente cita_item."""
        if zonas:
            cita.zonas = [s.get(Item, iid) for iid in zonas if iid]
        else:
            cita.zonas = []

    def _guardar_en_agenda(self, pid, item_id, plan_id, fecha, zonas=None):
        """Persiste la cita y refresca la agenda. Asume datos ya validados."""
        s = SessionLocal()
        nueva = Cita(
            idpaciente    = pid,
            idprofesional = self.cb_pro.currentData(),
            fecha_inicio  = fecha,
            duracion      = self.sp_dur.value(),
            observaciones = self.txt_obs.toPlainText().strip()
        )
        self._set_cita_refs(nueva, item_id=item_id, plan_id=plan_id)
        s.add(nueva); s.flush()
        self._sync_zonas_cita(s, nueva, zonas)

        AgendaPlanLinker.on_cita_creada_o_editada(s, nueva)

        s.commit(); s.close()
        self._recordar_contexto(self.cb_pro.currentData(), item_id)
        self.limpiar_formulario(keep_context=True); self._cargar_citas()

    def guardar_cita(self):
        datos = self._validar_form_cita()
        if not datos:
            return
        pid, item_id, plan_id, fecha, zonas = datos

        nombre_paciente = self.ppaciente.input.text().strip() or "el paciente seleccionado"
        if QMessageBox.question(
            self, "Confirmar",
            f"¿Desea agendar a {nombre_paciente} para {fecha.strftime('%d/%m/%Y %H:%M')}?"
        ) != QMessageBox.Yes:
            return

        self._guardar_en_agenda(pid, item_id, plan_id, fecha, zonas)
        QMessageBox.information(self, "Ok", "Turno agendado.")

    # ---------------- Dictado por voz ----------------
    def _dictar_turno(self):
        try:
            from services.dictado_turno import DictadoDialog
        except Exception as e:
            QMessageBox.critical(
                self, "Dictado",
                "Falta instalar el motor de dictado.\n\n"
                "Ejecutá en la terminal del proyecto:\n"
                "    venv\\Scripts\\pip install faster-whisper\n\n"
                f"Detalle: {e}"
            )
            return

        try:
            dlg = DictadoDialog(self)
            if dlg.exec_() != QDialog.Accepted or not dlg.resultado:
                return
        except Exception as e:
            import traceback
            QMessageBox.critical(
                self, "Dictado",
                "No se pudo iniciar el dictado por voz.\n\n"
                f"Detalle: {e}\n\n"
                "Revisá que el micrófono esté disponible y que el "
                "ejecutable incluya las dependencias de audio."
            )
            traceback.print_exc()
            return
        self._aplicar_dictado(dlg.resultado)

    def _aplicar_dictado(self, r):
        """Rellena el formulario con lo dictado y, si reconoció todo con
        seguridad, agenda el turno directo (con una única confirmación).
        Si algo quedó dudoso, deja el formulario cargado para revisar."""
        import difflib
        resumen = [f"Escuché: «{r.get('texto', '')}»", ""]

        def _norm(s):
            import unicodedata
            s = "".join(c for c in unicodedata.normalize("NFD", s or "")
                        if unicodedata.category(c) != "Mn")
            return s.lower().strip()

        pac_ok = prof_ok = item_ok = False

        # --- Paciente ---
        pac_txt = r.get("paciente")
        if pac_txt:
            pid, disp, score = self._match_paciente(pac_txt)
            if pid:
                self.ppaciente.set_current(pid, disp)
                pac_ok = score >= 0.6
                resumen.append(f"{'✓' if pac_ok else '≈'} Paciente: {disp}")
            else:
                self.ppaciente.set_current(None, pac_txt)
                resumen.append(f"✗ Paciente «{pac_txt}»: no encontrado, revisá.")
        else:
            resumen.append("✗ Paciente: no se entendió.")

        # --- Profesional ---
        prof_txt = r.get("profesional")
        if prof_txt:
            best_i, best_s = -1, 0.0
            npt = _norm(prof_txt)
            for i in range(self.cb_pro.count()):
                nombre = self.cb_pro.itemText(i)
                nn = _norm(nombre)
                s = difflib.SequenceMatcher(None, npt, nn).ratio()
                if npt in nn or any(npt in p for p in nn.split()):
                    s = max(s, 0.85)
                if s > best_s:
                    best_s, best_i = s, i
            if best_i >= 0 and best_s >= 0.4:
                self.cb_pro.setCurrentIndex(best_i)
                prof_ok = best_s >= 0.6
                resumen.append(f"{'✓' if prof_ok else '≈'} Profesional: {self.cb_pro.itemText(best_i)}")
            else:
                resumen.append(f"✗ Profesional «{prof_txt}»: no reconocido, revisá.")
        else:
            resumen.append("✗ Profesional: no se entendió.")

        # --- Item ---
        item_txt = r.get("item")
        if item_txt:
            self.cb_tipo.setCurrentIndex(0); self._toggle_tipo()
            best_i, best_s = -1, 0.0
            nit = _norm(item_txt)
            for i in range(self.cb_item.count()):
                if self.cb_item.itemData(i) is None:
                    continue
                nombre = self.cb_item.itemText(i).lstrip("★ ").strip()
                nn = _norm(nombre)
                s = difflib.SequenceMatcher(None, nit, nn).ratio()
                if nit and nit in nn:
                    s = max(s, 0.85)
                if s > best_s:
                    best_s, best_i = s, i
            if best_i >= 0 and best_s >= 0.4:
                self.cb_item.setCurrentIndex(best_i)
                self._on_item_changed()
                item_ok = best_s >= 0.6
                resumen.append(f"{'✓' if item_ok else '≈'} Item: {self.cb_item.itemText(best_i).lstrip('★ ').strip()}")
            else:
                resumen.append(f"✗ Item «{item_txt}»: no reconocido, revisá.")
        else:
            resumen.append("✗ Item: no se entendió.")

        # --- Fecha / Hora ---
        actual = self.dt_inicio.dateTime().toPyDateTime()
        fecha = r.get("fecha") or actual.date()
        hora  = r.get("hora")
        if hora is None:
            hora = actual.time()
        nuevo = datetime.combine(fecha, hora)
        self.dt_inicio.setDateTime(QDateTime(nuevo))
        dt_ok = bool(r.get("fecha")) and bool(r.get("hora"))
        if r.get("fecha") or r.get("hora"):
            resumen.append(f"{'✓' if dt_ok else '≈'} Fecha y hora: {nuevo.strftime('%d/%m/%Y %H:%M')}")
        else:
            resumen.append("✗ Fecha y hora: no se entendió (dejo la actual).")

        # --- Agendar directo si todo salió bien ---
        todo_ok = pac_ok and prof_ok and item_ok and dt_ok
        if todo_ok:
            datos = self._validar_form_cita()
            if datos:
                pid, item_id, plan_id, fecha_v, zonas = datos
                msg = "\n".join(resumen) + "\n\n¿Agendar este turno?"
                if QMessageBox.question(self, "Confirmar turno dictado", msg) == QMessageBox.Yes:
                    self._guardar_en_agenda(pid, item_id, plan_id, fecha_v, zonas)
                    QMessageBox.information(self, "Ok", "✓ Turno agendado en la agenda.")
                    return
                # Dijeron que no: dejamos el formulario cargado para editar.
                return

        # Algo quedó dudoso: no guardamos, dejamos todo cargado para revisar.
        resumen.append("")
        resumen.append("⚠ Revisá los campos marcados y apretá «Guardar».")
        QMessageBox.information(self, "Dictado cargado — revisá", "\n".join(resumen))

    def _match_paciente(self, texto):
        """Mejor coincidencia de paciente contra la base. -> (id, display, score)."""
        import difflib, unicodedata
        def _n(s):
            s = "".join(c for c in unicodedata.normalize("NFD", s or "")
                        if unicodedata.category(c) != "Mn")
            return s.lower().strip()

        tokens = [t for t in _n(texto).split() if len(t) >= 2]
        if not tokens:
            return None, texto, 0.0

        s = SessionLocal()
        try:
            from sqlalchemy import or_
            filtros = []
            for t in tokens:
                like = f"%{t}%"
                filtros.append(func.lower(Paciente.nombre).like(like))
                filtros.append(func.lower(Paciente.apellido).like(like))
            rows = (s.query(Paciente.idpaciente, Paciente.apellido, Paciente.nombre)
                      .filter(or_(*filtros))
                      .limit(40).all())
        finally:
            s.close()

        objetivo = _n(texto)
        best = (None, texto, 0.0)
        for pid, ap, no in rows:
            for cand in (f"{no} {ap}", f"{ap} {no}"):
                sc = difflib.SequenceMatcher(None, objetivo, _n(cand)).ratio()
                # bonus si todos los tokens aparecen
                if all(tok in _n(cand) for tok in tokens):
                    sc = max(sc, 0.8)
                if sc > best[2]:
                    disp = f"{ap or ''}, {no or ''}".strip(", ")
                    best = (int(pid), disp, sc)
        return best

    def _abrir_planes_paciente(self):
        pid = self._selected_paciente_id()
        if not pid:
            QMessageBox.information(self, "Planes del paciente", "Seleccioná un paciente primero.")
            return
        try:
            dlg = PlanesPaciente(self, idpaciente=int(pid))
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Planes del paciente", f"No se pudo abrir el gestor de planes.\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = CitaForm(usuario_id=1)
    w.show()
    sys.exit(app.exec_())
