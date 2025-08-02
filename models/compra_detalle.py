from sqlalchemy import Column, Integer, ForeignKey, Numeric, Date, String
from .base import Base

class CompraDetalle(Base):
    __tablename__ = 'compra_detalle'
    idcompra = Column(Integer, ForeignKey('compra.idcompra'), primary_key=True)
    idinsumo = Column(Integer, ForeignKey('insumo.idinsumo'), primary_key=True)
    cantidad = Column(Integer)
    preciounitario = Column(Numeric(14,2))
    iva = Column(Numeric(14,2), default=0)           # Monto de IVA por ítem
    fechavencimiento = Column(Date, nullable=True)   # Si el producto es perecedero
    lote = Column(String(30), nullable=True)         # Lote del producto
    observaciones = Column(String, nullable=True)    # Observación específica del ítem