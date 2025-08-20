from sqlalchemy import Column, Integer, ForeignKey, Numeric, Date, String
from sqlalchemy.orm import relationship
from .base import Base

class CompraDetalle(Base):
    __tablename__ = 'compra_detalle'

    idcompdet = Column(Integer, primary_key=True, autoincrement=True)
    idcompra = Column(Integer, ForeignKey('compra.idcompra', ondelete="CASCADE"), nullable=False, index=True)
    iditem   = Column(Integer, ForeignKey('item.iditem',   ondelete="RESTRICT"), nullable=False, index=True)
    cantidad       = Column(Numeric(14,2), nullable=False, default=0)
    preciounitario = Column(Numeric(14,2), nullable=False, default=0)
    iva            = Column(Numeric(14,2), default=0)
    fechavencimiento = Column(Date)
    lote             = Column(String(30))
    observaciones    = Column(String)

    item   = relationship("Item", back_populates="compra_detalles")
    compra = relationship("Compra", back_populates="detalles")
    