from sqlalchemy import Column, Enum, Integer, String
from .base import Base
from sqlalchemy.orm import relationship
class Insumo(Base):
    __tablename__ = 'insumo'
    idinsumo = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    tipo = Column(Enum(
        'MEDICAMENTO', 
        'DESCARTABLE', 
        'REACTIVO', 
        'ANTIBIOTICO',
        'VARIOS',
        name='tipo_insumo'
    ), nullable=False)
    unidad = Column(String(20), nullable=False)
    categoria = Column(Enum(
        'CONSUMO_INTERNO', 
        'USO_PROCEDIMIENTO', 
        name='categoria_insumo'
    ), nullable=False)
    #indicaciones = relationship('Indicacion', back_populates='insumo')