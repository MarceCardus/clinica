from sqlalchemy import Column, Integer, DateTime, ForeignKey, Numeric, String, Enum
from sqlalchemy.sql import func
from .base import Base

class StockMovimiento(Base):
    __tablename__ = 'stock_movimiento'
    idmovimiento = Column(Integer, primary_key=True, autoincrement=True)
    fecha = Column(DateTime, default=func.now())
    iditem = Column(Integer, ForeignKey('item.iditem'), nullable=False)  # CAMBIADO
    cantidad = Column(Numeric(10, 2), nullable=False)
    tipo = Column(Enum('INGRESO', 'EGRESO', name='tipo_movimiento'), nullable=False)
    motivo = Column(String(100))
    idorigen = Column(Integer)
    observacion = Column(String)