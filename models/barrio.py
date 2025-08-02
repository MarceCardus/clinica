from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class Barrio(Base):
    __tablename__ = 'barrio'
    idbarrio = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(80), nullable=False)
    idciudad = Column(Integer, ForeignKey('ciudad.idciudad'))
    ciudad = relationship("Ciudad", back_populates="barrios")
    pacientes = relationship("Paciente", back_populates="barrio")
