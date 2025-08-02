from sqlalchemy import Column, Integer, ForeignKey, Numeric
from .base import Base

class CobroVenta(Base):
    __tablename__ = 'cobro_venta'
    idcobro = Column(Integer, ForeignKey('cobro.idcobro'), primary_key=True)
    idventa = Column(Integer, ForeignKey('venta.idventa'), primary_key=True)
    montoimputado = Column(Numeric(14,2), nullable=False)
