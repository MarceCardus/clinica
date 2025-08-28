# services/informes_cobros_service.py
from decimal import Decimal
from sqlalchemy import or_
from models.cobro import Cobro
from models.venta import Venta
from models.cobro_venta import CobroVenta
from models.paciente import Paciente

def obtener_informe_cobros(session, fecha_desde, fecha_hasta):
    def to_dec(v):
        try:
            return Decimal(str(v))
        except Exception:
            return Decimal(0)

    def fmt_miles(v):
        try:
            n = int(Decimal(str(v)).quantize(Decimal("1")))
        except Exception:
            n = 0
        return f"{n:,}".replace(",", ".")

    # ------- COBROS ACTIVOS EN EL PERÍODO -------
    cobros = (session.query(Cobro)
              .filter(Cobro.fecha >= fecha_desde,
                      Cobro.fecha <= fecha_hasta,
                      Cobro.estado == "ACTIVO")
              .all())

    filas_cobros = []
    # acumulamos NUMÉRICO para evitar errores de redondeo
    sumatorias_forma_num = {}

    for cobro in cobros:
        fecha_cobro = cobro.fecha.strftime("%d/%m/%Y") if cobro.fecha else ""
        for imputacion in cobro.imputaciones:
            venta = imputacion.venta
            paciente = getattr(venta, "paciente", None)
            if paciente:
                cliente = f"{(paciente.nombre or '').strip()} {(paciente.apellido or '').strip()}".strip()
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

            # Totales por forma de pago (numérico)
            forma = cobro.formapago or "-"
            sumatorias_forma_num[forma] = sumatorias_forma_num.get(forma, Decimal(0)) + to_dec(imputacion.montoimputado)

    # ------- VENTAS SIN NINGÚN COBRO (por fecha de FACTURA) -------
    ventas_sin_cobro = (
        session.query(Venta)
        .outerjoin(CobroVenta, CobroVenta.idventa == Venta.idventa)
        .filter(
            Venta.fecha >= fecha_desde,
            Venta.fecha <= fecha_hasta,
            or_(Venta.estadoventa.is_(None), Venta.estadoventa != "Anulada"),
            CobroVenta.idcobro.is_(None)   # nunca tuvieron cobros
        )
        .all()
    )

    for venta in ventas_sin_cobro:
        paciente = getattr(venta, "paciente", None)
        if paciente:
            cliente = f"{(paciente.nombre or '').strip()} {(paciente.apellido or '').strip()}".strip()
        else:
            cliente = str(getattr(venta, "idpaciente", ""))

        fecha_factura = venta.fecha.strftime("%d/%m/%Y") if venta.fecha else ""
        filas_cobros.append({
            "factura": venta.nro_factura,
            "cliente": cliente,
            "fecha_factura": fecha_factura,
            "fecha_cobro": "",                         # sin cobro
            "total_factura": fmt_miles(venta.montototal),
            "pagado": fmt_miles(0),
            "saldo": fmt_miles(venta.saldo or venta.montototal),
            "forma": "-"                                # sin forma de pago
        })

    # ------- ANULACIONES -------
    ventas_anuladas = (
        session.query(Venta)
        .filter(Venta.estadoventa == "Anulada",
                Venta.fecha >= fecha_desde,
                Venta.fecha <= fecha_hasta)
        .all()
    )

    # Cobros anulados con NOMBRE del Paciente (join)
    cobros_anulados_rows = (
        session.query(
            Cobro.idcobro, Cobro.fecha, Cobro.monto, Cobro.observaciones,
            Cobro.idpaciente, Paciente.nombre, Paciente.apellido
        )
        .outerjoin(Paciente, Paciente.idpaciente == Cobro.idpaciente)
        .filter(Cobro.estado == "ANULADO",
                Cobro.fecha >= fecha_desde,
                Cobro.fecha <= fecha_hasta)
        .order_by(Cobro.fecha)
        .all()
    )

    anulaciones_ventas = [{
        "idventa": v.idventa,
        "factura": v.nro_factura,
        "cliente": f"{(getattr(v.paciente, 'nombre', '') or '').strip()} {(getattr(v.paciente, 'apellido', '') or '').strip()}".strip()
                   if getattr(v, 'paciente', None) else str(getattr(v, 'idpaciente', '')),
        "monto": fmt_miles(v.montototal),
        "motivo": v.observaciones or ""
    } for v in ventas_anuladas]

    anulaciones_cobros = []
    for r in cobros_anulados_rows:
        cliente = f"{(r.nombre or '').strip()} {(r.apellido or '').strip()}".strip()
        if not cliente:
            cliente = str(r.idpaciente or "")
        anulaciones_cobros.append({
            "idcobro": r.idcobro,
            "fecha": r.fecha.strftime("%d/%m/%Y") if r.fecha else "",
            "cliente": cliente,
            "monto": fmt_miles(r.monto),
            "motivo": r.observaciones or ""
        })

    # ------- FOOTER: sumatorias por forma + TOTAL INGRESO -------
    formas_posibles = ["Efectivo", "Transferencia", "Cheque", "T. Crédito", "T. Débito"]
    sumatorias_forma_fmt = {f: fmt_miles(sumatorias_forma_num.get(f, Decimal(0))) for f in formas_posibles}
    total_ingreso_num = sum(sumatorias_forma_num.get(f, Decimal(0)) for f in sumatorias_forma_num.keys())
    total_ingreso = fmt_miles(total_ingreso_num)

    return {
        "filas_cobros": filas_cobros,
        "anulaciones_ventas": anulaciones_ventas,
        "anulaciones_cobros": anulaciones_cobros,
        "sumatorias_forma": sumatorias_forma_fmt,
        "total_ingreso": total_ingreso,          # para footer/UI/PDF
        "total_ingreso_num": int(total_ingreso_num),  # por si necesitás operar
    }
