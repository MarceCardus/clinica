from sqlalchemy import Column, Integer, Date, DECIMAL, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class AntecedenteEnfermedadActual(Base):
    __tablename__ = 'antecedente_enfermedad_actual'

    id = Column(Integer, primary_key=True, autoincrement=True)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'))
    fecha = Column(Date, nullable=False)
    peso = Column(DECIMAL(5,2))
    altura = Column(DECIMAL(5,2))
    cint = Column(String(10))
    omb = Column(String(10))
    bajo_omb = Column(String(20))
    p_ideal = Column(String(20))
    brazo_izquierdo = Column(DECIMAL(5,2))
    brazo_derecho = Column(DECIMAL(5,2))
    pierna_izquierda = Column(DECIMAL(5,2))
    pierna_derecha = Column(DECIMAL(5,2))
    espalda = Column(DECIMAL(5,2))
    paciente = relationship("Paciente", back_populates="antecedentes_enfermedad_actual")
