# dao/historial.py
from sqlalchemy import text, func
from sqlalchemy.orm import Session

def get_historial_paciente(session: Session, idpaciente: int,
                           fecha_desde=None, fecha_hasta=None,
                           incluir_anuladas=True):
    """
    Devuelve filas cronológicas con:
    fecha, tipo_evento, item_nombre, cantidad, precio_unitario, subtotal, saldo, observacion.
    (Nota: ahora expone 'saldo' en vez de 'estado')
    """
    where_filtros = ["h.idpaciente = :idpaciente"]
    params = {"idpaciente": idpaciente}

    if fecha_desde:
        where_filtros.append("h.fecha >= :desde"); params["desde"] = fecha_desde
    if fecha_hasta:
        where_filtros.append("h.fecha <= :hasta"); params["hasta"] = fecha_hasta
    if not incluir_anuladas:
        # si tu vista distingue anuladas por estado, mantenemos el filtro
        where_filtros.append("(h.estado IS NULL OR UPPER(h.estado) <> 'ANULADO')")

    # Intento 1: la vista ya tiene columna SALDO
    sql_saldo = text(f"""
        SELECT h.fecha, h.tipo_evento, h.item_nombre, h.cantidad,
               h.precio_unitario, h.subtotal, h.saldo, h.observacion
        FROM vw_historial_paciente h
        WHERE {" AND ".join(where_filtros)}
        ORDER BY h.fecha ASC, h.tipo_evento ASC
    """)
    try:
        rows = session.execute(sql_saldo, params).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        # Intento 2 (retrocompat): vista sin 'saldo' -> devolvemos saldo=0
        sql_legacy = text(f"""
            SELECT h.fecha, h.tipo_evento, h.item_nombre, h.cantidad,
                   h.precio_unitario, h.subtotal, h.saldo, h.observacion
            FROM vw_historial_paciente h
            WHERE {" AND ".join(where_filtros)}
            ORDER BY h.fecha ASC, h.tipo_evento ASC
        """)
        rows = session.execute(sql_legacy, params).mappings().all()
        data = []
        for r in rows:
            d = dict(r)
            # mapeo: si no existe 'saldo', lo seteamos en 0 (hasta que actualices la vista)
            d["saldo"] = 0
            # limpiamos 'estado' para no confundir al caller
            d.pop("estado", None)
            data.append(d)
        return data


def get_resumen_financiero_paciente(session: Session, idpaciente: int):
    """
    Totales de ventas, cobros y saldo desde Venta (montototal y saldo).
    """
    from models.venta import Venta

    total_ventas = session.query(func.coalesce(func.sum(Venta.montototal), 0))\
                          .filter(Venta.idpaciente == idpaciente).scalar()
    total_saldo  = session.query(func.coalesce(func.sum(Venta.saldo), 0))\
                          .filter(Venta.idpaciente == idpaciente).scalar()
    total_cobrado = (total_ventas or 0) - (total_saldo or 0)
    return {
        "total_ventas": float(total_ventas or 0),
        "total_cobrado": float(total_cobrado or 0),
        "saldo_pendiente": float(total_saldo or 0),
    }
