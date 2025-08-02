from sqlalchemy import Column, Integer, DateTime, ForeignKey, String
from .base import Base

class Auditoria(Base):
    __tablename__ = 'auditoria'
    idauditoria = Column(Integer, primary_key=True, autoincrement=True)
    fechahora = Column(DateTime, nullable=False)
    idusuario = Column(Integer, ForeignKey('usuario.idusuario'))
    modulo = Column(String(50))
    accion = Column(String(80))
    observaciones = Column(String)
