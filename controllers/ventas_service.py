# services/ventas_service.py
from datetime import date, timedelta,datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.venta import Venta
from models.venta_detalle import VentaDetalle
from models.item import Item
from models.paquete import Paquete
from models.paquete_producto import PaqueteProducto  # si prorrateás paquetes
from models.StockMovimiento import StockMovimiento
from models.plan_sesiones import PlanSesiones, PlanSesion, PlanEstado, SesionEstado
from models.plan_tipo import PlanTipo
MERGE_DETALLES_REPETIDOS = True

#helper para calcular sesiones según item y cantidad
def _total_sesiones_para_item(item, cantidad:int|Decimal) -> int:
    base = int(item.sesiones_incluidas or (item.plan_tipo.sesiones_por_defecto if item.plan_tipo else 1) or 1)
    return max(1, base * int(cantidad or 1))


# ----------------- utilidades -----------------
def _money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _get_item(session: Session, iditem: int) -> Item:
    return session.execute(select(Item).where(Item.iditem == int(iditem))).scalar_one()

item_cache = {}
def _get_item_cached(session: Session, iditem: int) -> Item:
    """Obtiene el item desde caché si ya fue consultado, para evitar múltiples SELECT iguales."""
    if iditem not in item_cache:
        item_cache[iditem] = _get_item(session, iditem)
    return item_cache[iditem]

def _precio_item(session: Session, iditem: int) -> Decimal:
    it = _get_item(session, iditem)
    return _money(getattr(it, "precio_venta", 0) or 0)

def _tipo_item(session: Session, iditem: int) -> str:
    it = _get_item_cached(session, iditem)
    t = getattr(it, "tipo", None)
    if isinstance(t, str):
        return (t or "").strip().lower()
    return (getattr(t, "nombre", "") or "").strip().lower()

def _genera_stock(session: Session, iditem: int) -> bool:
    it = _get_item_cached(session, iditem)
    return bool(getattr(it, "genera_stock", True))

def _agregar_detalle_item(session, *, idventa, iditem, cantidad, preciounitario, descuento=Decimal("0")) -> VentaDetalle:
    cantidad = _money(cantidad)
    preciounitario = _money(preciounitario)
    descuento = _money(descuento)

    if MERGE_DETALLES_REPETIDOS:
        rowid = session.execute(
            select(VentaDetalle.idventadet).where(
                VentaDetalle.idventa == idventa,
                VentaDetalle.iditem == iditem,
                VentaDetalle.preciounitario == preciounitario,
                VentaDetalle.descuento == descuento,
            )
        ).scalar_one_or_none()
        if rowid is not None:
            existente = session.get(VentaDetalle, rowid)
            existente.cantidad = _money(Decimal(existente.cantidad) + cantidad)
            session.add(existente)
            return existente

    det = VentaDetalle(
        idventa=idventa,
        iditem=iditem,
        cantidad=cantidad,
        preciounitario=preciounitario,
        descuento=descuento,
    )
    session.add(det)
    return det

def _crear_planes_por_venta(session, venta):
    from sqlalchemy import select
    from models.venta_detalle import VentaDetalle
    from models.item import Item
    planes = []
    rows = session.execute(
        select(VentaDetalle, Item)
        .join(Item, Item.iditem == VentaDetalle.iditem)
        .where(VentaDetalle.idventa == venta.idventa, Item.idplantipo.isnot(None))
    ).all()

    for det, it in rows:
        total = _total_sesiones_para_item(it, det.cantidad)
        plan = PlanSesiones(
            idpaciente=venta.idpaciente,
            idventadet=det.idventadet,                 # ← tu PK en venta_detalle
            iditem_procedimiento=it.iditem,            # ← ítem que origina el plan
            idplantipo=it.idplantipo,
            total_sesiones=total,
            sesiones_completadas=0,
            estado=PlanEstado.ACTIVO,
            fecha_inicio=venta.fecha,
            notas=None,
        )
        session.add(plan); session.flush()

        for i in range(1, total + 1):
            session.add(PlanSesion(
                idplan=plan.idplan,
                nro=i,
                estado=SesionEstado.PROGRAMADA
            ))
        planes.append(plan)
    return planes


# ----------------- API principal -----------------
def registrar_venta(
    session: Session,
    *,
    fecha: date | None = None,
    idpaciente: int | None = None,
    idprofesional: int | None = None,
    idclinica: int | None = None,
    estadoventa: str = "Cerrada",
    observaciones: str | None = None,
    items: list | None = None,
    nro_factura: Optional[str] = None,
    prorratear_paquetes: bool = False,
) -> Venta:
    # 🧹 Limpieza del caché de ítems (evita reusar datos de otras ventas)
    global item_cache
    item_cache.clear()

    if not items:
        raise ValueError("La venta debe tener al menos un ítem.")

    # 📦 Crear encabezado de venta
    v = Venta(
        fecha=fecha or date.today(),
        idpaciente=idpaciente,
        idprofesional=idprofesional,
        idclinica=idclinica,
        montototal=_money(0),
        estadoventa=estadoventa,
        observaciones=observaciones,
        nro_factura=(nro_factura or "").strip(),
    )
    session.add(v)
    session.flush()

    total = Decimal("0.00")

    for it in items:
        iditem = int(it.get("iditem") or it.get("idproducto") or 0)
        if not iditem:
            raise ValueError("Falta iditem en un ítem del detalle.")

        tipo = (it.get("tipo") or "").strip().lower() or _tipo_item(session, iditem)
        cant = _money(it.get("cantidad", 1))
        precio = _money(it.get("precio", _precio_item(session, iditem)))
        desc = _money(it.get("descuento", 0))

        linea = (precio * cant) - desc
        total += linea

        _agregar_detalle_item(
            session,
            idventa=v.idventa,
            iditem=iditem,
            cantidad=cant,
            preciounitario=precio,
            descuento=desc,
        )

        # 🔍 Registrar movimiento solo si genera_stock = True
        if tipo in ("producto", "ambos") and _genera_stock(session, iditem):
            mov = StockMovimiento(
                fecha=fecha or datetime.now(),
                iditem=iditem,
                cantidad=-cant,
                tipo="EGRESO",
                motivo="Venta",
                idorigen=v.idventa,
                observacion=f"Venta N° {v.idventa}",
            )
            session.add(mov)

    v.montototal = _money(total)
    v.saldo = _money(total)
    _crear_planes_por_venta(session, v)
    session.commit()
    return v


def anular_venta(session, idventa):
    venta = session.get(Venta, idventa)
    if not venta:
        raise Exception("Venta no encontrada")

    venta.estadoventa = "Anulada"

    for det in venta.detalles:
        tipo = _tipo_item(session, det.iditem)
        if tipo in ("producto", "ambos") and _genera_stock(session, det.iditem):
            mov = StockMovimiento(
                fecha=datetime.now(),
                iditem=det.iditem,
                cantidad=det.cantidad,  # ingreso nuevamente
                tipo="INGRESO",
                motivo="Anulación de venta",
                idorigen=venta.idventa,
                observacion=f"Anulación Venta N° {venta.idventa}"
            )
            session.add(mov)

    session.commit()