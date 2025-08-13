# models/recordatorio_paciente.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class RecordatorioPaciente(Base):
    __tablename__ = 'recordatorio_paciente'

    id = Column(Integer, primary_key=True, autoincrement=True)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'), nullable=False)
    idprocedimiento = Column(Integer, ForeignKey('procedimiento.id'), nullable=True)  # puede ser NULL
    idindicacion = Column(Integer, ForeignKey('indicacion.idindicacion'), nullable=True)  # NUEVO
    fecha_recordatorio = Column(DateTime, nullable=False)  # AHORA DateTime para conservar la hora
    mensaje = Column(String(200))
    estado = Column(String(20), default="pendiente")  # pendiente, enviado, realizado, cancelado
    fecha_envio = Column(DateTime, nullable=True)

    paciente = relationship("Paciente")
    # procedimiento = relationship("Procedimiento")
    # indicacion = relationship("Indicacion")
