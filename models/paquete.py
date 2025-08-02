from sqlalchemy import Column, Integer, String, Numeric
from .base import Base

class Paquete(Base):
    __tablename__ = 'paquete'
    idpaquete = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(String)
    cantidadsesiones = Column(Integer)
    preciototal = Column(Numeric(14,2), nullable=False)
    observaciones = Column(String)
