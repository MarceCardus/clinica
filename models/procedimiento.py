# models/procedimiento.py
from sqlalchemy import Column, Integer, Date, String, ForeignKey
from .base import Base
from sqlalchemy.orm import relationship

class Procedimiento(Base):
    __tablename__ = 'procedimiento'
    id = Column(Integer, primary_key=True, autoincrement=True)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'))
    fecha = Column(Date, nullable=False)
    comentario = Column(String(200))
    paciente = relationship("Paciente", back_populates="procedimientos")