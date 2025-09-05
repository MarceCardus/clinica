# ui/informe_cobros_form.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox
)
from PyQt5.QtCore import QDate, Qt

from services.informes_cobros_service import (
    obtener_informe_cobros,
    obtener_informe_cobros_detallado
)

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet

import os
import sys
import datetime
from decimal import Decimal


# --- helpers locales (sólo para sumar/mostrar) ---
def _num(s) -> Decimal:
    if s is None:
        return Decimal(0)
    if isinstance(s, (int, float, Decimal)):
        return Decimal(str(s))
    t = str(s).strip().replace('.', '').replace(' ', '')
    t = t.replace(',', '.')
    try:
        return Decimal(t)
    except Exception:
        return Decimal(0)

def _fmt_miles(x) -> str:
    try:
        v = int(round(_num(x)))
    except Exception:
        v = 0
    return f"{v:,}".replace(",", ".")


class InformeCobrosForm(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Informe de Cobros")
        self.resize(1200, 700)
        layout = QVBoxLayout(self)

        # Filtros de fecha
        filtro_layout = QHBoxLayout()
        filtro_layout.addWidget(QLabel("Desde:"))
        self.date_desde = QDateEdit(QDate.currentDate())
        self.date_desde.setCalendarPopup(True)
        filtro_layout.addWidget(self.date_desde)
        filtro_layout.addWidget(QLabel("Hasta:"))
        self.date_hasta = QDateEdit(QDate.currentDate())
        self.date_hasta.setCalendarPopup(True)
        filtro_layout.addWidget(self.date_hasta)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(self.buscar)
        filtro_layout.addWidget(self.btn_buscar)

        self.btn_exportar = QPushButton("Exportar PDF")
        self.btn_exportar.clicked.connect(self.exportar_pdf_resumen)
        filtro_layout.addWidget(self.btn_exportar)

        self.btn_exportar_det = QPushButton("PDF Detalles")
        self.btn_exportar_det.clicked.connect(self.exportar_pdf_detallado)
        filtro_layout.addWidget(self.btn_exportar_det)

        layout.addLayout(filtro_layout)

        # Tabla de resultados (resumen)
        self.tabla = QTableWidget()
        layout.addWidget(self.tabla)

        # Footer de totales
        self.lbl_footer = QLabel()
        layout.addWidget(self.lbl_footer)

    def buscar(self):
        desde = self.date_desde.date().toPyDate()
        hasta = self.date_hasta.date().toPyDate()
        datos = obtener_informe_cobros(self.session, desde, hasta)
        self.mostrar_resultados(datos)

    def mostrar_resultados(self, datos):
        filas = datos.get("filas_cobros", [])
        self.tabla.setRowCount(len(filas))
        self.tabla.setColumnCount(8)
        self.tabla.setHorizontalHeaderLabels(
            ["Factura", "Cliente", "Fecha Factura", "Fecha Cobro", "Total", "Pagado", "Saldo", "Forma"]
        )

        for i, fila in enumerate(filas):
            self.tabla.setItem(i, 0, QTableWidgetItem(str(fila.get("factura", ""))))
            self.tabla.setItem(i, 1, QTableWidgetItem(str(fila.get("cliente", ""))))
            self.tabla.setItem(i, 2, QTableWidgetItem(str(fila.get("fecha_factura", ""))))
            self.tabla.setItem(i, 3, QTableWidgetItem(str(fila.get("fecha_cobro", ""))))
            self.tabla.setItem(i, 4, QTableWidgetItem(str(fila.get("total_factura", ""))))
            self.tabla.setItem(i, 5, QTableWidgetItem(str(fila.get("pagado", ""))))
            self.tabla.setItem(i, 6, QTableWidgetItem(str(fila.get("saldo", ""))))
            self.tabla.setItem(i, 7, QTableWidgetItem(str(fila.get("forma", ""))))
            for col in (4, 5, 6):
                item = self.tabla.item(i, col)
                if item:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # sumatorias del service
        sumatorias = datos.get("sumatorias_forma", {})

        alias = {
            "Efectivo": ["Efectivo"],
            "Transf.":  ["Transferencia", "Transf.", "Transf", "Transfer"],
            "Cheque":   ["Cheque"],
            "TC":       ["T. Crédito", "T Crédito", "TC", "Tarjeta Crédito", "Tarjeta de Crédito"],
            "TD":       ["T. Débito", "T Debito", "TD", "Tarjeta Débito", "Tarjeta de Débito"],
        }
        def _sum_keys(keys):
            return _fmt_miles(sum((_num(sumatorias.get(k)) for k in keys if sumatorias.get(k) is not None), Decimal(0)))

        total_ingreso = datos.get("total_ingreso", "0")
        total_saldo = _fmt_miles(sum((_num(f.get("saldo")) for f in filas), Decimal(0)))

        partes = [
            f"Efectivo: {_sum_keys(alias['Efectivo'])}",
            f"Transf.: {_sum_keys(alias['Transf.'])}",
            f"Cheque: {_sum_keys(alias['Cheque'])}",
            f"TC: {_sum_keys(alias['TC'])}",
            f"TD: {_sum_keys(alias['TD'])}",
        ]
        footer = "Totales: " + ",  ".join(partes) + f"    T. Ingreso: {total_ingreso}    T. Saldo: {total_saldo}"
        self.lbl_footer.setText(footer)

        self.tabla.setSortingEnabled(True)
        self.tabla.horizontalHeader().setStretchLastSection(True)


    # ---------------- PDF (RESUMEN) ----------------
    def exportar_pdf_resumen(self):
        desde = self.date_desde.date().toPyDate()
        hasta = self.date_hasta.date().toPyDate()
        datos = obtener_informe_cobros(self.session, desde, hasta)

        filas = datos.get("filas_cobros", datos.get("contado", []))
        sumatorias = datos.get("sumatorias_forma", {})
        anulaciones_ventas = datos.get("anulaciones_ventas", [])
        anulaciones_cobros = datos.get("anulaciones_cobros", [])
        total_ingreso = datos.get("total_ingreso", "0")

        now = datetime.datetime.now()
        path = f"informe_cobro_{now:%Y%m%d_%H%M%S}.pdf"
        exportar_cobros_pdf_resumen(
            filas, sumatorias, desde, hasta,
            anulaciones_ventas, anulaciones_cobros,
            total_ingreso,
            path
        )
        QMessageBox.information(self, "Exportar PDF", f"Informe exportado a {path}")

    # ---------------- PDF (DETALLADO) ----------------
    def exportar_pdf_detallado(self):
        desde = self.date_desde.date().toPyDate()
        hasta = self.date_hasta.date().toPyDate()
        res = obtener_informe_cobros_detallado(self.session, desde, hasta)

        now = datetime.datetime.now()
        path = f"informe_cobros_detallado_{now:%Y%m%d_%H%M%S}.pdf"
        exportar_cobros_pdf_detallado(res, desde, hasta, path)
        QMessageBox.information(self, "Exportar PDF", f"Informe exportado a {path}")


# ---------------- Implementación PDFs ----------------

def _logo_flowable():
    base_dir = getattr(sys, "_MEIPASS", os.getcwd())
    for fname in ["logo_grande.jpg", "logo.png", "logo_reporte.jpg", "logo_reporte.png"]:
        p = os.path.join(base_dir, "imagenes", fname)
        if os.path.exists(p):
            return Image(p, width=60*mm, height=25*mm)
    return None


def exportar_cobros_pdf_resumen(datos, sumatorias, desde, hasta,
                                anulaciones_ventas, anulaciones_cobros,
                                total_ingreso="0",
                                path_pdf="informe_cobros.pdf"):
    # --- márgenes en mm ---
    M = 12 * mm  # probá 8–15 mm a gusto
    page_w, page_h = landscape(A4)
    doc = SimpleDocTemplate(
        path_pdf, pagesize=(page_w, page_h),
        leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=M
    )
    W = page_w - doc.leftMargin - doc.rightMargin
    elements = []
    styles = getSampleStyleSheet()
    styleN = styles["Normal"]
    styleH = styles["Heading1"]

    lg = _logo_flowable()
    if lg:
        elements.append(lg)
    elements.append(Paragraph("<b>INFORME DE COBROS</b>", styleH))
    elements.append(Paragraph(f"Desde: {desde.strftime('%d/%m/%Y')}  Hasta: {hasta.strftime('%d/%m/%Y')}", styleN))
    elements.append(Spacer(1, 8))

    encabezado = ["Factura", "Cliente", "Fch Factura", "Fch Cobro", "Total", "Pagado", "Saldo", "Forma"]
    data = [encabezado]

    from datetime import datetime as _dt
    def _ff(s: str) -> str:
        if not s:
            return s
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y"):
            try:
                return _dt.strptime(s, fmt).strftime("%d-%m-%y")
            except Exception:
                pass
        return s

    for fila in datos:
        data.append([
            fila.get("factura", ""),
            fila.get("cliente", ""),
            _ff(fila.get("fecha_factura", "")),
            _ff(fila.get("fecha_cobro", "")),
            fila.get("total_factura", ""),
            fila.get("pagado", ""),
            fila.get("saldo", ""),
            fila.get("forma", "")
        ])

    alias = {
        "Efectivo": ["Efectivo"],
        "Transferencia": ["Transferencia", "Transf.", "Transf", "Transfer"],
        "Cheque": ["Cheque"],
        "T. Crédito": ["T. Crédito", "T Crédito", "TC", "Tarjeta Crédito", "Tarjeta de Crédito"],
        "T. Débito": ["T. Débito", "T Debito", "TD", "Tarjeta Débito", "Tarjeta de Débito"],
    }
    def _sum_keys(keys):
        return _fmt_miles(sum((_num(sumatorias.get(k)) for k in keys if sumatorias.get(k) is not None), Decimal(0)))

    total_saldo = _fmt_miles(sum((_num(f.get("saldo")) for f in datos), Decimal(0)))

    partes = [
        f"Efectivo: {_sum_keys(alias['Efectivo'])}",
        f"Transf.: {_sum_keys(alias['Transferencia'])}",
        f"Cheque: {_sum_keys(alias['Cheque'])}",
        f"TC: {_sum_keys(alias['T. Crédito'])}",
        f"TD: {_sum_keys(alias['T. Débito'])}",
    ]
    totales = "  ".join(partes) + f"    T. Ingreso: {total_ingreso}" + f"    T. Saldo: {total_saldo}"
    data.append([""] * 7 + [f"Totales: {totales}"])

    t = Table(
        data,
        colWidths=[
            W*0.09,  # Factura
            W*0.26,  # Cliente
            W*0.09,  # Fch Factura
            W*0.09,  # Fch Cobro
            W*0.12,  # Total
            W*0.12,  # Pagado
            W*0.11,  # Saldo
            W*0.12,  # Forma
        ]
    )
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#175ca4")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (4,1), (-2,-2), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        ('GRID', (0,0), (-1,-2), 0.7, colors.grey),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#eaf1fb")),
        ('SPAN', (0,-1), (6,-1)),
        ('ALIGN', (7,-1), (7,-1), 'RIGHT'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,-1), (-1,-1), 10),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 18))

    # (Opcional) Ventas anuladas / Cobros anulados
    if anulaciones_ventas:
        elements.append(Paragraph("<b>Ventas Anuladas</b>", styleN))
        encabezado_anul = ["ID Venta", "Factura", "Cliente", "Monto", "Observación"]
        data_anul = [encabezado_anul]
        for v in anulaciones_ventas:
            data_anul.append([
                v.get("idventa", ""), v.get("factura", ""), v.get("cliente", ""),
                v.get("monto", ""), v.get("motivo", "")
            ])
        t_anul = Table(data_anul, colWidths=[50, 60, 120, 60, 180])
        t_anul.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#c62828")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (3,1), (3,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        elements.append(t_anul)
        elements.append(Spacer(1, 12))

    if anulaciones_cobros:
        elements.append(Paragraph("<b>Cobros Anulados</b>", styleN))
        encabezado_cobros = ["ID Cobro", "Fch Cobro", "Cliente", "Monto", "Observación"]
        data_cobros = [encabezado_cobros]
        for c in anulaciones_cobros:
            data_cobros.append([
                c.get("idcobro", ""), c.get("fecha", ""),
                c.get("cliente", ""), c.get("monto", ""), c.get("motivo", "")
            ])
        t_cobros = Table(data_cobros, colWidths=[60, 70, 150, 80, 250])
        t_cobros.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#b26a00")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (3,1), (3,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 11),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            ('GRID', (0,0), (-1,-1), 0.7, colors.grey),
        ]))
        elements.append(t_cobros)

    doc.build(elements)
    return path_pdf


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

    # Helper separador delgado
    def _hr():
        t = Table([[""]], colWidths=[W])
        t.setStyle(TableStyle([('LINEBELOW', (0,0), (-1,-1), 0.25, colors.HexColor("#d0d5dd"))]))
        return t

    # Ventas
    for v in res.get("ventas", []):
        cab = (f"<b>ID:</b> {v.get('idventa','')}   "
               f"<b>Fecha:</b> {v.get('fecha_venta','')}   "
               f"<b>N° Fact:</b> {v.get('factura','') or '-'}   "
               f"<b>Cliente:</b> {v.get('cliente','')}")
        elements.append(Paragraph(cab, styleB))
        elements.append(Spacer(1, 4))

        data = [["Código", "Descripción", "Cant.", "Precio", "Subtotal"]]
        for it in v.get("items", []):
            data.append([
                it.get("codigo",""),
                it.get("descripcion",""),
                it.get("cantidad",""),
                f"Gs {it.get('precio','')}",
                f"Gs {it.get('subtotal','')}",
            ])
        # Fila total
        data.append(["", "", "", Paragraph("<b>Total Venta</b>", styleN), Paragraph(f"<b>Gs {v.get('total_venta','')}</b>", styleN)])

        t = Table(
            data,
            colWidths=[W*0.14, W*0.46, W*0.09, W*0.15, W*0.16]
            #  cód      descr        cant     precio   subtotal
        )
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-2), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e9edf7")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (2,1), (2,-1), 'CENTER'),
            ('ALIGN', (3,1), (4,-2), 'RIGHT'),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#eaf6e5")),
            ('ALIGN', (3,-1), (4,-1), 'RIGHT'),
            ('FONTNAME', (3,-1), (4,-1), 'Helvetica-Bold'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 6))

        # Pagos
        elements.append(Paragraph("<b>Pagos:</b>", styleN))
        pagos = v.get("pagos", [])
        if pagos:
            for p in pagos:
                elements.append(Paragraph(f"• {p['forma']} — {p['fecha']} — Gs {p['monto']}", styleN))
        else:
            elements.append(Paragraph("• (sin pagos en el período)", styleN))
        elements.append(Paragraph(f"<b>Saldo pendiente:</b> Gs {v.get('saldo','0')}", styleN))

        elements.append(Spacer(1, 8))
        elements.append(_hr())
        elements.append(Spacer(1, 10))

    # Totales del período
    elements.append(Paragraph("<b>Totales del período</b>", styleH))
    elements.append(Spacer(1, 6))

    suma = res.get("sumatorias_forma", {}) or {}
    data_totales = [
        ["Ventas con cobros", str(res.get("cant_ventas", 0))],
        ["Total cobrado",    f"Gs {res.get('total_cobrado','0')}"],
        ["Efectivo",         f"Gs {suma.get('Efectivo','0')}"],
        ["Transferencia",    f"Gs {suma.get('Transferencia','0')}"],
        ["Cheque",           f"Gs {suma.get('Cheque','0')}"],
        ["T. Crédito",       f"Gs {suma.get('T. Crédito','0')}"],
        ["T. Débito",        f"Gs {suma.get('T. Débito','0')}"],
        # NUEVAS filas solicitadas:
        ["Venta",            f"Gs {res.get('total_ventas_periodo','0')}"],
        ["Saldo",            f"Gs {res.get('total_saldo_periodo','0')}"],
    ]
    t_tot = Table(data_totales, colWidths=[W*0.5, W*0.5])
    t_tot.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e9edf7")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
    ]))
    elements.append(t_tot)

    doc.build(elements)
    return path_pdf
