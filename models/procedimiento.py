from sqlalchemy import Column, Integer, Date, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class Procedimiento(Base):
    __tablename__ = 'procedimiento'
    id = Column(Integer, primary_key=True, autoincrement=True)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'))
    fecha = Column(Date, nullable=False)
    idproducto = Column(Integer, ForeignKey('producto.idproducto'), nullable=False)  # CORRECTO
    comentario = Column(String(200))

    paciente = relationship("Paciente", back_populates="procedimientos")
    producto = relationship("Producto")  # Esto te permite acceder directo a proc.producto.nombre
