# services/ventas_service.py
from datetime import date, timedelta,datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.venta import Venta
from models.venta_detalle import VentaDetalle
from models.item import Item
from models.paquete import Paquete
from models.paquete_producto import PaqueteProducto  # si prorrateás paquetes
from models.StockMovimiento import StockMovimiento

MERGE_DETALLES_REPETIDOS = True


# ----------------- utilidades -----------------
def _money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _get_item(session: Session, iditem: int) -> Item:
    it = session.execute(select(Item).where(Item.iditem == int(iditem))).scalar_one()
    return it

def _precio_item(session: Session, iditem: int) -> Decimal:
    it = _get_item(session, iditem)
    return _money(getattr(it, "precio_venta", 0) or 0)

def _tipo_item(session: Session, iditem: int) -> str:
    """
    Devuelve 'producto' | 'paquete' | 'ambos' según tu esquema.
    Soporta que Item.tipo sea:
      - un string
      - una relación a ItemTipo con atributo .nombre
    """
    it = _get_item(session, iditem)
    t = getattr(it, "tipo", None)
    if isinstance(t, str):
        return (t or "").strip().lower()
    # relación
    nombre = getattr(t, "nombre", None)
    return (nombre or "").strip().lower()

def _agregar_detalle_item(
    session: Session,
    *,
    idventa: int,
    iditem: int,
    cantidad: Decimal,
    preciounitario: Decimal,
    descuento: Decimal = Decimal("0")
) -> VentaDetalle:
    cantidad = _money(cantidad)
    preciounitario = _money(preciounitario)
    descuento = _money(descuento)

    if MERGE_DETALLES_REPETIDOS:
        # OJO: NO seleccionar la entidad completa, porque arrastra columnas inexistentes
        rowid = session.execute(
            select(VentaDetalle.idventadet).where(
                VentaDetalle.idventa == idventa,
                VentaDetalle.iditem == iditem,
                VentaDetalle.preciounitario == preciounitario,
                VentaDetalle.descuento == descuento,
            )
        ).scalar_one_or_none()

        if rowid is not None:
            existente = session.get(VentaDetalle, rowid)
            existente.cantidad = _money(Decimal(existente.cantidad) + cantidad)
            session.add(existente)
            return existente

    det = VentaDetalle(
        idventa=idventa,
        iditem=iditem,
        cantidad=cantidad,
        preciounitario=preciounitario,
        descuento=descuento,
    )
    session.add(det)
    return det


# ----------------- API principal -----------------
def registrar_venta(
    session: Session,
    *,
    fecha: date | None = None,
    idpaciente: int | None = None,
    idprofesional: int | None = None,
    idclinica: int | None = None,
    estadoventa: str = "Cerrada",
    observaciones: str | None = None,
    items: list | None = None,     # ahora admite solo iditem/cantidad/precio(/descuento)
    nro_factura: Optional[str] = None,
    prorratear_paquetes: bool = False,
) -> Venta:
    if not items:
        raise ValueError("La venta debe tener al menos un ítem.")

    v = Venta(
        fecha=fecha or date.today(),
        idpaciente=idpaciente,
        idprofesional=idprofesional,
        idclinica=idclinica,
        montototal=_money(0),
        estadoventa=estadoventa,
        observaciones=observaciones,
        nro_factura=(nro_factura or "").strip(),
    )
    session.add(v)
    session.flush()  # idventa

    total = Decimal("0.00")

    for it in items:
        # Soporta payloads antiguos y nuevos
        iditem = it.get("iditem")
        if iditem is None:
            # retrocompatibilidad (por si aún mandaras idproducto)
            iditem = it.get("idproducto")
        if iditem is None:
            raise ValueError("Falta iditem en un ítem del detalle.")

        iditem = int(iditem)

        # tipo explícito u obtenido del Item
        tipo = (it.get("tipo") or "").strip().lower()
        if not tipo:
            tipo = _tipo_item(session, iditem)  # 'producto' | 'paquete' | 'ambos'

        # datos numéricos
        cant = _money(it.get("cantidad", 1))
        precio = _money(it.get("precio", _precio_item(session, iditem)))
        desc = _money(it.get("descuento", 0))

        if tipo in ("producto", "ambos"):
            # tratamos 'ambos' como producto cuando llega por la UI de productos
            linea = (precio * cant) - desc
            total += linea
            _agregar_detalle_item(
                session,
                idventa=v.idventa,
                iditem=iditem,
                cantidad=cant,
                preciounitario=precio,
                descuento=desc,
            )

            if tipo == "ambos":
                mov = StockMovimiento(
                    fecha=fecha or datetime.now(),
                    iditem=iditem,
                    cantidad=-cant,
                    tipo="EGRESO",
                    motivo="Venta",
                    idorigen=v.idventa,
                    observacion=f"Venta N° {v.idventa}"
                )
                session.add(mov)

        elif tipo == "paquete":
            if not prorratear_paquetes:
                # línea única con el iditem del paquete
                linea = (precio * cant) - desc
                total += linea
                _agregar_detalle_item(
                    session,
                    idventa=v.idventa,
                    iditem=iditem,
                    cantidad=cant,
                    preciounitario=precio,
                    descuento=desc,
                )
            else:
                # --- prorrateo sobre composición Paquete/PaqueteProducto (si lo usás) ---
                # Para esto necesitamos saber qué Paquete es. Lo intento por igualdad de IDs.
                paq = session.execute(select(Paquete).where(Paquete.idpaquete == iditem)).scalar_one_or_none()
                if paq is None:
                    # si tu mapping paquete->item no es 1:1 por id, ajusta este lookup
                    raise ValueError("No se pudo mapear el item de tipo 'paquete' a un registro de Paquete.")
                comp = session.execute(
                    select(PaqueteProducto).where(PaqueteProducto.idpaquete == paq.idpaquete)
                ).scalars().all()
                if not comp:
                    # sin composición: lo tratamos como línea única
                    linea = (precio * cant) - desc
                    total += linea
                    _agregar_detalle_item(
                        session,
                        idventa=v.idventa,
                        iditem=iditem,
                        cantidad=cant,
                        preciounitario=precio,
                        descuento=desc,
                    )
                else:
                    # Referencia proporcional según precio_venta de los items producto
                    suma_ref = Decimal("0.00")
                    refs: list[tuple[int, Decimal, Decimal]] = []
                    for c in comp:
                        # aquí esperamos que los "productos" del paquete también existan como Items tipo producto/ambos,
                        # con el mismo ID que el producto (ajústalo si tu mapping es distinto)
                        iditem_prod = int(c.idproducto)
                        pv = _precio_item(session, iditem_prod)
                        cant_comp = _money(c.cantidad or 1)
                        suma_ref += pv * cant_comp
                        refs.append((iditem_prod, pv, cant_comp))

                    if suma_ref <= 0:
                        partes = Decimal(len(refs))
                        for (iid, _pv, cant_comp) in refs:
                            precio_unit = _money(precio / partes / cant_comp)
                            cant_total = cant_comp * cant
                            linea = precio_unit * cant_total
                            total += linea
                            _agregar_detalle_item(
                                session,
                                idventa=v.idventa,
                                iditem=iid,
                                cantidad=cant_total,
                                preciounitario=precio_unit,
                                descuento=_money(0),
                            )
                    else:
                        for (iid, pv, cant_comp) in refs:
                            propor = (pv * cant_comp) / suma_ref
                            precio_unit = _money((precio * propor) / cant_comp)
                            cant_total = cant_comp * cant
                            linea = precio_unit * cant_total
                            total += linea
                            _agregar_detalle_item(
                                session,
                                idventa=v.idventa,
                                iditem=iid,
                                cantidad=cant_total,
                                preciounitario=precio_unit,
                                descuento=_money(0),
                            )
        else:
            # si algo raro viene, lo trato como producto por defecto
            linea = (precio * cant) - desc
            total += linea
            _agregar_detalle_item(
                session,
                idventa=v.idventa,
                iditem=iditem,
                cantidad=cant,
                preciounitario=precio,
                descuento=desc,
            )

    v.montototal = _money(total)
    v.saldo = _money(total)
    session.commit()
    return v
def crear_venta(self, venta_data: dict) -> int:
        v = registrar_venta(
            session=self.session,
            fecha=venta_data.get("fecha"),
            idpaciente=venta_data.get("idpaciente"),
            idprofesional=venta_data.get("idprofesional"),
            idclinica=venta_data.get("idclinica"),
            estadoventa="Cerrada",
            observaciones=venta_data.get("observaciones"),
            items=venta_data.get("items", []),
            nro_factura=venta_data.get("nro_factura"),
            prorratear_paquetes=False,  # o True si querés “explotar” paquetes
        )
        return v.idventa
def anular_venta(session, idventa):
    venta = session.query(Venta).get(idventa)
    if not venta:
        raise Exception("Venta no encontrada")
    venta.estadoventa = "Anulada"
    # Devolver stock de productos físicos ("ambos")
    for det in venta.detalles:
        tipo = _tipo_item(session, det.iditem)
        if tipo == "ambos":
            mov = StockMovimiento(
                fecha=datetime.now(),
                 iditem=det.iditem,  # o el campo correcto
                cantidad=det.cantidad,  # ingreso al stock
                tipo="INGRESO",
                motivo="Anulación de venta",
                idorigen=venta.idventa,
                observacion=f"Anulación Venta N° {venta.idventa}"
            )
            session.add(mov)
    session.commit()