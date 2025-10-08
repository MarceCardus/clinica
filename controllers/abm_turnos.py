# controllers/abm_turnos.py
import sys
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QComboBox, QDateTimeEdit,
    QSpinBox, QTextEdit, QMessageBox, QTabWidget, QInputDialog, QTimeEdit, QDialog, QDialogButtonBox, QAction, QSizePolicy
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
    "#66cdaa", "#f8d74e", "#d066d6", "#66b5f0", "#f06666",
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

        def _style_button(btn, base="#1976D2", hover="#1565C0", pressed="#0D47A1",
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
        form.addWidget(self.cb_item, r, 3)

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
        self.btn_save  = QPushButton("Guardar")
        self.btn_edit  = QPushButton("Editar")
        self.btn_del   = QPushButton("Eliminar")
        self.btn_clear = QPushButton("Limpiar")
        self.btn_planes = QPushButton("Planes")
        for b in (self.btn_save, self.btn_edit, self.btn_del, self.btn_clear, self.btn_planes):
            btns.addWidget(b)
        main.addLayout(btns)

        AZUL   = ("#1976D2", "#1565C0", "#0D47A1")
        NARAN  = ("#FB8C00", "#F57C00", "#EF6C00")
        ROJO   = ("#D32F2F", "#C62828", "#B71C1C")
        GRIS   = ("#455A64", "#37474F", "#263238")
        VERDE  = ("#2E7D32", "#1B5E20", "#1B5E20")

        btns.setSpacing(12)
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

        self._cargar_combos()
        self._toggle_tipo()
        self._cargar_citas()

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

        self.cb_plan.setEnabled(not es_item)
        self.cb_plan.setCursor(Qt.ArrowCursor if not es_item else Qt.ForbiddenCursor)
        self.cb_plan.setStyleSheet(self.ENABLED_CSS if not es_item else self.DISABLED_CSS)

        if es_item:
            if self.cb_plan.currentIndex() != 0:
                self.cb_plan.setCurrentIndex(0)
        else:
            if self.cb_item.currentIndex() != 0:
                self.cb_item.setCurrentIndex(0)

    def _cargar_combos(self):
        s = SessionLocal()
        try:
            self.cb_item.blockSignals(True)
            self.cb_item.clear()
            self.cb_item.addItem("Seleccionar Item", None)

            it_producto = (s.query(ItemTipo)
                            .filter(func.lower(ItemTipo.nombre) == func.lower("PRODUCTO"))
                            .first())

            q_items = s.query(Item).filter(Item.activo.is_(True))
            if it_producto:
                q_items = q_items.filter(Item.iditemtipo == it_producto.iditemtipo)

            for it in q_items.order_by(Item.nombre.asc()).all():
                self.cb_item.addItem(it.nombre, it.iditem)
            self.cb_item.blockSignals(False)

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
        s = SessionLocal()
        citas = s.query(Cita).all()
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
            idx_it = self.cb_item.findData(item_id)
            if idx_it >= 0: self.cb_item.setCurrentIndex(idx_it)
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
        item_id = self.cb_item.currentData() if es_item else None
        plan_id = self.cb_plan.currentData() if not es_item else None

        if (es_item and not item_id) or ((not es_item) and not plan_id):
            s.close()
            QMessageBox.warning(self, "Error", "Selecciona un Item o un Plan (según el tipo).")
            return

        c.idpaciente    = int(pid)
        c.idprofesional = self.cb_pro.currentData()
        self._set_cita_refs(c, item_id=item_id, plan_id=plan_id)
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

    def limpiar_formulario(self):
        self.cita_seleccionada = None
        try: self.ppaciente.set_current(None, "")
        except Exception: pass
        if self.cb_pro.count(): self.cb_pro.setCurrentIndex(0)
        self.cb_tipo.setCurrentIndex(0); self._toggle_tipo()
        self.cb_item.setCurrentIndex(0); self.cb_plan.setCurrentIndex(0)
        self.dt_inicio.setDateTime(QDateTime.currentDateTime())
        self.sp_dur.setValue(30); self.txt_obs.clear()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Down):
                self.focusNextChild(); return True
            if event.key() == Qt.Key_Up:
                self.focusPreviousChild(); return True
        return super().eventFilter(obj, event)

    def guardar_cita(self):
        pid = self._selected_paciente_id()
        if not pid:
            QMessageBox.warning(self, "Error", "Debes seleccionar un paciente.")
            return

        es_item = (self.cb_tipo.currentIndex() == 0)
        item_id = self.cb_item.currentData() if es_item else None
        plan_id = self.cb_plan.currentData() if not es_item else None

        if (es_item and not item_id) or ((not es_item) and not plan_id):
            QMessageBox.warning(self, "Error", "Selecciona un Item o un Plan (según el tipo).")
            return

        fecha = self.dt_inicio.dateTime().toPyDateTime()
        nombre_paciente = self.ppaciente.input.text().strip() or "el paciente seleccionado"
        if QMessageBox.question(
            self, "Confirmar",
            f"¿Desea agendar a {nombre_paciente} para {fecha.strftime('%d/%m/%Y %H:%M')}?"
        ) != QMessageBox.Yes:
            return

        s = SessionLocal()
        nueva = Cita(
            idpaciente    = int(pid),
            idprofesional = self.cb_pro.currentData(),
            fecha_inicio  = fecha,
            duracion      = self.sp_dur.value(),
            observaciones = self.txt_obs.toPlainText().strip()
        )
        self._set_cita_refs(nueva, item_id=item_id, plan_id=plan_id)
        s.add(nueva); s.flush()

        AgendaPlanLinker.on_cita_creada_o_editada(s, nueva)

        s.commit(); s.close()
        self.limpiar_formulario(); self._cargar_citas()
        QMessageBox.information(self, "Ok", "Turno agendado.")

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
