# models/venta_detalle.py
from sqlalchemy import Column, Integer, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from utils.db import Base  # importa tu Base declarativa

class VentaDetalle(Base):
    __tablename__ = "venta_detalle"

    idventadet     = Column(Integer, primary_key=True, autoincrement=True)
    idventa        = Column(Integer, ForeignKey("venta.idventa"), nullable=False)
    iditem         = Column(Integer, ForeignKey("item.iditem"), nullable=False)

    cantidad       = Column(Numeric(12, 2), nullable=False, default=0)
    preciounitario = Column(Numeric(12, 2), nullable=False, default=0)
    descuento      = Column(Numeric(12, 2), nullable=True)

    # Relaciones opcionales (ajustá nombres si ya existen en Venta/Item)
    venta = relationship("Venta", back_populates="detalles", lazy="joined")
    item  = relationship("Item", lazy="joined")
