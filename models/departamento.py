from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from .base import Base

class Departamento(Base):
    __tablename__ = 'departamento'
    iddepartamento = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(80), nullable=False)
    ciudades = relationship("Ciudad", back_populates="departamento")