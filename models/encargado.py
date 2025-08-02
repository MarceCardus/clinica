from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from .base import Base

class Encargado(Base):
    __tablename__ = 'encargado'

    idencargado = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(120), nullable=False)
    ci = Column(String(20))
    edad = Column(String(10))
    ocupacion = Column(String(80))
    telefono = Column(String(40))
    observaciones = Column(Text)
    pacientes = relationship("PacienteEncargado", back_populates="encargado")
