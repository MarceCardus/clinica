# printing/factura_txt.py
from decimal import Decimal
from datetime import date

# ===== Layout compacto y columnas =====
DEFAULT_LAYOUT = {
    "width": 40,          # ANCHO CHICO (ajustable)
    "row_offset": 0,
    "col_offset": 0,

    # Cabecera
    "row_fecha": 0,
    "row_cliente": 2,
    "row_ruc": 3,
    "row_tel": 4,
    "row_dir": 5,

    # Detalle
    "row_det_ini": 8,     # primera línea del detalle
    "detail_max_rows": 10,
    "col_num": 0,         # N°
    "col_desc": 2,        # Descripción empieza acá
    "col_unit": 23,       # Unitario (derecha aprox)
    "col_total": 32,      # Total por ítem (derecha)

    # Totales
    "row_totales": 22,
    "col_label_tot": 0,
    "col_val_tot": 30,

    # Letras + condición
    "row_letras": 26,
    "row_condicion": 29,
}

# ========= utilidades =========
def _pad(n): return " " * max(0, n)

def _off(txt, L):
    col = L.get("col_offset", 0)
    return (" " * col + txt) if col > 0 else txt[max(0, -col):]

def _fmt_int(n) -> str:
    try: i = int(Decimal(n))
    except Exception: i = 0
    return f"{i:,}".replace(",", ".")

def _fmt_unit(n) -> str:
    try: d = Decimal(n)
    except Exception: d = Decimal(0)
    entero = int(d)
    dec = int((d - entero) * 100) if d != entero else 0
    return f"{_fmt_int(entero)}.{dec:02d}"

def _wrap(texto: str, ancho: int):
    """Partir texto en 'ancho' sin cortar palabras si se puede."""
    t = (texto or "").replace("\n", " ").strip()
    out, cur = [], ""
    for palabra in t.split():
        if not cur:
            cur = palabra
        elif len(cur) + 1 + len(palabra) <= ancho:
            cur += " " + palabra
        else:
            out.append(cur)
            cur = palabra
    if cur:
        out.append(cur)
    if not out:
        out = [""]
    return out

def _en_letras(numero: Decimal):
    unidades = ["", "UNO", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
    decenas = ["", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA",
               "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
    centenas = ["", "CIEN", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS",
                "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]
    try: n = int(Decimal(numero))
    except Exception: n = 0
    if n == 0: return "CERO"
    if n > 999999: return f"{n:,}".replace(",", ".")
    c = n // 100; d = (n % 100) // 10; u = n % 10
    partes = [centenas[c], decenas[d], unidades[u]]
    return " ".join(p for p in partes if p)

# ========= composición del TXT =========
def render_factura_txt(venta, layout=None):
    L = (layout or DEFAULT_LAYOUT).copy()
    W = L["width"]
    lines = []

    def put(row, txt):
        row += L.get("row_offset", 0)
        while len(lines) <= row:
            lines.append("")
        lines[row] = _off(txt[:W], L)

    # Cabecera (compacta)
    fecha_txt = venta.fecha.strftime("%d/%m/%Y") if isinstance(venta.fecha, date) else ""
    put(L["row_fecha"], fecha_txt)

    pac = getattr(venta, "paciente", None)
    nombre = (getattr(pac, "nombre", "") or "").strip()
    apellido = (getattr(pac, "apellido", "") or "").strip()
    cliente = f"{apellido} {nombre}".strip()
    ruc = (getattr(pac, "ruc", "") or getattr(pac, "ci", "") or "").strip()
    tel = (getattr(pac, "telefono", "") or "").strip()
    direccion = (getattr(pac, "direccion", "") or "").strip()

    put(L["row_cliente"], f"Cliente: {cliente}")
    put(L["row_ruc"],     f"RUC/C.I.: {ruc}")
    put(L["row_tel"],     f"Tel: {tel}")
    put(L["row_dir"],     f"Dirección: ")

    # Detalle con WRAP en columna de descripción
    total_general = Decimal(0)
    row = L["row_det_ini"]
    max_rows = L["detail_max_rows"]

    desc_width = max(0, L["col_unit"] - L["col_desc"] - 1)  # ancho de la columna descripción

    for idx, det in enumerate(venta.detalles[:max_rows], start=1):
        cant = int(Decimal(getattr(det, "cantidad", 0)))
        precio = Decimal(getattr(det, "preciounitario", 0))
        total = precio * cant
        total_general += total

        desc = (getattr(det, "item", None) and getattr(det.item, "nombre", "")) or ""
        for j, chunk in enumerate(_wrap(desc, desc_width)):
            if j == 0:
                # primera línea: N°, desc, unitario, total
                txt = f"{idx}"
                # hasta descripción
                if len(txt) < L["col_desc"]:
                    txt += _pad(L["col_desc"] - len(txt))
                txt += chunk
                # hasta unitario
                if len(txt) < L["col_unit"]:
                    txt += _pad(L["col_unit"] - len(txt))
                txt += _fmt_unit(precio)
                # hasta total
                if len(txt) < L["col_total"]:
                    txt += _pad(L["col_total"] - len(txt))
                txt += _fmt_int(total)
                put(row, txt)
            else:
                # líneas envueltas: sólo descripción con indent
                txt = _pad(L["col_desc"]) + chunk
                put(row, txt)
            row += 1

    # Relleno visual hasta completar bloque de detalle (opcional)
    while (row - L["row_det_ini"]) < max_rows:
        put(row, "")
        row += 1

    # Totales
    iva10 = int(round(float(total_general) / 11.0))
    rt = L["row_totales"]
    put(rt + 0, ("SUBTOTAL".ljust(L["col_val_tot"])) + _fmt_int(total_general))
    put(rt + 1, ("IVA 10%".ljust(L["col_val_tot"])) + _fmt_int(iva10))
    put(rt + 2, ("TOTAL".ljust(L["col_val_tot"])) + _fmt_int(total_general))

    # Total en letras en 2 líneas si no entra
    letras = f"Total en letras: {_en_letras(total_general)}"
    wrap_letras = _wrap(letras, W)
    put(L["row_letras"], wrap_letras[0])
    if len(wrap_letras) > 1:
        put(L["row_letras"] + 1, wrap_letras[1])

    # Condición (sin X)
    saldo = getattr(venta, "saldo", None)
    es_contado = True if saldo is None else (Decimal(saldo) == 0)
    condicion = f"Condición de Venta: Contado  Crédito"
    put(L["row_condicion"], condicion)

    return "\n".join(lines)

# ========= impresión directa (Windows RAW) =========
def print_text_windows(text: str, printer_name: str, condensed=True):
    """
    Envía texto a impresora Windows (RAW). Si 'condensed'=True, activa letra chica
    (modo condensado 17 cpi) usando SI (0x0F) y cancela con DC2 (0x12).
    Requiere pywin32:  pip install pywin32
    """
    try:
        import win32print
    except Exception as e:
        raise RuntimeError("pywin32 no está instalado. Instalá 'pywin32' para imprimir.") from e

    # Secuencias ESC para matriciales/ESC-P (funciona en la mayoría)
    if condensed:
        text = "\x0F" + text + "\x12"   # SI (on) ... DC2 (off)

    h = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(h, 1, ("Factura TXT", None, "RAW"))
        try:
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, text.encode("utf-8"))
            win32print.EndPagePrinter(h)
        finally:
            win32print.EndDocPrinter(h)
    finally:
        win32print.ClosePrinter(h)
