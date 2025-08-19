# models/tipoproducto.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from .base import Base

class TipoProducto(Base):
    __tablename__ = "tipoproducto"
    idtipoproducto = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), unique=True, nullable=False)

    # inversa a Item.tipo_producto
    items = relationship("Item", back_populates="tipoproducto")
    productos = relationship("Producto", back_populates="tipoproducto")