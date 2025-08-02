from sqlalchemy import Column, Integer, Date, ForeignKey, Numeric, String
from .base import Base

class Compra(Base):
    __tablename__ = 'compra'
    idcompra = Column(Integer, primary_key=True, autoincrement=True)
    fecha = Column(Date, nullable=False)
    idproveedor = Column(Integer, ForeignKey('proveedor.idproveedor'))
    idclinica = Column(Integer, ForeignKey('clinica.idclinica'))
    montototal = Column(Numeric(14,2))
    observaciones = Column(String)
