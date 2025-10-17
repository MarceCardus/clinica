# enviar_informe.py
import os, sys, traceback, re, unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import imaplib, time
from models.base import Base
from models.clinica import Clinica
from models.paciente import Paciente
from models.profesional import Profesional
from models.especialidad import Especialidad
from models.profesional_especialidad import ProfesionalEspecialidad
from models.usuario import Usuario
from models.producto import Producto
from models.paquete import Paquete
from models.paquete_producto import PaqueteProducto
from models.proveedor import Proveedor
from models.insumo import Insumo
from models.compra import Compra
from models.compra_detalle import CompraDetalle
from models.venta import Venta
from models.venta_detalle import VentaDetalle
from models.cobro import Cobro
from models.cobro_venta import CobroVenta
from models.venta_cuota import VentaCuota
from models.sesion import Sesion
from models.fotoavance import FotoAvance
from models.receta import Receta
from models.comisionprofesional import ComisionProfesional
from models.cajamovimiento import CajaMovimiento
from models.auditoria import Auditoria
from models.antecPatologico import AntecedentePatologicoPersonal
from models.antecEnfActual import AntecedenteEnfermedadActual
from models.antecFliar import AntecedenteFamiliar
from models.barrio import Barrio
from models.ciudad import Ciudad
from models.tipoproducto import TipoProducto
import models.departamento
import models.plan_sesiones
import models.plan_tipo
import models.agenda

# ---------------- util ----------------
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


def load_env():
    """Carga .env desde la carpeta del ejecutable y desde el cwd como fallback."""
    try:
        from dotenv import load_dotenv  # pip install python-dotenv
        base_dir = Path(
            getattr(
                sys,
                "_MEIPASS",
                Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent,
            )
        )
        load_dotenv(base_dir / ".env", override=False)
        load_dotenv(override=False)  # cwd
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


def period_day(d: date):
    return d, d


def period_month(d: date):
    first = date(d.year, d.month, 1)
    last = (date(d.year + (d.month // 12), (d.month % 12) + 1, 1) - timedelta(days=1))
    return first, last


def period_year(d: date):
    return date(d.year, 1, 1), date(d.year, 12, 31)


def D(x):
    if x is None:
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal("0")


def money(x: Decimal):
    q = D(x).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"Gs. {q:,.0f}".replace(",", ".")


# --- Normalización de forma de pago ---
def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_fp(fp: str) -> str:
    if not fp:
        return ""
    s = _strip_accents(str(fp)).upper()
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    tokens = set(s.split())

    if "EFECTIVO" in tokens or "CASH" in tokens or "CONTADO" in tokens:
        return "EFECTIVO"
    if any(w in s for w in ("TRANSFER", "TRANSF", "GIRO", "DEPOSITO", "DEPOSI")):
        return "TRANSFERENCIA"
    if "CHEQUE" in s or "CHEQ" in s:
        return "CHEQUE"
    if "TD" in tokens or "DEBITO" in s or "DEBIT" in s:
        return "TARJETA_DEBITO"
    if "TC" in tokens or "CREDITO" in s or "CREDIT" in s or "TARJETA" in tokens:
        return "TARJETA_CREDITO"
    return s


# ---------------- DB ----------------
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


def _make_engine():
    host = os.getenv("PGHOST", "181.1.152.126")
    port = int(os.getenv("PGPORT", "5433"))
    user = os.getenv("PGUSER", "Cardus")
    pwd = os.getenv("PGPASSWORD", "S@nguines--23")
    db = os.getenv("PGDATABASE", "consultorio")
    sslmode = os.getenv("PGSSLMODE", "prefer")

    url = URL.create(
        "postgresql+psycopg2",
        username=user,
        password=pwd,
        host=host,
        port=port,
        database=db,
        query={"sslmode": sslmode},
    )

    eng = create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args={"connect_timeout": 8, "application_name": "enviar_informe"},
    )
    return eng


ENGINE = _make_engine()


def _diag_connection():
    """Diagnóstico detallado de conectividad."""
    import socket
    from psycopg2 import connect as _pg_connect, OperationalError as _PGOpError

    url = ENGINE.url
    host = url.host or "localhost"
    port = int(url.port or 5432)

    print("=== DIAGNÓSTICO DE CONEXIÓN ===")
    print("DSN:", url.render_as_string(hide_password=True))
    print("Host:", host, "Port:", port)
    print("SSLMode:", url.query.get("sslmode"))

    try:
        addrs = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        resolved = sorted(set([a[4][0] for a in addrs]))
        print("DNS OK ->", resolved)
    except Exception as e:
        print("❌ DNS fallo:", repr(e))

    try:
        with socket.create_connection((host, port), timeout=5):
            print("TCP OK -> se pudo abrir socket a", host, port)
    except Exception as e:
        print("❌ TCP fallo:", repr(e))

    try:
        import psycopg2
        kwargs = {
            "host": host,
            "port": port,
            "dbname": url.database,
            "user": url.username,
            "password": url.password,
        }
        sslmode = url.query.get("sslmode")
        if sslmode:
            kwargs["sslmode"] = sslmode

        conn = _pg_connect(**kwargs)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        ver = cur.fetchone()[0]
        cur.close()
        conn.close()
        print("psycopg2 OK ->", ver)
    except _PGOpError as e:
        print("❌ psycopg2 OperationalError:", repr(e))
    except Exception as e:
        print("❌ psycopg2 error:", repr(e))

    try:
        with ENGINE.connect() as cx:
            cx.execute(text("SELECT 1"))
        print("SQLAlchemy OK -> SELECT 1")
    except Exception as e:
        print("❌ SQLAlchemy fallo:", repr(e))


# ---------------- consultas ----------------
def _vigente_venta_sql(alias="v"):
    return f"AND ({alias}.estadoventa IS NULL OR UPPER({alias}.estadoventa) NOT IN ('ANULADO','ANULADA'))"


def _vigente_cobro_sql(alias="c"):
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
    res = {
        "EFECTIVO": D(0),
        "TRANSFERENCIA": D(0),
        "TARJETA_CREDITO": D(0),
        "TARJETA_DEBITO": D(0),
        "CHEQUE": D(0),
        "OTROS": D(0),
        "TOTAL": D(0),
    }
    with ENGINE.begin() as cx:
        for medio, total in cx.execute(text(sql), {"d1": d1, "d2": d2}):
            s = D(total)
            key = norm_fp(medio or "")
            res[key] = res.get(key, D(0)) + s
            res["TOTAL"] += s
    return res


def sum_saldo_periodo(d1: date, d2: date) -> Decimal:
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
    return "COALESCE(cd.cantidad,0) * COALESCE(cd.preciounitario,0)"


def sum_compras_insumos_productos(d1: date, d2: date) -> Decimal:
    line = _line_expr()
    sql = f"""
    SELECT COALESCE(SUM({line}),0) total
    FROM compra_detalle cd
    JOIN compra c ON c.idcompra = cd.idcompra
    LEFT JOIN item i ON i.iditem = cd.iditem
    LEFT JOIN item_tipo t ON t.iditemtipo = i.iditemtipo
    WHERE c.fecha BETWEEN :d1 AND :d2
      AND COALESCE(c.anulada, FALSE) = FALSE
      AND (t.nombre IN ('PRODUCTO','INSUMO','AMBOS') OR cd.iditem IS NOT NULL)
    """
    with ENGINE.begin() as cx:
        return D(cx.execute(text(sql), {"d1": d1, "d2": d2}).scalar())


def sum_gastos_daisy(d1: date, d2: date) -> Decimal:
    line = _line_expr()
    sql = f"""
    SELECT COALESCE(SUM({line}),0) total
    FROM compra_detalle cd
    JOIN compra c ON c.idcompra = cd.idcompra
    LEFT JOIN item i ON i.iditem = cd.iditem
    WHERE c.fecha BETWEEN :d1 AND :d2
      AND COALESCE(c.anulada, FALSE) = FALSE
      AND ((i.nombre ILIKE 'Gastos Daisy%%') OR (cd.observaciones ILIKE 'Gastos Daisy%%'))
    """
    with ENGINE.begin() as cx:
        return D(cx.execute(text(sql), {"d1": d1, "d2": d2}).scalar())


# ---------------- email ----------------
from email.message import EmailMessage


def build_email_text(rep_date: date, ventas_dia: Decimal, cobros_dia: dict, saldo_dia: Decimal,
                     compras_dia_ip: Decimal, compras_dia_gd: Decimal,
                     ventas_mes: Decimal, cobros_mes: dict, saldo_mes: Decimal,
                     compras_mes_ip: Decimal, compras_mes_gd: Decimal,
                     saldo_anual: Decimal) -> str:
    ddmmyyyy = rep_date.strftime("%d-%m-%Y")
    L = []
    L.append(f"📅 INFORME DEL DÍA: {ddmmyyyy}\n")
    L.append("📊 RESUMEN DEL DÍA")
    L.append(f"• 🧾 Ventas del día: {money(ventas_dia)}")
    L.append(f"• 💵 Efectivo del día: {money(cobros_dia['EFECTIVO'])}")
    L.append(f"• 🔁 Transferencia: {money(cobros_dia['TRANSFERENCIA'])}")
    L.append(f"• 💳 T. Crédito: {money(cobros_dia['TARJETA_CREDITO'])}")
    L.append(f"• 💳 T. Débito: {money(cobros_dia['TARJETA_DEBITO'])}")
    L.append(f"• 🧾 Cheque: {money(cobros_dia['CHEQUE'])}")
    L.append(f"• 📥 Total ingreso del día: {money(cobros_dia['TOTAL'])}")
    L.append(f"• 🧮 Saldo del día: {money(saldo_dia)}")
    L.append("\n🛒 COMPRAS DEL DÍA")
    L.append(f"  • 📦 Insumos y Productos: {money(compras_dia_ip)}")
    L.append(f"  • 🌼 Gastos Daisy: {money(compras_dia_gd)}")
    L.append("\n📈 RESUMEN DEL MES")
    L.append(f"• 🧾 Ventas del mes: {money(ventas_mes)}")
    L.append(f"• 💵 Efectivo del mes: {money(cobros_mes['EFECTIVO'])}")
    L.append(f"• 🔁 Transferencia del mes: {money(cobros_mes['TRANSFERENCIA'])}")
    L.append(f"• 💳 T. Crédito del mes: {money(cobros_mes['TARJETA_CREDITO'])}")
    L.append(f"• 💳 T. Débito del mes: {money(cobros_mes['TARJETA_DEBITO'])}")
    L.append(f"• 🧾 Cheque del mes: {money(cobros_mes['CHEQUE'])}")
    L.append(f"• 📥 Total ingreso del mes: {money(cobros_mes['TOTAL'])}")
    L.append(f"• 🧮 Saldo del mes: {money(saldo_mes)}")
    L.append("\n🛒 COMPRAS DEL MES")
    L.append(f"  • 📦 Insumos y Productos: {money(compras_mes_ip)}")
    L.append(f"  • 🌼 Gastos Daisy: {money(compras_mes_gd)}")
    L.append(f"\n🏦 SALDO ANUAL: {money(saldo_anual)}")
    return "\n".join(L)


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

    if os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes", "y") and port in (587, 25):
        with smtplib.SMTP(host, port) as s:
            s.ehlo()
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP_SSL(host, port) as s:
            s.login(user, password)
            s.send_message(msg)


# ---------------- main ----------------
def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Enviar Informe del día (PostgreSQL)")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (por defecto: hoy)")
    p.add_argument("--tz", default=os.getenv("REPORT_TZ", "America/Asuncion"))
    p.add_argument("--to", default=os.getenv("SMTP_TO", "Daisy Ramírez <dradaisyramirez@gmail.com>"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--diag", action="store_true", help="Ejecuta diagnóstico de conexión y sale")
    a = p.parse_args(argv)

    if a.diag:
        _diag_connection()
        return

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
            print(subject)
            print("=" * len(subject))
            print(body)
        else:
            send_email(subject, body, a.to)
            print(f"OK: Informe enviado a {a.to}")
    except Exception as ex:
        print("ERROR durante el envío del informe:", ex, file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
