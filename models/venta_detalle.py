# models/venta_detalle.py
from sqlalchemy import Column, Integer, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from .base import Base

class VentaDetalle(Base):
    __tablename__ = 'venta_detalle'
    idventadet = Column(Integer, primary_key=True, autoincrement=True)  # <- NUEVO
    idventa = Column(Integer, ForeignKey('venta.idventa'), nullable=False)
    idproducto = Column(Integer, ForeignKey('producto.idproducto'), nullable=False)
    idpaquete = Column(Integer, ForeignKey('paquete.idpaquete'))  # nullable OK
    cantidad = Column(Numeric(14,2), nullable=False)
    preciounitario = Column(Numeric(14,2), nullable=False)
    descuento = Column(Numeric(14,2), default=0)
