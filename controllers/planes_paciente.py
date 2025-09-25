# controllers/planes_paciente.py
from datetime import date, datetime

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QFormLayout, QComboBox, QSpinBox, QDateEdit, QMessageBox
)

from sqlalchemy import select, func

from models.plan_sesiones import PlanSesiones, PlanSesion, PlanEstado, SesionEstado
from models.plan_tipo import PlanTipo
from models.item import Item  # (queda por compatibilidad; ya no se usa en "Nuevo plan…")
from models.profesional import Profesional

# Aparato es opcional: si no existe el modelo, lo ignoramos silenciosamente
try:
    from models.aparato import Aparato
except Exception:  # noqa
    Aparato = None


# =========================
# 1) Lista de planes del paciente
# =========================
class PlanesPaciente(QDialog):
    def __init__(self, parent, idpaciente: int, ctx_venta: dict | None = None):
        super().__init__(parent)
        self.session = parent.session   # usamos la misma sesión del formulario de ventas
        self.idpaciente = idpaciente
        self.ctx_venta = ctx_venta or {}   # <-- guardar contexto
        self.setWindowTitle("Planes del Paciente")
        self.resize(820, 420)

        layout = QVBoxLayout(self)

        self.tbl = QTableWidget(0, 8)
        self.tbl.setHorizontalHeaderLabels(
            ["ID", "Tipo", "Total", "Hechas", "Restan", "Estado", "Inicio", "Fin"]
        )
        layout.addWidget(self.tbl)

        btns = QHBoxLayout()
        self.btn_nuevo = QPushButton("Nuevo plan…")
        self.btn_sesiones = QPushButton("Ver sesiones…")
        self.btn_cerrar = QPushButton("Cerrar")
        btns.addWidget(self.btn_nuevo)
        btns.addWidget(self.btn_sesiones)
        btns.addStretch()
        btns.addWidget(self.btn_cerrar)
        layout.addLayout(btns)

        self.btn_cerrar.clicked.connect(self.reject)
        self.btn_nuevo.clicked.connect(self.crear_plan)
        self.btn_sesiones.clicked.connect(self.abrir_sesiones_seleccionado)
        self.tbl.doubleClicked.connect(self.abrir_sesiones_seleccionado)

        self.cargar()
    

    def cargar(self):
        self.tbl.setRowCount(0)
        rows = self.session.execute(
            select(
                PlanSesiones.idplan,
                PlanTipo.nombre,
                PlanSesiones.total_sesiones,
                PlanSesiones.sesiones_completadas,
                PlanSesiones.estado,
                PlanSesiones.fecha_inicio,
                PlanSesiones.fecha_fin,
            )
            .join(PlanTipo, PlanTipo.idplantipo == PlanSesiones.idplantipo)
            .where(PlanSesiones.idpaciente == self.idpaciente)
            .order_by(PlanSesiones.idplan.desc())
        ).all()

        for (idplan, tnom, total, hechas, est, f_ini, f_fin) in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            rest = (total or 0) - (hechas or 0)
            data = [
                idplan,
                tnom or "",
                total or 0,
                hechas or 0,
                max(0, rest),
                getattr(est, "value", est) if est else "",
                f_ini.isoformat() if f_ini else "",
                f_fin.isoformat() if f_fin else "",
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

# =========================
# 2) Crear plan manualmente (con Fecha Lipo)
# =========================
class CrearPlanDialog(QDialog):
    def __init__(self, parent, idpaciente: int, ctx_venta: dict | None = None):
        super().__init__(parent)
        self.session = parent.session
        self.idpaciente = idpaciente
        self.ctx_venta = ctx_venta or {}   # <-- guardar contexto
        self.setWindowTitle("Nuevo plan del paciente")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # --- Tipo de plan: solo activos con sesiones_por_defecto > 0 ---
        self.cbo_tipo = QComboBox()
        tipos = self.session.execute(
            select(PlanTipo)
            .where(PlanTipo.activo == True, PlanTipo.sesiones_por_defecto > 0)
            .order_by(PlanTipo.nombre)
        ).scalars().all()
        for pt in tipos:
            # guardo también sesiones_por_defecto en los datos
            self.cbo_tipo.addItem(pt.nombre, (pt.idplantipo, int(pt.sesiones_por_defecto or 1)))

        # --- Total de sesiones (se carga desde el tipo y se puede editar) ---
        self.sp_total = QSpinBox()
        self.sp_total.setMinimum(1)
        self.sp_total.setMaximum(200)

        # --- Fechas: inicio + lipo (ligadas por reglas) ---
        self.dt_inicio = QDateEdit(QDate.currentDate())
        self.dt_inicio.setCalendarPopup(True)

        self.dt_lipo = QDateEdit(QDate.currentDate().addDays(-1))
        self.dt_lipo.setCalendarPopup(True)

        form.addRow("Tipo de plan:", self.cbo_tipo)
        form.addRow("Total de sesiones:", self.sp_total)
        form.addRow("Fecha inicio:", self.dt_inicio)
        form.addRow("Fecha lipo:", self.dt_lipo)
        layout.addLayout(form)

        btns = QHBoxLayout()
        ok = QPushButton("Crear")
        cancelar = QPushButton("Cancelar")
        btns.addStretch()
        btns.addWidget(ok)
        btns.addWidget(cancelar)
        layout.addLayout(btns)

        cancelar.clicked.connect(self.reject)
        ok.clicked.connect(self.crear)

        # señales para sincronizar
        self.cbo_tipo.currentIndexChanged.connect(self._on_tipo_changed)
        self.dt_lipo.dateChanged.connect(self._on_lipo_changed)
        self.dt_inicio.dateChanged.connect(self._on_inicio_changed)

        # estado inicial
        self._on_tipo_changed()
        self._on_lipo_changed(self.dt_lipo.date())

    # ---------- reglas de fechas ----------
    def _on_lipo_changed(self, d: QDate):
        # inicio = lipo + 1; si cae domingo, mover a lunes
        inicio = d.addDays(1)
        if inicio.dayOfWeek() == 7:  # 7 = domingo
            inicio = inicio.addDays(1)
        self.dt_inicio.blockSignals(True)
        self.dt_inicio.setDate(inicio)
        self.dt_inicio.blockSignals(False)

    def _on_inicio_changed(self, d: QDate):
        # lipo = inicio - 1; si da domingo, mover a sábado
        lipo = d.addDays(-1)
        if lipo.dayOfWeek() == 7:  # domingo
            lipo = lipo.addDays(-1)
        self.dt_lipo.blockSignals(True)
        self.dt_lipo.setDate(lipo)
        self.dt_lipo.blockSignals(False)

    def _on_tipo_changed(self):
        data = self.cbo_tipo.currentData()
        if not data:
            return
        _idplantipo, sesiones_def = data
        self.sp_total.setValue(max(1, int(sesiones_def or 1)))

    # ---------- persistencia ----------
    def crear(self):
        data = self.cbo_tipo.currentData()
        if not data:
            QMessageBox.warning(self, "Tipo de plan", "Seleccioná un tipo de plan.")
            return
        idplantipo, _sesdef = data
        total = int(self.sp_total.value())
        if total <= 0:
            QMessageBox.warning(self, "Sesiones", "El total de sesiones debe ser mayor a 0.")
            return

        fecha_inicio = self.dt_inicio.date().toPyDate()
        fecha_lipo = self.dt_lipo.date().toPyDate()
        idventadet = self.ctx_venta.get("idventadet")
        iditem_proc = self.ctx_venta.get("iditem_procedimiento")
        # Crear plan (sin item_procedimiento, como pediste)
        plan = PlanSesiones(
            idpaciente=self.idpaciente,
            idventadet=idventadet,                   # <-- AHORA se guarda
            iditem_procedimiento=iditem_proc,        # <-- AHORA se guarda
            idplantipo=int(idplantipo),
            total_sesiones=total,
            sesiones_completadas=0,
            estado=PlanEstado.ACTIVO,
            fecha_inicio=fecha_inicio,
            notas=None,
        )
        self.session.add(plan)
        self.session.flush()
        

        # Crear sesiones programadas (sin fecha por ahora)
        for i in range(1, total + 1):
            self.session.add(
                PlanSesion(idplan=plan.idplan, nro=i, estado=SesionEstado.PROGRAMADA)
            )

        # --- Hook: generar turno de Lipo en agenda (lo conectamos cuando me pases el controlador)
        # try:
        #     from controllers.agenda_controller import crear_turno_lipo
        #     crear_turno_lipo(
        #         self.session,
        #         paciente_id=self.idpaciente,
        #         fecha=fecha_lipo,
        #         plan_id=plan.idplan
        #     )
        # except Exception:
        #     pass

        self.session.commit()
        QMessageBox.information(self, "Plan", f"Plan {plan.idplan} creado.")
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
        self.tbl.setColumnHidden(8, True)  # ids
        layout.addWidget(self.tbl)

        btns = QHBoxLayout()
        self.btn_programar = QPushButton("Programar…")
        self.btn_completar = QPushButton("Marcar completada")
        self.btn_guardar = QPushButton("Guardar cambios")
        self.btn_cerrar = QPushButton("Cerrar")
        btns.addWidget(self.btn_programar)
        btns.addWidget(self.btn_completar)
        btns.addStretch()
        btns.addWidget(self.btn_guardar)
        btns.addWidget(self.btn_cerrar)
        layout.addLayout(btns)

        self.btn_cerrar.clicked.connect(self.reject)
        self.btn_guardar.clicked.connect(self.guardar)
        self.btn_completar.clicked.connect(self.marcar_completada)

        self.cargar()

    def cargar(self):
        self.tbl.setRowCount(0)

        sesiones = self.session.execute(
            select(PlanSesion).where(PlanSesion.idplan == self.idplan).order_by(PlanSesion.nro)
        ).scalars().all()

        # Terapeutas
        pros = [(None, "—")] + [
            (p.idprofesional, f"{p.apellido}, {p.nombre}")
            for p in self.session.execute(select(Profesional).order_by(Profesional.apellido)).scalars()
        ]

        # Aparatos
        aparatos = [(None, "—")]
        if Aparato is not None:
            aparatos += [
                (a.idaparato, a.nombre)
                for a in self.session.execute(select(Aparato).order_by(Aparato.nombre)).scalars()
            ]

        for s in sesiones:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(str(s.nro)))
            self.tbl.setItem(r, 1, QTableWidgetItem(getattr(s.estado, "value", s.estado)))
            self.tbl.setItem(r, 2, QTableWidgetItem(s.fecha_programada.isoformat() if s.fecha_programada else ""))
            self.tbl.setItem(
                r, 3,
                QTableWidgetItem(s.fecha_realizada.strftime("%Y-%m-%d %H:%M") if s.fecha_realizada else "")
            )

            # Terapeuta
            cbp = QComboBox()
            for pid, txt in pros:
                cbp.addItem(txt, pid)
            if s.idterapeuta:
                cbp.setCurrentIndex(cbp.findData(s.idterapeuta))
            self.tbl.setCellWidget(r, 4, cbp)

            # Masaje (Sí/No)
            cmbM = QComboBox()
            cmbM.addItems(["No", "Sí"])
            cmbM.setCurrentIndex(1 if s.hizo_masaje else 0)
            self.tbl.setCellWidget(r, 5, cmbM)

            # Aparato
            cba = QComboBox()
            for aid, txt in aparatos:
                cba.addItem(txt, aid)
            if getattr(s, "idaparato", None):
                cba.setCurrentIndex(cba.findData(s.idaparato))
            self.tbl.setCellWidget(r, 6, cba)

            # Notas
            self.tbl.setItem(r, 7, QTableWidgetItem(s.notas or ""))

            # ID oculto
            self.tbl.setItem(r, 8, QTableWidgetItem(str(s.idsesion)))

        self.tbl.resizeColumnsToContents()

    def _selected_idsesion(self):
        r = self.tbl.currentRow()
        if r < 0:
            return None
        try:
            return int(self.tbl.item(r, 8).text())
        except Exception:
            return None

    def marcar_completada(self):
        sid = self._selected_idsesion()
        if not sid:
            QMessageBox.information(self, "Sesión", "Seleccioná una sesión.")
            return

        s = self.session.get(PlanSesion, sid)
        s.estado = SesionEstado.COMPLETADA
        s.fecha_realizada = datetime.now()
        self.session.flush()

        # Actualizar contadores del plan
        plan = self.session.get(PlanSesiones, s.idplan)
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

        self.session.commit()
        self.cargar()

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
