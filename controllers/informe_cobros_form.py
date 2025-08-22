# controllers/informe_cobros_form.py
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QPushButton, QTableWidget, QTableWidgetItem, QMessageBox
from PyQt5.QtCore import QDate
from services.informes_cobros_service import obtener_informe_cobros
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
import os
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

        # Botón para exportar a PDF
        self.btn_exportar = QPushButton("Exportar PDF")
        self.btn_exportar.clicked.connect(self.exportar_pdf)
        filtro_layout.addWidget(self.btn_exportar)

        layout.addLayout(filtro_layout)

    # Tabla de resultados
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
        self.tabla.setHorizontalHeaderLabels(["Factura", "Cliente", "Fecha Factura", "Fecha Cobro", "Total", "Pagado", "Saldo", "Forma"])
        for i, fila in enumerate(filas):
            self.tabla.setItem(i, 0, QTableWidgetItem(str(fila.get("factura", ""))))
            self.tabla.setItem(i, 1, QTableWidgetItem(str(fila.get("cliente", ""))))
            self.tabla.setItem(i, 2, QTableWidgetItem(str(fila.get("fecha_factura", ""))))
            self.tabla.setItem(i, 3, QTableWidgetItem(str(fila.get("fecha_cobro", ""))))
            self.tabla.setItem(i, 4, QTableWidgetItem(str(fila.get("total_factura", ""))))
            self.tabla.setItem(i, 5, QTableWidgetItem(str(fila.get("pagado", ""))))
            self.tabla.setItem(i, 6, QTableWidgetItem(str(fila.get("saldo", ""))))
            self.tabla.setItem(i, 7, QTableWidgetItem(str(fila.get("forma", ""))))

        # Footer de totales por forma de pago (en QLabel debajo de la tabla)
        sumatorias = datos.get("sumatorias_forma", {})
        formas_posibles = ["Efectivo", "Transferencia", "Cheque", "T. Crédito", "T. Débito"]
        footer = "Totales: "
        partes = []
        for forma in formas_posibles:
            valor = sumatorias.get(forma, "0")
            partes.append(f"{forma}: {valor}")
        footer += ",  ".join(partes)
        self.lbl_footer.setText(footer)

    def exportar_pdf(self):
        import datetime
        desde = self.date_desde.date().toPyDate()
        hasta = self.date_hasta.date().toPyDate()
        datos = obtener_informe_cobros(self.session, desde, hasta)
        filas = datos.get("filas_cobros", datos.get("contado", []))
        sumatorias = datos["sumatorias_forma"]
        anulaciones_ventas = datos.get("anulaciones_ventas", [])
        anulaciones_cobros = datos.get("anulaciones_cobros", [])
        now = datetime.datetime.now()
        fecha_str = now.strftime("%Y%m%d")
        hora_str = now.strftime("%H%M%S")
        path = f"informe_cobro_{fecha_str}_{hora_str}.pdf"
        exportar_cobros_pdf(filas, sumatorias, desde, hasta, anulaciones_ventas, anulaciones_cobros, path)
        QMessageBox.information(self, "Exportar PDF", f"Informe exportado a {path}")
    
    # Mover la función fuera de la clase
def exportar_cobros_pdf(datos, sumatorias, desde, hasta, anulaciones_ventas, anulaciones_cobros, path_pdf="informe_cobros.pdf"):
    from reportlab.lib.pagesizes import landscape, A4
    doc = SimpleDocTemplate(path_pdf, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []
    styles = getSampleStyleSheet()
    styleN = styles["Normal"]
    styleH = styles["Heading1"]

    # Logo y título
    logo_path = os.path.join("imagenes", "logo_grande.jpg")
    if os.path.exists(logo_path):
        img = Image(logo_path, width=60*mm, height=25*mm)
        elements.append(img)
    elements.append(Paragraph("<b>INFORME DE COBROS</b>", styleH))
    elements.append(Paragraph(f"Desde: {desde.strftime('%d/%m/%Y')}  Hasta: {hasta.strftime('%d/%m/%Y')}", styleN))
    elements.append(Spacer(1, 8))

    # Tabla de cobros
    encabezado = ["Factura", "Cliente", "Fch Factura", "Fch Cobro", "Total", "Pagado", "Saldo", "Forma"]
    data = [encabezado]
    for fila in datos:
        # Formatear fechas a dd-MM-yy
        fecha_factura = fila.get("fecha_factura", "")
        fecha_cobro = fila.get("fecha_cobro", "")
        if fecha_factura:
            try:
                from datetime import datetime
                fecha_factura = datetime.strptime(fecha_factura, "%d/%m/%Y").strftime("%d-%m-%y")
            except Exception:
                pass
        if fecha_cobro:
            try:
                from datetime import datetime
                fecha_cobro = datetime.strptime(fecha_cobro, "%d/%m/%Y").strftime("%d-%m-%y")
            except Exception:
                pass
        data.append([
            fila.get("factura", ""),
            fila.get("cliente", ""),
            fecha_factura,
            fecha_cobro,
            fila.get("total_factura", ""),
            fila.get("pagado", ""),
            fila.get("saldo", ""),
            fila.get("forma", "")
        ])
    # Totales por forma de pago (todas)
    formas_posibles = ["Efectivo", "Transferencia", "Cheque", "T. Crédito", "T. Débito"]
    partes = []
    for forma in formas_posibles:
        valor = sumatorias.get(forma, "0")
        partes.append(f"{forma}: {valor}")
    totales = "  ".join(partes)
    data.append([""]*7 + [f"Totales: {totales}"])

    # Agrandar la grilla principal
    t = Table(data, colWidths=[60, 150, 70, 70, 80, 80, 80, 90])
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

    # Grilla de ventas anuladas
    if anulaciones_ventas:
        elements.append(Paragraph("<b>Ventas Anuladas</b>", styleN))
        encabezado_anul = ["ID Venta", "Factura", "Cliente", "Monto", "Observación"]
        data_anul = [encabezado_anul]
        for v in anulaciones_ventas:
            data_anul.append([
                v.get("idventa", ""),
                v.get("factura", ""),
                v.get("cliente", ""),
                v.get("monto", ""),
                v.get("motivo", "")
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

    # Grilla de cobros anulados
    if anulaciones_cobros:
        elements.append(Paragraph("<b>Cobros Anulados</b>", styleN))
        encabezado_cobros = ["ID Cobro", "Fch Cobro", "Cliente", "Monto", "Observación"]
        data_cobros = [encabezado_cobros]
        for c in anulaciones_cobros:
            # Formatear fecha a dd-MM-yy
            fecha_cobro = c.get("fecha", "")
            if fecha_cobro:
                try:
                    from datetime import datetime
                    fecha_cobro = datetime.strptime(fecha_cobro, "%d/%m/%Y").strftime("%d-%m-%y")
                except Exception:
                    pass
            data_cobros.append([
                c.get("idcobro", ""),
                fecha_cobro,
                c.get("cliente", ""),
                c.get("monto", ""),
                c.get("motivo", "")
            ])
        # Agrandar la grilla de cobros anulados para que sea igual a la principal
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