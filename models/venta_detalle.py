from sqlalchemy import Column, Integer, ForeignKey, Numeric
from .base import Base

class VentaDetalle(Base):
    __tablename__ = 'venta_detalle'
    idventa = Column(Integer, ForeignKey('venta.idventa'), primary_key=True)
    idproducto = Column(Integer, ForeignKey('producto.idproducto'), primary_key=True)
    idpaquete = Column(Integer, ForeignKey('paquete.idpaquete'), primary_key=True)
    cantidad = Column(Integer)
    preciounitario = Column(Numeric(14,2))
    descuento = Column(Numeric(14,2))
