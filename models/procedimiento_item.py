# models/procedimiento_item.py
from sqlalchemy import Table, Column, Integer, ForeignKey, Numeric
from utils.db import Base

procedimiento_item = Table(
    "procedimiento_item",
    Base.metadata,
    Column("idprocedimiento", Integer, ForeignKey("procedimiento.id", ondelete="CASCADE"), primary_key=True),
    Column("iditem", Integer, ForeignKey("item.iditem", ondelete="CASCADE"), primary_key=True),
    # si querés cantidad en la tabla intermedia:
    Column("cantidad", Numeric(14, 2), nullable=False, server_default="1")
)
