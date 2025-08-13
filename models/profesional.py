from sqlalchemy import Column, Integer, String,Boolean
from .base import Base
from sqlalchemy.orm import relationship
class Profesional(Base):
    __tablename__ = 'profesional'

    idprofesional = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(80), nullable=False)
    apellido = Column(String(80), nullable=False)
    documento = Column(String(20))
    matricula = Column(String(30))
    telefono = Column(String(40))
    email = Column(String(80))
    direccion = Column(String(200))
    observaciones = Column(String)
    estado = Column(Boolean, default=True)   # <-- Esto es clave
    indicaciones = relationship('Indicacion', back_populates='profesional')
