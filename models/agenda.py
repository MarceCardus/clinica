from sqlalchemy import (
    Column, Date, Integer, DateTime, Text, String,
    ForeignKey, Time, func, CheckConstraint
)
from sqlalchemy.orm import relationship

# Importa el mismo Base que usa Paciente, etc.
from .base import Base

# Importa tus otros modelos con ruta relativa
from .paciente    import Paciente
from .profesional import Profesional
from .producto    import Producto
from .paquete     import Paquete

class Cita(Base):
    __tablename__ = 'cita'
    __table_args__ = (
        CheckConstraint(
            "(idproducto IS NOT NULL AND idpaquete IS NULL) "
            "OR (idproducto IS NULL AND idpaquete IS NOT NULL)",
            name="chk_producto_paquete"
        ),
    )

    idcita        = Column(Integer, primary_key=True)
    idpaciente    = Column(Integer, ForeignKey('paciente.idpaciente'), nullable=False)
    paciente      = relationship(Paciente, lazy='joined')
    idprofesional = Column(Integer, ForeignKey('profesional.idprofesional'), nullable=False)
    profesional   = relationship(Profesional, lazy='joined')   # ← Y aquí

    idproducto    = Column(Integer, ForeignKey('producto.idproducto'), nullable=True)
    producto      = relationship(Producto, lazy='joined')      # ← …
    idpaquete     = Column(Integer, ForeignKey('paquete.idpaquete'), nullable=True)
    paquete       = relationship(Paquete, lazy='joined')

    fecha_inicio  = Column(DateTime, nullable=False)
    duracion      = Column(Integer, nullable=False)
    estado        = Column(String(20), nullable=False, server_default='Programada')
    observaciones = Column(Text)
    creado_en     = Column(DateTime, nullable=False, server_default=func.now())
    modificado_en = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )


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
