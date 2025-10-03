# services/inf_cobros_pac_service.py
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select, func, asc
from sqlalchemy.orm import Session

from models.venta import Venta
from models.cobro import Cobro
from models.paciente import Paciente
from models.cobro_venta import CobroVenta  # ajustá el import si tu módulo se llama distinto

DEC0 = Decimal("0")


def _to_date(d):
    if isinstance(d, datetime):
        return d.date()
    return d


def get_cobros_por_paciente(session: Session, idpaciente: int, fecha_desde: date, fecha_hasta: date):
    """
    Devuelve bloques por Venta con:
      - venta: {idventa, fecha, montototal, nro_factura, paciente}
      - saldo_inicial_rango: Decimal (para cálculo interno)
      - eventos: lista de cobros en el rango, con saldo corrido
      - saldo_final_rango: Decimal
    Reglas:
      - Solo cobros ACTIVO
      - saldo_inicial_rango = montototal - imputado antes de fecha_desde
      - Solo se listan ventas con alguna imputación dentro del rango
    """
    # 1) Ventas del paciente
    v_rows = session.execute(
        select(
            Venta.idventa,
            Venta.fecha,
            Venta.montototal,
            Venta.nro_factura,
            Paciente.apellido,
            Paciente.nombre
        ).join(Paciente, Paciente.idpaciente == Venta.idpaciente)
         .where(Venta.idpaciente == idpaciente)
         .order_by(asc(Venta.fecha), asc(Venta.idventa))
    ).all()

    resultados = []

    for idventa, fecha_venta, montototal, nro_factura, ape, nom in v_rows:
        montototal = Decimal(montototal or DEC0)

        # 2) Imputado previo al rango → para saldo inicial
        imputado_previo = session.execute(
            select(func.coalesce(func.sum(CobroVenta.montoimputado), 0))
            .join(Cobro, Cobro.idcobro == CobroVenta.idcobro)
            .where(
                CobroVenta.idventa == idventa,
                Cobro.estado == "ACTIVO",
                Cobro.fecha < fecha_desde
            )
        ).scalar() or DEC0

        saldo_inicial = (montototal - Decimal(imputado_previo))

        # 3) Cobros dentro del rango
        ev_rows = session.execute(
            select(
                Cobro.fecha,
                Cobro.idcobro,
                Cobro.formapago,
                Cobro.observaciones,
                CobroVenta.montoimputado
            )
            .join(Cobro, Cobro.idcobro == CobroVenta.idcobro)
            .where(
                CobroVenta.idventa == idventa,
                Cobro.estado == "ACTIVO",
                Cobro.fecha >= fecha_desde,
                Cobro.fecha <= fecha_hasta
            )
            .order_by(asc(Cobro.fecha), asc(Cobro.idcobro))
        ).all()

        if not ev_rows:
            # Sin actividad en el rango: no mostramos esta venta
            continue

        # 4) Construir eventos con saldo corrido
        saldo_corriente = saldo_inicial
        eventos = []
        for f, idc, fp, obs, montoimp in ev_rows:
            montoimp = Decimal(montoimp or DEC0)
            saldo_corriente = (saldo_corriente - montoimp)
            eventos.append({
                "fecha": _to_date(f),
                "idcobro": int(idc),
                "formapago": fp or "",
                "monto": montoimp,
                "saldo_despues": saldo_corriente,
                "observaciones": obs or ""
            })

        resultados.append({
            "venta": {
                "idventa": int(idventa),
                "fecha": _to_date(fecha_venta),
                "montototal": montototal,           # para “Total Venta”
                "nro_factura": (nro_factura or ""),
                "paciente": f"{ape}, {nom}",
            },
            "saldo_inicial_rango": saldo_inicial,   # se usa solo para calcular corrida
            "eventos": eventos,
            "saldo_final_rango": saldo_corriente
        })

    return resultados


def buscar_pacientes_min(session: Session, texto: str, limit: int = 25):
    """
    Búsqueda 'tipo Google' por nombre/apellido/CI.
    Retorna (idpaciente, 'Apellido, Nombre - CI')
    """
    from sqlalchemy import and_
    if not texto:
        texto = ""
    t = f"%{texto.strip()}%"

    rows = session.execute(
        select(
            Paciente.idpaciente,
            Paciente.apellido,
            Paciente.nombre,
            Paciente.ci_pasaporte
        ).where(
            and_(Paciente.estado == True,  # noqa: E712
                 func.concat(Paciente.apellido, " ", Paciente.nombre, " ", func.coalesce(Paciente.ci_pasaporte, "")).
                 ilike(t))
        )
        .order_by(asc(Paciente.apellido), asc(Paciente.nombre))
        .limit(limit)
    ).all()

    return [(r[0], f"{r[1]}, {r[2]} - {r[3] or ''}") for r in rows]
