# services/graficos_informe.py
# -*- coding: utf-8 -*-
from datetime import date
import os
from typing import Dict

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from sqlalchemy import func, and_, cast, Numeric, or_

from models.venta import Venta
from models.cobro import Cobro

def _figure() -> Figure:
    fig = plt.figure()   # el controlador inserta esto en Qt via FigureCanvas
    return fig

# -----------------------------
# 1) Evolución de Ventas (línea)
# -----------------------------
def fig_ventas_linea(session, desde: date, hasta: date) -> Figure:
    q = (
        session.query(
            func.date_trunc('month', Venta.fecha).label('mes'),
            func.sum(Venta.montototal).label('total_mes')
        )
        .filter(
            Venta.fecha >= desde,
            Venta.fecha <= hasta,
            or_(Venta.estadoventa == None, Venta.estadoventa != 'ANULADA')
        )
        .group_by('mes').order_by('mes')
    )
    rows = q.all()
    df = pd.DataFrame(rows, columns=["mes", "total_mes"])

    fig = _figure()
    ax = fig.add_subplot(111)
    if df.empty:
        ax.set_title("Evolución de Ventas (sin datos)")
        ax.set_xlabel("Mes"); ax.set_ylabel("Ventas [Gs.]")
        return fig

    ax.plot(df["mes"], df["total_mes"], marker="o")
    ax.set_title("Evolución de Ventas (mensual)")
    ax.set_xlabel("Mes"); ax.set_ylabel("Ventas [Gs.]")
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()
    return fig

# ----------------------------------------
# 2) Distribución por Método de Pago (donut)
# ----------------------------------------
def fig_metodos_pago_donut(session, desde: date, hasta: date) -> Figure:
    q = (
        session.query(
            Cobro.formapago.label("metodo"),
            func.sum(Cobro.monto).label("total")
        )
        .filter(
            Cobro.fecha >= desde,
            Cobro.fecha <= hasta,
            Cobro.estado == "ACTIVO"
        )
        .group_by(Cobro.formapago)
        .order_by(func.sum(Cobro.monto).desc())
    )
    rows = q.all()
    df = pd.DataFrame(rows, columns=["metodo", "total"])
    if df.empty:
        df = pd.DataFrame({"metodo": ["Sin datos"], "total": [1]})

    fig = _figure()
    ax = fig.add_subplot(111)
    wedges, texts, autotexts = ax.pie(
        df["total"], labels=None, autopct="%1.1f%%", startangle=90
    )
    # donut
    c = plt.Circle((0, 0), 0.55, fc="white")
    ax.add_artist(c)
    ax.set_title("Distribución por Método de Pago")

    # LEYENDA a la izquierda o derecha (no tapa el gráfico)
    ax.legend(
        wedges,
        [str(m) for m in df["metodo"]],
        title="Método",
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        borderaxespad=0.0
    )

    fig.tight_layout()
    return fig

# ---------------------------------------------------------
# 3) Cobrados vs Pendientes por mes (barras apiladas)
# ---------------------------------------------------------
def fig_cobros_apilados(session, desde: date, hasta: date) -> Figure:
    q = (
        session.query(
            func.date_trunc('month', Venta.fecha).label('mes'),
            func.sum(cast(Venta.montototal - Venta.saldo, Numeric(14,2))).label('cobrado'),
            func.sum(cast(Venta.saldo, Numeric(14,2))).label('pendiente')
        )
        .filter(
            Venta.fecha >= desde,
            Venta.fecha <= hasta,
            or_(Venta.estadoventa == None, Venta.estadoventa != 'ANULADA')
        )
        .group_by('mes').order_by('mes')
    )
    rows = q.all()
    df = pd.DataFrame(rows, columns=["mes", "cobrado", "pendiente"])

    fig = _figure()
    ax = fig.add_subplot(111)
    if df.empty:
        ax.set_title("Cobros: Cobrados vs Pendientes (sin datos)")
        ax.set_xlabel("Mes"); ax.set_ylabel("Monto [Gs.]")
        return fig

    x = range(len(df))
    ax.bar(x, df["cobrado"], label="Cobrados")
    ax.bar(x, df["pendiente"], bottom=df["cobrado"], label="Pendientes")
    ax.set_title("Cobros: Cobrados vs Pendientes (mensual)")
    ax.set_xlabel("Mes"); ax.set_ylabel("Monto [Gs.]")
    ax.set_xticks(list(x))
    ax.set_xticklabels([d.strftime("%b %Y") for d in df["mes"]], rotation=45, ha="right")
    ax.legend()
    fig.tight_layout()
    return fig

# -----------------------------
# Opcional: guardar figuras
# -----------------------------
def guardar_png(fig: Figure, carpeta: str, nombre: str) -> str:
    os.makedirs(carpeta, exist_ok=True)
    out = os.path.join(carpeta, f"{nombre}.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    return out
