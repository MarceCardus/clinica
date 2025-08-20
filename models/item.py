# models/item.py
from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Date, Text,
    ForeignKey, DateTime, func
)
from sqlalchemy.orm import relationship
from .base import Base

class ItemTipo(Base):
    __tablename__ = "item_tipo"
    iditemtipo = Column(Integer, primary_key=True, autoincrement=True)
    # Ejemplos de filas: PRODUCTO / INSUMO / AMBOS
    nombre = Column(String(20), unique=True, nullable=False)

    items = relationship(
        "Item",
        back_populates="tipo",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

class Item(Base):
    __tablename__ = "item"

    iditem = Column(Integer, primary_key=True, autoincrement=True)

    # Comunes
    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text)
    activo = Column(Boolean, nullable=False, default=True)
    fecha_creacion = Column(DateTime, nullable=False, server_default=func.now())
    fecha_actualizacion = Column(DateTime)

    # Clasificación general
    iditemtipo = Column(Integer, ForeignKey("item_tipo.iditemtipo", ondelete="RESTRICT"), nullable=False)
    tipo = relationship("ItemTipo", back_populates="items")

    # --- Campos heredados de PRODUCTO ---
    precio_venta = Column(Numeric(14, 2))
    idtipoproducto = Column(Integer, ForeignKey("tipoproducto.idtipoproducto", ondelete="RESTRICT"))
    idespecialidad = Column(Integer, ForeignKey("especialidad.idespecialidad", ondelete="RESTRICT"))
    requiere_recordatorio = Column(Boolean, default=False, nullable=False)
    dias_recordatorio = Column(Integer)
    mensaje_recordatorio = Column(String(160))
    # para compatibilidad con tu schema actual
    tipo_producto = Column(String(30))   # opcional (si lo usabas como etiqueta)

    # --- Campos heredados de INSUMO ---
    unidad = Column(String(20))
    categoria = Column(String(50))        # 'CONSUMO_INTERNO' / 'USO_PROCEDIMIENTO'
    tipo_insumo = Column(String(50))      # 'MEDICAMENTO', 'DESCARTABLE', etc.
    stock_minimo = Column(Numeric(14, 2))
    
    # Flags de uso (según tu captura: uso_interno / uso_procedimiento)
    uso_interno = Column(Boolean, nullable=False, default=False)
    uso_procedimiento = Column(Boolean, nullable=False, default=False)

    # Relaciones de negocio
    tipoproducto = relationship("TipoProducto", back_populates="items", foreign_keys=[idtipoproducto])
    especialidad  = relationship("Especialidad", back_populates="items", foreign_keys=[idespecialidad])
    
    # Detalles
    compra_detalles = relationship("CompraDetalle", back_populates="item", passive_deletes=True)
    venta_detalles  = relationship("VentaDetalle",  back_populates="item", passive_deletes=True)

# --- Shims de compatibilidad mientras migras usos antiguos ---
class ProductoMap(Base):
    __tablename__ = "producto_map"
    idproducto = Column(Integer, primary_key=True, autoincrement=True)
    iditem = Column(Integer, ForeignKey("item.iditem", ondelete="RESTRICT"), nullable=False, unique=True)
    item = relationship("Item")

class InsumoMap(Base):
    __tablename__ = "insumo_map"
    idinsumo = Column(Integer, primary_key=True, autoincrement=True)
    iditem = Column(Integer, ForeignKey("item.iditem", ondelete="RESTRICT"), nullable=False, unique=True)
    item = relationship("Item")
