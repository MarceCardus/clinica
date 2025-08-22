from sqlalchemy import Column, Integer, Date, ForeignKey, Numeric, String
from .base import Base
from sqlalchemy.orm import relationship
from sqlalchemy.ext.associationproxy import association_proxy

class Venta(Base):
    __tablename__ = 'venta'
    idventa = Column(Integer, primary_key=True, autoincrement=True)
    fecha = Column(Date, nullable=False)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'))
    idprofesional = Column(Integer, ForeignKey('profesional.idprofesional'))
    idclinica = Column(Integer, ForeignKey('clinica.idclinica'))
    montototal = Column(Numeric(14,2), nullable=False)
    saldo = Column(Numeric(14,2), nullable=False, default=0)
    estadoventa = Column(String(20))
    nro_factura = Column(String(15), nullable=True) 
    observaciones = Column(String)
    detalles = relationship("VentaDetalle", back_populates="venta", cascade="all, delete-orphan")
    imputaciones_cobro = relationship("CobroVenta", back_populates="venta",
                                      cascade="all, delete-orphan")
    cobros = association_proxy("imputaciones_cobro", "cobro")  # proxy read-only