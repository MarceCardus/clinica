from decimal import Decimal
from datetime import date
import os
import time

try:
    import win32print
except ImportError:
    raise ImportError("La librería 'pywin32' es necesaria. Por favor, instálala ejecutando: pip install pywin32")

# ===== Layout Final =====
DEFAULT_LAYOUT = {
    "width": 60,
    "row_offset": 0,
    "col_offset": 0,
    "row_fecha": 0,
    "row_cliente": 2,
    "row_ruc_tel": 3,
    "row_dir": 4,
    "row_det_ini": 7,
    "detail_max_rows": 12,
    "col_cant": 4,
    "col_desc": 7,
    "col_unit": 38,
    "col_total": 48,
    "row_totales": 19,
    "col_val_tot": 48,
    "row_letras": 22,
    "row_condicion": 24,
}

# ========= utilidades =========
def _pad(n): return " " * max(0, n)

def _fmt_int(n) -> str:
    try: i = int(Decimal(n))
    except Exception: i = 0
    return f"{i:,}".replace(",", ".")

def _wrap(texto: str, ancho: int):
    # Función de wrap sin cambios
    t = (texto or "").replace("\n", " ").strip()
    out, cur = [], ""
    if ancho <= 0: return [t]
    for palabra in t.split():
        if not cur: cur = palabra
        elif len(cur) + 1 + len(palabra) <= ancho: cur += " " + palabra
        else:
            out.append(cur)
            cur = palabra
    if cur: out.append(cur)
    if not out: out = [""]
    return out

def numero_a_letras(numero):
    # Función de conversión a letras sin cambios
    if not (0 <= numero < 1000000000): return f"{numero:,}".replace(",", ".")
    if numero == 0: return "cero guaraníes"
    unidades=["", "un", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve"]
    decenas=["", "diez", "veinte", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]
    centenas=["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos", "setecientos", "ochocientos", "novecientos"]
    especiales={11:"once", 12:"doce", 13:"trece", 14:"catorce", 15:"quince"}
    def _c(n):
        if n==100: return "cien"
        c,d,u=n//100,(n%100)//10,n%10;res=[]
        if c>0: res.append(centenas[c])
        dv=n%100
        if d>0:
            if 10<dv<16:res.append(especiales[dv]);return " ".join(res)
            elif dv==10:res.append(decenas[d])
            elif d==2:res.append(f"veinti{unidades[u]}" if u>0 else "veinte")
            else:
                res.append(decenas[d])
                if u>0:res.append(f"y {unidades[u]}")
        elif u>0:res.append(unidades[u])
        return " ".join(res)
    m,k,r=numero//1000000,(numero%1000000)//1000,numero%1000;p=[]
    if m>0:p.append("un millón" if m==1 else f"{_c(m)} millones")
    if k>0:p.append("mil" if k==1 else f"{_c(k)} mil")
    if r>0:p.append(_c(r))
    return f"{' '.join(p)} guaraníes"

# ========= composición del TXT (VERSIÓN FINAL) =========
def render_factura_txt(venta, layout=None):
    L = (layout or DEFAULT_LAYOUT).copy()
    W = L["width"]
    lines = {i: "" for i in range(30)}

    def put(row, txt):
        lines[row] = (txt + " " * W)[:W]

    # --- Cabecera (sin cambios) ---
    fecha_txt = venta.fecha.strftime("%d/%m/%Y") if isinstance(venta.fecha, date) else ""
    put(L["row_fecha"], fecha_txt)
    pac = getattr(venta, "paciente", None)
    cliente = f"Cliente: {(getattr(pac, 'apellido', '') or '').strip()} {(getattr(pac, 'nombre', '') or '').strip()}"
    ruc = f"RUC/C.I.: {(getattr(pac, 'ruc', '') or getattr(pac, 'ci', '') or '').strip()}"
    tel = f"Tel: {(getattr(pac, 'telefono', '') or '').strip()}"
    put(L["row_cliente"], cliente)
    put(L["row_ruc_tel"], f"{ruc.ljust(25)} {tel.ljust(18)}")
    put(L["row_dir"], "Dirección: ")

    # --- Detalle (CON LÓGICA DE WRAP MEJORADA) ---
    total_general = Decimal(0)
    row = L["row_det_ini"]
    desc_width = L['col_unit'] - L['col_desc'] - 1 # Ancho disponible para descripción

    for det in venta.detalles[:L["detail_max_rows"]]:
        cant = int(Decimal(getattr(det, "cantidad", 0)))
        precio = Decimal(getattr(det, "preciounitario", 0))
        total = precio * cant
        total_general += total
        desc = (getattr(det, "item", None) and getattr(det.item, "nombre", "")) or ""
        
        cant_str = str(cant)
        unit_str = _fmt_int(precio)
        total_str = _fmt_int(total)
        
        desc_chunks = _wrap(desc, desc_width)
        
        # Imprimir primera línea con todos los datos
        desc_primera_linea = desc_chunks[0] if desc_chunks else ""
        part1 = f"{_pad(L['col_cant'])}{cant_str}{_pad(1)}"
        linea = f"{part1.ljust(L['col_desc'])}{desc_primera_linea}"
        
        padding1 = L['col_unit'] - len(linea) - len(unit_str)
        if padding1 < 0: # Si el texto se pasó, se trunca
            linea = linea[:L['col_unit'] - len(unit_str) -1]
            padding1 = 1
        linea = f"{linea}{_pad(padding1)}{unit_str}"
        
        padding2 = L['col_total'] - len(linea) - len(total_str)
        linea = f"{linea}{_pad(padding2)}{total_str}"
        put(row, linea)
        row += 1

        # Imprimir líneas adicionales de descripción si las hay
        for chunk in desc_chunks[1:]:
            put(row, f"{_pad(L['col_desc'])}{chunk}")
            row += 1

    # --- Totales (CON ALINEACIÓN RÍGIDA MEJORADA) ---
    rt = L["row_totales"]
    indent = _pad(L['col_desc'])
    for i, (label, value) in enumerate([
        ("SUBTOTAL", _fmt_int(total_general)),
        ("IVA 10%", _fmt_int(round(float(total_general) / 11.0))),
        ("TOTAL", _fmt_int(total_general))
    ]):
        label_part = f"{indent}{label}"
        linea_total = f"{label_part.ljust(L['col_val_tot'] - len(value))}{value}"
        put(rt + i, linea_total)

    total_en_letras = numero_a_letras(int(total_general))
    put(L["row_letras"], f"Total en letras: {total_en_letras}")
    put(L["row_condicion"], "Condición de Venta: Contado")

    final_lines = [lines.get(i, "") for i in range(max(lines.keys()) + 1)]
    return "\n".join(final_lines)

# ========= MÉTODO DE IMPRESIÓN DEFINITIVO =========
def print_file_by_name(filepath: str, printer_name: str):
    # Función de impresión sin cambios
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"El archivo de factura no se encontró en: {filepath}")
    original_printer = None
    try:
        original_printer = win32print.GetDefaultPrinter()
        win32print.SetDefaultPrinter(printer_name)
        os.startfile(filepath, "print")
        time.sleep(4)
    except Exception as e:
        raise RuntimeError(f"No se pudo imprimir en '{printer_name}'. Error: {e}")
    finally:
        if original_printer:
            win32print.SetDefaultPrinter(original_printer)