from sqlalchemy import Column, Integer, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base
from .encargado import Encargado

class AntecedentePatologicoPersonal(Base):
    __tablename__ = 'antecedente_patologico_personal'

    id = Column(Integer, primary_key=True, autoincrement=True)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'))
    cardiovasculares = Column(Boolean)
    respiratorios = Column(Boolean)
    alergicos = Column(Boolean)
    neoplasicos = Column(Boolean)
    digestivos = Column(Boolean)
    genitourinarios = Column(Boolean)
    asmatico = Column(Boolean)
    metabolicos = Column(Boolean)
    osteoarticulares = Column(Boolean)
    neuropsiquiatricos = Column(Boolean)
    internaciones = Column(Boolean)
    cirugias = Column(Boolean)
    psicologicos = Column(Boolean)
    audiovisuales = Column(Boolean)
    transfusiones = Column(Boolean)
    otros = Column(Text)
    
    paciente = relationship("Paciente", back_populates="antecedentes_patologicos_personales")
