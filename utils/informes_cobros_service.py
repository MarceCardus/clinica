# services/informes_cobros_service.py

from sqlalchemy.orm import Session
from sqlalchemy import text
from decimal import Decimal

# Helper para convertir a Decimal de forma segura
def _d(val):
    return Decimal(val) if val is not None else Decimal(0)

def obtener_informe_cobros_detallado(session: Session, desde, hasta):
    """
    Obtiene los datos detallados de ventas y cobros en un período.
    Esta es la consulta principal que alimenta al PDF detallado.
    """
    # Consulta para obtener las ventas del período que tuvieron cobros en el mismo período.
    sql_ventas = text("""
        SELECT DISTINCT
            v.idventa, v.fecha AS fecha_venta, v.nrofactura AS factura, cl.nombrecompleto AS cliente,
            v.montototal AS total_venta, v.saldo
        FROM venta v
        JOIN cliente cl ON v.idcliente = cl.idcliente
        JOIN cobro_detalle cd ON v.idventa = cd.idventa
        JOIN cobro c ON cd.idcobro = c.idcobro
        WHERE c.fecha BETWEEN :desde AND :hasta
          AND (v.estadoventa IS NULL OR UPPER(v.estadoventa) NOT IN ('ANULADO','ANULADA'))
          AND (c.estado IS NULL OR UPPER(c.estado) NOT IN ('ANULADO','ANULADA'))
        ORDER BY v.fecha, v.idventa;
    """)
    
    ventas_result = session.execute(sql_ventas, {"desde": desde, "hasta": hasta}).mappings().all()

    ventas_list = []
    total_cobrado_periodo = Decimal(0)
    sumatorias_forma = {}

    for venta_row in ventas_result:
        venta_dict = dict(venta_row)
        venta_id = venta_dict['idventa']

        # Por cada venta, buscamos sus items
        sql_items = text("""
            SELECT i.codigo, i.nombre AS descripcion, vd.cantidad, vd.preciounitario AS precio, vd.subtotal
            FROM venta_detalle vd
            JOIN item i ON vd.iditem = i.iditem
            WHERE vd.idventa = :venta_id;
        """)
        items_result = session.execute(sql_items, {"venta_id": venta_id}).mappings().all()
        venta_dict['items'] = [dict(r) for r in items_result]

        # Y también buscamos sus pagos DENTRO del período solicitado
        sql_pagos = text("""
            SELECT c.fecha, c.monto, c.formapago AS forma
            FROM cobro c
            JOIN cobro_detalle cd ON c.idcobro = cd.idcobro
            WHERE cd.idventa = :venta_id AND c.fecha BETWEEN :desde AND :hasta
              AND (c.estado IS NULL OR UPPER(c.estado) NOT IN ('ANULADO','ANULADA'));
        """)
        pagos_result = session.execute(sql_pagos, {"venta_id": venta_id, "desde": desde, "hasta": hasta}).mappings().all()
        pagos_list = []
        for pago in pagos_result:
            pagos_list.append(dict(pago))
            monto_pago = _d(pago['monto'])
            forma_pago = pago['forma'] or "Otro"
            total_cobrado_periodo += monto_pago
            sumatorias_forma[forma_pago] = sumatorias_forma.get(forma_pago, Decimal(0)) + monto_pago
        
        venta_dict['pagos'] = pagos_list
        ventas_list.append(venta_dict)

    return {
        "ventas": ventas_list,
        "total_cobrado": str(total_cobrado_periodo),
        "sumatorias_forma": {k: str(v) for k, v in sumatorias_forma.items()},
        "cant_ventas": len(ventas_list)
        # Puedes añadir más totales si los necesitas
    }