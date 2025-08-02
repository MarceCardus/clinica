from sqlalchemy import Column, Integer, ForeignKey
from .base import Base

class ProfesionalEspecialidad(Base):
    __tablename__ = 'profesional_especialidad'
    idprofesional = Column(Integer, ForeignKey('profesional.idprofesional'), primary_key=True)
    idespecialidad = Column(Integer, ForeignKey('especialidad.idespecialidad'), primary_key=True)
