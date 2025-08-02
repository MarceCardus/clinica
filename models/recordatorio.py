from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from .base import Base

class Recordatorio(Base):
    __tablename__ = "recordatorio"
    idrecordatorio = Column(Integer, primary_key=True, autoincrement=True)
    idindicacion = Column(Integer, ForeignKey('indicacion.idindicacion'), nullable=False)
    fecha_hora = Column(DateTime, nullable=False)
    mensaje = Column(String)
    enviado = Column(Boolean, default=False)
