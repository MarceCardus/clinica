from sqlalchemy import (
    Column, Integer, DateTime, Date, Time, Text, String,
    ForeignKey, func, CheckConstraint
)
from sqlalchemy.orm import relationship

from .base        import Base
from .paciente    import Paciente
from .profesional import Profesional
from .producto    import Producto          # legacy
from .item        import Item              # nuevo
from .plan_tipo   import PlanTipo          # nuevo


class Cita(Base):
    __tablename__ = 'cita'

    # EXACTAMENTE UNO: iditem OR idplantipo OR idproducto (histórico)
    __table_args__ = (
        CheckConstraint(
            "((iditem IS NOT NULL)::int + (idplantipo IS NOT NULL)::int + (idproducto IS NOT NULL)::int) = 1",
            name="chk_cita_un_solo_origen"
        ),
    )

    idcita        = Column(Integer, primary_key=True)
    idpaciente    = Column(Integer, ForeignKey('paciente.idpaciente'), nullable=False)
    idprofesional = Column(Integer, ForeignKey('profesional.idprofesional'), nullable=False)

    # Nuevos
    iditem        = Column(Integer, ForeignKey('item.iditem'), nullable=True)
    idplantipo    = Column(Integer, ForeignKey('plan_tipo.idplantipo'), nullable=True)

    # Legacy (se mantiene para datos históricos)
    idproducto    = Column(Integer, ForeignKey('producto.idproducto'), nullable=True)

    fecha_inicio  = Column(DateTime, nullable=False)
    duracion      = Column(Integer, nullable=False)
    estado        = Column(String(20), nullable=False, server_default='Programada')
    observaciones = Column(Text)
    creado_en     = Column(DateTime, nullable=False, server_default=func.now())
    modificado_en = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # --- Relationships útiles (joined para que cargue junto y no haga N+1) ---
    paciente      = relationship(Paciente,   lazy='joined')
    profesional   = relationship(Profesional, lazy='joined')
    item          = relationship(Item,       lazy='joined')
    plan_tipo     = relationship(PlanTipo,   lazy='joined')
    producto      = relationship(Producto,   lazy='joined')   # legacy


class BloqueoHorario(Base):
    __tablename__ = 'bloqueo_horario'

    idbloqueo     = Column(Integer, primary_key=True)
    idprofesional = Column(Integer, ForeignKey('profesional.idprofesional'), nullable=False)
    profesional   = relationship('Profesional')
    fecha         = Column(Date, nullable=False)
    hora_inicio   = Column(Time, nullable=False)
    hora_fin      = Column(Time, nullable=False)
    tipo          = Column(String(50), nullable=False)
    motivo        = Column(Text)
    creado_en     = Column(DateTime, nullable=False, server_default=func.now())
