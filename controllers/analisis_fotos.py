import cv2
import mediapipe as mp
import numpy as np
from rembg import remove
from PIL import Image

def quitar_fondo_cv2(img):
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    out_pil = remove(img_pil)
    bg = Image.new("RGBA", out_pil.size, (255,255,255,255))
    out_pil = Image.alpha_composite(bg, out_pil.convert("RGBA")).convert("RGB")
    return cv2.cvtColor(np.array(out_pil), cv2.COLOR_RGB2BGR)

def obtener_landmarks(img):
    mp_pose = mp.solutions.pose
    with mp_pose.Pose(static_image_mode=True) as pose:
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        res = pose.process(img_rgb)
        if res.pose_landmarks:
            h, w = img.shape[:2]
            puntos = [(int(lm.x * w), int(lm.y * h)) for lm in res.pose_landmarks.landmark]
            return puntos
        return None

def sugerir_ys_por_landmarks(img):
    """
    Devuelve sugerencias de y para hombros, cintura, cadera, muslo (en ese orden).
    Si no encuentra landmarks, devuelve alturas relativas a la imagen.
    """
    puntos = obtener_landmarks(quitar_fondo_cv2(img))
    h = img.shape[0]
    if puntos:
        # Hombros: promedio entre 11 y 12
        y_hombros = int((puntos[11][1] + puntos[12][1]) / 2)
        # Cintura: mitad entre hombros y cadera (aprox. anatómica)
        y_cadera = int((puntos[23][1] + puntos[24][1]) / 2)
        y_cintura = int(y_hombros + (y_cadera - y_hombros) * 0.55)  # 55% entre hombro y cadera
        # Muslo: landmark rodilla (25 y 26)
        if len(puntos) > 26:
            y_muslo = int((puntos[25][1] + puntos[26][1]) / 2)
        else:
            y_muslo = int(h * 0.78)
    else:
        # Fallback: alturas relativas
        y_hombros = int(h * 0.20)
        y_cintura = int(h * 0.45)
        y_cadera = int(h * 0.60)
        y_muslo = int(h * 0.78)
    return [y_hombros, y_cintura, y_cadera, y_muslo]

def medir_ancho_en_y(img, y):
    img_sf = quitar_fondo_cv2(img)
    h, w = img_sf.shape[:2]
    mp_selfie = mp.solutions.selfie_segmentation
    with mp_selfie.SelfieSegmentation(model_selection=1) as segmenter:
        img_rgb = cv2.cvtColor(img_sf, cv2.COLOR_BGR2RGB)
        res = segmenter.process(img_rgb)
        mask = (res.segmentation_mask > 0.5).astype(np.uint8) * 255
    fila = mask[y, :]
    indices = np.where(fila > 0)[0]
    if len(indices) >= 2:
        ancho_px = indices[-1] - indices[0]
    else:
        ancho_px = 0
    img_out = img_sf.copy()
    cv2.line(img_out, (0, y), (w, y), (0, 255, 0), 2)
    return ancho_px, y, img_out

# --- PyQt: Diálogo de ajuste múltiple (sliders para todas las líneas) ---
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QGroupBox
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt

class AjusteLineasMultiDialog(QDialog):
    def __init__(self, img1, img2, ys1, ys2, labels=["Hombros","Cintura","Cadera","Muslo"], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajuste de Líneas de Medición")
        self.img1, self.img2 = img1, img2
        self.h1, self.h2 = img1.shape[0], img2.shape[0]
        self.n = len(ys1)
        self.labels = labels

        self.y1s = ys1[:]
        self.y2s = ys2[:]

        main_layout = QHBoxLayout(self)

        # -- Imagen 1 --
        vbox1 = QVBoxLayout()
        self.lbl1 = QLabel()
        vbox1.addWidget(self.lbl1)
        self.sliders1 = []
        for i, label in enumerate(self.labels):
            box = QGroupBox(label + " (foto 1)")
            box_layout = QVBoxLayout()
            s = QSlider(Qt.Vertical)
            s.setMinimum(0)
            s.setMaximum(self.h1-1)
            s.setValue(self.y1s[i])
            s.valueChanged.connect(self.make_actualiza1(i))
            self.sliders1.append(s)
            box_layout.addWidget(s)
            box.setLayout(box_layout)
            vbox1.addWidget(box)
        main_layout.addLayout(vbox1)

        # -- Imagen 2 --
        vbox2 = QVBoxLayout()
        self.lbl2 = QLabel()
        vbox2.addWidget(self.lbl2)
        self.sliders2 = []
        for i, label in enumerate(self.labels):
            box = QGroupBox(label + " (foto 2)")
            box_layout = QVBoxLayout()
            s = QSlider(Qt.Vertical)
            s.setMinimum(0)
            s.setMaximum(self.h2-1)
            s.setValue(self.y2s[i])
            s.valueChanged.connect(self.make_actualiza2(i))
            self.sliders2.append(s)
            box_layout.addWidget(s)
            box.setLayout(box_layout)
            vbox2.addWidget(box)
        main_layout.addLayout(vbox2)

        # Botón aceptar
        self.btn_aceptar = QPushButton("Analizar con estas líneas")
        self.btn_aceptar.clicked.connect(self.accept)
        main_layout.addWidget(self.btn_aceptar)

        self.actualiza1()
        self.actualiza2()

    def make_actualiza1(self, idx):
        def update(val):
            self.y1s[idx] = self.sliders1[idx].value()
            self.actualiza1()
        return update
    def make_actualiza2(self, idx):
        def update(val):
            self.y2s[idx] = self.sliders2[idx].value()
            self.actualiza2()
        return update

    def actualiza1(self):
        img = self.img1.copy()
        for y in self.y1s:
            cv2.line(img, (0, y), (img.shape[1], y), (0, 255, 0), 2)
        self.lbl1.setPixmap(self.cv2pix(img))
    def actualiza2(self):
        img = self.img2.copy()
        for y in self.y2s:
            cv2.line(img, (0, y), (img.shape[1], y), (0, 255, 0), 2)
        self.lbl2.setPixmap(self.cv2pix(img))
    def cv2pix(self, img):
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        img_qt = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        return QPixmap.fromImage(img_qt).scaled(340, 500, Qt.KeepAspectRatio)
    def get_ys(self):
        return self.y1s[:], self.y2s[:]

# -- Función principal de análisis avanzado --

def analizar_fotos_completo_multi(ruta1, ruta2, etiqueta, parent=None):
    img1 = cv2.imread(ruta1)
    img2 = cv2.imread(ruta2)

    labels = ["Hombros","Cintura","Cadera","Muslo"]
    ys1 = sugerir_ys_por_landmarks(img1)
    ys2 = sugerir_ys_por_landmarks(img2)

    # Diálogo de ajuste
    dlg = AjusteLineasMultiDialog(img1, img2, ys1, ys2, labels=labels, parent=parent)
    if dlg.exec_():
        ys1, ys2 = dlg.get_ys()
    else:
        # Si canceló, usa sugerencias
        pass

    resultados = []
    imgs_out1 = []
    imgs_out2 = []
    for i, nombre in enumerate(labels):
        ancho1, y1, img1_out = medir_ancho_en_y(img1, ys1[i])
        ancho2, y2, img2_out = medir_ancho_en_y(img2, ys2[i])
        imgs_out1.append(img1_out)
        imgs_out2.append(img2_out)
        diff = ancho2 - ancho1
        pct = 100 * diff / ancho1 if ancho1 else 0
        resultados.append((nombre, ancho1, ancho2, diff, pct, ys1[i], ys2[i]))

    # Devuelve resultados, las imágenes originales y posiciones de línea
    return resultados, img1, img2, ys1, ys2

# ========== Para el PDF ==========
# Guarda las fotos ORIGINALES (img1 y img2).
# Al exportar, podés dibujar las líneas verdes encima si querés, pero la base es la original.
# Usa las variables ys1, ys2 para saber en qué altura dibujar cada línea si lo querés marcar.

# Ejemplo de uso en tu GUI:
# resultados, img1_original, img2_original, ys1, ys2 = analizar_fotos_completo_multi(ruta1, ruta2, etiqueta, parent=self)
