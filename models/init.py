from sqlalchemy.orm import relationship
from .base import Base
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
from .barrio import Barrio
from .ciudad import Ciudad
Paciente.procedimientos = relationship(
    "Procedimiento",                 # Usa el string, ¡no la clase!
    order_by=Procedimiento.id,       # ¡Acá sí podés usar Procedimiento, porque ya está importada!
    back_populates="paciente",
    cascade="all, delete-orphan"
) 
__all__ = [
    "Base",
    "Clinica",
    "Paciente",
    "Procedimiento",
    "Profesional",
    "Especialidad",
    "ProfesionalEspecialidad",
    "Usuario",
    "Producto",
    "Paquete",
    "PaqueteProducto",
    "Proveedor",
    "Insumo",
    "Compra",
    "CompraDetalle",
    "Venta",
    "VentaDetalle",
    "Cobro",
    "CobroVenta",
    "VentaCuota",
    "Sesion",
    "FotoAvance",
    "Receta",
    "ComisionProfesional",
    "CajaMovimiento",
    "Auditoria",
    "AntecedentePatologicoPersonal",
    "AntecedenteEnfermedadActual",
    "AntecedenteFamiliar",
]
