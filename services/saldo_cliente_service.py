from sqlalchemy import text
from typing import Optional, Literal
from datetime import date

Modo = Literal["resumen", "detalle"]

SQL_RESUMEN_VIEW = text("""
SELECT
  idventa, fecha, nro_factura, idpaciente, paciente, total, saldo, detalle_items
FROM public.vw_saldo_cliente_resumen
WHERE fecha BETWEEN :desde AND :hasta
  AND (:idpaciente IS NULL OR idpaciente = :idpaciente)
  AND (:paciente_txt IS NULL OR paciente ILIKE :paciente_txt)
ORDER BY fecha, idventa
""")

SQL_DETALLE_VIEW = text("""
SELECT
  idventa, fecha, nro_factura, idpaciente, paciente,
  item, cantidad, preciounitario, descuento, subtotal_item,
  total_venta, saldo_venta
FROM public.vw_saldo_cliente_detalle
WHERE fecha BETWEEN :desde AND :hasta
  AND (:idpaciente IS NULL OR idpaciente = :idpaciente)
  AND (:paciente_txt IS NULL OR paciente ILIKE :paciente_txt)
ORDER BY fecha, idventa, item
""")

SQL_DETALLE_POR_VENTA_VIEW = text("""
SELECT
  item, cantidad, preciounitario, descuento, subtotal_item
FROM public.vw_saldo_cliente_detalle
WHERE idventa = :idventa
ORDER BY item
""")

def get_saldo_por_cliente(session, desde: date, hasta: date,
                          idpaciente: Optional[int],
                          modo: Modo = "resumen",
                          paciente_txt: Optional[str] = None):
    sql = SQL_RESUMEN_VIEW if modo == "resumen" else SQL_DETALLE_VIEW
    params = {
        "desde": desde, "hasta": hasta,
        "idpaciente": idpaciente,
        "paciente_txt": f"%{paciente_txt}%" if paciente_txt else None
    }
    res = session.execute(sql, params)
    cols = res.keys()
    return [dict(zip(cols, row)) for row in res.fetchall()]

def get_detalle_por_venta(session, idventa: int):
    res = session.execute(SQL_DETALLE_POR_VENTA_VIEW, {"idventa": idventa})
    cols = res.keys()
    return [dict(zip(cols, row)) for row in res.fetchall()]
