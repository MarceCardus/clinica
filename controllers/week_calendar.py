# controllers/week_calendar.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QCalendarWidget, QListWidget, QFrame, QHeaderView
)
from PyQt5.QtCore import Qt, QLocale, QDate, QDateTime, pyqtSignal
from PyQt5.QtGui import QColor
from datetime import date, datetime, timedelta, time
from collections import defaultdict
from utils.db import SessionLocal
from models.agenda import Cita

COLORS = [
    "#66cdaa", "#f8d74e", "#d066d6", "#66b5f0", "#f06666",
    "#042f42", "#FC0AF0", "#fcf9f9", "#09f81d"
]
SPANISH_DAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]

SPANISH_MONTHS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre", "diciembre"
]

SPANISH_DAYS_FULL = [
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"
]

class WeekCalendar(QWidget):
    cita_seleccionada = pyqtSignal(int)

    def __init__(self, profesionales, color_por_profesional, start_date=None, parent=None, form_parent=None):
        super().__init__(parent)
        self.form_parent = form_parent
        self.profesionales = profesionales
        self.color_por_profesional = color_por_profesional
        hoy = date.today()
        self.start_date = start_date or (hoy - timedelta(days=hoy.weekday()))
        self._build_ui()
        self._update_headers()

    def clear_events(self):
        self.table.clearContents()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        nav = QHBoxLayout()
        self.btn_prev = QPushButton("‹ Anterior")
        self.lbl_week = QLabel("", alignment=Qt.AlignCenter)
        self.btn_next = QPushButton("Siguiente ›")
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.lbl_week)
        nav.addWidget(self.btn_next)
        layout.addLayout(nav)

        self.btn_prev.clicked.connect(self.prev_week)
        self.btn_next.clicked.connect(self.next_week)

        cont = QHBoxLayout()
        legend = QFrame()
        lg = QVBoxLayout(legend)
        lg.addWidget(QLabel("Leyenda:", alignment=Qt.AlignLeft))
        for idx, (pid, nombre) in enumerate(self.profesionales):
            sw = QLabel()
            sw.setFixedSize(20, 20)
            color = self.color_por_profesional.get(pid, COLORS[idx % len(COLORS)])
            sw.setStyleSheet(
                f"background:{color}; border:1px solid #666;"
            )
            row = QHBoxLayout()
            row.addWidget(sw)
            row.addWidget(QLabel(nombre))
            lg.addLayout(row)
        cont.addWidget(legend, 0)

        # Horarios por filas, columnas después las generamos
        self.table = QTableWidget()
        self.table.verticalHeader().setDefaultSectionSize(60)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        cont.addWidget(self.table, 1)
        layout.addLayout(cont)
        self.table.cellClicked.connect(self._on_cell_clicked)

        self.horas = list(range(6, 20))

    def prev_week(self):
        self.start_date -= timedelta(weeks=1)
        self._update_headers()
        if self.form_parent:
            self.form_parent._cargar_citas()

    def next_week(self):
        self.start_date += timedelta(weeks=1)
        self._update_headers()
        if self.form_parent:
            self.form_parent._cargar_citas()

    def _update_headers(self):
        fin = self.start_date + timedelta(days=6)
        self.lbl_week.setText(
            f"{self.start_date.strftime('%d %b')} – {fin.strftime('%d %b %Y')}"
        )

        # Se preparan labels de días
        dias = [self.start_date + timedelta(days=i) for i in range(7)]
        labels = [
            f"{SPANISH_DAYS[d.weekday()]} {d.day:02d}/{d.month:02d}"
            for d in dias
        ]
        # La cantidad de columnas será 7 * superposición_max
        # Pero acá solo definimos headers, las columnas se definen al agregar eventos

    def add_eventos_batch(self, citas):
        """
        En vez de add_event por cita, llamá una sola vez por semana, y pasale todas las citas de la semana
        """
        self.clear_events()
        # Mapeo: (dia, hora) => lista de (cita, texto, idprofesional, idcita)
        slots = defaultdict(list)
        for c in citas:
            dia = (c.fecha_inicio.date() - self.start_date).days
            if not (0 <= dia < 7):
                continue
            row = c.fecha_inicio.hour - 6
            slots[(dia, row)].append((c, f"{c.paciente.nombre} {c.paciente.apellido}\n{c.duracion} min", c.idprofesional, c.idcita))

        # Detectar superposición máxima por cada horario
        max_super = 1
        super_por_slot = defaultdict(int)
        for (dia, row), items in slots.items():
            super_por_slot[(dia, row)] = len(items)
            if len(items) > max_super:
                max_super = len(items)

        self.table.setRowCount(len(self.horas))
        self.table.setColumnCount(7 * max_super)

        # Generar headers agrupados
        headers = []
        for dia in range(7):
            for col in range(max_super):
                headers.append(f"{SPANISH_DAYS[(self.start_date + timedelta(days=dia)).weekday()]} { (self.start_date + timedelta(days=dia)).day:02d}/{ (self.start_date + timedelta(days=dia)).month:02d} {col+1 if max_super > 1 else ''}")
        self.table.setHorizontalHeaderLabels(headers)
        for r, h in enumerate(self.horas):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(f"{h}:00"))

        # Cargar las citas en su columna correspondiente
        # Cada slot con superposición reparte las citas en columnas contiguas
        for (dia, row), items in slots.items():
            for idx, (c, texto, idprofesional, idcita) in enumerate(items):
                col = dia * max_super + idx
                color = self.color_por_profesional.get(idprofesional, COLORS[0])
                item = QTableWidgetItem(texto)
                item.setBackground(QColor(color))
                item.setTextAlignment(Qt.AlignCenter)
                item.setData(Qt.UserRole, idcita)
                self.table.setItem(row, col, item)

    def _on_cell_clicked(self, row, col):
        item = self.table.item(row, col)
        # Determinar la fecha/hora correspondiente
        hora = self.horas[row]  # para WeekCalendar
        dia = col // self.max_super if hasattr(self, 'max_super') else col // 1
        base_date = self.start_date + timedelta(days=dia)
        dt = datetime.combine(base_date, datetime.min.time()).replace(hour=hora, minute=0)
        if item:
            cita_id = item.data(Qt.UserRole)
            if cita_id:
                self.form_parent.seleccionar_cita_por_id(cita_id)
            if hasattr(self.form_parent, "dt_inicio"):
                self.form_parent.dt_inicio.setDateTime(QDateTime(dt))
        else:
            # Si está vacía, limpiar formulario y setear horario
            if hasattr(self.form_parent, "limpiar_formulario"):
                self.form_parent.limpiar_formulario()
            if hasattr(self.form_parent, "dt_inicio"):
                self.form_parent.dt_inicio.setDateTime(QDateTime(dt))

class DayCalendar(WeekCalendar):
    cita_seleccionada = pyqtSignal(int)

    def __init__(self, profesionales, color_por_profesional, start_date=None, parent=None, form_parent=None):
        super().__init__(profesionales, color_por_profesional, start_date or date.today(), parent, form_parent=form_parent)

    def _build_ui(self):
        super()._build_ui()
        # Usamos slots de media hora
        self.slots = [f"{h//2:02d}:{(h%2)*30:02d}" for h in range(12, 48)]
        self.table.setRowCount(len(self.slots))
        self.table.clearSpans()
        for r, lbl in enumerate(self.slots):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(lbl))
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    def add_eventos_batch(self, citas):
        """
        Igual que WeekCalendar pero en formato de día
        """
        self.clear_events()
        # slots: fila = slot de media hora (desde 8:00), columna = superposición
        slots = defaultdict(list)
        for c in citas:
            if c.fecha_inicio.date() != self.start_date:
                continue
            slot = (c.fecha_inicio.hour - 6) * 2 + (c.fecha_inicio.minute // 30)
            slots[slot].append((c, f"{c.paciente.nombre} {c.paciente.apellido}\n{c.duracion} min", c.idprofesional, c.idcita))

        max_super = max([len(v) for v in slots.values()] + [1])
        self.table.setRowCount(len(self.slots))
        self.table.setColumnCount(max_super)
        d = self.start_date
        dia = SPANISH_DAYS_FULL[d.weekday()]
        mes = SPANISH_MONTHS[d.month-1]
        texto = f"{dia.capitalize()} {d.day:02d} {mes} {d.year}"
        headers = [f"{texto} {i+1 if max_super>1 else ''}" for i in range(max_super)]
        self.table.setHorizontalHeaderLabels(headers)
        for r, lbl in enumerate(self.slots):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(lbl))

        for slot, items in slots.items():
            for idx, (c, texto, idprofesional, idcita) in enumerate(items):
                color = self.color_por_profesional.get(idprofesional, COLORS[0])
                item = QTableWidgetItem(texto)
                item.setBackground(QColor(color))
                item.setTextAlignment(Qt.AlignCenter)
                item.setData(Qt.UserRole, idcita)
                self.table.setItem(slot, idx, item)

    def _on_cell_clicked(self, row, col):
        # Calcular hora/minuto a partir del slot (cada fila es media hora desde 8:00)
        hora = 6 + (row // 2)
        minuto = 0 if row % 2 == 0 else 30
        base_date = self.start_date
        dt = datetime.combine(base_date, datetime.min.time()).replace(hour=hora, minute=minuto)
        item = self.table.item(row, col)
        if item:
            cita_id = item.data(Qt.UserRole)
            if cita_id:
                self.form_parent.seleccionar_cita_por_id(cita_id)
            # Siempre actualiza la fecha/hora al hacer click (para feedback inmediato)
            if hasattr(self.form_parent, "dt_inicio"):
                self.form_parent.dt_inicio.setDateTime(QDateTime(dt))
        else:
            # Si no hay cita en ese slot, limpiar formulario y setear fecha/hora
            if hasattr(self.form_parent, "limpiar_formulario"):
                self.form_parent.limpiar_formulario()
            if hasattr(self.form_parent, "dt_inicio"):
                self.form_parent.dt_inicio.setDateTime(QDateTime(dt))

    def prev_week(self):
        self.start_date -= timedelta(days=1)
        self._update_headers()
        if self.form_parent:
            self.form_parent._cargar_citas()

    def next_week(self):
        self.start_date += timedelta(days=1)
        self._update_headers()
        if self.form_parent:
            self.form_parent._cargar_citas()

    def _update_headers(self):
        d = self.start_date
        dia = SPANISH_DAYS_FULL[d.weekday()]
        mes = SPANISH_MONTHS[d.month-1]
        texto = f"{dia.capitalize()} {d.day:02d} {mes} {d.year}"
        max_super = self.table.columnCount()
        headers = [f"{texto} {i+1 if max_super>1 else ''}" for i in range(max_super)]
        self.table.setHorizontalHeaderLabels(headers)

class MonthCalendar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.cal = QCalendarWidget()
        self.cal.setLocale(QLocale(QLocale.Spanish, QLocale.Spain))
        self.lst = QListWidget()
        layout.addWidget(self.cal)
        layout.addWidget(self.lst)
        self.cal.selectionChanged.connect(self._on_date_changed)
        self.cal.setSelectedDate(QDate.currentDate())
        self._on_date_changed()

    def _on_date_changed(self):
        qd = self.cal.selectedDate()
        fecha_py = date(qd.year(), qd.month(), qd.day())
        inicio = datetime.combine(fecha_py, time.min)
        fin    = inicio + timedelta(days=1)
        self.lst.clear()
        s = SessionLocal()
        citas = s.query(Cita).filter(
            Cita.fecha_inicio >= inicio,
            Cita.fecha_inicio <  fin
        ).all()
        for c in citas:
            txt = f"{c.fecha_inicio.strftime('%H:%M')} • {c.paciente.nombre} {c.paciente.apellido} ({c.duracion} m)"
            self.lst.addItem(txt)
        s.close()
