from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class PacienteEncargado(Base):
    __tablename__ = 'paciente_encargado'

    id = Column(Integer, primary_key=True, autoincrement=True)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente', ondelete='CASCADE'))
    idencargado = Column(Integer, ForeignKey('encargado.idencargado', ondelete='CASCADE'))
    tipo = Column(String(30))  # Ejemplo: 'Padre', 'Madre', 'Tutor', etc.

    paciente = relationship("Paciente", back_populates="encargados")
    encargado = relationship("Encargado", back_populates="pacientes")
