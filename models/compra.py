from sqlalchemy import Column, Integer, Date, ForeignKey, Numeric, String, Enum,Boolean
from .base import Base
from sqlalchemy.orm import relationship
class Compra(Base):
    __tablename__ = 'compra'
    idcompra = Column(Integer, primary_key=True, autoincrement=True)
    fecha = Column(Date, nullable=False)
    idproveedor = Column(Integer, ForeignKey("proveedor.idproveedor", ondelete="RESTRICT"), nullable=False, index=True)
    idclinica = Column(Integer, ForeignKey('clinica.idclinica'))
    tipo_comprobante = Column(String(30))        # Factura, Nota de Remisión, etc.
    nro_comprobante = Column(String(30))         # Número de factura, etc.
    condicion_compra = Column(Enum('CONTADO', 'CREDITO', name='condicion_compra'))
    montototal = Column(Numeric(14,2))
    observaciones = Column(String)
    proveedor = relationship("Proveedor", back_populates="compras")
    detalles  = relationship("CompraDetalle", back_populates="compra", cascade="all, delete-orphan")
    anulada = Column(Boolean, default=False)