# services/informe_stock_mensual_service.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from calendar import monthrange
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import func, case, literal, or_, false
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
        s = t.nombre if hasattr(t, "nombre") else (t.name if hasattr(t, "name") else str(t or ""))
    except Exception:
        s = str(t or "")
    s = (s or "").strip()
    return s.upper() if s else "SIN TIPO"

def _icol(cls, names: tuple[str, ...]):
    for n in names:
        if hasattr(cls, n):
            return getattr(cls, n)
    return None

# ===================== Autodetección de columnas =====================

ITEM_ID_COL   = _icol(Item, ("id", "iditem", "id_item", "itemid"))
ITEM_NOM_COL  = _icol(Item, ("nombre", "descripcion", "detalle", "nombreitem"))
ITEM_UNI_COL  = _icol(Item, ("unidad", "unidadmedida", "unid", "unidad_medida"))
ITEM_TIPO_COL = _icol(Item, ("categoria", "grupo", "rubro", "tipo_item", "tipoi"))
ITEM_GEN_STOCK_COL = _icol(Item, ("genera_stock", "generaStock", "genera_existencia", "generaExistencia"))

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
    genera_stock: bool = True

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
    - Inicial = saldo al último día del mes anterior (INGRESO - EGRESO)
    - Ingreso = COMPRAS del mes
    - Ventas  = EGRESOS del mes por venta (idventa* o texto 'VENTA')
    - Otros   = EGRESOS del mes no-venta
    """
    desde, hasta, corte = _periodo(year, month)

    filtros_no_anulado = []
    if hasattr(StockMovimiento, "anulado"):
        filtros_no_anulado.append(or_(
            StockMovimiento.anulado.is_(False),
            StockMovimiento.anulado.is_(None)
        ))

    if hasattr(StockMovimiento, "estado"):
        filtros_no_anulado.append(or_(
            StockMovimiento.estado.is_(None),
            StockMovimiento.estado != "ANULADO"
        ))

    # ---------- Inicial ----------
    q_ini = (
        session.query(
            StockMovimiento.iditem.label("iditem"),
            func.coalesce(func.sum(case((StockMovimiento.tipo == "INGRESO", func.abs(StockMovimiento.cantidad)), else_=0)), 0).label("sum_in"),
            func.coalesce(func.sum(case((StockMovimiento.tipo == "EGRESO", func.abs(StockMovimiento.cantidad)), else_=0)), 0).label("sum_out"),
        )
        .filter(
            StockMovimiento.fecha < desde,
            *filtros_no_anulado
        )
        .group_by(StockMovimiento.iditem)
        .all()
    )
    inicial_por_item: Dict[int, Decimal] = {r.iditem: _as_decimal(r.sum_in) - _as_decimal(r.sum_out) for r in q_ini}

    # ---------- Ingreso (SOLO COMPRAS del mes) ----------
    compra_preds = []
    for col in ("idcompra", "id_compra", "compra_id", "idCompra", "compraId"):
        if hasattr(StockMovimiento, col):
            compra_preds.append(getattr(StockMovimiento, col).isnot(None))
    for col in ("origen", "motivo", "tipo_origen", "tipo_mov", "tipomov"):
        if hasattr(StockMovimiento, col):
            compra_preds.append(func.upper(getattr(StockMovimiento, col)) == "COMPRA")

    compra_cond = or_(*compra_preds) if compra_preds else false()

    q_ing = (
        session.query(
            StockMovimiento.iditem.label("iditem"),
            func.coalesce(func.sum(func.abs(StockMovimiento.cantidad)), 0).label("ing")
        )
        .filter(
            StockMovimiento.fecha >= desde,
            StockMovimiento.fecha <= hasta,
            StockMovimiento.tipo == "INGRESO",
            compra_cond,
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
            StockMovimiento.tipo == "EGRESO",
            *filtros_no_anulado
        )
        .group_by(StockMovimiento.iditem)
        .all()
    )
    egreso_total_por_item: Dict[int, Decimal] = {r.iditem: _as_decimal(r.egr) for r in q_egr_total}

    # ---------- Ventas ----------
    venta_preds = []
    for col in ("idventa", "id_venta", "venta_id", "idVenta", "ventaId"):
        if hasattr(StockMovimiento, col):
            venta_preds.append(getattr(StockMovimiento, col).isnot(None))
    for col in ("origen", "motivo", "tipo_origen", "tipo_mov", "tipomov"):
        if hasattr(StockMovimiento, col):
            venta_preds.append(func.upper(getattr(StockMovimiento, col)) == "VENTA")

    venta_cond = or_(*venta_preds) if venta_preds else false()

    q_ven = (
        session.query(
            StockMovimiento.iditem.label("iditem"),
            func.coalesce(func.sum(func.abs(StockMovimiento.cantidad)), 0).label("ven")
        )
        .filter(
            StockMovimiento.fecha >= desde,
            StockMovimiento.fecha <= hasta,
            StockMovimiento.tipo == "EGRESO",
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

    # ---------- Datos de ítems ----------
    nom_col = ITEM_NOM_COL or literal("")
    uni_col = ITEM_UNI_COL or literal("")

    q_items = session.query(
        ITEM_ID_COL.label("iid"),
        nom_col.label("nombre"),
        uni_col.label("unidad"),
    )

    # Si existe genera_stock, traemos y filtramos
    if ITEM_GEN_STOCK_COL is not None:
        q_items = q_items.add_columns(ITEM_GEN_STOCK_COL.label("genera_stock"))
        q_items = q_items.filter(ITEM_GEN_STOCK_COL.is_(True))

    q_items = (
        q_items.filter(ITEM_ID_COL.in_(ids_informe))
               .group_by(ITEM_ID_COL, nom_col, uni_col, *([ITEM_GEN_STOCK_COL] if ITEM_GEN_STOCK_COL is not None else []))
               .order_by(nom_col.asc())
    )

    items = q_items.all()

    rows: List[ItemRow] = []
    for tup in items:
        if ITEM_GEN_STOCK_COL is not None:
            iid, nombre, unidad, gen = tup
            gen = bool(gen)
        else:
            iid, nombre, unidad = tup
            gen = True

        rows.append(
            ItemRow(
                iditem=iid,
                nombre=str(nombre or ""),
                unidad=str(unidad or "") if unidad else "",
                inicial=inicial_por_item.get(iid, Decimal(0)),
                ingreso=ingreso_por_item.get(iid, Decimal(0)),
                ventas=ventas_por_item.get(iid, Decimal(0)),
                otros=otros_por_item.get(iid, Decimal(0)),
                genera_stock=gen,
            )
        )

    return InformeStockMensual(
        year=year, month=month, desde=desde, hasta=hasta, corte_inicial=corte,
        grupos=[GrupoTipo(tipo="", items=rows)]
    )

# ===================== Exportadores =====================

def exportar_pdf_informe_stock_mensual(session: Session, *, year: int, month: int, ruta_pdf: str) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, LongTable, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from xml.sax.saxutils import escape

    info = obtener_informe_stock_mensual(session, year=year, month=month)

    doc = SimpleDocTemplate(
        ruta_pdf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm
    )
    styles = getSampleStyleSheet()
    st_item = ParagraphStyle("item", parent=styles["Normal"], fontSize=9, leading=11)

    story = []
    titulo = Paragraph("<b>Informe de Stock Mensual</b>", styles["Title"])
    leyenda = Paragraph(f"Período: {SPANISH_MONTHS[month]} {year}", styles["Normal"])
    story += [titulo, Spacer(1, 6*mm), leyenda, Spacer(1, 6*mm)]

    head = ["#", "Item", "Inicial", "Ingreso", "Ventas", "Insumo", "Actual"]
    avail_w = A4[0] - doc.leftMargin - doc.rightMargin
    fixed_after_item = [20*mm, 20*mm, 20*mm, 22*mm, 20*mm]
    fixed_total = 12*mm + sum(fixed_after_item)
    item_w = max(60*mm, avail_w - fixed_total)
    col_widths = [12*mm, item_w] + fixed_after_item

    def _fmt(n) -> str:
        try:
            return f"{int(Decimal(str(n)).quantize(Decimal('1'))):,}".replace(",", ".")
        except Exception:
            return str(n or 0)

    rows = []
    idx = 1
    for g in info.grupos:
        for r in g.items:
            rows.append([
                idx,
                Paragraph(escape(r.nombre or ""), st_item),
                _fmt(r.inicial),
                _fmt(r.ingreso),
                _fmt(r.ventas),
                _fmt(r.otros),
                _fmt(r.actual),
            ])
            idx += 1

    t = LongTable([head] + rows, repeatRows=1, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))
    story += [t]
    doc.build(story)
    return ruta_pdf


def exportar_excel_informe_stock_mensual(session: Session, *, year: int, month: int, ruta_xlsx: str) -> str:
    import pandas as pd
    info = obtener_informe_stock_mensual(session, year=year, month=month)
    rows = []
    for g in info.grupos:
        for r in g.items:
            rows.append({
                "Item": r.nombre,
                "Inicial": int(r.inicial),
                "Ingreso": int(r.ingreso),
                "Ventas": int(r.ventas),
                "Insumo": int(r.otros),
                "Actual": int(r.actual),
            })
    with pd.ExcelWriter(ruta_xlsx, engine="openpyxl") as writer:
        sheet_name = f"{SPANISH_MONTHS[month]} {year}"
        pd.DataFrame({"Período:": [f"{SPANISH_MONTHS[month]} {year}"]}).to_excel(
            writer, index=False, header=False, sheet_name=sheet_name, startrow=0, startcol=0
        )
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name=sheet_name, startrow=2)
    return ruta_xlsx
