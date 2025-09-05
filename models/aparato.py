from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class Aparato(Base):
    __tablename__ = "aparato"
    idaparato = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(120), unique=True, nullable=False)
    marca = Column(String(80))
    modelo = Column(String(80))
    nro_serie = Column(String(80))
    descripcion = Column(Text)
    activo = Column(Boolean, nullable=False, server_default="true")
    creado_en = Column(DateTime, nullable=False, server_default=func.now())
    actualizado_en = Column(DateTime)

    # si más adelante querés ver usos: relationship desde PlanSesion (abajo)
