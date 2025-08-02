from sqlalchemy import Column, Integer, String, Date, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class FotoAvance(Base):
    __tablename__ = "fotoavance"
    idfoto = Column(Integer, primary_key=True, autoincrement=True)
    idpaciente = Column(Integer, ForeignKey("paciente.idpaciente"))
    rutaarchivo = Column(String(255))
    fecha = Column(Date)
    comentario = Column(Text)
    etiquetas = Column(String(120))
    sensible = Column(Boolean, default=False)
    usuariocarga = Column(Integer, ForeignKey('usuario.idusuario'))
    usuario = relationship("Usuario")   
