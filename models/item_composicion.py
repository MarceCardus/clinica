# models/item_composicion.py
from sqlalchemy import Column, Integer, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from utils.db import Base

class ItemComposicion(Base):
    __tablename__ = "item_composicion"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Ítem “padre” (servicio/kit que agrupa componentes)
    iditem_padre = Column(
        Integer,
        ForeignKey("item.iditem", ondelete="CASCADE"),
        nullable=False
    )

    # Ítem “insumo/componente” (lo que se consume)
    iditem_insumo = Column(
        Integer,
        ForeignKey("item.iditem", ondelete="RESTRICT"),
        nullable=False
    )

    # Cantidad usada por 1 unidad del padre
    cantidad = Column(Numeric(14, 3), nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("iditem_padre", "iditem_insumo", name="uq_item_composicion"),
    )

    item_padre = relationship("Item", foreign_keys=[iditem_padre])
    insumo = relationship("Item", foreign_keys=[iditem_insumo])

    def __repr__(self):
        return f"<ItemComposicion padre={self.iditem_padre} insumo={self.iditem_insumo} cant={self.cantidad}>"
