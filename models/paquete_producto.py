from sqlalchemy import Column, Integer, ForeignKey
from .base import Base

class PaqueteProducto(Base):
    __tablename__ = 'paquete_producto'
    idpaquete = Column(Integer, ForeignKey('paquete.idpaquete'), primary_key=True)
    idproducto = Column(Integer, ForeignKey('producto.idproducto'), primary_key=True)
    sesionorden = Column(Integer, primary_key=True)
    duracionsesion = Column(Integer)
