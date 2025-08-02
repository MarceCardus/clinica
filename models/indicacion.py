from sqlalchemy import Column, Integer, String, Date, Time, Boolean, ForeignKey, Enum, JSON, Float
from sqlalchemy.orm import relationship
from .base import Base

class Indicacion(Base):
    __tablename__ = "indicacion"
    idindicacion = Column(Integer, primary_key=True, autoincrement=True)
    fecha = Column(Date, nullable=False)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'), nullable=False)
    idprofesional = Column(Integer, ForeignKey('profesional.idprofesional'), nullable=False)
    tipo = Column(Enum('GENERAL', 'MEDICAMENTO', 'CONTROL', name='tipo_indicacion'), nullable=False)
    descripcion = Column(String)  # Para texto libre
    idinsumo = Column(Integer, ForeignKey('insumo.idinsumo'), nullable=True)  # Solo si es medicamento
    dosis = Column(String)       # Ej: "500mg"
    frecuencia_horas = Column(Integer)  # Cada cuántas horas
    duracion_dias = Column(Integer)
    hora_inicio = Column(Time)
    recordatorio_activo = Column(Boolean, default=False)
    idproducto = Column(Integer, ForeignKey('producto.idproducto'), nullable=True) # Si es tratamiento/procedimiento
    esquema_control = Column(JSON)  # Para controles programados (arreglo de días o fechas)
    observaciones = Column(String)

    # Relaciones opcionales
    insumo = relationship('Insumo')
    producto = relationship('Producto')
    paciente = relationship('Paciente')
    profesional = relationship('Profesional')
