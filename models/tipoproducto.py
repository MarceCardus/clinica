from sqlalchemy import Column, Integer, String
from .base import Base

class TipoProducto(Base):
    __tablename__ = "tipoproducto"
    idtipoproducto = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(50), unique=True, nullable=False)