# services/informes_cobros_service.py
from __future__ import annotations
from decimal import Decimal
from datetime import date
from typing import Dict, Any, List, Tuple
from collections.abc import Iterable

from sqlalchemy.orm import Session
from sqlalchemy import func

from models.cobro import Cobro
from models.venta import Venta
from models.cobro_venta import CobroVenta  # relación cobro-venta (imputaciones)


# =========================== Utilidades num/str ===========================

def _num(s) -> Decimal:
    """Convierte a Decimal soportando strings con miles '.' y decimal ','."""
    if s is None:
        return Decimal(0)
    if isinstance(s, (int, float, Decimal)):
        return Decimal(str(s))
    t = str(s).replace('.', '').replace(' ', '')
    t = t.replace(',', '.')
    try:
        return Decimal(t)
    except Exception:
        return Decimal(0)


def _fmt_miles(x) -> str:
    """Formatea entero con separador de miles '.'."""
    try:
        v = int(round(_num(x)))
    except Exception:
        v = 0
    return f"{v:,}".replace(",", ".")


def _fmt_fecha(d) -> str:
    """dd-mm-yy (string vacía si no hay fecha)."""
    try:
        return d.strftime("%d-%m-%y") if d else ""
    except Exception:
        return ""


# ===== helpers genéricos attr/dict + números =====

def _get(obj, name, default=None):
    """Lee atributo o key de dict de forma segura."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _first_not_empty(obj, names: List[str]):
    """Primer atributo/key no vacío encontrado en names."""
    for n in names:
        v = _get(obj, n, None)
        if v not in (None, "", 0):
            return v
    return None


def _pick_amount(obj, names: List[str]) -> Decimal | None:
    """Primer monto no-cero; si todos son 0, devuelve el primero existente."""
    for n in names:
        if (isinstance(obj, dict) and n in obj) or hasattr(obj, n):
            dv = _num(_get(obj, n))
            if dv != 0:
                return dv
    for n in names:
        if (isinstance(obj, dict) and n in obj) or hasattr(obj, n):
            return _num(_get(obj, n))
    return None


def _pad(val, width):
    if val in (None, ""):
        return None
    try:
        s = str(int(val))
    except Exception:
        s = str(val)
    s = s.strip()
    if not s:
        return None
    return s.zfill(width)


# ======= helpers para elegir mejor descripción de ítems =======

def _get_str_attr(obj, names: List[str]) -> str | None:
    """Retorna el primer atributo/key string no vacío de names."""
    for n in names:
        if (isinstance(obj, dict) and n in obj) or hasattr(obj, n):
            v = _get(obj, n)
            if isinstance(v, str):
                v = v.strip()
                if v:
                    return v
    return None


def _is_generic_label(s: str | None) -> bool:
    """Detecta etiquetas genéricas que no sirven como descripción final."""
    lab = (s or "").strip().lower()
    return lab in {"procedimiento", "indicacion", "producto", "servicio", "item"}


def _first_of_iterable(x):
    """Devuelve un elemento representativo de una relación iterable (InstrumentedList, etc.)."""
    if x is None:
        return None
    if isinstance(x, (str, bytes, dict, Decimal, int, float, bool)):
        return None
    if isinstance(x, Iterable):
        for el in x:
            return el  # primero
    return None


def _db_get(session: Session, Model, pk):
    """Obtiene por PK tolerando SQLAlchemy 1.4/2.0 y ausencia de modelo."""
    if session is None or Model is None or pk in (None, ""):
        return None
    try:
        obj = session.get(Model, pk)  # SA 1.4+/2.0
        if obj is None:
            obj = session.query(Model).get(pk)  # fallback legacy
        return obj
    except Exception:
        return None


def _resolve_desc_via_lookup(session: Session, det) -> str | None:
    """
    Si la descripción no está en el detalle/relaciones, intenta resolver por IDs
    mirando tablas catálogos si están disponibles.
    """
    Indicacion = Procedimiento = Item = Producto = Servicio = None
    try:
        from models.indicacion import Indicacion as _Indicacion  # type: ignore
        Indicacion = _Indicacion
    except Exception:
        pass
    try:
        from models.procedimiento import Procedimiento as _Procedimiento  # type: ignore
        Procedimiento = _Procedimiento
    except Exception:
        pass
    try:
        from models.item import Item as _Item  # type: ignore
        Item = _Item
    except Exception:
        pass
    try:
        from models.producto import Producto as _Producto  # type: ignore
        Producto = _Producto
    except Exception:
        pass
    try:
        from models.servicio import Servicio as _Servicio  # type: ignore
        Servicio = _Servicio
    except Exception:
        pass

    candidates = [
        (_get(det, "idindicacion") or _get(det, "indicacion_id"), Indicacion),
        (_get(det, "idprocedimiento") or _get(det, "procedimiento_id"), Procedimiento),
        (_get(det, "iditem") or _get(det, "item_id"), Item),
        (_get(det, "id_producto") or _get(det, "idproducto") or _get(det, "producto_id"), Producto),
        (_get(det, "idservicio") or _get(det, "servicio_id"), Servicio),
    ]

    for pk, Model in candidates:
        if not Model or pk in (None, "", 0):
            continue
        obj = _db_get(session, Model, pk)
        if obj is None:
            continue
        desc = _get_str_attr(obj, ["nombre", "descripcion", "detalle", "titulo", "producto"])
        if desc and not _is_generic_label(desc):
            return desc
    return None


def _extract_desc_any(det, session: Session | None = None) -> str:
    """
    Busca la mejor descripción posible: detalle -> relaciones típicas -> escaneo amplio -> lookup por ID.
    """
    # 1) detalle directo (incluye variantes *_nombre)
    desc = _get_str_attr(det, [
        "descripcion_item", "descripcion", "detalle", "concepto",
        "nombre", "procedimiento", "indicacion",
        "item_nombre", "producto_nombre", "procedimiento_nombre",
        "indicacion_nombre", "servicio_nombre",
    ])
    if desc and not _is_generic_label(desc):
        return desc

    # 2) relaciones frecuentes
    for rel in ["item", "producto", "procedimiento", "indicacion", "servicio"]:
        obj = _get(det, rel)
        if obj is None:
            continue
        first = _first_of_iterable(obj)
        if first is not None:
            obj = first
        if isinstance(obj, (int, float, Decimal, str, bool)):
            continue
        d = _get_str_attr(obj, ["descripcion", "detalle", "nombre", "producto", "titulo",
                                "procedimiento", "indicacion"])
        if d and not _is_generic_label(d):
            return d

    # 3) escaneo amplio de cualquier relación/atributo
    for attr in dir(det):
        if attr.startswith("_") or attr in ("metadata", "registry", "query", "query_class"):
            continue
        try:
            obj = _get(det, attr)
        except Exception:
            continue
        if isinstance(obj, (str, int, float, bool, Decimal, type(None))):
            continue
        if isinstance(obj, dict):
            d = _get_str_attr(obj, ["descripcion", "detalle", "nombre", "titulo", "producto",
                                    "procedimiento", "indicacion"])
            if d and not _is_generic_label(d):
                return d
        first = _first_of_iterable(obj)
        if first is not None:
            obj = first
        if isinstance(obj, (str, int, float, bool, Decimal, type(None))):
            continue
        d = _get_str_attr(obj, ["descripcion", "detalle", "nombre", "titulo", "producto",
                                "procedimiento", "indicacion"])
        if d and not _is_generic_label(d):
            return d

    # 4) último recurso: resolver por IDs con DB
    if session is not None:
        resolved = _resolve_desc_via_lookup(session, det)
        if resolved:
            return resolved

    return desc or ""


def _factura_str(venta: Venta) -> str:
    """SOLO devuelve Venta.nro_factura (o string vacío)."""
    val = getattr(venta, "nro_factura", None)
    return str(val) if val not in (None, "") else ""


def _nombre_cliente(venta: Venta) -> str:
    pac = getattr(venta, "paciente", None)
    if pac:
        nom = (getattr(pac, "nombre", "") or "").strip()
        ape = (getattr(pac, "apellido", "") or "").strip()
        full = f"{nom} {ape}".strip()
        if full:
            return full
    return _first_not_empty(venta, ["cliente", "nombrecliente"]) or ""


def _norm_forma(s: str | None) -> str:
    """Normaliza la forma de pago a un set acotado."""
    if not s:
        return "Efectivo"
    t = str(s).strip().lower()
    if "efect" in t: return "Efectivo"
    if "trans" in t: return "Transferencia"
    if "cheq"  in t: return "Cheque"
    if "credit" in t: return "T. Crédito"
    if "débit" in t or "debit" in t: return "T. Débito"
    return s


# =========================== Informe RESUMEN (tabla en pantalla) ===========================

def obtener_informe_cobros(session: Session, fecha_desde: date, fecha_hasta: date) -> Dict[str, Any]:
    """Devuelve estructura para el informe de cobros en tabla (resumen por imputación)."""
    filas: List[Dict[str, Any]] = []

    formas = ["Efectivo", "Transferencia", "Cheque", "T. Crédito", "T. Débito"]
    sumatorias_forma_num: Dict[str, Decimal] = {f: Decimal(0) for f in formas}

    cobros: List[Cobro] = (
        session.query(Cobro)
        .filter(Cobro.fecha >= fecha_desde, Cobro.fecha <= fecha_hasta, Cobro.estado == "ACTIVO")
        .all()
    )

    # IDs de ventas involucradas (para calcular pagado histórico por venta en UNA query)
    venta_ids: set[int] = set()
    for c in cobros:
        for imp in (getattr(c, "imputaciones", []) or []):
            v = getattr(imp, "venta", None)
            if v is not None and getattr(v, "idventa", None) is not None:
                venta_ids.add(int(v.idventa))

    # Detectar columnas dinámicas en CobroVenta
    amount_col = None
    for n in ["monto", "importe", "valor", "monto_imputado", "montoimputado",
              "monto_aplicado", "montoaplicado", "monto_pago", "monto_pagado"]:
        if hasattr(CobroVenta, n):
            amount_col = getattr(CobroVenta, n)
            break
    idventa_col = None
    for n in ["idventa", "id_venta", "venta_id", "fk_idventa"]:
        if hasattr(CobroVenta, n):
            idventa_col = getattr(CobroVenta, n)
            break

    pagado_total_por_venta: Dict[int, Decimal] = {}
    if venta_ids and amount_col is not None and idventa_col is not None:
        try:
            rows = (
                session.query(idventa_col, func.coalesce(func.sum(amount_col), 0))
                .filter(idventa_col.in_(venta_ids))
                .group_by(idventa_col)
                .all()
            )
            pagado_total_por_venta = {int(r[0]): _num(r[1]) for r in rows}
        except Exception:
            pagado_total_por_venta = {}

    total_ingreso_num = Decimal(0)
    total_saldo_num = Decimal(0)

    for c in cobros:
        fecha_cobro = _fmt_fecha(getattr(c, "fecha", None))
        forma_norm = _norm_forma(getattr(c, "formapago", None) or getattr(c, "forma", None))

        imputaciones = getattr(c, "imputaciones", []) or []
        if not imputaciones:
            # Cobro sin imputaciones: mostrar suelto
            monto_cobro = _pick_amount(c, ["monto", "importe", "total", "monto_total"]) or Decimal(0)
            filas.append({
                "factura": "",
                "cliente": "",
                "fecha_factura": "",
                "fecha_cobro": fecha_cobro,
                "total_factura": "0",
                "pagado": _fmt_miles(monto_cobro),
                "saldo": "0",
                "forma": forma_norm,
            })
            sumatorias_forma_num[forma_norm] += monto_cobro
            total_ingreso_num += monto_cobro
            continue

        for idx, imp in enumerate(imputaciones):
            venta: Venta | None = getattr(imp, "venta", None)
            if not venta:
                continue

            # ---- TOTAL VENTA/FACTURA ----
            total_factura_num = _pick_amount(venta, [
                "montototal",
                "total", "total_final", "totalventa", "total_venta",
                "monto_total", "total_factura", "importe_total",
                "totalgeneral", "total_general", "totalconiva", "total_con_iva",
            ]) or Decimal(0)

            if total_factura_num == 0:
                vid = getattr(venta, "idventa", None)
                pagado_hist = pagado_total_por_venta.get(int(vid)) if vid is not None else Decimal(0)
                saldo_v = _num(getattr(venta, "saldo", 0))
                est = pagado_hist + saldo_v
                if est > 0:
                    total_factura_num = est

            # ---- PAGADO de esta imputación ----
            pagado_num = _pick_amount(imp, [
                "monto", "importe", "montoimputado", "monto_imputado",
                "montoaplicado", "monto_aplicado", "aplicado",
                "valor", "monto_pago", "monto_pagado"
            ])
            if pagado_num is None:
                pagado_num = _pick_amount(c, ["monto", "importe", "total", "monto_total"]) or Decimal(0)
                if idx > 0:
                    pagado_num = Decimal(0)

            # ---- SALDO ----
            if hasattr(venta, "saldo") and getattr(venta, "saldo") is not None:
                saldo_num = _num(getattr(venta, "saldo"))
            else:
                saldo_num = max(Decimal(0), total_factura_num - pagado_num)

            # ---- Acumuladores / fila ----
            sumatorias_forma_num[forma_norm] += pagado_num
            total_ingreso_num += pagado_num
            total_saldo_num += saldo_num

            filas.append({
                "factura": _factura_str(venta),
                "cliente": _nombre_cliente(venta),
                "fecha_factura": _fmt_fecha(getattr(venta, "fecha", getattr(venta, "fechaventa", None))),
                "fecha_cobro": fecha_cobro,
                "total_factura": _fmt_miles(total_factura_num),
                "pagado": _fmt_miles(pagado_num),
                "saldo": _fmt_miles(saldo_num),
                "forma": forma_norm,
            })

    anulaciones_ventas: List[Dict[str, Any]] = []
    anulaciones_cobros: List[Dict[str, Any]] = []

    sumatorias_forma = {k: _fmt_miles(v) for k, v in sumatorias_forma_num.items()}
    total_ingreso = _fmt_miles(total_ingreso_num)
    total_saldo = _fmt_miles(total_saldo_num)

    return {
        "filas_cobros": filas,
        "sumatorias_forma": sumatorias_forma,
        "anulaciones_ventas": anulaciones_ventas,
        "anulaciones_cobros": anulaciones_cobros,
        "total_ingreso": total_ingreso,
        "total_saldo": total_saldo,
    }


# =========================== Informe DETALLADO (para “PDF Detalles”) ===========================

def _iter_detalles_posibles(venta: Venta):
    """Devuelve una lista-like de detalles de la venta, probando varios nombres comunes."""
    for attr in ["detalles", "items", "venta_detalles", "venta_detalle", "det", "ventadetalle", "ventadet"]:
        dets = getattr(venta, attr, None)
        if dets:
            return dets
    return []


def _detalle_to_row(det, session: Session | None = None) -> Tuple[str, str, Decimal, Decimal, Decimal]:
    """
    Normaliza un detalle a (codigo, descripcion, cantidad, precio, subtotal).
    Acepta session para poder resolver descripciones por ID vía lookup.
    """
    # --- CÓDIGO / ID ---
    cod = _first_not_empty(det, [
        "codigo", "coditem", "codigoitem", "item_codigo",
        "cod_producto", "producto_codigo", "codigo_barra", "codbarra",
        "iditem", "id_item", "item_id", "id_producto", "idproducto",
        "idprocedimiento", "procedimiento_id", "idindicacion", "indicacion_id",
    ])
    if not cod:
        for rel in ["item", "producto", "procedimiento", "indicacion", "servicio"]:
            obj = _get(det, rel)
            if obj is None:
                continue
            first = _first_of_iterable(obj)
            if first is not None:
                obj = first
            if isinstance(obj, (int, float, Decimal, str, bool)):
                continue
            cod = _first_not_empty(obj, [
                "codigo", "sku", "coditem", "codigo_barra",
                "iditem", "id_item", "id_producto", "idprocedimiento", "idindicacion",
            ])
            if cod:
                break
    cod = "" if cod is None else str(cod)

    # --- DESCRIPCIÓN real ---
    desc = _extract_desc_any(det, session=session)

    # --- CANTIDAD / PRECIO / SUBTOTAL ---
    cant = _pick_amount(det, ["cantidad", "cant", "qty", "cantidaditem"]) or Decimal(0)
    precio = _pick_amount(det, ["precio", "precio_unitario", "preciounitario", "pu", "importe_unitario"]) or Decimal(0)
    st = _pick_amount(det, ["subtotal", "importe", "total_item", "total"]) or (cant * precio)

    return cod, desc, _num(cant), _num(precio), _num(st)


def obtener_informe_cobros_detallado(session: Session, fecha_desde: date, fecha_hasta: date) -> Dict[str, Any]:
    """
    Estructura para PDF “cabecera + detalle” por venta. SOLO incluye pagos del rango.
    """
    ventas: List[Dict[str, Any]] = []
    sumatorias_forma_num: Dict[str, Decimal] = {
        "Efectivo": Decimal(0),
        "Transferencia": Decimal(0),
        "Cheque": Decimal(0),
        "T. Crédito": Decimal(0),
        "T. Débito": Decimal(0),
    }

    # NUEVO: acumuladores Venta/Saldo del período
    total_ventas_periodo_num = Decimal(0)
    total_saldo_periodo_num = Decimal(0)

    cobros = (
        session.query(Cobro)
        .filter(Cobro.fecha >= fecha_desde, Cobro.fecha <= fecha_hasta, Cobro.estado == "ACTIVO")
        .all()
    )

    pagos_por_venta: Dict[int, List[Dict[str, Any]]] = {}
    ventas_ids: set[int] = set()

    for c in cobros:
        forma = _norm_forma(getattr(c, "formapago", None) or getattr(c, "forma", None))
        fch = _fmt_fecha(getattr(c, "fecha", None))
        imputaciones = getattr(c, "imputaciones", []) or []

        if not imputaciones:
            continue  # en detallado, solo ventas con imputación

        for idx, imp in enumerate(imputaciones):
            v = getattr(imp, "venta", None)
            if not v:
                continue
            vid = getattr(v, "idventa", None)
            if vid is None:
                continue
            vid = int(vid)

            # Monto del pago (imputación)
            monto = _pick_amount(imp, [
                "monto", "importe", "montoimputado", "monto_imputado",
                "montoaplicado", "monto_aplicado", "aplicado",
                "valor", "monto_pago", "monto_pagado"
            ])
            if monto is None:
                # fallback: monto del cobro (sólo para la primera imputación)
                monto = _pick_amount(c, ["monto", "importe", "total", "monto_total"]) or Decimal(0)
                if idx > 0:
                    monto = Decimal(0)

            pagos_por_venta.setdefault(vid, []).append({
                "forma": forma,
                "fecha": fch,
                "monto": _fmt_miles(monto),
                "_monto_num": _num(monto),
            })
            ventas_ids.add(vid)
            sumatorias_forma_num[forma] += _num(monto)

    # Pagado histórico por venta (para saldo actual)
    amount_col = None
    for n in ["monto", "importe", "valor", "monto_imputado", "montoimputado",
              "monto_aplicado", "montoaplicado", "monto_pago", "monto_pagado"]:
        if hasattr(CobroVenta, n):
            amount_col = getattr(CobroVenta, n)
            break
    idventa_col = None
    for n in ["idventa", "id_venta", "venta_id", "fk_idventa"]:
        if hasattr(CobroVenta, n):
            idventa_col = getattr(CobroVenta, n)
            break

    pagado_hist: Dict[int, Decimal] = {}
    if ventas_ids and amount_col is not None and idventa_col is not None:
        rows = (
            session.query(idventa_col, func.coalesce(func.sum(amount_col), 0))
            .filter(idventa_col.in_(ventas_ids))
            .group_by(idventa_col)
            .all()
        )
        pagado_hist = {int(r[0]): _num(r[1]) for r in rows}

    # Armar estructura por venta
    if ventas_ids:
        q = session.query(Venta).filter(getattr(Venta, "idventa").in_(list(ventas_ids)))
        for v in q.all():
            vid = int(getattr(v, "idventa"))
            fventa = _fmt_fecha(getattr(v, "fecha", getattr(v, "fechaventa", None)))
            factura = _factura_str(v)
            cliente = _nombre_cliente(v)

            # Detalles
            items = []
            total_venta_num = _pick_amount(v, [
                "montototal",
                "total", "total_final", "totalventa", "total_venta",
                "monto_total", "total_factura", "importe_total",
                "totalgeneral", "total_general", "totalconiva", "total_con_iva",
            ]) or Decimal(0)

            dets = _iter_detalles_posibles(v)
            st_suma = Decimal(0)
            for d in dets:
                cod, desc, cant, precio, st = _detalle_to_row(d, session=session)
                st_suma += _num(st)
                items.append({
                    "codigo": cod,
                    "descripcion": desc,
                    "cantidad": str(cant).rstrip('0').rstrip('.') if '.' in str(cant) else str(cant),
                    "precio": _fmt_miles(precio),
                    "subtotal": _fmt_miles(st),
                })
            if total_venta_num == 0 and st_suma > 0:
                total_venta_num = st_suma

            # Saldo actual
            if hasattr(v, "saldo") and getattr(v, "saldo") is not None:
                saldo_num = _num(getattr(v, "saldo"))
            else:
                saldo_num = max(Decimal(0), total_venta_num - pagado_hist.get(vid, Decimal(0)))

            # Acumular totales del período
            total_ventas_periodo_num += total_venta_num
            total_saldo_periodo_num += saldo_num

            ventas.append({
                "idventa": vid,
                "fecha_venta": fventa,
                "factura": factura,
                "cliente": cliente,
                "items": items,
                "total_venta": _fmt_miles(total_venta_num),
                "pagos": sorted(pagos_por_venta.get(vid, []), key=lambda x: x["fecha"]),
                "saldo": _fmt_miles(saldo_num),
            })

    total_cobrado_num = sum(sumatorias_forma_num.values())
    return {
        "ventas": ventas,
        "sumatorias_forma": {k: _fmt_miles(v) for k, v in sumatorias_forma_num.items()},
        "total_cobrado": _fmt_miles(total_cobrado_num),
        "cant_ventas": len(ventas),
        "total_ventas_periodo": _fmt_miles(total_ventas_periodo_num),
        "total_saldo_periodo": _fmt_miles(total_saldo_periodo_num),
    }
