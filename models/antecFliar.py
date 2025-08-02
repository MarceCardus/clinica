from sqlalchemy import Column, Integer, Boolean, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class AntecedenteFamiliar(Base):
    __tablename__ = 'antecedente_familiar'

    id = Column(Integer, primary_key=True, autoincrement=True)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'))
    aplica = Column(Boolean, default=True)
    patologia_padre = Column(String(120))
    patologia_madre = Column(String(120))
    patologia_hermanos = Column(String(120))
    patologia_hijos = Column(String(120))
    observaciones = Column(Text)
    
    paciente = relationship("Paciente", back_populates="antecedentes_familiares")
