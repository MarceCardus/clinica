# models/plan_tipo.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class PlanTipo(Base):
    __tablename__ = "plan_tipo"

    idplantipo = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), unique=True, nullable=False)

    # Mapea a la columna existente "sesiones_por_defecto"
    sesiones_por_defecto = Column("sesiones_por_defecto", Integer, nullable=False, server_default="1")

    requiere_masaje  = Column(Boolean, nullable=False, server_default="false")
    requiere_aparato = Column(Boolean, nullable=False, server_default="false")
    activo           = Column(Boolean, nullable=False, server_default="true")

    creado_en      = Column(DateTime, nullable=False, server_default=func.now())
    actualizado_en = Column(DateTime)

    # inversa con Item
    items = relationship("Item", back_populates="plan_tipo")

    def __repr__(self):
        return f"<PlanTipo {self.idplantipo} {self.nombre!r}>"
