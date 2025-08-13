# models/paquete_producto.py
from sqlalchemy import Column, Integer, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from .base import Base

class PaqueteProducto(Base):
    __tablename__ = 'paquete_producto'
    idpaquete = Column(Integer, ForeignKey('paquete.idpaquete'), primary_key=True)
    idproducto = Column(Integer, ForeignKey('producto.idproducto'), primary_key=True)
    cantidad = Column(Numeric(14,2), nullable=False)

    producto = relationship("Producto")
    paquete = relationship("Paquete", back_populates="componentes")
