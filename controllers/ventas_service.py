# services/ventas_service.py
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Iterable

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from models.venta import Venta
from models.venta_detalle import VentaDetalle
from models.item import Item                 # <-- NUEVO: usamos Item unificado
from models.paquete import Paquete
from models.paquete_producto import PaqueteProducto  # composición del paquete -> productos

MERGE_DETALLES_REPETIDOS = True

def _money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _agregar_detalle_item(
    session: Session,
    *,
    idventa: int,
    iditem: int,
    cantidad: Decimal,
    preciounitario: Decimal,
    descuento: Decimal = Decimal("0")
) -> VentaDetalle:
    cantidad = _money(cantidad); preciounitario = _money(preciounitario); descuento = _money(descuento)

    if MERGE_DETALLES_REPETIDOS:
        existente = session.execute(
            select(VentaDetalle).where(
                VentaDetalle.idventa == idventa,
                VentaDetalle.iditem  == iditem,
                VentaDetalle.preciounitario == preciounitario,
                VentaDetalle.descuento == descuento,
            )
        ).scalar_one_or_none()
        if existente:
            existente.cantidad = _money(Decimal(existente.cantidad) + cantidad)
            session.add(existente)
            return existente

    det = VentaDetalle(
        idventa=idventa,
        iditem=iditem,                    # <-- SOLO iditem
        cantidad=cantidad,
        preciounitario=preciounitario,
        descuento=descuento
    )
    session.add(det)
    return det

def _precio_item(session: Session, iditem: int) -> Decimal:
    it = session.execute(select(Item).where(Item.iditem == int(iditem))).scalar_one()
    return _money(getattr(it, "precio_venta", 0) or 0)

def registrar_venta(
    session: Session,
    *,
    fecha: date = None,
    idpaciente: int = None,
    idprofesional: int = None,
    idclinica: int = None,
    estadoventa: str = "Cerrada",
    observaciones: str = None,
    items: list = None,         # ← ahora viene con iditem para productos; y/o idpaquete para paquetes
    nro_factura: Optional[str] = None,
    prorratear_paquetes: bool = False    # si True, explota paquete a sus productos (ítems producto)
) -> Venta:
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
    session.add(v); session.flush()

    total = Decimal("0.00")

    for it in items:
        tipo = (it.get("tipo") or "").lower().strip()

        if tipo == "producto":
            # Esperamos {"tipo":"producto","iditem":..., "cantidad":..., "precio":..., "descuento":...}
            iditem = int(it["iditem"])
            # seguridad: aceptar sólo items tipo producto o ambos
            tipo_item = (session.execute(select(Item.tipo).where(Item.iditem == iditem)).scalar_one() or "").lower()
            if tipo_item not in ("producto", "ambos"):
                raise ValueError("El ítem seleccionado no es de tipo 'producto' ni 'ambos'.")

            cant = _money(it.get("cantidad", 1))
            precio = _money(it.get("precio", _precio_item(session, iditem)))
            desc = _money(it.get("descuento", 0))

            linea = (precio * cant) - desc
            total += linea

            _agregar_detalle_item(session,
                idventa=v.idventa, iditem=iditem, cantidad=cant,
                preciounitario=precio, descuento=desc
            )

        elif tipo == "paquete":
            # Esperamos {"tipo":"paquete","idpaquete":..., "cantidad":..., "precio":...}
            idpaq = int(it["idpaquete"])
            cant_paq = _money(it.get("cantidad", 1))
            paq = session.execute(select(Paquete).where(Paquete.idpaquete == idpaq)).scalar_one()
            precio_paq = _money(it.get("precio", getattr(paq, "precio_venta", 0)))

            if not prorratear_paquetes:
                # Guardar como una sola línea: debe existir un Item de tipo 'paquete' que represente este paquete
                iditem_paq = session.execute(
                    select(Item.iditem).where(Item.tipo.in_(["paquete","ambos"]), Item.referencia == f"PAQ:{idpaq}")
                ).scalar_one_or_none()
                if iditem_paq is None:
                    # fallback: si llevás Item con mismo id que el paquete
                    iditem_paq = session.execute(
                        select(Item.iditem).where(Item.iditem == idpaq, Item.tipo.in_(["paquete","ambos"]))
                    ).scalar_one_or_none()
                if iditem_paq is None:
                    raise ValueError("No existe Item para el paquete seleccionado.")

                linea = precio_paq * cant_paq
                total += linea

                _agregar_detalle_item(session,
                    idventa=v.idventa, iditem=int(iditem_paq),
                    cantidad=cant_paq, preciounitario=precio_paq, descuento=_money(0)
                )
            else:
                # Prorrateo a sus productos (necesitás mapear cada producto a su Item 'producto/ambos')
                comp = session.execute(
                    select(PaqueteProducto).where(PaqueteProducto.idpaquete == idpaq)
                ).scalars().all()
                if not comp:
                    raise ValueError("El paquete no tiene productos asociados.")

                # suma de referencia: precio_item(prod)*cantidad_en_comp
                suma_ref = Decimal("0.00")
                refs = []
                for c in comp:
                    # Mapear producto -> Item (producto/ambos). Ajustá este where a tu esquema.
                    iditem_prod = session.execute(
                        select(Item.iditem).where(Item.tipo.in_(["producto","ambos"]),
                                                  Item.referencia == f"PROD:{int(c.idproducto)}")
                    ).scalar_one_or_none()
                    if iditem_prod is None:
                        raise ValueError(f"Producto {c.idproducto} del paquete no está mapeado a Item.")

                    pv = _precio_item(session, iditem_prod)
                    cant_comp = _money(c.cantidad or 1)
                    ref = pv * cant_comp
                    suma_ref += ref
                    refs.append((iditem_prod, pv, cant_comp))

                if suma_ref <= 0:
                    # dividir en partes iguales
                    partes = Decimal(len(refs))
                    for (iditem_prod, _pv, cant_comp) in refs:
                        precio_unit = _money(precio_paq / partes / cant_comp)
                        cant_total = cant_comp * cant_paq
                        linea = precio_unit * cant_total
                        total += linea
                        _agregar_detalle_item(session,
                            idventa=v.idventa, iditem=int(iditem_prod),
                            cantidad=cant_total, preciounitario=precio_unit, descuento=_money(0)
                        )
                else:
                    for (iditem_prod, pv, cant_comp) in refs:
                        propor = (pv * cant_comp) / suma_ref
                        precio_unit = _money((precio_paq * propor) / cant_comp)
                        cant_total = cant_comp * cant_paq
                        linea = precio_unit * cant_total
                        total += linea
                        _agregar_detalle_item(session,
                            idventa=v.idventa, iditem=int(iditem_prod),
                            cantidad=cant_total, preciounitario=precio_unit, descuento=_money(0)
                        )
        else:
            raise ValueError("Tipo de ítem inválido. Use 'producto' o 'paquete'.")

    v.montototal = _money(total)
    session.commit()
    return v
