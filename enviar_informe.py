# enviar_informe.py (PostgreSQL) — ajustado a tus tablas/columnas
# Reqs: pip install SQLAlchemy psycopg2-binary python-dotenv
# .env: DATABASE_URL=postgresql+psycopg2://usuario:pass@host:5432/consultorio
#       SMTP_* (host, port, user, pass, from, to), REPORT_TZ=America/Asuncion
#       IMAP_* (opcional, para guardar en Enviados)

import os, sys, traceback
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import imaplib, time

# ---------------- util ----------------
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

def load_env():
    """
    Carga variables desde:
      1) .env en la carpeta del ejecutable (cuando está “frozen”)
      2) .env en el cwd como fallback
    """
    try:
        from dotenv import load_dotenv  # pip install python-dotenv
        base_dir = Path(getattr(sys, "_MEIPASS",
                         Path(sys.executable).parent if getattr(sys, "frozen", False)
                         else Path(__file__).parent))
        load_dotenv(base_dir / ".env", override=False)
        load_dotenv(override=False)  # por si ejecutás desde consola
    except Exception:
        pass

load_env()

def asu_now(tz_name: str | None):
    tz = None
    if tz_name and ZoneInfo is not None:
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = None
    return datetime.now(tz) if tz else datetime.now()

def period_day(d: date): return d, d

def period_month(d: date):
    first = date(d.year, d.month, 1)
    last  = (date(d.year + (d.month//12), (d.month%12)+1, 1) - timedelta(days=1))
    return first, last

def period_year(d: date): return date(d.year,1,1), date(d.year,12,31)

def D(x):
    if x is None: return Decimal("0")
    if isinstance(x, Decimal): return x
    try: return Decimal(str(x))
    except Exception: return Decimal("0")

def money(x: Decimal):
    q = D(x).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"Gs. {q:,.0f}".replace(",", ".")

def norm_fp(fp: str) -> str:
    if not fp: return ""
    s = fp.strip().upper()
    m = {
        "EFECTIVO": {"EFECTIVO", "CASH", "CONTADO"},
        "TRANSFERENCIA": {"TRANSFERENCIA", "TRANSF", "TRANSFER", "GIRO"},
        "TARJETA_CREDITO": {"TC", "TARJETA CREDITO", "TARJETA CRÉDITO", "CREDITO", "CRÉDITO"},
        "TARJETA_DEBITO": {"TD", "TARJETA DEBITO", "TARJETA DÉBITO", "DEBITO", "DÉBITO"},
        "CHEQUE": {"CHEQUE", "CHEQUES"},
    }
    for k, vals in m.items():
        if s in vals: return k
    if "TARJETA" in s: return "TARJETA_CREDITO"
    return s

# ---------------- DB ----------------
from sqlalchemy import create_engine, text
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("Definí DATABASE_URL en .env (postgresql+psycopg2://...)")
ENGINE = create_engine(DB_URL, pool_pre_ping=True, future=True)

# ---------------- consultas (ajustadas a tu esquema) ----------------
# Tablas/columnas:
# venta(idventa, fecha, montototal, estadoventa, saldo)
# cobro(idcobro, fecha, monto, formapago, estado)
# compra(idcompra, fecha, montototal, anulada bool)
# compra_detalle(idcompra, iditem, cantidad, preciounitario, observaciones, ...)
# item(iditem, nombre, iditemtipo)
# item_tipo(iditemtipo, nombre -> 'PRODUCTO'/'INSUMO'/'AMBOS')

def _vigente_venta_sql(alias="v"):
    # Excluimos anuladas según tu campo 'estadoventa'
    return f"AND ({alias}.estadoventa IS NULL OR UPPER({alias}.estadoventa) NOT IN ('ANULADO','ANULADA'))"

def _vigente_cobro_sql(alias="c"):
    # Excluimos cobros anulados si existiese 'ANULADO'
    return f"AND ({alias}.estado IS NULL OR UPPER({alias}.estado) NOT IN ('ANULADO','ANULADA'))"

def sum_ventas(d1: date, d2: date) -> Decimal:
    sql = f"""
    SELECT COALESCE(SUM(v.montototal),0) total
    FROM venta v
    WHERE v.fecha BETWEEN :d1 AND :d2
      {_vigente_venta_sql('v')}
    """
    with ENGINE.begin() as cx:
        return D(cx.execute(text(sql), {"d1": d1, "d2": d2}).scalar())

def sum_cobros_por_fp(d1: date, d2: date):
    sql = f"""
    SELECT c.formapago, COALESCE(SUM(c.monto),0) total
    FROM cobro c
    WHERE c.fecha BETWEEN :d1 AND :d2
      {_vigente_cobro_sql('c')}
    GROUP BY c.formapago
    """
    res = {"EFECTIVO": D(0), "TRANSFERENCIA": D(0), "TC_TD_CHEQUE": D(0), "TOTAL": D(0)}
    with ENGINE.begin() as cx:
        for medio, total in cx.execute(text(sql), {"d1": d1, "d2": d2}):
            s = D(total); n = norm_fp(medio or "")
            if n == "EFECTIVO": res["EFECTIVO"] += s
            elif n == "TRANSFERENCIA": res["TRANSFERENCIA"] += s
            elif n in {"TARJETA_CREDITO","TARJETA_DEBITO","CHEQUE"}: res["TC_TD_CHEQUE"] += s
            res["TOTAL"] += s
    return res

def sum_saldo_periodo(d1: date, d2: date) -> Decimal:
    # Tenés venta.saldo -> sumamos directo
    sql = f"""
    SELECT COALESCE(SUM(v.saldo),0) saldo
    FROM venta v
    WHERE v.fecha BETWEEN :d1 AND :d2
      {_vigente_venta_sql('v')}
    """
    with ENGINE.begin() as cx:
        return D(cx.execute(text(sql), {"d1": d1, "d2": d2}).scalar())

def sum_saldo_year(any_date: date) -> Decimal:
    y1, y2 = period_year(any_date)
    return sum_saldo_periodo(y1, y2)

def _line_expr():
    # Si tu IVA en compra_detalle es MONTO adicional, podés sumar " + COALESCE(cd.iva,0)".
    # Si IVA es porcentaje, sería "* (1 + COALESCE(cd.iva,0)/100.0)".
    return "COALESCE(cd.cantidad,0) * COALESCE(cd.preciounitario,0)"

def sum_compras_insumos_productos(d1: date, d2: date) -> Decimal:
    line = _line_expr()
    sql = f"""
    SELECT COALESCE(SUM({line}),0) total
    FROM compra_detalle cd
    JOIN compra c         ON c.idcompra = cd.idcompra
    LEFT JOIN item i      ON i.iditem = cd.iditem
    LEFT JOIN item_tipo t ON t.iditemtipo = i.iditemtipo
    WHERE c.fecha BETWEEN :d1 AND :d2
      AND COALESCE(c.anulada, FALSE) = FALSE
      AND (
            t.nombre IN ('PRODUCTO','INSUMO','AMBOS')
            OR cd.iditem IS NOT NULL
          )
    """
    with ENGINE.begin() as cx:
        return D(cx.execute(text(sql), {"d1": d1, "d2": d2}).scalar())

def sum_gastos_daisy(d1: date, d2: date) -> Decimal:
    line = _line_expr()
    sql = f"""
    SELECT COALESCE(SUM({line}),0) total
    FROM compra_detalle cd
    JOIN compra c         ON c.idcompra = cd.idcompra
    LEFT JOIN item i      ON i.iditem = cd.iditem
    WHERE c.fecha BETWEEN :d1 AND :d2
      AND COALESCE(c.anulada, FALSE) = FALSE
      AND (
            (i.nombre ILIKE 'Gastos Daisy%%')
         OR (cd.observaciones ILIKE 'Gastos Daisy%%')
          )
    """
    with ENGINE.begin() as cx:
        return D(cx.execute(text(sql), {"d1": d1, "d2": d2}).scalar())

# ---------------- email ----------------
from email.message import EmailMessage

def build_email_text(rep_date: date,
                     ventas_dia: Decimal, cobros_dia: dict, saldo_dia: Decimal,
                     compras_dia_ip: Decimal, compras_dia_gd: Decimal,
                     ventas_mes: Decimal, cobros_mes: dict, saldo_mes: Decimal,
                     compras_mes_ip: Decimal, compras_mes_gd: Decimal,
                     saldo_anual: Decimal) -> str:
    ddmmyyyy = rep_date.strftime("%d-%m-%Y")
    L = []
    L.append(f"📅 INFORME DEL DÍA: {ddmmyyyy}")
    L.append("")

    # Día
    L.append("📊 RESUMEN DEL DÍA")
    L.append(f"• 🧾 Ventas del día: {money(ventas_dia)}")
    L.append(f"• 💵 Efectivo del día: {money(cobros_dia['EFECTIVO'])}")
    L.append(f"• 🔁 Transferencia: {money(cobros_dia['TRANSFERENCIA'])}")
    L.append(f"• 💳 TC/TD (y cheque): {money(cobros_dia['TC_TD_CHEQUE'])}")
    L.append(f"• 📥 Total ingreso del día: {money(cobros_dia['TOTAL'])}")
    L.append(f"• 🧮 Saldo del día: {money(saldo_dia)}")
    L.append("")
    L.append("🛒 COMPRAS DEL DÍA")
    L.append(f"  • 📦 Insumos y Productos: {money(compras_dia_ip)}")
    L.append(f"  • 🌼 Gastos Daisy: {money(compras_dia_gd)}")

    # Dos saltos entre Día y Mes
    L.append("")
    L.append("")

    # Mes
    L.append("📈 RESUMEN DEL MES")
    L.append(f"• 🧾 Ventas del mes: {money(ventas_mes)}")
    L.append(f"• 💵 Efectivo del mes: {money(cobros_mes['EFECTIVO'])}")
    L.append(f"• 🔁 Transferencia del mes: {money(cobros_mes['TRANSFERENCIA'])}")
    L.append(f"• 💳 TC/TD del mes: {money(cobros_mes['TC_TD_CHEQUE'])}")
    L.append(f"• 📥 Total ingreso del mes: {money(cobros_mes['TOTAL'])}")
    L.append(f"• 🧮 Saldo del mes: {money(saldo_mes)}")
    L.append("")
    L.append("🛒 COMPRAS DEL MES")
    L.append(f"  • 📦 Insumos y Productos: {money(compras_mes_ip)}")
    L.append(f"  • 🌼 Gastos Daisy: {money(compras_mes_gd)}")
    L.append("")
    L.append(f"🏦 SALDO ANUAL: {money(saldo_anual)}")

    return "\n".join(L)


def _imap_append_to_sent(raw_bytes: bytes):
    if os.getenv("IMAP_SAVE_SENT", "false").lower() not in ("1","true","yes","y"):
        return
    host = os.getenv("IMAP_HOST", "imap.gmail.com")
    port = int(os.getenv("IMAP_PORT", "993"))
    user = os.getenv("IMAP_USER")
    password = os.getenv("IMAP_PASS")
    sent_box = os.getenv("IMAP_SENT_FOLDER", "[Gmail]/Sent Mail")
    if not (host and user and password):
        return  # no config IMAP, salteamos
    with imaplib.IMAP4_SSL(host, port) as M:
        M.login(user, password)
        M.append(sent_box, "\\Seen", imaplib.Time2Internaldate(time.time()), raw_bytes)
        M.logout()

def send_email(subject: str, body: str, to_addr: str):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    sender = os.getenv("SMTP_FROM", user or "noreply@example.com")

    import smtplib
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    if os.getenv("SMTP_TLS", "true").lower() in ("1","true","yes","y") and port in (587, 25):
        with smtplib.SMTP(host, port) as s:
            s.ehlo()
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP_SSL(host, port) as s:
            s.login(user, password)
            s.send_message(msg)

    # Guardar copia en Enviados (si está configurado)
    try:
        _imap_append_to_sent(msg.as_bytes())
    except Exception:
        pass

# ---------------- main ----------------
def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Enviar Informe del día (PostgreSQL)")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (por defecto: hoy)")
    p.add_argument("--tz", default=os.getenv("REPORT_TZ","America/Asuncion"))
    p.add_argument("--to", default=os.getenv("SMTP_TO","Daisy Ramírez <dradaisyramirez@gmail.com>"))
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)

    rep_date = datetime.strptime(a.date, "%Y-%m-%d").date() if a.date else asu_now(a.tz).date()
    d1, d2 = period_day(rep_date)
    m1, m2 = period_month(rep_date)

    try:
        ventas_dia = sum_ventas(d1, d2)
        ventas_mes = sum_ventas(m1, m2)

        cobros_dia = sum_cobros_por_fp(d1, d2)
        cobros_mes = sum_cobros_por_fp(m1, m2)

        saldo_dia = sum_saldo_periodo(d1, d2)
        saldo_mes = sum_saldo_periodo(m1, m2)
        saldo_anual = sum_saldo_year(rep_date)

        compras_dia_ip = sum_compras_insumos_productos(d1, d2)
        compras_mes_ip = sum_compras_insumos_productos(m1, m2)
        compras_dia_gd = sum_gastos_daisy(d1, d2)
        compras_mes_gd = sum_gastos_daisy(m1, m2)

        body = build_email_text(rep_date, ventas_dia, cobros_dia, saldo_dia,
                                compras_dia_ip, compras_dia_gd,
                                ventas_mes, cobros_mes, saldo_mes,
                                compras_mes_ip, compras_mes_gd,
                                saldo_anual)
        subject = f"Informe del día: {rep_date.strftime('%d-%m-%Y')}"
        if a.dry_run:
            print(subject); print("="*len(subject)); print(body)
        else:
            send_email(subject, body, a.to); print(f"OK: Informe enviado a {a.to}")
    except Exception as ex:
        print("ERROR durante el envío del informe:", ex, file=sys.stderr)
        traceback.print_exc(); sys.exit(1)

if __name__ == "__main__":
    main()
