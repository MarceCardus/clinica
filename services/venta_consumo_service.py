# services/venta_consumo_service.py
from decimal import Decimal
from sqlalchemy import select, func
from models import (
    item, item_composicion, venta, venta_detalle,
    StockMovimiento, procedimiento, procedimiento_item  # asumiendo nombres
)

def _buscar_o_crear_procedimiento(session, venta, vd):
    # 1 procedimiento POR DETALLE facilita anulación
    if vd.idprocedimiento:
        return session.get(procedimiento, vd.idprocedimiento)

    proc = procedimiento(
        idpaciente = venta.idpaciente,
        fecha      = venta.fecha,          # o datetime.now() si preferís
        observacion= f"Generado por venta #{venta.idventa} / det #{vd.idventadetalle}: {vd.item.nombre}"
        # idterapeuta si corresponde, etc.
    )
    session.add(proc)
    session.flush()  # obtener id
    vd.idprocedimiento = proc.id  # guardar enlace
    return proc

def anular_venta_revertir_consumo(session, idventa:int):
    venta = session.get(venta, idventa)
    assert venta is not None

    for vd in venta.detalles:
        ref = f"VD-{vd.idventadetalle}"

        # Reponer stock espejo de cada EGRESO original
        sms = (session.query(StockMovimiento)
               .filter(StockMovimiento.referencia == ref,
                       StockMovimiento.tipo == "EGRESO")
               .all())
        for eg in sms:
            session.add(StockMovimiento(
                fecha      = venta.fecha_anulacion or venta.fecha,
                tipo       = "INGRESO",
                iditem     = eg.iditem,
                cantidad   = eg.cantidad,
                motivo     = "ANULACION_VENTA",
                referencia = f"ANU-{vd.idventadetalle}",
                idventa_detalle = vd.idventadetalle,
                idusuario  = getattr(venta, "idusuario_anula", venta.idusuario)
            ))

        # Limpiar carga al procedimiento hecha por este detalle
        session.query(procedimiento_item).filter(
            procedimiento_item.idventa_detalle == vd.idventadetalle,
            procedimiento_item.origen == "VENTA"
        ).delete(synchronize_session=False)

        # Si el procedimiento quedó vacío y lo creamos por esta venta, eliminarlo
        if vd.idprocedimiento:
            restantes = session.query(procedimiento_item).filter(
                procedimiento_item.idprocedimiento == vd.idprocedimiento
            ).count()
            if restantes == 0:
                proc = session.get(procedimiento, vd.idprocedimiento)
                if proc:
                    session.delete(proc)
            vd.idprocedimiento = None

def confirmar_venta_generar_consumo(session, idventa:int):
    venta = session.get(venta, idventa)
    assert venta is not None

    for vd in venta.detalles:  # recorre VentaDetalle
        item_padre = vd.item
        ref = f"VD-{vd.idventadetalle}"

        # Evitar doble generación (si ya existen SM con esta ref, saltar)
        ya_existen = session.query(StockMovimiento).filter(StockMovimiento.referencia == ref).first()
        if ya_existen:
            continue

        # buscar composición
        comps = (session.query(item_composicion)
                 .filter(item_composicion.iditem_padre == item_padre.iditem)
                 .all())

        if comps:
            # 1) crear/reusar procedimiento
            proc = _buscar_o_crear_procedimiento(session, venta, vd)

            # 2) por cada componente, EGRESO y cargar al procedimiento_item
            for c in comps:
                cant = Decimal(vd.cantidad) * Decimal(c.cantidad)

                # Stock: EGRESO
                sm = StockMovimiento(
                    fecha      = venta.fecha,
                    tipo       = "EGRESO",
                    iditem     = c.iditem_insumo,
                    cantidad   = cant,
                    motivo     = "VENTA",
                    referencia = ref,
                    idventa_detalle = vd.idventadetalle,
                    idusuario  = venta.idusuario  # si lo tenés
                )
                session.add(sm)

                # Procedimiento: detalle usado
                pi = procedimiento_item(
                    idprocedimiento = proc.id,
                    iditem          = c.iditem_insumo,
                    cantidad        = cant,
                    idventa_detalle = vd.idventadetalle,
                    origen          = "VENTA"
                )
                session.add(pi)

        else:
            # Sin composición → si genera stock, egreso del propio item
            if getattr(item_padre, "genera_stock", True):
                sm = StockMovimiento(
                    fecha      = venta.fecha,
                    tipo       = "EGRESO",
                    iditem     = item_padre.iditem,
                    cantidad   = Decimal(vd.cantidad),
                    motivo     = "VENTA",
                    referencia = ref,
                    idventa_detalle = vd.idventadetalle,
                    idusuario  = venta.idusuario
                )
                session.add(sm)

    session.commit()
