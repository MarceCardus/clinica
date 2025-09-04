from sqlalchemy import Column, Integer, String, Date, Time, Boolean, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from .base import Base

class Indicacion(Base):
    __tablename__ = "indicacion"

    idindicacion = Column(Integer, primary_key=True, autoincrement=True)
    fecha = Column(Date, nullable=False)

    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'), nullable=False)
    idprofesional = Column(Integer, ForeignKey('profesional.idprofesional'), nullable=False)

    tipo = Column(Enum('GENERAL', 'MEDICAMENTO', 'CONTROL', name='tipo_indicacion'), nullable=False)
    descripcion = Column(String)

    # MEDICAMENTO -> SOLO ITEM
    iditem = Column(Integer, ForeignKey('item.iditem'), nullable=True)
    dosis = Column(String)
    frecuencia_horas = Column(Integer)
    duracion_dias = Column(Integer)
    hora_inicio = Column(Time)
    recordatorio_activo = Column(Boolean, default=False)

    # CONTROL (opcional)
    esquema_control = Column(JSON)

    observaciones = Column(String)

    # 🔹 NUEVO: FK opcional al procedimiento
    idprocedimiento = Column(
        Integer,
        ForeignKey('procedimiento.id', ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relaciones
    paciente = relationship('Paciente', back_populates='indicaciones')
    profesional = relationship('Profesional', back_populates='indicaciones')
    item = relationship('Item')

    # 🔹 NUEVO: relación inversa
    procedimiento = relationship(
        'Procedimiento',
        back_populates='indicaciones',
        foreign_keys=[idprocedimiento],
    )
