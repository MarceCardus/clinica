from sqlalchemy import Column, Integer, String
from .base import Base

class Clinica(Base):
    __tablename__ = 'clinica'

    idclinica = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    direccion = Column(String(200))
    telefono = Column(String(50))
