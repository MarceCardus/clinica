# models/producto.py
from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .base import Base

class Producto(Base):
    __tablename__ = "producto"

    idproducto = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(80), nullable=False)
    descripcion = Column(String(200))
    duracion = Column(Integer)  # minutos, si aplica
    precio = Column(Numeric(14, 2), nullable=False, default=0)

    idtipoproducto = Column(
        Integer,
        ForeignKey("tipoproducto.idtipoproducto", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    idespecialidad = Column(
        Integer,
        ForeignKey("especialidad.idespecialidad", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )

    requiere_recordatorio = Column(Boolean, nullable=False, default=False)
    dias_recordatorio = Column(Integer)
    mensaje_recordatorio = Column(String(160))

    # Importante: el nombre de la relación debe matchear la CLASE
    # y el back_populates debe matchear lo definido en TipoProducto
    tipoproducto = relationship("TipoProducto", back_populates="productos")
    especialidad  = relationship("Especialidad", back_populates="productos")
     # indicaciones = relationship("Indicacion", back_populates="producto", cascade="all, delete-orphan")


    # si usás Indicacion:
    # indicaciones = relationship("Indicacion", back_populates="producto", cascade="all, delete-orphan")
