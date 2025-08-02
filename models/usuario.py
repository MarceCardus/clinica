from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from .base import Base

class Usuario(Base):
    __tablename__ = 'usuario'

    idusuario = Column(Integer, primary_key=True, autoincrement=True)
    usuario = Column(String(50), nullable=False, unique=True)
    contrasena = Column(String(120), nullable=False)
    rol = Column(String(40), nullable=False)
    idprofesional = Column(Integer, ForeignKey('profesional.idprofesional'))
    idclinica = Column(Integer, ForeignKey('clinica.idclinica'))
    estado = Column(Boolean, default=True) 