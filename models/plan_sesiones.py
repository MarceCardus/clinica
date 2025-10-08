# models/plan_sesiones.py
from enum import Enum as PyEnum
from datetime import date, datetime
from sqlalchemy import (
    Column, Integer, SmallInteger, Text, Date, DateTime, Boolean, Enum,
    ForeignKey, String, Numeric, func
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from utils.db import Base  # ajustá si tu Base está en otro módulo

# =========================
# Enums (mapeo a tipos existentes en PostgreSQL)
# =========================
class SesionEstado(PyEnum):
    PROGRAMADA = "PROGRAMADA"
    COMPLETADA = "COMPLETADA"
    AUSENTE = "AUSENTE"
    CANCELADA = "CANCELADA"
    REPROGRAMADA = "REPROGRAMADA"

class PlanEstado(PyEnum):
    ACTIVO = "ACTIVO"
    PAUSADO = "PAUSADO"
    CANCELADO = "CANCELADO"
    FINALIZADO = "FINALIZADO"

# =========================
# Plan del Paciente
# =========================
class PlanSesiones(Base):
    __tablename__ = "plan_sesiones"

    idplan = Column(Integer, primary_key=True, autoincrement=True)
    idpaciente = Column(Integer, ForeignKey("paciente.idpaciente"), nullable=False)

    # IMPORTANTE: fk a venta_detalle.idventadet (no idventadetalle)
    idventadet = Column(Integer, ForeignKey("venta_detalle.idventadet"))

    # Item vendido (procedimiento que origina el plan)
    iditem_procedimiento = Column(Integer, ForeignKey("item.iditem"), nullable=True)

    idplantipo = Column(Integer, ForeignKey("plan_tipo.idplantipo"), nullable=False)
    total_sesiones = Column(Integer, nullable=False)
    sesiones_completadas = Column(Integer, nullable=False, default=0)
    estado = Column(Enum(PlanEstado, name="plan_estado"), nullable=False, default=PlanEstado.ACTIVO)
    fecha_inicio = Column(Date, nullable=False, server_default=func.current_date())
    fecha_fin = Column(Date)
    notas = Column(Text)

    creado_en = Column(DateTime, nullable=False, server_default=func.now())
    creado_por = Column(Integer)
    actualizado_en = Column(DateTime)
    actualizado_por = Column(Integer)

    # Relaciones (ajustá si querés back_populates desde otras clases)
    sesiones = relationship("PlanSesion", back_populates="plan", cascade="all, delete-orphan")
    plantipo = relationship("PlanTipo")

    def __repr__(self):
        return f"<PlanSesiones id={self.idplan} paciente={self.idpaciente} total={self.total_sesiones}>"

# =========================
# Sesión individual
# =========================
class PlanSesion(Base):
    __tablename__ = "plan_sesion"

    idsesion = Column(Integer, primary_key=True, autoincrement=True)
    idplan = Column(Integer, ForeignKey("plan_sesiones.idplan", ondelete="CASCADE"), nullable=False)
    nro = Column(SmallInteger, nullable=False)
    estado = Column(Enum(SesionEstado, name="sesion_estado"), nullable=False, default=SesionEstado.PROGRAMADA)

    # ✅ Recomendado: TIMESTAMP para guardar exactamente fecha+hora de la cita
    # (si aún es Date en tu DB, ver migración más abajo)
    fecha_programada = Column(DateTime)     # <— cambiar a DateTime
    fecha_realizada  = Column(DateTime)
    idterapeuta      = Column(Integer, ForeignKey("profesional.idprofesional"))

    hizo_masaje = Column(Boolean, nullable=False, default=False)
    idaparato   = Column(Integer, ForeignKey("aparato.idaparato", ondelete="SET NULL"))
    parametros  = Column(JSONB, nullable=False, default=dict)
    notas       = Column(Text)

    creado_en       = Column(DateTime, nullable=False, server_default=func.now())
    creado_por      = Column(Integer)
    actualizado_en  = Column(DateTime)
    actualizado_por = Column(Integer)

    plan  = relationship("PlanSesiones", back_populates="sesiones")

    # 🔗 inversa a Cita (la FK vive en Cita.idsesion)
    cita  = relationship("Cita", back_populates="sesion", uselist=False)

    def __repr__(self):
        return f"<PlanSesion id={self.idsesion} plan={self.idplan} nro={self.nro} estado={self.estado.value}>"

# =========================
# (Opcional) Consumos por sesión
# =========================
class PlanSesionConsumo(Base):
    __tablename__ = "plan_sesion_consumo"

    idconsumo = Column(Integer, primary_key=True, autoincrement=True)
    idsesion = Column(Integer, ForeignKey("plan_sesion.idsesion", ondelete="CASCADE"), nullable=False)
    iditem = Column(Integer, ForeignKey("item.iditem"), nullable=False)
    cantidad = Column(Numeric(12, 3), nullable=False)
    notas = Column(Text)

    creado_en = Column(DateTime, nullable=False, server_default=func.now())
    creado_por = Column(Integer)

    # relationships opcionales:
    # sesion = relationship("PlanSesion")
    # item = relationship("Item")

    def __repr__(self):
        return f"<PlanSesionConsumo id={self.idconsumo} sesion={self.idsesion} item={self.iditem} cant={self.cantidad}>"
