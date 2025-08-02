from sqlalchemy import Column, Integer, String, Boolean
from .base import Base

class Proveedor(Base):
    __tablename__ = 'proveedor'
    idproveedor = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(120), nullable=False)
    ruc = Column(String(20))
    direccion = Column(String(200))
    telefono = Column(String(50))
    email = Column(String(80))
    observaciones = Column(String)
    estado = Column(Boolean, default=True)   # <-- Esto es clave