from sqlalchemy import Column, Integer, Date, ForeignKey, Numeric, String
from .base import Base

class VentaCuota(Base):
    __tablename__ = 'venta_cuota'
    idventa = Column(Integer, ForeignKey('venta.idventa'), primary_key=True)
    numerocuota = Column(Integer, primary_key=True)
    fechavencimiento = Column(Date)
    montocuota = Column(Numeric(14,2))
    estadocuota = Column(String(20))
    fechapago = Column(Date)
    idcobro = Column(Integer, ForeignKey('cobro.idcobro'))
    observaciones = Column(String)
