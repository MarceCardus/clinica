# services/informe_stock_mensual_service.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from calendar import monthrange
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import func, case, literal, or_
from sqlalchemy.orm import Session

from models.item import Item
from models.StockMovimiento import StockMovimiento

# ===================== Constantes =====================

SPANISH_MONTHS = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

# ===================== Util =====================

def _periodo(year: int, month: int) -> tuple[date, date, date]:
    d1 = date(year, month, 1)
    last_day = monthrange(year, month)[1]
    d2 = date(year, month, last_day)
    if month == 1:
        corte = date(year - 1, 12, 31)
    else:
        prev_last = monthrange(year, month - 1)[1]
        corte = date(year, month - 1, prev_last)
    return d1, d2, corte

def _as_decimal(x) -> Decimal:
    if x is None: return Decimal(0)
    if isinstance(x, Decimal): return x
    return Decimal(str(x))

def _tipo_to_str(t) -> str:
    try:
        return t.name if hasattr(t, "name") else str(t or "").upper()
    except Exception:
        return str(t or "")

def _icol(cls, names: tuple[str, ...]):
    for n in names:
        if hasattr(cls, n):
            return getattr(cls, n)
    return None

# ===================== Autodetección de columnas =====================

ITEM_ID_COL   = _icol(Item, ("id", "iditem", "id_item", "itemid"))
ITEM_NOM_COL  = _icol(Item, ("nombre", "descripcion", "detalle", "nombreitem"))
ITEM_UNI_COL  = _icol(Item, ("unidad", "unidadmedida", "unid", "unidad_medida"))
ITEM_TIPO_COL = _icol(Item, ("tipo", "categoria", "tipoi", "tipo_item"))

if ITEM_ID_COL is None:
    raise AttributeError("Item: no se encontró la PK (id, iditem, id_item o itemid).")

# ===================== Estructuras de salida =====================

@dataclass
class ItemRow:
    iditem: int
    nombre: str
    unidad: str | None
    inicial: Decimal
    ingreso: Decimal
    ventas: Decimal
    otros: Decimal
    @property
    def actual(self) -> Decimal:
        return self.inicial + self.ingreso - self.ventas - self.otros

@dataclass
class GrupoTipo:
    tipo: str
    items: List[ItemRow]

@dataclass
class InformeStockMensual:
    year: int
    month: int
    desde: date
    hasta: date
    corte_inicial: date
    grupos: List[GrupoTipo]

# ===================== Cálculo principal =====================

def obtener_informe_stock_mensual(session: Session, *, year: int, month: int) -> InformeStockMensual:
    """
    - Inicial = saldo al último día del mes anterior (INGRESO - EGRESO) con ABS(cantidad)
    - Ingreso = COMPRAS del mes
    - Ventas  = EGRESOS del mes por venta (idventa* o texto 'VENTA')
    - Otros   = EGRESOS del mes no-venta
    """
    desde, hasta, corte = _periodo(year, month)

    filtros_no_anulado = []
    if hasattr(StockMovimiento, "anulado"):
        filtros_no_anulado.append(StockMovimiento.anulado.is_(False))
    if hasattr(StockMovimiento, "estado"):
        filtros_no_anulado.append(StockMovimiento.estado != literal("ANULADO"))

    # ---------- Inicial ----------
    q_ini = (
        session.query(
            StockMovimiento.iditem.label("iditem"),
            func.coalesce(
                func.sum(
                    case((StockMovimiento.tipo == literal("INGRESO"), func.abs(StockMovimiento.cantidad)), else_=literal(0))
                ), 0
            ).label("sum_in"),
            func.coalesce(
                func.sum(
                    case((StockMovimiento.tipo == literal("EGRESO"), func.abs(StockMovimiento.cantidad)), else_=literal(0))
                ), 0
            ).label("sum_out"),
        )
        .filter(StockMovimiento.fecha <= corte, *filtros_no_anulado)
        .group_by(StockMovimiento.iditem)
        .all()
    )
    inicial_por_item: Dict[int, Decimal] = {r.iditem: _as_decimal(r.sum_in) - _as_decimal(r.sum_out) for r in q_ini}

    # ---------- Ingreso (SOLO COMPRAS del mes) ----------
    compra_preds = []
    # por ID de compra
    for col in ("idcompra", "id_compra", "compra_id", "idCompra", "compraId"):
        if hasattr(StockMovimiento, col):
            compra_preds.append(getattr(StockMovimiento, col).isnot(None))
    # por texto COMPRA en columnas de origen/motivo/etc.
    for col in ("origen", "motivo", "tipo_origen", "tipo_mov", "tipomov"):
        if hasattr(StockMovimiento, col):
            compra_preds.append(func.upper(getattr(StockMovimiento, col)) == literal("COMPRA"))

    compra_cond = or_(*compra_preds) if compra_preds else literal(False)

    q_ing = (
        session.query(
            StockMovimiento.iditem.label("iditem"),
            func.coalesce(func.sum(func.abs(StockMovimiento.cantidad)), 0).label("ing")
        )
        .filter(
            StockMovimiento.fecha >= desde,
            StockMovimiento.fecha <= hasta,
            StockMovimiento.tipo == literal("INGRESO"),
            compra_cond,                         # <-- sólo compras
            *filtros_no_anulado
        )
        .group_by(StockMovimiento.iditem)
        .all()
    )
    ingreso_por_item: Dict[int, Decimal] = {r.iditem: _as_decimal(r.ing) for r in q_ing}

    # ---------- EGRESOS totales del mes ----------
    q_egr_total = (
        session.query(
            StockMovimiento.iditem.label("iditem"),
            func.coalesce(func.sum(func.abs(StockMovimiento.cantidad)), 0).label("egr")
        )
        .filter(
            StockMovimiento.fecha >= desde,
            StockMovimiento.fecha <= hasta,
            StockMovimiento.tipo == literal("EGRESO"),
            *filtros_no_anulado
        )
        .group_by(StockMovimiento.iditem)
        .all()
    )
    egreso_total_por_item: Dict[int, Decimal] = {r.iditem: _as_decimal(r.egr) for r in q_egr_total}

    # ---------- Ventas (idventa* o texto 'VENTA') ----------
    venta_preds = []
    for col in ("idventa", "id_venta", "venta_id", "idVenta", "ventaId"):
        if hasattr(StockMovimiento, col):
            venta_preds.append(getattr(StockMovimiento, col).isnot(None))
    for col in ("origen", "motivo", "tipo_origen", "tipo_mov", "tipomov"):
        if hasattr(StockMovimiento, col):
            venta_preds.append(func.upper(getattr(StockMovimiento, col)) == literal("VENTA"))

    venta_cond = or_(*venta_preds) if venta_preds else literal(False)

    q_ven = (
        session.query(
            StockMovimiento.iditem.label("iditem"),
            func.coalesce(func.sum(func.abs(StockMovimiento.cantidad)), 0).label("ven")
        )
        .filter(
            StockMovimiento.fecha >= desde,
            StockMovimiento.fecha <= hasta,
            StockMovimiento.tipo == literal("EGRESO"),
            venta_cond,
            *filtros_no_anulado
        )
        .group_by(StockMovimiento.iditem)
        .all()
    )
    ventas_por_item: Dict[int, Decimal] = {r.iditem: _as_decimal(r.ven) for r in q_ven}

    # ---------- Otros (no-venta) ----------
    otros_por_item: Dict[int, Decimal] = {
        iid: egreso_total_por_item[iid] - ventas_por_item.get(iid, Decimal(0))
        for iid in egreso_total_por_item.keys()
    }

    # Ítems a listar
    ids_informe = set(inicial_por_item) | set(ingreso_por_item) | set(egreso_total_por_item)
    if not ids_informe:
        return InformeStockMensual(year=year, month=month, desde=desde, hasta=hasta, corte_inicial=corte, grupos=[])

    # Datos de ítems
    nom_col  = ITEM_NOM_COL  or literal("")
    uni_col  = ITEM_UNI_COL  or literal("")
    tipo_col = ITEM_TIPO_COL or literal("SIN TIPO")

    items = (
        session.query(
            ITEM_ID_COL.label("iid"),
            nom_col.label("nombre"),
            uni_col.label("unidad"),
            tipo_col.label("tipo"),
        )
        .filter(ITEM_ID_COL.in_(ids_informe))
        .order_by(tipo_col, nom_col)
        .all()
    )

    grupos_dict: Dict[str, List[ItemRow]] = {}
    for iid, nombre, unidad, tipo in items:
        tstr = _tipo_to_str(tipo) if ITEM_TIPO_COL is not None else "SIN TIPO"
        grupos_dict.setdefault(tstr, []).append(
            ItemRow(
                iditem=iid,
                nombre=str(nombre or ""),
                unidad=str(unidad or "") if unidad is not None else "",
                inicial=inicial_por_item.get(iid, Decimal(0)),
                ingreso=ingreso_por_item.get(iid, Decimal(0)),
                ventas=ventas_por_item.get(iid, Decimal(0)),
                otros=otros_por_item.get(iid, Decimal(0)),
            )
        )

    grupos = [GrupoTipo(tipo=k, items=v) for k, v in sorted(grupos_dict.items(), key=lambda kv: kv[0])]
    return InformeStockMensual(year=year, month=month, desde=desde, hasta=hasta, corte_inicial=corte, grupos=grupos)

# ===================== Exportadores =====================

def exportar_pdf_informe_stock_mensual(session: Session, *, year: int, month: int, ruta_pdf: str) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm

    info = obtener_informe_stock_mensual(session, year=year, month=month)

    doc = SimpleDocTemplate(ruta_pdf, pagesize=A4,
                            rightMargin=12*mm, leftMargin=12*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    styles = getSampleStyleSheet()
    story = []

    titulo = Paragraph("<b>Informe de Stock Mensual (Agrupado por Tipo)</b>", styles["Title"])
    leyenda = Paragraph(
        f"Período: {SPANISH_MONTHS[month]} {year} — "
        f"Inicial = stock al {info.corte_inicial.strftime('%d/%m/%Y')} • "
        f"Ingreso = compras de {SPANISH_MONTHS[month]} {year} • "
        f"Ventas = ventas de {SPANISH_MONTHS[month]} {year} • "
        f"Otros (Insumo) = salidas no-venta de {SPANISH_MONTHS[month]} {year}",
        styles["Normal"]
    )
    story += [titulo, Spacer(1, 6*mm), leyenda, Spacer(1, 6*mm)]

    head = ["#", "Item", "Unidad", "Inicial", "Ingreso", "Ventas", "Otros (Insumo)", "Actual"]

    def _fmt(n) -> str:
        try:
            return f"{int(Decimal(str(n)).quantize(Decimal('1'))):,}".replace(",", ".")
        except Exception:
            return str(n or 0)

    i_global = 1
    for g in info.grupos:
        story.append(Paragraph(f"<b>{g.tipo}</b>", styles["Heading3"]))
        data = [head[:]]
        for r in g.items:
            data.append([i_global, r.nombre, r.unidad or "", _fmt(r.inicial), _fmt(r.ingreso), _fmt(r.ventas), _fmt(r.otros), _fmt(r.actual)])
            i_global += 1

        t = Table(data, repeatRows=1, colWidths=[12*mm, None, 20*mm, 22*mm, 22*mm, 22*mm, 28*mm, 22*mm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("ALIGN", (3,1), (-1,-1), "RIGHT"),
            ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
            ("BOTTOMPADDING", (0,0), (-1,0), 6),
        ]))
        story += [t, Spacer(1, 6*mm)]

    doc.build(story)
    return ruta_pdf

def exportar_excel_informe_stock_mensual(session: Session, *, year: int, month: int, ruta_xlsx: str) -> str:
    import pandas as pd
    info = obtener_informe_stock_mensual(session, year=year, month=month)
    rows = []
    for g in info.grupos:
        for r in g.items:
            rows.append({
                "Tipo": g.tipo,
                "Item": r.nombre,
                "Unidad": r.unidad or "",
                "Inicial": int(r.inicial),
                "Ingreso": int(r.ingreso),
                "Ventas": int(r.ventas),
                "Otros (Insumo)": int(r.otros),
                "Actual": int(r.actual),
            })
    with pd.ExcelWriter(ruta_xlsx, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name=f"{SPANISH_MONTHS[month]} {year}")
    return ruta_xlsx
