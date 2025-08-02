from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class Ciudad(Base):
    __tablename__ = 'ciudad'
    idciudad = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(80), nullable=False)
    iddepartamento = Column(Integer, ForeignKey('departamento.iddepartamento'))
    departamento = relationship("Departamento", back_populates="ciudades")
    barrios = relationship("Barrio", back_populates="ciudad")