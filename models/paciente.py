# models/paciente.py
from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base
from .antecPatologico import AntecedentePatologicoPersonal
from .antecEnfActual import AntecedenteEnfermedadActual
from .antecFliar import AntecedenteFamiliar
from .barrio import Barrio
from .pacienteEncargado import PacienteEncargado
# (Opcional) si realmente necesitás, importá aquí arriba:
from .procedimiento import Procedimiento
from .indicacion import Indicacion

class Paciente(Base):
    __tablename__ = 'paciente'

    idpaciente = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(80), nullable=False)
    apellido = Column(String(80), nullable=False)
    ci_pasaporte = Column(String(20), nullable=False)
    tipo_documento = Column(String(20))
    fechanacimiento = Column(Date)
    sexo = Column(String(10))
    telefono = Column(String(40))
    contacto_alternativo = Column(String(40))
    email = Column(String(80))
    direccion = Column(String(200))
    nacionalidad = Column(String(40))
    ruc = Column(String(20))
    razon_social = Column(String(160))
    ruta_foto = Column(String(200))
    fecha_alta = Column(Date)
    estado = Column(Boolean, default=True)
    observaciones = Column(String)
    idbarrio = Column(Integer, ForeignKey('barrio.idbarrio'), nullable=False)

    barrio = relationship("Barrio", back_populates="pacientes")
    antecedentes_patologicos_personales = relationship(
        "AntecedentePatologicoPersonal", back_populates="paciente", cascade="all, delete-orphan"
    )
    antecedentes_enfermedad_actual = relationship(
        "AntecedenteEnfermedadActual", back_populates="paciente", cascade="all, delete-orphan"
    )
    antecedentes_familiares = relationship(
        "AntecedenteFamiliar", back_populates="paciente", cascade="all, delete-orphan"
    )
    encargados = relationship(
        "PacienteEncargado", back_populates="paciente", cascade="all, delete-orphan"
    )
    procedimientos = relationship(
        "Procedimiento", back_populates="paciente", cascade="all, delete-orphan"
    )
    indicaciones = relationship(
        "Indicacion", back_populates="paciente", cascade="all, delete-orphan"
        # sin order_by aquí para evitar el error
    )
   