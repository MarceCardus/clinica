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
    idinsumo = Column(Integer, ForeignKey('insumo.idinsumo'), nullable=True)
    dosis = Column(String)
    frecuencia_horas = Column(Integer)
    duracion_dias = Column(Integer)
    hora_inicio = Column(Time)
    recordatorio_activo = Column(Boolean, default=False)
    idproducto = Column(Integer, ForeignKey('producto.idproducto'), nullable=True)
    esquema_control = Column(JSON)
    observaciones = Column(String)

    # Relaciones con inversas
    paciente = relationship('Paciente', back_populates='indicaciones')
    profesional = relationship('Profesional', back_populates='indicaciones')
    insumo = relationship('Insumo', back_populates='indicaciones')
    producto = relationship('Producto', back_populates='indicaciones')
