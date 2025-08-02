from sqlalchemy import Column, Integer, ForeignKey, Numeric
from .base import Base

class CompraDetalle(Base):
    __tablename__ = 'compra_detalle'
    idcompra = Column(Integer, ForeignKey('compra.idcompra'), primary_key=True)
    idinsumo = Column(Integer, ForeignKey('insumo.idinsumo'), primary_key=True)
    cantidad = Column(Integer)
    preciounitario = Column(Numeric(14,2))
