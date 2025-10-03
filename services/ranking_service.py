# services/ranking_service.py
from sqlalchemy import func, literal, case, or_
from sqlalchemy.orm import Session, aliased
from datetime import date

from models.paciente import Paciente
from models.venta import Venta
from models.venta_detalle import VentaDetalle
from models.item import Item

# Estados válidos (en minúsculas para comparar en lower())
ESTADOS_VALIDOS = ("confirmada", "cerrada", "facturada", "pagada")


def _filtro_estado(ignorar_estado: bool):
    """
    Devuelve una expresión SQLAlchemy para filtrar por estado válido o ninguna si se ignora.
    - Acepta NULL como válido (ventas viejas que no tengan estado).
    - Comparación case-insensitive con LOWER(estadoventa).
    """
    if ignorar_estado:
        return literal(True)
    return or_(Venta.estadoventa.is_(None), func.lower(Venta.estadoventa).in_(ESTADOS_VALIDOS))


def top_pacientes_por_monto(
    session: Session,
    desde: date | None,
    hasta: date | None,
    limit: int = 10,
    ignorar_estado: bool = False,
):
    """
    Ranking de pacientes por monto total vendido.
    """
    nombre_completo = func.concat_ws(' ', Paciente.nombre, Paciente.apellido)

    q = (
        session.query(
            Paciente.idpaciente,
            nombre_completo.label("paciente"),
            func.sum(Venta.montototal).label("monto_total"),
            func.count(Venta.idventa).label("ventas")
        )
        .join(Venta, Venta.idpaciente == Paciente.idpaciente)
        .filter(Paciente.estado.is_(True))
        .filter(_filtro_estado(ignorar_estado))
    )
    if desde:
        q = q.filter(Venta.fecha >= desde)
    if hasta:
        q = q.filter(Venta.fecha <= hasta)

    q = q.group_by(Paciente.idpaciente, Paciente.nombre, Paciente.apellido)
    q = q.order_by(func.sum(Venta.montototal).desc())
    return q.limit(limit).all()


def top_items_por_cantidad(
    session: Session,
    desde: date | None,
    hasta: date | None,
    limit: int = 10,
    ignorar_estado: bool = False,
    incluir_inactivos: bool = False,
):
    """
    Ranking de items más vendidos por cantidad.
    """
    total_linea = VentaDetalle.cantidad * (VentaDetalle.preciounitario - func.coalesce(VentaDetalle.descuento, 0))

    q = (
        session.query(
            Item.iditem,
            Item.nombre.label("item"),
            func.sum(VentaDetalle.cantidad).label("cant_total"),
            func.sum(total_linea).label("monto_estimado")
        )
        .join(VentaDetalle, VentaDetalle.iditem == Item.iditem)
        .join(Venta, Venta.idventa == VentaDetalle.idventa)
        .filter(_filtro_estado(ignorar_estado))
    )
    if not incluir_inactivos:
        q = q.filter(Item.activo.is_(True))
    if desde:
        q = q.filter(Venta.fecha >= desde)
    if hasta:
        q = q.filter(Venta.fecha <= hasta)

    q = q.group_by(Item.iditem, Item.nombre)
    q = q.order_by(func.sum(VentaDetalle.cantidad).desc())
    return q.limit(limit).all()


def bottom_items_por_cantidad(
    session: Session,
    desde: date | None,
    hasta: date | None,
    limit: int = 10,
    incluir_cero: bool = True,
    ignorar_estado: bool = False,
    incluir_inactivos: bool = False,
):
    """
    Ranking de items menos vendidos (incluye 0 si incluir_cero=True).
    LEFT JOIN con filtros de fecha/estado en el ON para no volver INNER.
    """
    V = aliased(Venta)
    VD = aliased(VentaDetalle)

    on_clause = (VD.iditem == Item.iditem) & (VD.idventa == V.idventa)
    if desde:
        on_clause &= (V.fecha >= desde)
    if hasta:
        on_clause &= (V.fecha <= hasta)
    # Estado en el ON
    if not ignorar_estado:
        on_clause &= or_(V.estadoventa.is_(None), func.lower(V.estadoventa).in_(ESTADOS_VALIDOS))

    q = (
        session.query(
            Item.iditem,
            Item.nombre.label("item"),
            func.coalesce(func.sum(VD.cantidad), 0).label("cant_total")
        )
        .outerjoin(VD, on_clause)
        .outerjoin(V, VD.idventa == V.idventa)
    )
    if not incluir_inactivos:
        q = q.filter(Item.activo.is_(True))

    q = q.group_by(Item.iditem, Item.nombre).order_by(func.coalesce(func.sum(VD.cantidad), 0).asc(), Item.nombre.asc())
    if not incluir_cero:
        q = q.having(func.coalesce(func.sum(VD.cantidad), 0) > 0)

    return q.limit(limit).all()
