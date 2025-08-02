from sqlalchemy import Column, Integer, Date, ForeignKey, String
from .base import Base

class Sesion(Base):
    __tablename__ = 'sesion'
    idsesion = Column(Integer, primary_key=True, autoincrement=True)
    fecha = Column(Date, nullable=False)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'))
    idprofesional = Column(Integer, ForeignKey('profesional.idprofesional'))
    idproducto = Column(Integer, ForeignKey('producto.idproducto'))
    idpaquete = Column(Integer, ForeignKey('paquete.idpaquete'))
    observaciones = Column(String)
    estado = Column(String(20))
    idclinica = Column(Integer, ForeignKey('clinica.idclinica'))
    numerosesionenpaquete = Column(Integer)
