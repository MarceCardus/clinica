# utils/pdf_generator.py

import os
import sys
from decimal import Decimal
from datetime import datetime as _dt

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet

# (Aquí irían tus helpers _num, _fmt_miles si los necesitas para el PDF)

def _logo_flowable():
    base_dir = getattr(sys, "_MEIPASS", os.getcwd())
    for fname in ["logo_grande.jpg", "logo.png", "logo_reporte.jpg", "logo_reporte.png"]:
        p = os.path.join(base_dir, "imagenes", fname)
        if os.path.exists(p):
            return Image(p, width=60*mm, height=25*mm)
    return None

# Copiamos la función que genera el PDF detallado aquí
def exportar_cobros_pdf_detallado(res: dict, desde, hasta, path_pdf="informe_cobros_detallado.pdf"):
    M = 12 * mm
    page_w, page_h = A4
    doc = SimpleDocTemplate(
        path_pdf, pagesize=(page_w, page_h),
        leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=M
    )
    W = page_w - doc.leftMargin - doc.rightMargin
    elements = []
    styles = getSampleStyleSheet()
    styleN = styles["Normal"]
    styleH = styles["Heading1"]
    styleB = styles["BodyText"]

    lg = _logo_flowable()
    if lg:
        elements.append(lg)
    elements.append(Paragraph("<b>INFORME DE COBROS — Resumen Detallado</b>", styleH))
    elements.append(Paragraph(f"Período: {desde.strftime('%d/%m/%Y')} — {hasta.strftime('%d/%m/%Y')}", styleN))
    elements.append(Spacer(1, 8))

    # ... (El resto del código de la función exportar_cobros_pdf_detallado va aquí sin cambios)
    # ... (pego solo una parte para no ser redundante)
    
    # Ventas
    for v in res.get("ventas", []):
        cab = (f"<b>ID:</b> {v.get('idventa','')}   "
               f"<b>Fecha:</b> {v.get('fecha_venta','')}   "
               f"<b>N° Fact:</b> {v.get('factura','') or '-'}   "
               f"<b>Cliente:</b> {v.get('cliente','')}")
        elements.append(Paragraph(cab, styleB))
        # etc...

    # ... al final
    doc.build(elements)
    return path_pdf

# (También podés mover la función 'exportar_cobros_pdf_resumen' aquí si la necesitás)