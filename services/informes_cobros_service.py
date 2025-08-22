# services/informes_cobros_service.py
from PyQt5.QtCore import Qt
from models.cobro import Cobro
from models.venta import Venta

def obtener_informe_cobros(session, fecha_desde, fecha_hasta):
    cobros = session.query(Cobro).filter(
        Cobro.fecha >= fecha_desde,
        Cobro.fecha <= fecha_hasta,
        Cobro.estado == "ACTIVO"
    ).all()

    filas_cobros = []
    sumatorias_forma = {}

    def fmt_miles(x):
        return f"{int(round(x)):,}".replace(",", ".")

    for cobro in cobros:
        fecha_cobro = cobro.fecha.strftime("%d/%m/%Y") if cobro.fecha else ""
        for imputacion in cobro.imputaciones:
            venta = imputacion.venta
            paciente = getattr(venta, "paciente", None)
            if paciente:
                cliente = f"{getattr(paciente, 'nombre', '')} {getattr(paciente, 'apellido', '')}".strip()
            else:
                cliente = str(getattr(venta, "idpaciente", ""))
            fecha_factura = venta.fecha.strftime("%d/%m/%Y") if venta.fecha else ""
            filas_cobros.append({
                "factura": venta.nro_factura,
                "cliente": cliente,
                "fecha_factura": fecha_factura,
                "fecha_cobro": fecha_cobro,
                "total_factura": fmt_miles(venta.montototal),
                "pagado": fmt_miles(imputacion.montoimputado),
                "saldo": fmt_miles(venta.saldo),
                "forma": cobro.formapago or "-"
            })
            # Sumar por forma de pago
            forma = cobro.formapago or "-"
            sumatorias_forma[forma] = sumatorias_forma.get(forma, 0) + float(imputacion.montoimputado)

    # Anulaciones
    ventas_anuladas = session.query(Venta).filter(
        Venta.estadoventa == "Anulada",
        Venta.fecha >= fecha_desde,
        Venta.fecha <= fecha_hasta
    ).all()
    cobros_anulados = session.query(Cobro).filter(
        Cobro.estado == "ANULADO",
        Cobro.fecha >= fecha_desde,
        Cobro.fecha <= fecha_hasta
    ).all()


    anulaciones_ventas = [
        {
            "idventa": v.idventa,
            "factura": v.nro_factura,
            "cliente": f"{getattr(v.paciente, 'nombre', '')} {getattr(v.paciente, 'apellido', '')}".strip() if getattr(v, 'paciente', None) else str(getattr(v, 'idpaciente', '')),
            "monto": fmt_miles(v.montototal),
            "motivo": v.observaciones or ""
        }
        for v in ventas_anuladas
    ]
    anulaciones_cobros = [
        {
            "idcobro": c.idcobro,
            "fecha": c.fecha.strftime("%d/%m/%Y") if c.fecha else "",
            "cliente": f"{getattr(c.paciente, 'nombre', '')} {getattr(c.paciente, 'apellido', '')}".strip() if getattr(c, 'paciente', None) else str(getattr(c, 'idpaciente', '')),
            "monto": fmt_miles(c.monto),
            "motivo": c.observaciones or ""
        }
        for c in cobros_anulados
    ]

    # Formatear sumatorias (todas las formas posibles)
    formas_posibles = ["Efectivo", "Transferencia", "Cheque", "T. Crédito", "T. Débito"]
    sumatorias_forma_fmt = {k: fmt_miles(sumatorias_forma.get(k, 0)) for k in formas_posibles}

    return {
        "filas_cobros": filas_cobros,
        "anulaciones_ventas": anulaciones_ventas,
        "anulaciones_cobros": anulaciones_cobros,
        "sumatorias_forma": sumatorias_forma_fmt
    }