from sqlalchemy import Column, Enum, Integer, String
from .base import Base

class Insumo(Base):
    __tablename__ = 'insumo'
    idinsumo = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    tipo = Column(Enum(
        'MEDICAMENTO', 
        'DESCARTABLE', 
        'REACTIVO', 
        'ANTIBIOTICO',
        name='tipo_insumo'
    ), nullable=False)
    unidad = Column(String(20), nullable=False)
    categoria = Column(Enum(
        'CONSUMO_INTERNO', 
        'USO_PROCEDIMIENTO', 
        name='categoria_insumo'
    ), nullable=False)
