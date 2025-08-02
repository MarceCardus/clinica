from sqlalchemy import Column, Integer, Date, ForeignKey, Numeric, Boolean
from .base import Base

class ComisionProfesional(Base):
    __tablename__ = 'comisionprofesional'
    idcomision = Column(Integer, primary_key=True, autoincrement=True)
    idventa = Column(Integer, ForeignKey('venta.idventa'))
    idprofesional = Column(Integer, ForeignKey('profesional.idprofesional'))
    porcentaje = Column(Numeric(5,2))
    montocalculado = Column(Numeric(14,2))
    pagada = Column(Boolean, default=False)
    fechapago = Column(Date)
