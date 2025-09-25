# services/informe_ventas_service.py
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, List

from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session

from models.venta import Venta
from models.venta_detalle import VentaDetalle
from models.item import Item, ItemTipo


def _monto_linea_expr():
    return (VentaDetalle.cantidad * VentaDetalle.preciounitario) - func.coalesce(VentaDetalle.descuento, 0)

def _vigente_venta_expr():
    # Excluir ANULADO/ANULADA, con trim + upper
    return or_(
        Venta.estadoventa.is_(None),
        func.upper(func.trim(Venta.estadoventa)).notin_(("ANULADO", "ANULADA")),
    )

def get_informe_ventas_por_item(
    db: Session,
    fecha_desde: date,
    fecha_hasta: date,
    iditemtipo: Optional[int] = None,
    iditem: Optional[int] = None,
    item_nombre_like: Optional[str] = None,
    incluir_anuladas: bool = False,
) -> Dict[str, Any]:

    filtros = [Venta.fecha >= fecha_desde, Venta.fecha <= fecha_hasta, _vigente_venta_expr()]
    if not incluir_anuladas:
        filtros.append(or_(Venta.estadoventa.is_(None), Venta.estadoventa != 'ANULADA'))

    # Excluir INSUMO SIEMPRE
    filtros.append(func.upper(func.trim(ItemTipo.nombre)) != "INSUMO")

    if iditemtipo:
        filtros.append(Item.iditemtipo == iditemtipo)
    if iditem:
        filtros.append(VentaDetalle.iditem == iditem)
    if item_nombre_like:
        filtros.append(Item.nombre.ilike(f'%{item_nombre_like.strip()}%'))

    monto_linea = (VentaDetalle.cantidad * VentaDetalle.preciounitario) - func.coalesce(VentaDetalle.descuento, 0)


    q_items = (
        select(
            Item.iditem.label("iditem"),
            Item.nombre.label("item_nombre"),
            ItemTipo.iditemtipo.label("iditemtipo"),
            ItemTipo.nombre.label("tipo_nombre"),
            func.sum(VentaDetalle.cantidad).label("cantidad_total"),
            func.sum(monto_linea).label("monto_total"),
            (func.sum(monto_linea) / func.nullif(func.count(VentaDetalle.idventadet), 0)).label("promedio"),
        )
        .join(Venta, Venta.idventa == VentaDetalle.idventa)
        .join(Item, Item.iditem == VentaDetalle.iditem)
        .join(ItemTipo, ItemTipo.iditemtipo == Item.iditemtipo)
        .where(and_(*filtros))
        .group_by(Item.iditem, Item.nombre, ItemTipo.iditemtipo, ItemTipo.nombre)
        .order_by(ItemTipo.nombre.asc(), Item.nombre.asc())
    )

    rows_items = db.execute(q_items).all()

    def _to_int(x) -> int:
        d = Decimal(x or 0)
        return int(d.quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    items: List[Dict[str, Any]] = []
    total_cant = 0
    total_monto = 0

    for r in rows_items:
        cant_i = _to_int(r.cantidad_total)
        monto_i = _to_int(r.monto_total)
        prom_i  = _to_int(r.promedio)
        items.append(
            dict(
                iditem=r.iditem,
                item_nombre=r.item_nombre,
                iditemtipo=r.iditemtipo,
                tipo_nombre=r.tipo_nombre,
                cantidad_total=cant_i,
                monto_total=monto_i,
                promedio=prom_i,
            )
        )
        total_cant += cant_i
        total_monto += monto_i

    # Resumen por tipo (mismo filtro/exclusión INSUMO)
    q_tipos = (
        select(
            ItemTipo.iditemtipo.label("iditemtipo"),
            ItemTipo.nombre.label("tipo_nombre"),
            func.sum(VentaDetalle.cantidad).label("cantidad_total"),
            func.sum(monto_linea).label("monto_total"),
            (func.sum(monto_linea) / func.nullif(func.count(VentaDetalle.idventadet), 0)).label("promedio"),
        )
        .join(Venta, Venta.idventa == VentaDetalle.idventa)
        .join(Item, Item.iditem == VentaDetalle.iditem)
        .join(ItemTipo, ItemTipo.iditemtipo == Item.iditemtipo)
        .where(and_(*filtros))
        .group_by(ItemTipo.iditemtipo, ItemTipo.nombre)
        .order_by(ItemTipo.nombre.asc())
    )
    rows_tipos = db.execute(q_tipos).all()
    por_tipo = [
        dict(
            iditemtipo=r.iditemtipo,
            tipo_nombre=r.tipo_nombre,
            cantidad_total=_to_int(r.cantidad_total),
            monto_total=_to_int(r.monto_total),
            promedio=_to_int(r.promedio),
        )
        for r in rows_tipos
    ]

    return {
        "items": items,
        "por_tipo": por_tipo,
        "totales": {"cantidad_total": total_cant, "monto_total": total_monto},
    }
