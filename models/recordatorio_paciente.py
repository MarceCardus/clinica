# models/recordatorio_paciente.py
from sqlalchemy import Column, Integer, String, Date, ForeignKey,DateTime
from sqlalchemy.orm import relationship
from .base import Base


class RecordatorioPaciente(Base):
    __tablename__ = 'recordatorio_paciente'
    id = Column(Integer, primary_key=True)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'))
    idprocedimiento = Column(Integer, ForeignKey('procedimiento.id'))  # o el modelo que uses
    fecha_recordatorio = Column(Date)
    mensaje = Column(String(160))
    estado = Column(String(20), default="pendiente")  # pendiente, enviado, realizado, cancelado
    fecha_envio = Column(DateTime, nullable=True)

    paciente = relationship("Paciente")
    # procedimiento = relationship("Procedimiento")  # si lo necesitás
