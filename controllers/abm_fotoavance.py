from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QFileDialog, QHBoxLayout, QLineEdit, QTextEdit, QDateEdit, QCheckBox, QMessageBox
)
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QPixmap
from models.fotoavance import FotoAvance
from utils.db import SessionLocal
from controllers.analisis_fotos import analizar_fotos_completo_multi
from controllers.analisis_resultados import AnalisisResultadoDialog
from models.paciente import Paciente
import os
import sys
import shutil

# Configuración: carpeta de red
CARPETA_RED = r'\\192.168.1.32\consultorio\imagenes'

class FotosAvanceDialog(QDialog):
    def __init__(self, idpaciente, usuario_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fotos de Avance del Paciente")
        self.idpaciente = idpaciente
        self.session = SessionLocal()
        self.editando_id = None
        self.init_ui()
        self.cargar_fotos()
        self.usuario_id = usuario_id

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Fecha", "Archivo", "Comentario", "Etiquetas", "Sensible", "Usuario", "Ver", "Eliminar"
        ])
        self.table.setSelectionMode(QTableWidget.MultiSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.cellClicked.connect(self.click_tabla)
        layout.addWidget(self.table)

        form_layout = QHBoxLayout()
        self.input_fecha = QDateEdit(calendarPopup=True)
        self.input_fecha.setDate(QDate.currentDate())
        self.input_ruta = QLineEdit()
        self.btn_sel_foto = QPushButton("...")
        self.btn_sel_foto.clicked.connect(self.seleccionar_foto)
        self.input_comentario = QLineEdit()
        self.input_etiquetas = QLineEdit()
        self.input_sensible = QCheckBox("Sensible")
        self.btn_guardar = QPushButton("Agregar")
        self.btn_guardar.clicked.connect(self.guardar_foto)
        form_layout.addWidget(QLabel("Fecha:"))
        form_layout.addWidget(self.input_fecha)
        form_layout.addWidget(QLabel("Archivo:"))
        form_layout.addWidget(self.input_ruta)
        form_layout.addWidget(self.btn_sel_foto)
        form_layout.addWidget(QLabel("Comentario:"))
        form_layout.addWidget(self.input_comentario)
        form_layout.addWidget(QLabel("Etiquetas:"))
        form_layout.addWidget(self.input_etiquetas)
        form_layout.addWidget(self.input_sensible)
        form_layout.addWidget(self.btn_guardar)
        layout.addLayout(form_layout)

        self.btn_analizar = QPushButton("Analizar")
        self.btn_analizar.clicked.connect(self.analizar_fotos_seleccionadas)
        form_layout.addWidget(self.btn_analizar)

        self.lbl_imagen = QLabel("Vista previa")
        self.lbl_imagen.setFixedSize(350, 220)
        self.lbl_imagen.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_imagen)

        self.input_fecha.editingFinished.connect(lambda: self.input_ruta.setFocus())
        self.input_ruta.returnPressed.connect(lambda: self.input_comentario.setFocus())
        self.input_comentario.returnPressed.connect(lambda: self.input_etiquetas.setFocus())
        self.input_etiquetas.returnPressed.connect(lambda: self.input_sensible.setFocus())
        self.input_sensible.stateChanged.connect(lambda: self.btn_guardar.setFocus())

    def seleccionar_foto(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Seleccionar foto", "", "Imágenes (*.jpg *.png *.jpeg)")
        if ruta:
            self.input_ruta.setText(ruta)

    def cargar_fotos(self):
        self.table.setRowCount(0)
        fotos = self.session.query(FotoAvance).filter_by(idpaciente=self.idpaciente).all()
        for row, foto in enumerate(fotos):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(foto.fecha)))
            self.table.setItem(row, 1, QTableWidgetItem(foto.rutaarchivo or ""))
            self.table.setItem(row, 2, QTableWidgetItem(foto.comentario or ""))
            self.table.setItem(row, 3, QTableWidgetItem(foto.etiquetas or ""))
            self.table.setItem(row, 4, QTableWidgetItem("Sí" if foto.sensible else "No"))
            self.table.setItem(row, 5, QTableWidgetItem(str(foto.usuariocarga or "")))
            btn_ver = QPushButton("Ver")
            btn_ver.clicked.connect(lambda _, ruta=foto.rutaarchivo: self.mostrar_imagen(ruta))
            self.table.setCellWidget(row, 6, btn_ver)
            btn_del = QPushButton("Eliminar")
            btn_del.clicked.connect(lambda _, fid=foto.idfoto: self.eliminar_foto(fid))
            self.table.setCellWidget(row, 7, btn_del)
            self.table.itemDoubleClicked.connect(self.cargar_para_editar)
        self.lbl_imagen.setText("Vista previa")
        self.lbl_imagen.setPixmap(QPixmap())
        self.reset_form()

    def analizar_fotos_seleccionadas(self):
        selected = self.table.selectionModel().selectedRows()
        if len(selected) != 2:
            QMessageBox.warning(self, "Análisis", "Seleccione dos fotos con la misma etiqueta para analizar.")
            return
        row1, row2 = selected[0].row(), selected[1].row()
        ruta1 = self.table.item(row1, 1).text()
        ruta2 = self.table.item(row2, 1).text()
        etiqueta1 = self.table.item(row1, 3).text()
        etiqueta2 = self.table.item(row2, 3).text()
        if etiqueta1 != etiqueta2:
            QMessageBox.warning(self, "Análisis", "Las fotos deben tener la misma etiqueta.")
            return
        resultados, img1, img2, ys1, ys2 = analizar_fotos_completo_multi(ruta1, ruta2, etiqueta1, parent=self)
        paciente = self.session.query(Paciente).filter_by(idpaciente=self.idpaciente).first()
        nombre = paciente.nombre if paciente else "Nombre"
        apellido = paciente.apellido if paciente else "Apellido"
        dlg = AnalisisResultadoDialog(resultados, ruta1, ruta2, nombre, apellido, etiqueta1, ys1, ys2)
        dlg.exec_()

    def mostrar_imagen(self, ruta):
        if ruta and os.path.exists(ruta):
            pixmap = QPixmap(ruta).scaled(350, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_imagen.setPixmap(pixmap)
        else:
            self.lbl_imagen.setText("No se encuentra la imagen.")

    def copiar_a_red(self, ruta_local):
        if not ruta_local or not os.path.exists(ruta_local):
            QMessageBox.warning(self, "Error", "No se encuentra la imagen local seleccionada.")
            return None
        nombre_archivo = os.path.basename(ruta_local)
        destino = os.path.join(CARPETA_RED, nombre_archivo)
        try:
            # Solo copia si no existe (no sobreescribe)
            if not os.path.exists(destino):
                shutil.copy2(ruta_local, destino)
            return destino  # Guardar en base la ruta UNC
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo copiar la imagen al servidor:\n{e}")
            return None

    def guardar_foto(self):
        ruta_local = self.input_ruta.text().strip()
        if not ruta_local:
            QMessageBox.warning(self, "Validación", "Debe seleccionar una imagen.")
            self.input_ruta.setFocus()
            return

        # Copiar a servidor y obtener ruta UNC
        ruta_servidor = self.copiar_a_red(ruta_local)
        if not ruta_servidor:
            return  # Error al copiar

        if self.editando_id:  # EDITAR
            foto = self.session.query(FotoAvance).filter_by(idfoto=self.editando_id).first()
            if foto:
                foto.fecha = self.input_fecha.date().toPyDate()
                foto.rutaarchivo = ruta_servidor
                foto.comentario = self.input_comentario.text().strip()
                foto.etiquetas = self.input_etiquetas.text().strip()
                foto.sensible = self.input_sensible.isChecked()
                foto.usuariocarga = self.usuario_id
            self.editando_id = None
            self.btn_guardar.setText("Agregar")
        else:  # NUEVO
            foto = FotoAvance(
                idpaciente=self.idpaciente,
                rutaarchivo=ruta_servidor,
                fecha=self.input_fecha.date().toPyDate(),
                comentario=self.input_comentario.text().strip(),
                etiquetas=self.input_etiquetas.text().strip(),
                sensible=self.input_sensible.isChecked(),
                usuariocarga=self.usuario_id
            )
            self.session.add(foto)
        self.session.commit()
        self.cargar_fotos()
        QMessageBox.information(self, "Guardado", "Foto guardada correctamente.")

    def cargar_para_editar(self, item):
        row = item.row()
        idfoto = self.session.query(FotoAvance).filter_by(idpaciente=self.idpaciente).all()[row].idfoto
        foto = self.session.query(FotoAvance).filter_by(idfoto=idfoto).first()
        if foto:
            self.input_fecha.setDate(QDate(foto.fecha.year, foto.fecha.month, foto.fecha.day))
            self.input_ruta.setText(foto.rutaarchivo or "")
            self.input_comentario.setText(foto.comentario or "")
            self.input_etiquetas.setText(foto.etiquetas or "")
            self.input_sensible.setChecked(foto.sensible)
            self.editando_id = idfoto
            self.btn_guardar.setText("Guardar cambios")

    def eliminar_foto(self, idfoto):
        if QMessageBox.question(self, "Eliminar", "¿Eliminar la foto seleccionada?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            self.session.query(FotoAvance).filter_by(idfoto=idfoto).delete()
            self.session.commit()
            self.cargar_fotos()

    def click_tabla(self, row, col):
        if col == 1:  # Archivo
            ruta = self.table.item(row, 1).text()
            self.mostrar_imagen(ruta)

    def reset_form(self):
        self.input_fecha.setDate(QDate.currentDate())
        self.input_ruta.clear()
        self.input_comentario.clear()
        self.input_etiquetas.clear()
        self.input_sensible.setChecked(False)
        self.btn_guardar.setText("Agregar")
        self.editando_id = None

    def closeEvent(self, event):
        self.session.close()
        event.accept()
