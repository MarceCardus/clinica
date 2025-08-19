# models/especialidad.py  (solo la parte relevante)
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from .base import Base

class Especialidad(Base):
    __tablename__ = "especialidad"
    idespecialidad = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), unique=True, nullable=False)

    items = relationship("Item", back_populates="especialidad")
    productos = relationship("Producto", back_populates="especialidad")