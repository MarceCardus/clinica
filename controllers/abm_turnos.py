import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QComboBox, QDateTimeEdit,
    QSpinBox, QTextEdit, QMessageBox, QTabWidget, QCompleter, QInputDialog, QTimeEdit, QDialog, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QDateTime, QEvent, QLocale, QTime
from utils.db import SessionLocal
from models.agenda      import Cita
from models.paciente    import Paciente
from models.profesional import Profesional
from models.producto    import Producto
from models.paquete     import Paquete
from controllers.week_calendar import WeekCalendar, DayCalendar, MonthCalendar
from datetime import datetime
from controllers.circular_time_picker import CircularTimePicker

COLORS = [
    "#66cdaa", "#f8d74e", "#d066d6", "#66b5f0", "#f06666",
    "#042f42", "#FC0AF0", "#fcf9f9", "#09f81d"
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

        # Fecha
        layout.addWidget(QLabel("Selecciona la nueva fecha:"))
        self.date_edit = QDateTimeEdit(self)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(fecha_hora_actual.date())
        self.date_edit.setDisplayFormat("dd-MM-yyyy")
        layout.addWidget(self.date_edit)

        # Hora
        layout.addWidget(QLabel("Selecciona la nueva hora:"))
        self.time_edit = QTimeEdit(self)
        self.time_edit.setTime(fecha_hora_actual.time())
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setMinimumTime(QTime(5, 0))
        self.time_edit.setMaximumTime(QTime(21, 0))
        layout.addWidget(self.time_edit)

        # Forzamos minutos de a 10
        self.time_edit.timeChanged.connect(self.ajustar_minutos_a_10)

        # Botones
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def ajustar_minutos_a_10(self, qtime):
        minutos = (qtime.minute() // 10) * 10
        # Previene loops infinitos:
        if qtime.minute() != minutos:
            self.time_edit.blockSignals(True)
            self.time_edit.setTime(QTime(qtime.hour(), minutos))
            self.time_edit.blockSignals(False)

    def get_datetime(self):
        fecha = self.date_edit.date()
        hora = self.time_edit.time()
        return QDateTime(fecha, hora).toPyDateTime()
class ReagendarDialog(QDialog):
    def __init__(self, fecha_actual, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reagendar Turno")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Selecciona nueva fecha y hora para el turno:"))

        self.dt_nueva = QDateTimeEdit(self)
        self.dt_nueva.setCalendarPopup(True)
        self.dt_nueva.setDateTime(QDateTime(fecha_actual))
        layout.addWidget(self.dt_nueva)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_datetime(self):
        return self.dt_nueva.dateTime().toPyDateTime()

class CitaForm(QMainWindow):
    def __init__(self, usuario_id):
        super().__init__()
        self.usuario_id = usuario_id
        self.cita_seleccionada = None

        self.setWindowTitle("ABM de Citas")
        self.resize(1200, 800)
        cw = QWidget()
        self.setCentralWidget(cw)
        main = QVBoxLayout(cw)

        # Profesionales
        s = SessionLocal()
        self.profes = [(p.idprofesional, f"{p.nombre} {p.apellido}")
                       for p in s.query(Profesional).order_by(Profesional.apellido)]
        # Colores fijos
        self.color_por_profesional = {
            pid: COLORS[i % len(COLORS)] for i, (pid, _) in enumerate(self.profes)
        }
        s.close()

        self.tabs = QTabWidget()
        self.day_view   = DayCalendar(self.profes, self.color_por_profesional, parent=self, form_parent=self)
        self.week_view  = WeekCalendar(self.profes, self.color_por_profesional, parent=self, form_parent=self)
        self.month_view = MonthCalendar()
        self.tabs.addTab(self.day_view,   "Día")
        self.tabs.addTab(self.week_view,  "Semana")
        self.tabs.addTab(self.month_view, "Mes")
        main.addWidget(self.tabs)

        # Cargar los formularios
        form = QGridLayout()
        r = 0
        form.addWidget(QLabel("Paciente:"), r, 0)
        self.cb_paciente = QComboBox()
        self.cb_paciente.setEditable(True)  # Permite escribir y buscar
        self.cb_paciente.addItem("Seleccionar Paciente", None)
        form.addWidget(self.cb_paciente, r, 1)

        form.addWidget(QLabel("Profesional:"), r, 2)
        self.cb_pro = QComboBox()
        for pid, nombre in self.profes:
            self.cb_pro.addItem(nombre, pid)
        form.addWidget(self.cb_pro, r, 3)

        r += 1
        form.addWidget(QLabel("Producto:"), r, 0)
        self.cb_prod = QComboBox()
        form.addWidget(self.cb_prod, r, 1)
        form.addWidget(QLabel("Paquete:"), r, 2)
        self.cb_paquete = QComboBox()
        form.addWidget(self.cb_paquete, r, 3)

        r += 1
        form.addWidget(QLabel("Fecha y Hora:"), r, 0)
        self.dt_inicio = CustomDateTimeEdit()
        form.addWidget(self.dt_inicio, r, 1)
        form.addWidget(QLabel("Duración (min):"), r, 2)
        self.sp_dur = QSpinBox()
        self.sp_dur.setRange(5, 480)
        self.sp_dur.setValue(30)
        form.addWidget(self.sp_dur, r, 3)

        r += 1
        form.addWidget(QLabel("Observaciones:"), r, 0)
        self.txt_obs = QTextEdit()
        self.txt_obs.setMaximumHeight(60)
        form.addWidget(self.txt_obs, r, 1, 1, 3)
        main.addLayout(form)

        # Botones de acción
        btns = QHBoxLayout()
        self.btn_save  = QPushButton("Guardar")
        self.btn_edit  = QPushButton("Editar")
        self.btn_del   = QPushButton("Eliminar")
        self.btn_clear = QPushButton("Limpiar")
        for b in (self.btn_save, self.btn_edit, self.btn_del, self.btn_clear):
            btns.addWidget(b)
        main.addLayout(btns)

        self.btn_save.clicked.connect(self.guardar_cita)
        self.btn_edit.clicked.connect(self.editar_cita)
        self.btn_del.clicked.connect(self.eliminar_cita)
        self.btn_clear.clicked.connect(self.limpiar_formulario)

        self._cargar_combos()
        self._cargar_citas()

        for w in (
            self.cb_paciente, self.cb_pro, self.cb_prod, self.cb_paquete,
            self.dt_inicio, self.sp_dur, self.txt_obs,
            self.btn_save, self.btn_edit, self.btn_del, self.btn_clear
        ):
            w.installEventFilter(self)

    def seleccionar_cita_por_id(self, cita_id):
        # Si viene una lista, mostrar para elegir, o agarrar el primero
        if isinstance(cita_id, list):
            if len(cita_id) == 1:
                cita_id = cita_id[0]
            elif len(cita_id) > 1:
                # Mostrar un diálogo para elegir cuál cita, con datos claros
                s = SessionLocal()
                opciones = []
                id_map = []
                for cid in cita_id:
                    c = s.query(Cita).get(cid)
                    if c and c.paciente:
                        opciones.append(f"{c.paciente.nombre} {c.paciente.apellido} - {c.fecha_inicio.strftime('%d/%m %H:%M')} (ID {cid})")
                        id_map.append(cid)
                    else:
                        opciones.append(f"ID {cid}")
                        id_map.append(cid)
                s.close()
                idx, ok = QInputDialog.getItem(
                    self, 
                    "Turnos en este horario", 
                    "Seleccione el turno:",
                    opciones, 
                    0, 
                    False
                )
                if ok and idx:
                    # Buscar el ID elegido por el texto
                    for op, cid in zip(opciones, id_map):
                        if op == idx:
                            cita_id = cid
                            break
                else:
                    return  # El usuario canceló
            else:
                return  # Lista vacía, no hace nada

        if cita_id is None:
            return

        s = SessionLocal()
        c = s.query(Cita).get(cita_id)
        s.close()
        if not c:
            QMessageBox.warning(self, "Error", "No se encontró la cita.")
            return

        self.cita_seleccionada = cita_id
        idx_pac = self.cb_paciente.findData(c.idpaciente)
        idx_pro = self.cb_pro.findData(c.idprofesional)
        idx_prod = self.cb_prod.findData(c.idproducto)
        idx_pack = self.cb_paquete.findData(c.idpaquete)
        if idx_pac >= 0: self.cb_paciente.setCurrentIndex(idx_pac)
        if idx_pro >= 0: self.cb_pro.setCurrentIndex(idx_pro)
        if idx_prod >= 0: self.cb_prod.setCurrentIndex(idx_prod)
        if idx_pack >= 0: self.cb_paquete.setCurrentIndex(idx_pack)
        self.dt_inicio.setDateTime(QDateTime(c.fecha_inicio))
        self.sp_dur.setValue(c.duracion)
        self.txt_obs.setPlainText(c.observaciones or "")

    def _cargar_combos(self):
        s = SessionLocal()
        self.cb_paciente.blockSignals(True)
        self.cb_paciente.clear()
        self.cb_paciente.addItem("Seleccionar Paciente", None)
        pacientes_lista = []

        for p in s.query(Paciente).order_by(Paciente.apellido):
            nombre_completo = f"{p.nombre} {p.apellido}"
            self.cb_paciente.addItem(nombre_completo, p.idpaciente)
            pacientes_lista.append(nombre_completo)

        self.cb_paciente.blockSignals(False)
        self.cb_paciente.setEditable(True)
        completer = QCompleter(pacientes_lista)
        completer.setCaseSensitivity(False)
        self.cb_paciente.setCompleter(completer)
        self.cb_prod.clear()
        # PRODUCTOS
        self.cb_prod.clear()
        self.cb_prod.addItem("Seleccionar Producto", None)  # <<< AGREGADO
        for prod in s.query(Producto).order_by(Producto.nombre):
            self.cb_prod.addItem(prod.nombre, prod.idproducto)
        # PAQUETES
        self.cb_paquete.clear()
        self.cb_paquete.addItem("Seleccionar Paquete", None)  # <<< AGREGADO
        for pkg in s.query(Paquete).order_by(Paquete.nombre):
            self.cb_paquete.addItem(pkg.nombre, pkg.idpaquete)
        s.close()

    def _cargar_citas(self):
        self.day_view.clear_events()
        self.week_view.clear_events()
        s = SessionLocal()
        citas = s.query(Cita).all()
        for c in citas:
            texto = f"{c.paciente.nombre}\n{c.duracion} min"
            self.day_view.add_eventos_batch(citas)
            self.week_view.add_eventos_batch(citas)
        s.close()
        self.month_view._on_date_changed()

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

        # Diálogo de reagendamiento único
        dlg = ReagendarTurnoDialog(QDateTime(c.fecha_inicio), self)
        if dlg.exec_() == QDialog.Accepted:
            nueva_fecha_hora = dlg.get_datetime()

            c.idpaciente    = self.cb_paciente.currentData()
            c.idprofesional = self.cb_pro.currentData()
            c.idproducto    = self.cb_prod.currentData()
            c.idpaquete     = self.cb_paquete.currentData()
            c.fecha_inicio  = nueva_fecha_hora
            c.duracion      = self.sp_dur.value()
            c.observaciones = self.txt_obs.toPlainText().strip()
            s.commit()
            s.close()
            self.limpiar_formulario()
            self._cargar_citas()
            QMessageBox.information(self, "Ok", "Turno reagendado con éxito.")
        else:
            s.close()

    def eliminar_cita(self):
        if not self.cita_seleccionada:
            QMessageBox.warning(self, "Atención", "Selecciona un turno de la grilla para eliminar.")
            return
        if QMessageBox.question(self, "Confirmar", "¿Eliminar este turno?") != QMessageBox.Yes:
            return
        s = SessionLocal()
        c = s.query(Cita).get(self.cita_seleccionada)
        if c:
            s.delete(c)
            s.commit()
        s.close()
        self.limpiar_formulario()
        self._cargar_citas()
        QMessageBox.information(self, "Ok", "Turno eliminado.")

    def limpiar_formulario(self):
        self.cita_seleccionada = None
        self.cb_paciente.setCurrentIndex(0)
        self.cb_pro.setCurrentIndex(0)
        self.cb_prod.setCurrentIndex(0)
        self.cb_paquete.setCurrentIndex(0)
        self.dt_inicio.setDateTime(QDateTime.currentDateTime())
        self.sp_dur.setValue(30)
        self.txt_obs.clear()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Down):
                self.focusNextChild()
                return True
            if event.key() == Qt.Key_Up:
                self.focusPreviousChild()
                return True
        return super().eventFilter(obj, event)

    def guardar_cita(self):
        if self.cb_paciente.currentData() is None:
            QMessageBox.warning(self, "Error", "Debes seleccionar un paciente.")
            return
        if self.cb_prod.currentData() and self.cb_paquete.currentData():
            QMessageBox.warning(self, "Error", "Elige producto O paquete, no ambos.")
            return
        if not (self.cb_prod.currentData() or self.cb_paquete.currentData()):
            QMessageBox.warning(self, "Error", "Debes elegir producto o paquete.")
            return
        fecha = self.dt_inicio.dateTime().toPyDateTime()
        paciente = self.cb_paciente.currentText()
        if QMessageBox.question(self, "Confirmar", f"¿Desea agendar a {paciente} para {fecha.strftime('%d/%m/%Y %H:%M')}?") != QMessageBox.Yes:
            return
        s = SessionLocal()
        nueva = Cita(
            idpaciente    = self.cb_paciente.currentData(),
            idprofesional = self.cb_pro.currentData(),
            idproducto    = self.cb_prod.currentData(),
            idpaquete     = self.cb_paquete.currentData(),
            fecha_inicio  = fecha,
            duracion      = self.sp_dur.value(),
            observaciones = self.txt_obs.toPlainText().strip()
        )
        s.add(nueva)
        s.commit()
        s.close()
        self.limpiar_formulario()
        self._cargar_citas()
        QMessageBox.information(self, "Ok", "Turno agendado.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = CitaForm(usuario_id=1)
    w.show()
    sys.exit(app.exec_())
