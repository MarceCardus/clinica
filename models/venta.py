from sqlalchemy import Column, Integer, Date, ForeignKey, Numeric, String
from .base import Base

class Venta(Base):
    __tablename__ = 'venta'
    idventa = Column(Integer, primary_key=True, autoincrement=True)
    fecha = Column(Date, nullable=False)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'))
    idprofesional = Column(Integer, ForeignKey('profesional.idprofesional'))
    idclinica = Column(Integer, ForeignKey('clinica.idclinica'))
    montototal = Column(Numeric(14,2), nullable=False)
    estadoventa = Column(String(20))
    nro_factura = Column(String(15), nullable=True) 
    observaciones = Column(String)
