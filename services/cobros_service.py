# services/cobros_service.py
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable
from contextlib import contextmanager
from sqlalchemy import select, func, delete, update, case
from sqlalchemy.orm import Session
from models.cobro import Cobro
from models.cobro_venta import CobroVenta
from models.venta import Venta
from models.StockMovimiento import StockMovimiento  # si lo usás para auditoría de stock

# --- util ---
def _money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _least(a, b):
    """MIN(a, b) portable para cualquier motor (incluye SQL Server)."""
    return case((a <= b, a), else_=b)
# ============== API PRINCIPAL ==============

def registrar_cobro(
    session: Session,
    *,
    fecha: date | None,
    idpaciente: int,
    monto: Decimal,
    formapago: str | None = None,
    observaciones: str | None = None,
    usuarioregistro: str | None = None,
    imputaciones: Iterable[dict] | None = None,  # [{idventa, monto}]
    auto_fifo: bool = False,
) -> int:
    """
    Crea el Cobro y, opcionalmente, lo imputa a una o varias ventas.
    Descuenta 'saldo' de cada venta afectada en el acto.
    Si no se pasan imputaciones, queda como anticipo (crédito del paciente).
    """

    monto = _money(monto)
    if monto <= 0:
        raise ValueError("El monto del cobro debe ser > 0.")

    with _begin_tx(session):  # transacción atómica
        c = Cobro(
            fecha=fecha or date.today(),
            idpaciente=int(idpaciente),
            monto=monto,
            formapago=(formapago or "").strip()[:30] or None,
            observaciones=(observaciones or None),
            usuarioregistro=(str(usuarioregistro).strip() if usuarioregistro not in (None, "") else None),
        )
        session.add(c)
        session.flush()  # idcobro

        total_imputado = Decimal("0.00")

        if imputaciones:
            for imp in imputaciones:
                idventa = int(imp["idventa"])
                monto_imp = _money(imp["monto"])
                if monto_imp <= 0:
                    raise ValueError("Cada imputación debe ser > 0.")
                total_imputado += _imputar_cobro_a_venta(
                    session, idcobro=c.idcobro, idventa=idventa,
                    monto=monto_imp, idpaciente=idpaciente
                )

        elif auto_fifo:
            total_imputado = _imputar_fifo_por_paciente(
                session, idcobro=c.idcobro, idpaciente=idpaciente, monto=monto
            )

        # ✅ esto aplica para ambos casos (manual o FIFO)
        if total_imputado > monto:
            raise ValueError(f"Las imputaciones ({total_imputado}) exceden el monto del cobro ({monto}).")

        _auditar(session,
                 usuario=usuarioregistro,
                 accion="COBRO_CREAR",
                 entidad="cobro",
                 iddoc=c.idcobro,
                 extra={"total_imputado": str(total_imputado), "monto": str(monto)})

        return c.idcobro


def _imputar_cobro_a_venta(session: Session, *, idcobro: int, idventa: int, monto: Decimal, idpaciente: int) -> Decimal:
    """
    Inserta una fila en cobro_venta y descuenta 'saldo' de la venta.
    Valida: misma persona, venta no anulada y saldo suficiente.
    Usa bloqueos 'FOR UPDATE' para evitar carreras.
    """
    monto = _money(monto)

    # Bloqueo de la venta (evita carreras si imputan en paralelo)
    v = session.execute(
        select(Venta).where(Venta.idventa == idventa).with_for_update()
    ).scalar_one_or_none()
    if not v:
        raise ValueError("Venta no encontrada.")
    if v.estadoventa and v.estadoventa.strip().upper() == "ANULADA":
        raise ValueError("No se puede imputar a una venta anulada.")
    if v.idpaciente and int(v.idpaciente) != int(idpaciente):
        # Si querés permitir cruces entre pacientes, quitá esta validación
        raise ValueError("La venta pertenece a otro paciente.")

    # Bloqueo del cobro (para consistencia)
    c = session.execute(
        select(Cobro).where(Cobro.idcobro == idcobro).with_for_update()
    ).scalar_one_or_none()
    if not c:
        raise ValueError("Cobro no encontrado.")
    if int(c.idpaciente) != int(idpaciente):
        raise ValueError("El cobro pertenece a otro paciente.")

    # Verificar no sobre-imputar el cobro
    total_actual = session.execute(
        select(func.coalesce(func.sum(CobroVenta.montoimputado), 0))
        .where(CobroVenta.idcobro == idcobro)
    ).scalar_one()
    if total_actual + monto > c.monto:
        raise ValueError("Esta imputación excede el monto del cobro.")

    # Verificar saldo disponible de la venta
    saldo_disp = _money(v.saldo or 0)
    if saldo_disp <= 0:
        raise ValueError("La venta no tiene saldo pendiente.")
    if monto > saldo_disp:
        # podés elegir 'recortar' o rechazar; aquí recortamos a lo pendiente
        monto = saldo_disp  # aplicar solo lo que falta

    # Insertar imputación
    cv = CobroVenta(idcobro=idcobro, idventa=idventa, montoimputado=monto)
    session.add(cv)

    # Descontar saldo en memoria (la instancia ya está bloqueada)
    v.saldo = _money(max(Decimal("0.00"), Decimal(v.saldo) - monto))

    session.flush()
    return monto

def _in_tx(session) -> bool:
    try:
        return session.in_transaction()
    except AttributeError:
        return session.get_transaction() is not None

@contextmanager
def _begin_tx(session):
    """Abre una TX normal si no hay una activa; si ya hay, usa SAVEPOINT."""
    if _in_tx(session):
        with session.begin_nested():
            yield
    else:
        with session.begin():      # ← abrir la TX del Session, no llamarse a sí mismo
            yield
# ============== ANULACIONES / REVERSAS ==============

def anular_cobro(session: Session, idcobro: int, motivo: str | None = None,
                 usuario: int | str | None = None):

    """
    Anula un cobro: elimina sus imputaciones (devolviendo los saldos a las ventas)
    y deja el cobro sin efecto. Si querés, podés moverlo a una tabla auditoría.
    """
    with _begin_tx(session):
        c = session.execute(
            select(Cobro).where(Cobro.idcobro == idcobro).with_for_update()
        ).scalar_one_or_none()
        if not c:
            raise ValueError("Cobro no encontrado.")

        # Revertir cada imputación
        cvs = session.execute(
            select(CobroVenta).where(CobroVenta.idcobro == idcobro).with_for_update()
        ).scalars().all()

        for cv in cvs:
            session.execute(
                update(Venta)
                .where(Venta.idventa == cv.idventa)
                .values(
                    saldo=_least(
                        Venta.montototal,
                        func.coalesce(Venta.saldo, 0) + cv.montoimputado
                    )
                )
            )
        # borrar imputaciones
        session.execute(delete(CobroVenta).where(CobroVenta.idcobro == idcobro))
        if hasattr(c, "estado"):
            c.estado = "ANULADO"

        _auditar(session, usuario=usuario, accion="COBRO_ANULAR",
                 entidad="cobro", iddoc=idcobro, motivo=motivo)
        # Si preferís marcar estado en Cobro, agrega un campo 'estado' en vez de borrar.


def revertir_imputaciones_por_venta(session: Session, idventa: int):
    """
    Elimina todas las imputaciones de una venta (cuando se anula la venta),
    devolviendo ese dinero al 'crédito' de cada cobro (simplemente se liberan
    las filas; el cobro queda con más disponible).
    """
    with _begin_tx(session):
        cvs = session.execute(
            select(CobroVenta).where(CobroVenta.idventa == idventa).with_for_update()
        ).scalars().all()

        # devolver saldo a la venta (igual la vas a poner en 0 al anular)
        total_revertido = sum((cv.montoimputado or 0) for cv in cvs)
        if total_revertido:
            session.execute(
                update(Venta)
                .where(Venta.idventa == idventa)
                .values(
                    saldo=_least(
                        Venta.montototal,
                        func.coalesce(Venta.saldo, 0) + total_revertido
                    )
                )
            )

        session.execute(delete(CobroVenta).where(CobroVenta.idventa == idventa))


def anular_venta(session: Session, idventa: int, motivo: str | None = None):

    with _begin_tx(session):
        venta = session.execute(
            select(Venta).where(Venta.idventa == idventa).with_for_update()
        ).scalar_one_or_none()
        if not venta:
            raise Exception("Venta no encontrada")

        # 1) Revertir imputaciones de cobro (libera créditos)
        cvs = session.execute(
            select(CobroVenta).where(CobroVenta.idventa == idventa).with_for_update()
        ).scalars().all()
        if cvs:
            # devolvemos lo imputado a 'saldo' antes de anular
            total_revertido = sum((cv.montoimputado or 0) for cv in cvs)
            if total_revertido:
                venta.saldo = _money(Decimal(venta.saldo or 0) + Decimal(total_revertido))

            # borrar imputaciones
            for cv in cvs:
                session.delete(cv)

        # 2) Stock: devolver productos físicos ("ambos")
        for det in venta.detalles:
            if _es_fisico(session, det.iditem):
                mov = StockMovimiento(
                    fecha=datetime.now(),
                    iditem=det.iditem,
                    cantidad=det.cantidad,
                    tipo="INGRESO",
                    motivo="Anulación de venta",
                    idorigen=venta.idventa,
                    observacion=f"Anulación Venta N° {venta.idventa}"
                )
                session.add(mov)

        # 3) Marcar estado y saldo final = 0
        venta.estadoventa = "Anulada"
        venta.saldo = _money(0)

        _auditar(session, usuario=None, accion="VENTA_ANULAR",
                entidad="venta", iddoc=idventa, motivo=motivo)

def _imputar_fifo_por_paciente(session: Session, *, idcobro: int, idpaciente: int, monto: Decimal) -> Decimal:
    restante = _money(monto)
    if restante <= 0:
        return Decimal("0.00")

    ventas = session.execute(
        select(Venta)
        .where(
            Venta.idpaciente == idpaciente,
            func.upper(func.coalesce(Venta.estadoventa, '')) != 'ANULADA',
            Venta.saldo > 0
        )
        .order_by(Venta.fecha.asc(), Venta.idventa.asc())
        .with_for_update()
    ).scalars().all()

    aplicado_total = Decimal("0.00")
    for v in ventas:
        if restante <= 0:
            break
        saldo_v = _money(v.saldo or 0)
        if saldo_v <= 0:
            continue
        aplicar = min(restante, saldo_v)
        session.add(CobroVenta(idcobro=idcobro, idventa=v.idventa, montoimputado=aplicar))
        v.saldo = _money(max(Decimal("0.00"), Decimal(v.saldo) - aplicar))
        aplicado_total += aplicar
        restante -= aplicar

    session.flush()
    return aplicado_total


def _auditar(session, *, usuario: int | str | None, accion: str, entidad: str,
             iddoc: int, motivo: str | None = None, extra: dict | None = None):
    """
    Guarda una línea en 'auditoria'.
    - 'usuario' puede ser int (id), str numérica ("3") o el login ("Cardus").
    """
    from datetime import datetime
    from sqlalchemy import select
    from models.auditoria import Auditoria

    # --- armar observaciones legibles ---
    partes = []
    if motivo:
        partes.append(f"Motivo: {motivo}")
    if entidad:
        partes.append(f"Entidad: {entidad} (id={iddoc})")
    if extra:
        partes.append(f"Extra: {extra}")
    obs = " | ".join(partes) or None

    # --- resolver idusuario ---
    uid = None
    if usuario is not None:
        s = str(usuario).strip()
        if s.isdigit():
            uid = int(s)
        else:
            # Intentar resolver por login
            try:
                from models.usuario import Usuario
                uid = session.execute(
                    select(Usuario.idusuario).where(Usuario.usuario == s)
                ).scalar_one_or_none()
            except Exception:
                uid = None  # si no existe la tabla/modelo o falla, seguimos sin UID

    a = Auditoria(
        fechahora=datetime.now(),
        idusuario=uid,
        modulo=entidad,
        accion=accion,
        observaciones=obs,
    )
    session.add(a)


def _es_fisico(session: Session, iditem: int) -> bool:
    from models.item import Item
    t = session.execute(select(Item.tipo).where(Item.iditem == iditem)).scalar_one_or_none()
    nombre = t if isinstance(t, str) else getattr(t, "nombre", None)
    return (nombre or "").strip().lower() in ("producto", "ambos")


