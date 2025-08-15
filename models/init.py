# models/__init__.py
from .base import Base

# Importa TODOS los modelos primero
from .clinica import Clinica
from .paciente import Paciente
from .procedimiento import Procedimiento
from .profesional import Profesional
from .especialidad import Especialidad
from .profesional_especialidad import ProfesionalEspecialidad
from .usuario import Usuario
from .producto import Producto
from .paquete import Paquete
from .paquete_producto import PaqueteProducto
from .proveedor import Proveedor
from .insumo import Insumo
from .compra import Compra
from .compra_detalle import CompraDetalle
from .venta import Venta
from .venta_detalle import VentaDetalle
from .cobro import Cobro
from .cobro_venta import CobroVenta
from .venta_cuota import VentaCuota
from .sesion import Sesion
from .fotoavance import FotoAvance
from .receta import Receta
from .comisionprofesional import ComisionProfesional
from .cajamovimiento import CajaMovimiento
from .auditoria import Auditoria
from .antecPatologico import AntecedentePatologicoPersonal
from .antecEnfActual import AntecedenteEnfermedadActual
from .antecFliar import AntecedenteFamiliar

# Importa también los que faltaban:
from .pacienteEncargado import PacienteEncargado
from .indicacion import Indicacion
from .recordatorio_paciente import RecordatorioPaciente
from .departamento import Departamento
from .ciudad import Ciudad
from .barrio import Barrio

# Ahora sí, definí relaciones DIFERIDAS con CLASES (no strings)
from sqlalchemy.orm import relationship

# Ciudad <-> Departamento
Ciudad.departamento = relationship(Departamento, back_populates="ciudades")
Departamento.ciudades = relationship(Ciudad, back_populates="departamento",
                                     cascade="all, delete-orphan")

# Barrio <-> Ciudad
Barrio.ciudad = relationship(Ciudad, back_populates="barrios")
Ciudad.barrios = relationship(Barrio, back_populates="ciudad",
                              cascade="all, delete-orphan")

# (tu ejemplo existente)
Paciente.procedimientos = relationship(
    "Procedimiento",
    order_by=Procedimiento.id,
    back_populates="paciente",
    cascade="all, delete-orphan"
)

__all__ = [
    "Base","Clinica","Paciente","Procedimiento","Profesional","Especialidad",
    "ProfesionalEspecialidad","Usuario","Producto","Paquete","PaqueteProducto",
    "Proveedor","Insumo","Compra","CompraDetalle","Venta","VentaDetalle","Cobro",
    "CobroVenta","VentaCuota","Sesion","FotoAvance","Receta","ComisionProfesional",
    "CajaMovimiento","Auditoria","AntecedentePatologicoPersonal",
    "AntecedenteEnfermedadActual","AntecedenteFamiliar",
    "PacienteEncargado","Indicacion","RecordatorioPaciente",
    "Departamento","Ciudad","Barrio",
]
