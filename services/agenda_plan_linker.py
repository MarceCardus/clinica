# services/agenda_plan_linker.py
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from models.agenda import Cita
from models.plan_sesiones import PlanSesiones, PlanSesion, PlanEstado, SesionEstado
from models.item import Item

class AgendaPlanLinker:
    """Enlaza Cita <-> PlanSesion y sincroniza fecha/profesional."""

    @staticmethod
    def _resolver_plantipo_id(db: Session, cita: Cita) -> int | None:
        if getattr(cita, "idplantipo", None):
            return cita.idplantipo
        if getattr(cita, "iditem", None):
            it = db.get(Item, cita.iditem)
            return getattr(it, "idplantipo", None)
        return None

    @staticmethod
    def _plan_activo(db: Session, idpaciente: int, idplantipo: int) -> PlanSesiones | None:
        q = (select(PlanSesiones)
             .where(and_(PlanSesiones.idpaciente == idpaciente,
                         PlanSesiones.idplantipo == idplantipo,
                         PlanSesiones.estado == PlanEstado.ACTIVO))
             .order_by(PlanSesiones.idplan.asc()))
        return db.execute(q).scalars().first()

    @staticmethod
    def _proxima_sesion_libre(db: Session, idplan: int) -> PlanSesion | None:
        q = (select(PlanSesion)
             .where(PlanSesion.idplan == idplan)
             .order_by(PlanSesion.nro.asc(), PlanSesion.idsesion.asc()))
        for ps in db.execute(q).scalars():
            if ps.fecha_realizada is None and ps.cita is None:
                return ps
        return None

    # -------- Hooks sobre CITA --------
    @staticmethod
    def on_cita_creada_o_editada(db: Session, cita: Cita):
        """Crear/editar/mover/reasignar: asegurar enlace y sincronizar."""
        if cita.sesion is not None:
            ps = cita.sesion
        else:
            plantipo_id = AgendaPlanLinker._resolver_plantipo_id(db, cita)
            if not plantipo_id:
                return None
            plan = AgendaPlanLinker._plan_activo(db, cita.idpaciente, plantipo_id)
            if not plan:
                return None
            ps = AgendaPlanLinker._proxima_sesion_libre(db, plan.idplan)
            if not ps:
                return None
            cita.idsesion = ps.idsesion  # enlazar 1–1

        ps.fecha_programada = cita.fecha_inicio
        ps.idterapeuta = cita.idprofesional
        db.add(ps); db.add(cita)
        return ps

    @staticmethod
    def on_cita_cancelada_o_eliminada(db: Session, cita: Cita):
        """Liberar sesión si no está COMPLETADA."""
        ps = cita.sesion
        if not ps:
            return
        if ps.estado != SesionEstado.COMPLETADA:
            ps.fecha_programada = None
            ps.idterapeuta = None
        cita.idsesion = None
        db.add(ps); db.add(cita)

    # -------- Hook sobre SESIÓN (opcional) --------
    @staticmethod
    def on_sesion_completada(db: Session, idsesion: int, fecha_realizada):
        ps = db.get(PlanSesion, idsesion)
        if not ps: return
        ps.estado = SesionEstado.COMPLETADA
        ps.fecha_realizada = fecha_realizada
        if ps.cita and ps.cita.estado.lower() == "programada":
            ps.cita.estado = "Realizada"
            db.add(ps.cita)
        db.add(ps)
