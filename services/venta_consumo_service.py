# services/venta_consumo_service.py
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models.venta import Venta
from models.venta_detalle import VentaDetalle
from models.StockMovimiento import StockMovimiento


def _D(x) -> Decimal:
    try:
        return Decimal(str(x or 0))
    except Exception:
        return Decimal("0")


def confirmar_venta_generar_consumo(session, idventa: int):
    """
    Genera SOLO el egreso del ítem vendido cuando 'genera_stock' es True.
    NO descuenta componentes (sin composición / sin procedimiento_item).
    """
    venta = session.execute(
        select(Venta)
        .options(selectinload(Venta.detalles).selectinload(VentaDetalle.item))
        .where(Venta.idventa == int(idventa))
    ).scalar_one_or_none()
    if not venta:
        raise ValueError(f"Venta {idventa} no existe")

    for vd in (venta.detalles or []):
        item = vd.item
        if not item:
            continue

        # Solo productos/ítems que mueven stock
        if not getattr(item, "genera_stock", True):
            continue

        # Evitar duplicados (si ya se generó para este detalle)
        ya_existe = (
            session.query(StockMovimiento.idmovimiento)
            .filter(
                StockMovimiento.idorigen == int(vd.idventadet),
                StockMovimiento.motivo == "VENTA",
                StockMovimiento.tipo == "EGRESO",
            )
            .first()
            is not None
        )
        if ya_existe:
            continue

        cant = _D(vd.cantidad)
        if cant <= 0:
            continue

        ref = f"VD-{vd.idventadet}"  # solo para rastreo humano en 'observacion'
        session.add(
            StockMovimiento(
                fecha=venta.fecha,
                tipo="EGRESO",
                iditem=item.iditem,
                cantidad=cant,
                motivo="VENTA",
                idorigen=int(vd.idventadet),
                observacion=ref,
            )
        )
    # sin commit: lo hace el caller (tu with self._txn_ctx())


def anular_venta_revertir_consumo(session, idventa: int):
    """
    Reversa lo que generamos arriba: por cada EGRESO creado, crea un INGRESO espejo.
    """
    venta = session.get(Venta, int(idventa))
    assert venta is not None

    for vd in (venta.detalles or []):
        ref = f"VD-{vd.idventadet}"

        egresos = (
            session.query(StockMovimiento)
            .filter(
                StockMovimiento.idorigen == int(vd.idventadet),
                StockMovimiento.motivo == "VENTA",
                StockMovimiento.tipo == "EGRESO",
            )
            .all()
        )
        for eg in egresos:
            session.add(
                StockMovimiento(
                    fecha=getattr(venta, "fecha_anulacion", venta.fecha),
                    tipo="INGRESO",
                    iditem=eg.iditem,
                    cantidad=eg.cantidad,
                    motivo="ANULACION_VENTA",
                    idorigen=int(vd.idventadet),
                    observacion=f"ANU-{ref}",
                )
            )
    # sin commit
