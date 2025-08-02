from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class Producto(Base):
    __tablename__ = "producto"
    idproducto = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(80))
    descripcion = Column(String(200))
    duracion = Column(Integer)
    precio = Column(Float)
    idtipoproducto = Column(Integer, ForeignKey("tipoproducto.idtipoproducto"))
    idespecialidad = Column(Integer, ForeignKey("especialidad.idespecialidad"))

    tipoproducto = relationship("TipoProducto")
    especialidad = relationship("Especialidad")