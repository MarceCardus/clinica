# models/item.py
from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Text,
    ForeignKey, DateTime, func
)
from sqlalchemy.orm import relationship
from utils.db import Base
from .procedimiento_item import procedimiento_item  # <— IMPORTANTE

class ItemTipo(Base):
    __tablename__ = "item_tipo"
    iditemtipo = Column(Integer, primary_key=True, autoincrement=True)
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
    genera_stock = Column(Boolean, nullable=False, default=True)
    codigo_barra = Column(String(64), unique=True)

    # Clasificación general
    iditemtipo = Column(Integer, ForeignKey("item_tipo.iditemtipo", ondelete="RESTRICT"), nullable=False)
    tipo = relationship("ItemTipo", back_populates="items")

    # Plan/tipo (opcional)
    idplantipo = Column(Integer, ForeignKey("plan_tipo.idplantipo", ondelete="RESTRICT"), nullable=True)
    sesiones_incluidas = Column(Integer)

    # Producto/insumo
    precio_venta = Column(Numeric(14, 2))
    idtipoproducto = Column(Integer, ForeignKey("tipoproducto.idtipoproducto", ondelete="RESTRICT"))
    idespecialidad = Column(Integer, ForeignKey("especialidad.idespecialidad", ondelete="RESTRICT"))
    requiere_recordatorio = Column(Boolean, default=False, nullable=False)
    dias_recordatorio = Column(Integer)
    mensaje_recordatorio = Column(String(160))
    tipo_producto = Column(String(30))

    unidad = Column(String(20))
    categoria = Column(String(50))
    tipo_insumo = Column(String(50))
    stock_minimo = Column(Numeric(14, 2))

    uso_interno = Column(Boolean, nullable=False, default=False)
    uso_procedimiento = Column(Boolean, nullable=False, default=False)

    # Relaciones de negocio
    tipoproducto = relationship("TipoProducto", back_populates="items", foreign_keys=[idtipoproducto])
    especialidad  = relationship("Especialidad", back_populates="items", foreign_keys=[idespecialidad])

    # Detalles
    compra_detalles = relationship("CompraDetalle", back_populates="item", passive_deletes=True)
    venta_detalles  = relationship("VentaDetalle",  back_populates="item", passive_deletes=True)

    # Inversas
    indicaciones = relationship("Indicacion", back_populates="item", passive_deletes=True)
    plan_tipo = relationship("PlanTipo", back_populates="items")

    # ⚠️ Separar las dos lógicas:
    # 1) Procedimientos donde este ítem es el **principal** (FK directa en Procedimiento.iditem)
    procedimientos_principales = relationship(
        "Procedimiento",
        back_populates="item",
        foreign_keys="Procedimiento.iditem"
    )

    # 2) Procedimientos donde este ítem es un **insumo** (M2M)
    procedimientos = relationship(
        "Procedimiento",
        secondary=procedimiento_item,    # <— variable Table, NO string
        back_populates="items"
    )

    def __repr__(self):
        return f"<Item id={self.iditem} nombre={self.nombre!r}>"
