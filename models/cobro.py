from sqlalchemy import Column, Integer, Date, ForeignKey, Numeric, String
from .base import Base

class Cobro(Base):
    __tablename__ = 'cobro'
    idcobro = Column(Integer, primary_key=True, autoincrement=True)
    fecha = Column(Date, nullable=False)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'))
    monto = Column(Numeric(14,2), nullable=False)
    formapago = Column(String(30))
    observaciones = Column(String)
    usuarioregistro = Column(String(50))
