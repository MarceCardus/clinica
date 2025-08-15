# services/ventas_service.py
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from models.venta import Venta
from models.venta_detalle import VentaDetalle
from models.producto import Producto
from models.paquete import Paquete
from models.paquete_producto import PaqueteProducto  # relaciona paquete-producto

# Si mantenés PK compuesta en venta_detalle, conviene mergear líneas iguales:
MERGE_DETALLES_REPETIDOS = True  # si usás idventadet autonumérico podés poner False

def _money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _agregar_detalle(
    session: Session,
    *,
    idventa: int,
    idproducto: int,
    idpaquete: Optional[int],
    cantidad: Decimal,
    preciounitario: Decimal,
    descuento: Decimal
):
    """
    Inserta un detalle o mergea con uno existente (misma clave) si MERGE_DETALLES_REPETIDOS=True.
    Útil cuando la PK de venta_detalle es (idventa, idproducto[, idpaquete]).
    """
    cantidad = _money(cantidad)
    preciounitario = _money(preciounitario)
    descuento = _money(descuento)

    if MERGE_DETALLES_REPETIDOS:
        q = select(VentaDetalle).where(
            and_(
                VentaDetalle.idventa == idventa,
                VentaDetalle.idproducto == idproducto,
                (VentaDetalle.idpaquete == idpaquete) if idpaquete is not None else (VentaDetalle.idpaquete.is_(None))
            )
        )
        existente = session.execute(q).scalar_one_or_none()
        if existente:
            # Sumamos cantidades y descuentos; mantenemos el último precio unitario
            existente.cantidad = _money(Decimal(existente.cantidad) + cantidad)
            existente.descuento = _money(Decimal(existente.descuento or 0) + descuento)
            existente.preciounitario = preciounitario
            session.add(existente)
            return existente

    det = VentaDetalle(
        idventa=idventa,
        idproducto=idproducto,
        idpaquete=idpaquete,
        cantidad=cantidad,
        preciounitario=preciounitario,
        descuento=descuento
    )
    session.add(det)
    return det

def _precio_venta_producto(session: Session, prod_or_id) -> Decimal:
    if isinstance(prod_or_id, Producto):
        pv = getattr(prod_or_id, "precio_venta", 0)
    else:
        prod = session.execute(select(Producto).where(Producto.idproducto == int(prod_or_id))).scalar_one()
        pv = getattr(prod, "precio_venta", 0)
    return _money(pv or 0)

# def _descontar_stock(session: Session, idproducto: int, cantidad: Decimal):
#     """Hook opcional para controlar stock."""
#     prod = session.execute(select(Producto).where(Producto.idproducto == idproducto)).scalar_one()
#     if getattr(prod, "stock_actual", None) is None:
#         return  # no controla stock
#     cantidad = Decimal(cantidad)
#     if Decimal(prod.stock_actual) < cantidad:
#         raise ValueError(f"Stock insuficiente para producto {idproducto}.")
#     prod.stock_actual = _money(Decimal(prod.stock_actual) - cantidad)
#     session.add(prod)

def registrar_venta(
    session: Session,
    *,
    fecha: date = None,
    idpaciente: int = None,
    idprofesional: int = None,
    idclinica: int = None,
    estadoventa: str = "Cerrada",  # o "Abierta"
    observaciones: str = None,
    items: list = None,
    nro_factura: str | None = None
) -> Venta:
    """
    items: lista de dicts
      - Producto: {"tipo":"producto", "idproducto":int, "cantidad":Decimal|int, "precio":Decimal(opc), "descuento":Decimal(opc)}
      - Paquete:  {"tipo":"paquete", "idpaquete":int, "cantidad":Decimal|int, "precio":Decimal(opc)}
        * El precio del paquete se prorratea entre sus productos según (precio_venta * cantidad) de la composición.
    """
    if not items:
        raise ValueError("La venta debe tener al menos un ítem.")

    v = Venta(
        fecha = fecha or date.today(),
        idpaciente = idpaciente,
        idprofesional = idprofesional,
        idclinica = idclinica,
        montototal = _money(0),
        estadoventa = estadoventa,
        observaciones = observaciones,
        nro_factura = (nro_factura or "").strip()
    )
    session.add(v)
    session.flush()  # asegura v.idventa

    total = Decimal("0.00")

    for it in items:
        tipo = (it.get("tipo") or "").lower().strip()

        if tipo == "producto":
            idprod = int(it["idproducto"])
            cant = _money(it.get("cantidad", 1))
            if cant <= 0:
                raise ValueError("Cantidad inválida para producto.")

            prod = session.execute(select(Producto).where(Producto.idproducto == idprod)).scalar_one()

            precio = _money(it.get("precio", _precio_venta_producto(session, prod)))
            desc = _money(it.get("descuento", 0))

            linea = (precio * cant) - desc
            total += linea

            _agregar_detalle(
                session,
                idventa=v.idventa,
                idproducto=prod.idproducto,
                idpaquete=None,  # viene directo de producto
                cantidad=cant,
                preciounitario=precio,
                descuento=desc
            )
            # _descontar_stock(session, prod.idproducto, cant)

        elif tipo == "paquete":
            idpaq = int(it["idpaquete"])
            cant_paq = _money(it.get("cantidad", 1))
            if cant_paq <= 0:
                raise ValueError("Cantidad inválida para paquete.")

            paq = session.execute(select(Paquete).where(Paquete.idpaquete == idpaq)).scalar_one()
            precio_paq = _money(it.get("precio", getattr(paq, "precio_venta", 0)))

            # Traer composición
            comp = session.execute(
                select(PaqueteProducto).where(PaqueteProducto.idpaquete == idpaq)
            ).scalars().all()
            if not comp:
                raise ValueError("El paquete no tiene productos asociados.")

            # Suma de referencia: precio_venta * cantidad_en_paquete
            suma_ref = Decimal("0.00")
            for c in comp:
                # c.producto puede no estar cargado si no definiste relationship
                prod_ref = getattr(c, "producto", None)
                pv = _precio_venta_producto(session, prod_ref.idproducto if prod_ref else c.idproducto)
                cant_comp = _money(c.cantidad)
                suma_ref += pv * cant_comp

            # Si no hay referencia válida (precios/cantidades en cero), dividir en partes iguales
            if suma_ref <= 0:
                partes = Decimal(len(comp))
                for c in comp:
                    prod_ref = getattr(c, "producto", None)
                    idprod = prod_ref.idproducto if prod_ref else int(c.idproducto)
                    cant_comp = _money(c.cantidad)
                    if cant_comp <= 0:
                        cant_comp = Decimal("1.00")  # evita /0
                    precio_unit = _money(precio_paq / partes / cant_comp)
                    cant_total = cant_comp * cant_paq
                    linea = precio_unit * cant_total
                    total += linea

                    _agregar_detalle(
                        session,
                        idventa=v.idventa,
                        idproducto=idprod,
                        idpaquete=paq.idpaquete,  # trazabilidad
                        cantidad=cant_total,
                        preciounitario=precio_unit,
                        descuento=_money(0)
                    )
                    # _descontar_stock(session, idprod, cant_total)

            else:
                # Prorrateo proporcional
                for c in comp:
                    prod_ref = getattr(c, "producto", None)
                    idprod = prod_ref.idproducto if prod_ref else int(c.idproducto)
                    pv = _precio_venta_producto(session, idprod)
                    cant_comp = _money(c.cantidad)
                    if cant_comp <= 0:
                        cant_comp = Decimal("1.00")  # evita /0

                    ref = pv * cant_comp
                    propor = ref / suma_ref
                    precio_unit = _money((precio_paq * propor) / cant_comp)

                    cant_total = cant_comp * cant_paq
                    linea = precio_unit * cant_total
                    total += linea

                    _agregar_detalle(
                        session,
                        idventa=v.idventa,
                        idproducto=idprod,
                        idpaquete=paq.idpaquete,
                        cantidad=cant_total,
                        preciounitario=precio_unit,
                        descuento=_money(0)
                    )
                    # _descontar_stock(session, idprod, cant_total)

        else:
            raise ValueError("Tipo de ítem inválido. Use 'producto' o 'paquete'.")

    v.montototal = _money(total)
    session.commit()
    return v

def generar_cuotas_por_dias(
    session: Session,
    *,
    idventa: int,
    monto_total: Decimal,
    n_cuotas: int,
    primer_vencimiento: date,
    intervalo_dias: int = 30
):
    """
    Crea n_cuotas en venta_cuota prorrateando el monto.
    El redondeo deja el residuo en la última cuota.
    """
    from models.venta_cuota import VentaCuota

    if n_cuotas <= 0:
        raise ValueError("El número de cuotas debe ser mayor a 0.")

    monto_total = _money(monto_total)
    cuota_base = (monto_total / Decimal(n_cuotas)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Ajustar residuo en la última cuota
    montos = [cuota_base for _ in range(n_cuotas)]
    diff = monto_total - sum(montos)
    montos[-1] = _money(montos[-1] + diff)

    for i in range(n_cuotas):
        fv = primer_vencimiento + timedelta(days=intervalo_dias * i)
        session.add(VentaCuota(
            idventa=idventa,
            numerocuota=i+1,
            fechavencimiento=fv,
            montocuota=montos[i],
            estadocuota="Pendiente",
            fechapago=None,
            idcobro=None,
            observaciones=None
        ))
    session.commit()
