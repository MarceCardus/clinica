from sqlalchemy import Column, Integer, String, Numeric
from sqlalchemy.orm import relationship
from .base import Base

class Paquete(Base):
    __tablename__ = 'paquete'
    idpaquete = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(String)
    cantidadsesiones = Column(Integer)
    preciototal = Column(Numeric(14,2), nullable=False)
    observaciones = Column(String)
    componentes = relationship("PaqueteProducto", back_populates="paquete", cascade="all, delete-orphan")