from sqlalchemy import Column, Integer, Date, ForeignKey, Numeric, String
from .base import Base

class CajaMovimiento(Base):
    __tablename__ = 'cajamovimiento'
    idcajamov = Column(Integer, primary_key=True, autoincrement=True)
    fecha = Column(Date, nullable=False)
    idclinica = Column(Integer, ForeignKey('clinica.idclinica'))
    tipo = Column(String(20))
    monto = Column(Numeric(14,2))
    concepto = Column(String)
    usuario = Column(String(50))
