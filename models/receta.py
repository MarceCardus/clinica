from sqlalchemy import Column, Integer, Date, ForeignKey, String
from .base import Base

class Receta(Base):
    __tablename__ = 'receta'
    idreceta = Column(Integer, primary_key=True, autoincrement=True)
    fecha = Column(Date, nullable=False)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'))
    idprofesional = Column(Integer, ForeignKey('profesional.idprofesional'))
    textolibremedicamento = Column(String)
    dosisindicaciones = Column(String)
    observaciones = Column(String)
    rutaarchivopdf = Column(String(255))
