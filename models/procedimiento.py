# models/procedimiento.py
from sqlalchemy import Column, Integer, Date, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base
from .procedimiento_item import procedimiento_item  # <— IMPORTANTE

class Procedimiento(Base):
    __tablename__ = "procedimiento"

    id = Column(Integer, primary_key=True, autoincrement=True)
    idpaciente = Column(Integer, ForeignKey("paciente.idpaciente"), nullable=False)
    fecha = Column(Date, nullable=False)

    # ÍTEM PRINCIPAL del procedimiento (p.ej. “Lipo Láser” como servicio)
    iditem = Column(Integer, ForeignKey("item.iditem"), nullable=False)
    comentario = Column(String(200))

    # Relaciones
    paciente = relationship("Paciente", back_populates="procedimientos")

    # ítem principal (renombrado para no colisionar con el M2M)
    item = relationship(
        "Item",
        back_populates="procedimientos_principales",   # <— nombre nuevo del lado Item
        foreign_keys=[iditem]
    )

    # muchos-a-muchos: insumos/ítems consumidos por el procedimiento
    items = relationship(
        "Item",
        secondary=procedimiento_item,                  # <— variable Table, NO string
        back_populates="procedimientos"
    )

    indicaciones = relationship(
        "Indicacion",
        back_populates="procedimiento",
        foreign_keys="Indicacion.idprocedimiento",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<Procedimiento id={self.id} fecha={self.fecha} iditem={self.iditem}>"
