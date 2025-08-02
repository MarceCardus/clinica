from PyQt5.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QTextEdit, QPushButton, QFileDialog, QMessageBox
)
from PyQt5.QtGui import QPixmap, QImage
import cv2
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
import qrcode
import tempfile
import os
from datetime import datetime

class AnalisisResultadoDialog(QDialog):
    def __init__(self, resultados, ruta1, ruta2, nombre, apellido, etiqueta, ys1, ys2, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resultado del Análisis")
        self.resize(900, 900)  # Ventana más grande

        self.nombre = nombre
        self.apellido = apellido
        self.etiqueta = etiqueta
        self.resultados = resultados  # Lista de tuplas (nombre, antes, despues, diff, pct, y1, y2)
        self.ruta1 = ruta1
        self.ruta2 = ruta2
        self.ys1 = ys1
        self.ys2 = ys2

        layout = QVBoxLayout(self)

        # Imágenes grandes lado a lado con líneas dibujadas
        imgs_layout = QHBoxLayout()
        img1_out = self.dibujar_lineas(cv2.imread(ruta1), self.ys1)
        img2_out = self.dibujar_lineas(cv2.imread(ruta2), self.ys2)

        label1 = QLabel()
        label1.setPixmap(self.cv2pix(img1_out))
        label1.setToolTip(ruta1)
        label2 = QLabel()
        label2.setPixmap(self.cv2pix(img2_out))
        label2.setToolTip(ruta2)
        imgs_layout.addWidget(label1)
        imgs_layout.addWidget(label2)
        layout.addLayout(imgs_layout)

        # Tabla de resultados
        self.table = QTableWidget(len(resultados), 5)
        self.table.setHorizontalHeaderLabels(["Medida", "Antes (px)", "Después (px)", "Diferencia", "% Cambio"])
        for i, (nombre_medida, antes, despues, dif, pcambio, _, _) in enumerate(resultados):
            self.table.setItem(i, 0, QTableWidgetItem(str(nombre_medida)))
            self.table.setItem(i, 1, QTableWidgetItem(f"{antes:.1f}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{despues:.1f}"))
            self.table.setItem(i, 3, QTableWidgetItem(f"{dif:+.1f}"))
            self.table.setItem(i, 4, QTableWidgetItem(f"{pcambio:+.1f}%"))
        layout.addWidget(self.table)

        # Resumen del análisis (texto automático)
        self.txt_resumen = QTextEdit()
        self.txt_resumen.setReadOnly(True)
        resumen = self.generar_resumen(resultados)
        self.txt_resumen.setPlainText(resumen)
        layout.addWidget(self.txt_resumen)

        # Botón para exportar a PDF
        self.btn_pdf = QPushButton("Exportar PDF")
        self.btn_pdf.clicked.connect(
            lambda: self.exportar_pdf(resultados, self.ruta1, self.ruta2, resumen)
        )
        layout.addWidget(self.btn_pdf)

    def dibujar_lineas(self, img, ys):
        img2 = img.copy()
        for y in ys:
            cv2.line(img2, (0, y), (img2.shape[1], y), (0, 255, 0), 3)
        return img2

    def cv2pix(self, img):
        if img is None:
            return QPixmap()
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        img_qt = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        return QPixmap.fromImage(img_qt).scaled(260, 390, aspectRatioMode=1)

    def generar_resumen(self, resultados):
        resumen = "Resumen del Análisis:\n\n"
        for nombre, antes, despues, dif, pcambio, _, _ in resultados:
            if abs(pcambio) < 0.01:
                resumen += f"Sin cambios en {nombre.lower()} respecto a la foto anterior.\n"
            elif pcambio < 0:
                resumen += (
                    f"Reducción de {abs(pcambio):.1f}% en {nombre.lower()} respecto a la foto anterior.\n"
                )
            else:
                resumen += (
                    f"Aumento de {abs(pcambio):.1f}% en {nombre.lower()} respecto a la foto anterior.\n"
                )
        return resumen

    def exportar_pdf(self, resultados, ruta1, ruta2, resumen):
        # === Nombre de archivo sugerido ===
        nombre = getattr(self, "nombre", "Nombre")
        apellido = getattr(self, "apellido", "Apellido")
        etiqueta = getattr(self, "etiqueta", "Etiqueta")
        fecha = datetime.now().strftime('%d%m%y')
        def limpiar(txt):
            return str(txt).strip().replace(' ', '_')
        sugerido = f"{limpiar(nombre)}_{limpiar(apellido)}_{limpiar(etiqueta)}_{fecha}.pdf"

        filename, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", sugerido, "PDF Files (*.pdf)")
        if not filename:
            return

        # Guardar imágenes temporales (dibujando líneas verdes en originales SOLO para PDF)
        def crear_temp_con_lineas(img_path, ys):
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            img = cv2.imread(img_path)
            for y in ys:
                cv2.line(img, (0, y), (img.shape[1], y), (0, 255, 0), 3)
            cv2.imwrite(tmp.name, img)
            return tmp

        tmp1 = crear_temp_con_lineas(ruta1, [r[5] for r in resultados])
        tmp2 = crear_temp_con_lineas(ruta2, [r[6] for r in resultados])

        c = canvas.Canvas(filename, pagesize=letter)
        width, height = letter

        # Imágenes lado a lado en PDF
        c.drawImage(tmp1.name, inch, height - 5*inch, width=2.4*inch, height=3.7*inch)
        c.drawImage(tmp2.name, 4*inch, height - 5*inch, width=2.4*inch, height=3.7*inch)

        # Tabla de resultados
        data = [["Medida", "Antes (px)", "Después (px)", "Diferencia", "% Cambio"]]
        for nombre_medida, antes, despues, dif, pcambio, _, _ in resultados:
            data.append([nombre_medida, f"{antes:.1f}", f"{despues:.1f}", f"{dif:+.1f}", f"{pcambio:+.1f}%"])
        t = Table(data, colWidths=[2*inch, 1.0*inch, 1.0*inch, 1.0*inch, 1.0*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (1,1), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
        ]))
        t.wrapOn(c, width, height)
        t.drawOn(c, inch, height - 6.5*inch)

        # Resumen automático
        textobject = c.beginText()
        textobject.setTextOrigin(inch, inch + 1.5*inch)
        textobject.setFont("Helvetica", 11)
        for line in resumen.splitlines():
            textobject.textLine(line)
        c.drawText(textobject)

        # QR opcional
        qr_text = "https://tuconsultorio.com/resultados"
        qr_img = qrcode.make(qr_text)
        qr_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        qr_img.save(qr_path.name)
        c.drawImage(qr_path.name, width - 2.1*inch, inch, width=1.1*inch, height=1.1*inch)

        c.save()
        tmp1.close()
        tmp2.close()
        qr_path.close()
        os.remove(tmp1.name)
        os.remove(tmp2.name)
        os.remove(qr_path.name)

        QMessageBox.information(self, "PDF Exportado", f"Informe exportado correctamente a:\n{filename}")
