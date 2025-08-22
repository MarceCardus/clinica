from sqlalchemy import Column, Integer, Date, ForeignKey, Numeric, String
from .base import Base
from sqlalchemy.orm import relationship
from sqlalchemy.ext.associationproxy import association_proxy
from decimal import Decimal

class Cobro(Base):
    __tablename__ = 'cobro'
    idcobro = Column(Integer, primary_key=True, autoincrement=True)
    fecha = Column(Date, nullable=False)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'))
    monto = Column(Numeric(14,2), nullable=False)
    formapago = Column(String(30))
    observaciones = Column(String)
    usuarioregistro = Column(String(50))
    estado = Column(String(20), default="ACTIVO")  # ← NUEVO (ACTIVO / ANULADO)
    imputaciones = relationship("CobroVenta", back_populates="cobro",
                                cascade="all, delete-orphan")
    ventas = association_proxy("imputaciones", "venta")

    @property
    def total_imputado(self):
         return sum((cv.montoimputado or Decimal("0")) for cv in self.imputaciones)

    @property
    def monto_disponible(self):
        return (self.monto or Decimal("0")) - self.total_imputado
