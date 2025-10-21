# controllers/planes_paciente.py
from datetime import date, datetime, time, timedelta

from PyQt5.QtCore import Qt, QDate, QDateTime
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QFormLayout, QComboBox, QSpinBox, QDateEdit, QMessageBox
)

from sqlalchemy import select, func, asc, delete, update, and_, or_, text
from models.venta_detalle import VentaDetalle
from models.venta import Venta
from models.plan_sesiones import PlanSesiones, PlanSesion, PlanEstado, SesionEstado
from models.plan_tipo import PlanTipo
from models.item import Item  # compatibilidad
from models.profesional import Profesional
from models.agenda import Cita  # para crear/eliminar turnos
from services.agenda_plan_linker import AgendaPlanLinker
from utils.db import SessionLocal

# Aparato opcional
try:
    from models.aparato import Aparato
except Exception:  # noqa
    Aparato = None


# =========================
# 1) Lista de planes del paciente
# =========================
class PlanesPaciente(QDialog):
    def __init__(self, parent, idpaciente: int, ctx_venta: dict | None = None, session=None):
        super().__init__(parent)
        self.session = session or getattr(parent, "session", None) or SessionLocal()
        self._own_session = (session is None and not hasattr(parent, "session"))
        self.idpaciente = idpaciente
        self.ctx_venta = ctx_venta or {}
        self.setWindowTitle("Planes del Paciente")
        self.resize(820, 420)

        layout = QVBoxLayout(self)

        self.tbl = QTableWidget(0, 9)
        self.tbl.setHorizontalHeaderLabels(
            ["ID", "Tipo", "Total", "Hechas", "Restan", "Estado", "Inicio", "Fin", "Venta"]
        )
        layout.addWidget(self.tbl)

        btns = QHBoxLayout()
        self.btn_nuevo    = QPushButton("Nuevo plan…")
        self.btn_editar   = QPushButton("Editar…")
        self.btn_anular   = QPushButton("Anular plan")
        self.btn_sesiones = QPushButton("Ver sesiones…")
        self.btn_cerrar   = QPushButton("Cerrar")
        for b in (self.btn_nuevo, self.btn_editar, self.btn_anular, self.btn_sesiones):
            btns.addWidget(b)
        btns.addStretch()
        btns.addWidget(self.btn_cerrar)
        layout.addLayout(btns)

        self.btn_nuevo.clicked.connect(self.crear_plan)
        self.btn_editar.clicked.connect(self.editar_plan)
        self.btn_anular.clicked.connect(self.anular_plan)
        self.btn_sesiones.clicked.connect(self.abrir_sesiones_seleccionado)
        self.btn_cerrar.clicked.connect(self.reject)

        self.cargar()

    def editar_plan(self):
        pid = self._idplan_selected()
        if not pid:
            QMessageBox.information(self, "Planes", "Seleccioná un plan.")
            return
        dlg = EditarPlanDialog(self, idplan=pid)
        if dlg.exec_():
            self.cargar()

    def anular_plan(self):
        pid = self._idplan_selected()
        if not pid:
            QMessageBox.information(self, "Planes", "Seleccioná un plan.")
            return

        plan = self.session.get(PlanSesiones, pid)
        if not plan:
            return

        if QMessageBox.question(
            self, "Anular plan",
            "¿Seguro que querés ANULAR este plan?\n"
            "Se eliminarán los turnos pendientes y se marcarán las sesiones no completadas."
        ) != QMessageBox.Yes:
            return

        # 1) Cambiar estado del plan
        plan.estado = PlanEstado.CANCELADO
        plan.fecha_fin = None  # mantenemos nulo (histórico: plan cancelado sin fecha fin)

        # 2) Marcar/limpiar sesiones NO completadas
        sesiones = self.session.execute(
            select(PlanSesion).where(
                PlanSesion.idplan == plan.idplan,
                PlanSesion.estado != SesionEstado.COMPLETADA
            )
        ).scalars().all()

        tiene_cancelada = hasattr(SesionEstado, "CANCELADA") or hasattr(SesionEstado, "ANULADA")
        for s in sesiones:
            # set estado cancelado si existe; si no, limpiar como "no programada"
            if tiene_cancelada:
                try:
                    s.estado = getattr(SesionEstado, "CANCELADA")
                except Exception:
                    s.estado = getattr(SesionEstado, "ANULADA")
            s.fecha_programada = None
            s.idterapeuta = None

        self.session.flush()

        # 3) Eliminar Citas vinculadas a sesiones NO completadas
        #    a) Primero por el linker (si existe relación persistida)
        try:
            # método hipotético: que cancele/desenlace en cascada
            AgendaPlanLinker.on_plan_cancelado(self.session, plan.idplan)
        except Exception:
            #    b) Fallback: borrar por convención de observaciones
            #       Observaciones generadas: "Plan #<id> - Sesión <n>"
            like_pat = f"Plan #{plan.idplan} - Sesión %"
            self.session.query(Cita).filter(
                Cita.idpaciente == plan.idpaciente,
                Cita.observaciones.ilike(like_pat)
            ).delete(synchronize_session=False)

        self.session.commit()
        self.cargar()
        QMessageBox.information(self, "Listo", "Plan anulado. Citas pendientes eliminadas.")

    def cargar(self):
        self.tbl.clearSelection()
        self.tbl.setRowCount(0)

        rows = self.session.execute(
            text("""
                SELECT idplan, plan_tipo, total, hechas, restan, estado, fecha_inicio, fecha_fin, idventa
                FROM vw_planes_por_paciente
                WHERE idplan IN (
                    SELECT idplan FROM plan_sesiones WHERE idpaciente = :pid
                )
                ORDER BY idplan DESC
            """),
            {"pid": self.idpaciente}
        ).all()

        for (idplan, tnom, total, hechas, rest, est, f_ini, f_fin, idventa) in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            data = [
                idplan,
                tnom or "",
                int(total or 0),
                int(hechas or 0),
                int(rest or 0),
                str(getattr(est, "value", est) or ""),
                f_ini.isoformat() if f_ini else "",
                f_fin.isoformat() if f_fin else "",
                idventa or "",
            ]
            for c, val in enumerate(data):
                self.tbl.setItem(r, c, QTableWidgetItem(str(val)))

        self.tbl.resizeColumnsToContents()

    def _idplan_selected(self):
        r = self.tbl.currentRow()
        if r < 0:
            return None
        try:
            return int(self.tbl.item(r, 0).text())
        except Exception:
            return None

    def abrir_sesiones_seleccionado(self):
        pid = self._idplan_selected()
        if not pid:
            QMessageBox.information(self, "Planes", "Seleccioná un plan.")
            return
        dlg = SesionesPlanDialog(self, idplan=pid)
        if dlg.exec_():
            self.cargar()

    def crear_plan(self):
        dlg = CrearPlanDialog(self, idpaciente=self.idpaciente, ctx_venta=self.ctx_venta)
        if dlg.exec_():
            self.cargar()

    def closeEvent(self, e):
        try:
            if self._own_session and self.session:
                self.session.close()
        finally:
            super().closeEvent(e)


# =========================
# 2) Crear plan (con Lipo) + agendado opcional
# =========================
class CrearPlanDialog(QDialog):
    def __init__(self, parent, idpaciente: int, ctx_venta: dict | None = None):
        super().__init__(parent)
        self.session = parent.session
        self.idpaciente = idpaciente
        self.ctx_venta = ctx_venta or {}
        self.setWindowTitle("Nuevo plan del paciente")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Tipos activos con sesiones > 0
        self.cbo_tipo = QComboBox()
        tipos = self.session.execute(
            select(PlanTipo)
            .where(PlanTipo.activo == True, PlanTipo.sesiones_por_defecto > 0)
            .order_by(PlanTipo.nombre)
        ).scalars().all()
        for pt in tipos:
            self.cbo_tipo.addItem(pt.nombre, (pt.idplantipo, int(pt.sesiones_por_defecto or 1)))

        self.sp_total = QSpinBox()
        self.sp_total.setRange(1, 200)

        self.dt_inicio = QDateEdit(QDate.currentDate())
        self.dt_inicio.setCalendarPopup(True)
        self.dt_lipo = QDateEdit(QDate.currentDate().addDays(-1))
        self.dt_lipo.setCalendarPopup(True)

        form.addRow("Tipo de plan:", self.cbo_tipo)
        form.addRow("Total de sesiones:", self.sp_total)
        form.addRow("Fecha inicio:", self.dt_inicio)
        form.addRow("Fecha lipo:", self.dt_lipo)
        layout.addLayout(form)

        hb = QHBoxLayout()
        ok = QPushButton("Crear")
        ca = QPushButton("Cancelar")
        hb.addStretch()
        hb.addWidget(ok)
        hb.addWidget(ca)
        layout.addLayout(hb)
        ca.clicked.connect(self.reject)
        ok.clicked.connect(self.crear)

        # señales: SOLO Lipo → Inicio (cambiar inicio NO toca lipo)
        self.cbo_tipo.currentIndexChanged.connect(self._on_tipo_changed)
        self.dt_lipo.dateChanged.connect(self._on_lipo_changed)

        self._on_tipo_changed()
        self._on_lipo_changed(self.dt_lipo.date())

    def _on_lipo_changed(self, d: QDate):
        # inicio = lipo + 1; si cae domingo, mover a lunes
        inicio = d.addDays(1)
        if inicio.dayOfWeek() == 7:  # domingo
            inicio = inicio.addDays(1)
        self.dt_inicio.blockSignals(True)
        self.dt_inicio.setDate(inicio)
        self.dt_inicio.blockSignals(False)

    def _on_tipo_changed(self):
        data = self.cbo_tipo.currentData()
        if not data:
            return
        _idplantipo, sesiones_def = data
        self.sp_total.setValue(max(1, int(sesiones_def or 1)))

    def crear(self):
        data = self.cbo_tipo.currentData()
        if not data:
            QMessageBox.warning(self, "Tipo de plan", "Seleccioná un tipo de plan.")
            return
        idplantipo, _ = data
        total = int(self.sp_total.value())
        if total <= 0:
            QMessageBox.warning(self, "Sesiones", "El total de sesiones debe ser mayor a 0.")
            return

        fecha_inicio = self.dt_inicio.date().toPyDate()
        fecha_lipo = self.dt_lipo.date().toPyDate()
        idventadet = self.ctx_venta.get("idventadet")
        iditem_proc = self.ctx_venta.get("iditem_procedimiento")

        plan = PlanSesiones(
            idpaciente=self.idpaciente,
            idventadet=idventadet,
            iditem_procedimiento=iditem_proc,
            idplantipo=int(idplantipo),
            total_sesiones=total,
            sesiones_completadas=0,
            estado=PlanEstado.ACTIVO,
            fecha_inicio=fecha_inicio,
            notas=None,
        )
        self.session.add(plan)
        self.session.flush()

        for i in range(1, total + 1):
            self.session.add(PlanSesion(idplan=plan.idplan, nro=i, estado=SesionEstado.PROGRAMADA))

        self.session.commit()

        # =========================
        # Preguntar programación masiva (botones "Sí" / "No")
        # =========================
        msg = QMessageBox(self)
        msg.setWindowTitle("Plan creado")
        msg.setText("Plan creado.\n\n¿Desea programar (agendar) las sesiones ahora?")
        msg.setIcon(QMessageBox.Question)

        btn_si = msg.addButton("Sí", QMessageBox.YesRole)
        btn_no = msg.addButton("No", QMessageBox.NoRole)
        msg.setDefaultButton(btn_no)
        msg.setEscapeButton(btn_no)
        msg.exec_()

        if msg.clickedButton() is btn_si:
            # =========================
            # Diálogo para elegir profesional y horario
            # =========================
            from PyQt5.QtWidgets import QTimeEdit
            dlg = QDialog(self)
            dlg.setWindowTitle("Programar sesiones")
            v = QVBoxLayout(dlg)
            frm = QFormLayout()
            v.addLayout(frm)

            cb_prof = QComboBox()
            pros = self.session.execute(
                select(Profesional)
                .where(Profesional.estado == True)
                .order_by(Profesional.apellido)
            ).scalars().all()
            for p in pros:
                cb_prof.addItem(f"{p.apellido}, {p.nombre}", p.idprofesional)
            frm.addRow("Profesional:", cb_prof)

            te = QTimeEdit()
            te.setDisplayFormat("HH:mm")
            te.setTime(te.time().fromString("09:00", "HH:mm"))
            frm.addRow("Horario L-V:", te)

            hb = QHBoxLayout()
            o = QPushButton("Programar")
            c = QPushButton("Cancelar")
            hb.addStretch()
            hb.addWidget(o)
            hb.addWidget(c)
            v.addLayout(hb)
            c.clicked.connect(dlg.reject)
            o.clicked.connect(dlg.accept)

            if dlg.exec_() == QDialog.Accepted:
                if cb_prof.currentData() is None:
                    QMessageBox.warning(self, "Programar", "Elegí un profesional.")
                else:
                    prof_id = cb_prof.currentData()
                    hora_lv = te.time()
                    hh_lv, mm_lv = hora_lv.hour(), hora_lv.minute()
                    if hh_lv < 7:
                        hh_lv, mm_lv = 7, 0
                    if hh_lv > 19 or (hh_lv == 19 and mm_lv > 0):
                        hh_lv, mm_lv = 19, 0

                    current = fecha_inicio
                    sesiones = self.session.execute(
                        select(PlanSesion)
                        .where(PlanSesion.idplan == plan.idplan)
                        .order_by(PlanSesion.nro)
                    ).scalars().all()

                    for s in sesiones:
                        # Saltar domingos
                        while current.weekday() == 6:
                            current = current + timedelta(days=1)

                        # Sábado 08:00 — L-V hora elegida
                        if current.weekday() == 5:
                            dt_prog = datetime.combine(current, time(8, 0))
                        else:
                            dt_prog = datetime.combine(current, time(hh_lv, mm_lv))

                        # Programar sesión
                        s.fecha_programada = dt_prog
                        s.idterapeuta = prof_id

                        # 🔧 Upsert por idsesion para no violar uq_cita_idsesion
                        existing = self.session.execute(
                            select(Cita).where(Cita.idsesion == s.idsesion)
                        ).scalar_one_or_none()

                        obs_txt = f"Plan #{plan.idplan} - Sesión {s.nro}"

                        if existing:
                            existing.idpaciente    = self.idpaciente
                            existing.idprofesional = prof_id
                            existing.fecha_inicio  = dt_prog
                            existing.duracion      = 30
                            existing.observaciones = obs_txt
                            if hasattr(existing, "idplantipo"):
                                existing.idplantipo = plan.idplantipo
                        else:
                            c = Cita(
                                idpaciente=self.idpaciente,
                                idprofesional=prof_id,
                                fecha_inicio=dt_prog,
                                duracion=30,
                                observaciones=obs_txt
                            )
                            if hasattr(c, "idplantipo"):
                                c.idplantipo = plan.idplantipo
                            # Enlazar DIRECTO con la sesión
                            c.idsesion = s.idsesion
                            self.session.add(c)

                        # siguiente día
                        current = current + timedelta(days=1)

                    self.session.commit()
                    QMessageBox.information(
                        self, "Listo", "Sesiones programadas y turnos creados en la agenda."
                    )

        QMessageBox.information(self, "Plan", f"Plan #{plan.idplan} creado.")
        self.accept()


# =========================
# 3) Sesiones de un plan (detalle)
# =========================
class SesionesPlanDialog(QDialog):
    def __init__(self, parent, idplan: int):
        super().__init__(parent)
        self.session = parent.session
        self.idplan = idplan

        self.setWindowTitle(f"Sesiones del plan #{idplan}")
        self.resize(900, 420)

        layout = QVBoxLayout(self)

        self.tbl = QTableWidget(0, 9)
        self.tbl.setHorizontalHeaderLabels(
            ["N°", "Estado", "Prog.", "Realizada", "Terapeuta", "Masaje", "Aparato", "Notas", "ID"]
        )
        self.tbl.setColumnHidden(8, True)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.setSelectionMode(QTableWidget.SingleSelection)
        self.tbl.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tbl)

        btns = QHBoxLayout()
        self.btn_programar = QPushButton("Programar…")
        self.btn_reprogramar = QPushButton("Reprogramar…")
        self.btn_completar = QPushButton("Marcar completada")
        self.btn_guardar = QPushButton("Guardar cambios")
        self.btn_cerrar = QPushButton("Cerrar")
        btns.addWidget(self.btn_programar)
        btns.addWidget(self.btn_reprogramar)
        btns.addWidget(self.btn_completar)
        btns.addStretch()
        btns.addWidget(self.btn_guardar)
        btns.addWidget(self.btn_cerrar)
        layout.addLayout(btns)

        self.btn_programar.clicked.connect(self.programar)
        self.btn_reprogramar.clicked.connect(self.reprogramar)
        self.btn_completar.clicked.connect(self.toggle_completada)
        self.btn_cerrar.clicked.connect(self.reject)
        self.btn_guardar.clicked.connect(self.guardar)

        self.tbl.currentCellChanged.connect(self._on_row_change)
        self._on_row_change(0, 0, -1, -1)

        self.cargar()

    # --- agregá este método nuevo dentro de la clase SesionesPlanDialog ---
    def reprogramar(self):
        sid = self._selected_idsesion()
        if not sid:
            QMessageBox.information(self, "Sesión", "Seleccioná una sesión.")
            return

        s = self.session.get(PlanSesion, sid)
        plan = self.session.get(PlanSesiones, s.idplan)

        if plan.estado == PlanEstado.CANCELADO:
            QMessageBox.warning(self, "Reprogramar", "No se puede reprogramar: el plan está CANCELADO.")
            return
        if s.estado == SesionEstado.COMPLETADA:
            QMessageBox.warning(self, "Reprogramar", "La sesión ya está COMPLETADA.")
            return

        # --- diálogo de reprogramación ---
        from PyQt5.QtWidgets import QDateTimeEdit, QCheckBox
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Reprogramar sesión {s.nro}")
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        lay.addLayout(form)

        dt = QDateTimeEdit()
        dt.setCalendarPopup(True)
        # fecha/hora sugerida = actual programada o ahora
        if s.fecha_programada:
            dt.setDateTime(QDateTime(s.fecha_programada))
        else:
            dt.setDateTime(QDateTime.currentDateTime())

        cbp = QComboBox()
        pros = [
            (p.idprofesional, f"{p.apellido}, {p.nombre}")
            for p in self.session.execute(
                select(Profesional).where(Profesional.estado == True).order_by(Profesional.apellido)
            ).scalars()
        ]
        for pid, txt in pros:
            cbp.addItem(txt, pid)
        if s.idterapeuta:
            cbp.setCurrentIndex(cbp.findData(s.idterapeuta))

        chk_mantener_prof = QCheckBox("Mantener terapeuta actual")
        chk_mantener_prof.setChecked(True)

        chk_shift = QCheckBox("Desplazar siguientes sesiones (en cadena)")
        chk_shift.setChecked(False)

        form.addRow("Nueva fecha y hora:", dt)
        form.addRow("Terapeuta:", cbp)
        form.addRow("", chk_mantener_prof)
        form.addRow("", chk_shift)

        # botones
        hb = QHBoxLayout()
        ok = QPushButton("Aplicar")
        ca = QPushButton("Cancelar")
        hb.addStretch()
        hb.addWidget(ok)
        hb.addWidget(ca)
        lay.addLayout(hb)
        ca.clicked.connect(dlg.reject)
        ok.clicked.connect(dlg.accept)

        if dlg.exec_() != QDialog.Accepted:
            return

        # Determinar terapeuta a usar
        new_prof = s.idterapeuta if chk_mantener_prof.isChecked() else cbp.currentData()
        if new_prof is None:
            QMessageBox.warning(self, "Reprogramar", "Elegí un terapeuta.")
            return

        # Normalizar nueva fecha/hora (evitar domingo; sábado 08:00, L-V mantiene hora)
        new_dt = dt.dateTime().toPyDateTime()
        # si cae domingo -> mover al lunes a la misma hora (o 08:00 si era sábado-regla)
        if new_dt.weekday() == 6:  # domingo
            new_dt = new_dt + timedelta(days=1)

        def _ajustar_horario(dtime: datetime) -> datetime:
            # sábado a las 08:00; L-V respetar hora; domingo se trata afuera
            if dtime.weekday() == 5:  # sábado
                return datetime.combine(dtime.date(), time(8, 0))
            return dtime

        new_dt = _ajustar_horario(new_dt)

        old_dt = s.fecha_programada or new_dt
        delta = new_dt - old_dt

        # --- actualizar la sesión seleccionada ---
        s.fecha_programada = new_dt
        s.idterapeuta = new_prof

        # Upsert de cita para esta sesión
        existing = self.session.execute(select(Cita).where(Cita.idsesion == s.idsesion)).scalar_one_or_none()
        obs_txt = f"Plan #{plan.idplan} - Sesión {s.nro}"
        if existing:
            existing.idpaciente = plan.idpaciente
            existing.idprofesional = new_prof
            existing.fecha_inicio = new_dt
            existing.duracion = getattr(existing, "duracion", 30) or 30
            existing.observaciones = obs_txt
            if hasattr(existing, "idplantipo"):
                existing.idplantipo = plan.idplantipo
        else:
            c = Cita(
                idpaciente=plan.idpaciente,
                idprofesional=new_prof,
                fecha_inicio=new_dt,
                duracion=30,
                observaciones=obs_txt,
                idsesion=s.idsesion
            )
            if hasattr(c, "idplantipo"):
                c.idplantipo = plan.idplantipo
            self.session.add(c)

        # --- desplazar siguientes en cadena (opcional) ---
        if chk_shift.isChecked() and delta != timedelta(0):
            siguientes = self.session.execute(
                select(PlanSesion)
                .where(
                    PlanSesion.idplan == s.idplan,
                    PlanSesion.nro > s.nro,
                    PlanSesion.estado == SesionEstado.PROGRAMADA
                )
                .order_by(PlanSesion.nro)
            ).scalars().all()

            for sx in siguientes:
                if not sx.fecha_programada:
                    continue
                cand = sx.fecha_programada + delta
                # evitar domingos y ajustar horario de sábado
                if cand.weekday() == 6:
                    cand = cand + timedelta(days=1)
                cand = _ajustar_horario(cand)

                sx.fecha_programada = cand
                # mantener su propio terapeuta si tiene; si no, usar el nuevo_prof
                if not sx.idterapeuta:
                    sx.idterapeuta = new_prof

                ex = self.session.execute(select(Cita).where(Cita.idsesion == sx.idsesion)).scalar_one_or_none()
                obs_txt2 = f"Plan #{plan.idplan} - Sesión {sx.nro}"
                if ex:
                    ex.idpaciente = plan.idpaciente
                    ex.idprofesional = sx.idterapeuta or new_prof
                    ex.fecha_inicio = cand
                    ex.duracion = getattr(ex, "duracion", 30) or 30
                    ex.observaciones = obs_txt2
                    if hasattr(ex, "idplantipo"):
                        ex.idplantipo = plan.idplantipo
                else:
                    c2 = Cita(
                        idpaciente=plan.idpaciente,
                        idprofesional=sx.idterapeuta or new_prof,
                        fecha_inicio=cand,
                        duracion=30,
                        observaciones=obs_txt2,
                        idsesion=sx.idsesion
                    )
                    if hasattr(c2, "idplantipo"):
                        c2.idplantipo = plan.idplantipo
                    self.session.add(c2)

        self.session.commit()
        self.cargar()
        QMessageBox.information(self, "Reprogramar", "Reprogramación aplicada correctamente.")



    def _on_row_change(self, cr, cc, pr, pc):
        try:
            estado = self.tbl.item(cr, 1).text()
        except Exception:
            estado = ""
        if hasattr(self, "btn_completar"):
            self.btn_completar.setText("Deshacer completada" if estado == "COMPLETADA" else "Marcar completada")

    def programar(self):
        sid = self._selected_idsesion()
        if not sid:
            QMessageBox.information(self, "Sesión", "Seleccioná una sesión.")
            return
        s = self.session.get(PlanSesion, sid)

        dlg = QDialog(self)
        dlg.setWindowTitle("Programar sesión")
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        from PyQt5.QtWidgets import QDateTimeEdit
        dt = QDateTimeEdit()
        dt.setCalendarPopup(True)
        dt.setDateTime(QDateTime.currentDateTime())

        cbp = QComboBox()
        pros = [(None, "—")] + [
            (p.idprofesional, f"{p.apellido}, {p.nombre}")
            for p in self.session.execute(
                select(Profesional).where(Profesional.estado == True).order_by(Profesional.apellido)
            ).scalars()
        ]
        for pid, txt in pros:
            cbp.addItem(txt, pid)
        if s.idterapeuta:
            cbp.setCurrentIndex(cbp.findData(s.idterapeuta))

        form.addRow("Fecha y hora:", dt)
        form.addRow("Terapeuta:", cbp)
        lay.addLayout(form)
        hb = QHBoxLayout()
        ok = QPushButton("Guardar")
        ca = QPushButton("Cancelar")
        hb.addStretch()
        hb.addWidget(ok)
        hb.addWidget(ca)
        lay.addLayout(hb)
        ca.clicked.connect(dlg.reject)
        ok.clicked.connect(dlg.accept)

        if dlg.exec_():
            if cbp.currentData() is None:
                QMessageBox.warning(self, "Programar", "Elegí un terapeuta.")
                return
            s.fecha_programada = dt.dateTime().toPyDateTime()
            s.idterapeuta = cbp.currentData()
            self.session.commit()
            self.cargar()

    def toggle_completada(self):
        sid = self._selected_idsesion()
        if not sid:
            QMessageBox.information(self, "Sesión", "Seleccioná una sesión.")
            return
        s = self.session.get(PlanSesion, sid)
        plan = self.session.get(PlanSesiones, s.idplan)

        if plan.estado == PlanEstado.CANCELADO:
            QMessageBox.warning(self, "Sesión", "No se puede completar: el plan está CANCELADO.")
            return

        if s.estado == SesionEstado.COMPLETADA:
            s.estado = SesionEstado.PROGRAMADA
            s.fecha_realizada = None
        else:
            row = self.tbl.currentRow()
            cbp = self.tbl.cellWidget(row, 4)
            if not cbp or cbp.currentData() is None:
                QMessageBox.warning(self, "Sesión", "Elegí un terapeuta antes de completar.")
                if cbp:
                    cbp.setFocus()
                return
            s.idterapeuta = cbp.currentData()
            s.estado = SesionEstado.COMPLETADA
            s.fecha_realizada = datetime.now()

        self.session.flush()

        # Mantener contadores/estado (si usás trigger en DB, esto puede omitirse)
        hechas = self.session.execute(
            select(func.count()).where(
                PlanSesion.idplan == s.idplan,
                PlanSesion.estado == SesionEstado.COMPLETADA
            )
        ).scalar()
        plan.sesiones_completadas = int(hechas or 0)

        if plan.sesiones_completadas >= plan.total_sesiones:
            plan.estado = PlanEstado.FINALIZADO
            plan.fecha_fin = date.today()
        else:
            if plan.estado == PlanEstado.FINALIZADO:
                plan.estado = PlanEstado.ACTIVO
                plan.fecha_fin = None

        self.session.commit()
        self.cargar()

    def cargar(self):
        self.tbl.setRowCount(0)

        rows = self.session.execute(
            text("""
                SELECT
                    s.idsesion, s.nro, s.estado, s.fecha_programada, s.fecha_realizada,
                    s.idterapeuta, s.hizo_masaje, s.idaparato, s.notas
                FROM plan_sesion s
                WHERE s.idplan = :pid
                ORDER BY s.nro
            """),
            {"pid": self.idplan}
        ).all()

        pros = [(None, "—")] + [
            (p.idprofesional, f"{p.apellido}, {p.nombre}")
            for p in self.session.execute(
                select(Profesional).where(Profesional.estado == True).order_by(Profesional.apellido)
            ).scalars()
        ]

        aparatos = [(None, "—")]
        if Aparato is not None:
            aparatos += [
                (a.idaparato, a.nombre)
                for a in self.session.execute(select(Aparato).order_by(Aparato.nombre)).scalars()
            ]

        for (idsesion, nro, estado, fprog, freal, idter, hizo_masaje, idap, notas) in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(str(nro)))
            self.tbl.setItem(r, 1, QTableWidgetItem(str(getattr(estado, "value", estado) or "")))
            self.tbl.setItem(r, 2, QTableWidgetItem(fprog.strftime("%Y-%m-%d %H:%M") if fprog else ""))
            self.tbl.setItem(r, 3, QTableWidgetItem(freal.strftime("%Y-%m-%d %H:%M") if freal else ""))

            # Terapeuta
            cbp = QComboBox()
            for pid, txt in pros:
                cbp.addItem(txt, pid)
            if idter:
                cbp.setCurrentIndex(cbp.findData(idter))
            self.tbl.setCellWidget(r, 4, cbp)

            # Masaje
            cmbM = QComboBox()
            cmbM.addItems(["No", "Sí"])
            cmbM.setCurrentIndex(1 if hizo_masaje else 0)
            self.tbl.setCellWidget(r, 5, cmbM)

            # Aparato
            cba = QComboBox()
            for aid, txt in aparatos:
                cba.addItem(txt, aid)
            if idap:
                cba.setCurrentIndex(cba.findData(idap))
            self.tbl.setCellWidget(r, 6, cba)

            self.tbl.setItem(r, 7, QTableWidgetItem(notas or ""))
            self.tbl.setItem(r, 8, QTableWidgetItem(str(idsesion)))

        self.tbl.resizeColumnsToContents()

    def _selected_idsesion(self):
        r = self.tbl.currentRow()
        if r < 0:
            return None
        try:
            return int(self.tbl.item(r, 8).text())
        except Exception:
            return None

    def guardar(self):
        # guarda terapeuta, masaje, aparato y notas
        n = self.tbl.rowCount()
        for r in range(n):
            try:
                sid = int(self.tbl.item(r, 8).text())
            except Exception:
                continue

            s = self.session.get(PlanSesion, sid)

            cbp = self.tbl.cellWidget(r, 4)
            s.idterapeuta = cbp.currentData() if cbp else None

            cmbM = self.tbl.cellWidget(r, 5)
            s.hizo_masaje = True if (cmbM and cmbM.currentIndex() == 1) else False

            cba = self.tbl.cellWidget(r, 6)
            s.idaparato = cba.currentData() if cba else None

            s.notas = (self.tbl.item(r, 7).text() if self.tbl.item(r, 7) else None)

        self.session.commit()
        QMessageBox.information(self, "Sesiones", "Cambios guardados.")
        self.accept()


class EditarPlanDialog(QDialog):
    def __init__(self, parent, idplan: int):
        super().__init__(parent)
        self.session = parent.session
        self.plan = self.session.get(PlanSesiones, idplan)
        self.setWindowTitle(f"Editar plan #{idplan}")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.sp_total = QSpinBox()
        self.sp_total.setRange(1, 200)
        self.sp_total.setValue(self.plan.total_sesiones or 1)

        self.dt_inicio = QDateEdit()
        self.dt_inicio.setCalendarPopup(True)
        d = self.plan.fecha_inicio
        self.dt_inicio.setDate(QDate(d.year, d.month, d.day) if d else QDate.currentDate())

        self.cbo_estado = QComboBox()
        self.cbo_estado.addItems([e.value for e in PlanEstado])
        if self.plan.estado:
            self.cbo_estado.setCurrentIndex(self.cbo_estado.findText(self.plan.estado.value))

        form.addRow("Total de sesiones:", self.sp_total)
        form.addRow("Fecha inicio:", self.dt_inicio)
        form.addRow("Estado:", self.cbo_estado)
        layout.addLayout(form)

        hb = QHBoxLayout()
        ok = QPushButton("Guardar")
        ca = QPushButton("Cancelar")
        hb.addStretch()
        hb.addWidget(ok)
        hb.addWidget(ca)
        layout.addLayout(hb)
        ca.clicked.connect(self.reject)
        ok.clicked.connect(self._guardar)

        def _guardar(self):
            try:
                nuevo_total = int(self.sp_total.value())
                hechas = int(self.plan.sesiones_completadas or 0)
                if nuevo_total < hechas:
                    QMessageBox.warning(
                        self, "Total de sesiones",
                        f"No se puede fijar el total ({nuevo_total}) por debajo de las completadas ({hechas})."
                    )
                    return

                # 1) Sincronizar sesiones (agregar/borrar)
                actual = self.session.execute(
                    select(func.count()).where(PlanSesion.idplan == self.plan.idplan)
                ).scalar() or 0

                if nuevo_total > actual:
                    for nro in range(actual + 1, nuevo_total + 1):
                        self.session.add(PlanSesion(idplan=self.plan.idplan, nro=nro, estado=SesionEstado.PROGRAMADA))
                elif nuevo_total < actual:
                    sobrantes = self.session.execute(
                        select(PlanSesion)
                        .where(PlanSesion.idplan == self.plan.idplan, PlanSesion.nro > nuevo_total)
                        .order_by(asc(PlanSesion.nro))
                    ).scalars().all()
                    if any(s.estado != SesionEstado.PROGRAMADA for s in sobrantes):
                        QMessageBox.warning(
                            self, "Total de sesiones",
                            "No se puede reducir: las sesiones que sobran no están PROGRAMADA."
                        )
                        return
                    self.session.execute(
                        delete(PlanSesion).where(PlanSesion.idplan == self.plan.idplan, PlanSesion.nro > nuevo_total)
                    )

                self.plan.total_sesiones = nuevo_total
                self.plan.fecha_inicio = self.dt_inicio.date().toPyDate()

                # 2) Estado/fecha_fin en base a totales ya sincronizados
                est_txt = self.cbo_estado.currentText()
                for e in PlanEstado:
                    if e.value == est_txt:
                        self.plan.estado = e
                        break

                if self.plan.estado == PlanEstado.FINALIZADO:
                    if (self.plan.sesiones_completadas or 0) >= (self.plan.total_sesiones or 0):
                        if not self.plan.fecha_fin:
                            self.plan.fecha_fin = date.today()
                    else:
                        self.plan.estado = PlanEstado.ACTIVO
                        self.plan.fecha_fin = None
                elif self.plan.estado == PlanEstado.CANCELADO:
                    self.plan.fecha_fin = None

                self.session.commit()
                self.accept()
            except Exception as e:
                self.session.rollback()
                QMessageBox.critical(self, "Editar plan", f"Ocurrió un error al guardar:\n{e}")
