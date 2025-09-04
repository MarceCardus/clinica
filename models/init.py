# models/__init__.py
from .base import Base

# --- Núcleo de ítems (unificado) ---
from .item import Item, ItemTipo
from .tipoproducto import TipoProducto          # Item lo referencia
from .especialidad import Especialidad          # Item lo referencia

# --- Clínica / Personas / Profesionales ---
from .clinica import Clinica
from .paciente import Paciente
from .profesional import Profesional
from .profesional_especialidad import ProfesionalEspecialidad
from .usuario import Usuario

# --- Historia clínica ---
from .indicacion import Indicacion              # usa idinsumo por ahora o iditem si ya migraste
from .procedimiento import Procedimiento
from .antecPatologico import AntecedentePatologicoPersonal
from .antecEnfActual import AntecedenteEnfermedadActual
from .antecFliar import AntecedenteFamiliar
from .pacienteEncargado import PacienteEncargado
from .recordatorio_paciente import RecordatorioPaciente

# --- Geografía ---
from .departamento import Departamento
from .ciudad import Ciudad
from .barrio import Barrio

# Si necesitás StockMovimiento en otros lados, lo importás directo:
# from .StockMovimiento import StockMovimiento

# --------------------------------------------------------------------
# Relaciones diferidas SEGURAS (sin forzar joins entre tablas sin FK)
# --------------------------------------------------------------------
from sqlalchemy.orm import relationship

# Ciudad <-> Departamento
Ciudad.departamento = relationship(Departamento, back_populates="ciudades")
Departamento.ciudades = relationship(
    Ciudad, back_populates="departamento", cascade="all, delete-orphan"
)

# Barrio <-> Ciudad
Barrio.ciudad = relationship(Ciudad, back_populates="barrios")
Ciudad.barrios = relationship(
    Barrio, back_populates="ciudad", cascade="all, delete-orphan"
)

# Paciente <-> Procedimiento (si Paciente no lo declara en su modelo)
# Nota: Procedimiento sí declara `paciente = relationship('Paciente', back_populates='procedimientos')`
# así que acá agregamos el lado inverso en Paciente.
Paciente.procedimientos = relationship(
    Procedimiento,
    order_by=Procedimiento.id,
    back_populates="paciente",
    cascade="all, delete-orphan",
)

# --------------------------------------------------------------------
# __all__ solo con lo que realmente exponemos ahora
# --------------------------------------------------------------------
__all__ = [
    # Base
    "Base",
    # Ítems
    "Item", "ItemTipo", "TipoProducto", "Especialidad",
    # Clínica / Personas
    "Clinica", "Paciente", "Profesional", "ProfesionalEspecialidad", "Usuario",
    # Historia clínica
    "Indicacion", "Procedimiento",
    "AntecedentePatologicoPersonal", "AntecedenteEnfermedadActual", "AntecedenteFamiliar",
    "PacienteEncargado", "RecordatorioPaciente",
    # Geografía
    "Departamento", "Ciudad", "Barrio",
]
