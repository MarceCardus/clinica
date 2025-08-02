from sqlalchemy import Column, Integer, String
from .base import Base

class Especialidad(Base):
    __tablename__ = 'especialidad'

    idespecialidad = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(60), nullable=False)
