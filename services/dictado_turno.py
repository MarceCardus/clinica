# services/dictado_turno.py
"""
Dictado de turnos por voz (offline, local).

Flujo:
  1. DictadoDialog graba audio con sounddevice mientras la persona habla.
  2. Al detener, transcribe con faster-whisper (modelo local, en español).
  3. parse_turno() interpreta la frase y extrae los campos crudos:
        paciente, profesional, item, fecha (date) y hora (time).

No resuelve contra la base ni guarda nada: eso lo hace el formulario
(CitaForm), que hace el "fuzzy match" contra sus combos y deja todo
cargado para que la persona revise y confirme.

Requiere:  pip install faster-whisper
(sounddevice, numpy y python-dateutil ya están en requirements.txt)
"""
import re
import unicodedata
from datetime import date, time, timedelta

import numpy as np

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
)

# ----------------------------------------------------------------------
#  Motor de transcripción (se carga una sola vez y queda cacheado)
# ----------------------------------------------------------------------
SAMPLE_RATE = 16000
MODEL_SIZE  = "small"      # "base" = más rápido, "small" = mejor con nombres
_model = None


def get_model():
    """Carga (una vez) el modelo de faster-whisper. Puede tardar la 1ª vez."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel   # import perezoso
        # int8 = rápido en CPU y con poca RAM
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


# ----------------------------------------------------------------------
#  Normalización de texto
# ----------------------------------------------------------------------
def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s or "")
        if unicodedata.category(c) != "Mn"
    )


def _norm(s: str) -> str:
    """minúsculas + sin acentos, para comparar."""
    return _strip_accents(s).lower()


# ----------------------------------------------------------------------
#  Interpretación de la frase → campos
# ----------------------------------------------------------------------
_DIAS = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "domingo": 6,
}
_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_NUM_PALABRA = {
    "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12,
}


def _blank(text: str, spans) -> str:
    """Reemplaza por espacios los tramos ya consumidos (fecha/hora)."""
    chars = list(text)
    for a, b in spans:
        for i in range(a, min(b, len(chars))):
            chars[i] = " "
    return "".join(chars)


def _extract_fecha(norm: str, spans: list):
    """Devuelve un date o None. Acumula en `spans` los tramos usados."""
    hoy = date.today()

    # pasado mañana
    m = re.search(r"pasado\s+manana", norm)
    if m:
        spans.append(m.span())
        return hoy + timedelta(days=2)

    # "mañana" como DÍA — pero NO si la palabra anterior es de/la/por
    # (esos casos son la franja AM: "de la mañana"). Chequeo por palabra
    # completa para no confundir con "meLA manana".
    for m in re.finditer(r"\bmanana\b", norm):
        prev = norm[:m.start()].split()
        if prev and prev[-1] in ("de", "la", "por"):
            continue
        spans.append(m.span())
        return hoy + timedelta(days=1)

    m = re.search(r"\bhoy\b", norm)
    if m:
        spans.append(m.span())
        return hoy

    # "el 15 de agosto"
    m = re.search(r"\b(?:el\s+)?(\d{1,2})\s+de\s+(" + "|".join(_MESES) + r")\b", norm)
    if m:
        spans.append(m.span())
        d, mes = int(m.group(1)), _MESES[m.group(2)]
        y = hoy.year
        try:
            cand = date(y, mes, d)
            if cand < hoy:
                cand = date(y + 1, mes, d)
            return cand
        except ValueError:
            pass

    # "15/08" o "15-08" (opcional /2026)
    m = re.search(r"\b(?:el\s+)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", norm)
    if m:
        spans.append(m.span())
        d, mes = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else hoy.year
        if y < 100:
            y += 2000
        try:
            return date(y, mes, d)
        except ValueError:
            pass

    # día de la semana → próxima ocurrencia (1..7 días adelante)
    for nombre, idx in _DIAS.items():
        m = re.search(r"\b" + nombre + r"\b", norm)
        if m:
            spans.append(m.span())
            delta = (idx - hoy.weekday()) % 7
            delta = delta or 7          # si es hoy, se entiende la semana que viene
            return hoy + timedelta(days=delta)

    return None


def _extract_hora(norm: str, spans: list):
    """Devuelve un time o None. Acumula en `spans` los tramos usados."""
    # franja horaria (y la borramos para que no ensucie el item)
    franja = None
    mf = re.search(r"\b(?:de|por)\s+la\s+(manana|tarde|noche)\b", norm)
    if mf:
        franja = "am" if mf.group(1) == "manana" else "pm"
        spans.append(mf.span())
    elif re.search(r"\bam\b", norm):
        franja = "am"
    elif re.search(r"\bpm\b", norm):
        franja = "pm"

    hh = mm = None
    ini = fin = None

    # 1) "9:30", "9.30", "9h30"  (siempre es hora)
    m = re.search(r"\b(\d{1,2})[:h\.](\d{2})\b", norm)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2))
        ini, fin = m.span()
    if hh is None:
        # 2) "a las 9", "las 9", "a las 9 30", "a las 16 hs"
        m = re.search(r"\b(?:a\s+)?las?\s+(\d{1,2})(?:\s*[:h]?\s*(\d{2}))?\s*(?:hs?|horas)?\b", norm)
        if m:
            hh = int(m.group(1))
            mm = int(m.group(2)) if m.group(2) else 0
            ini, fin = m.span()
    if hh is None:
        # 3) "9 hs", "9 horas"
        m = re.search(r"\b(\d{1,2})\s*(?:hs?|horas)\b", norm)
        if m:
            hh, mm = int(m.group(1)), 0
            ini, fin = m.span()
    if hh is None and franja:
        # 4) "3 de la tarde" (número suelto + franja ya detectada)
        m = re.search(r"\b(\d{1,2})\b", norm[:mf.start()] if mf else norm)
        if m:
            hh, mm = int(m.group(1)), 0
            ini, fin = m.span()
    if hh is None:
        # 5) en palabras: "a las nueve", "las nueve"
        m = re.search(r"\b(?:a\s+)?las?\s+(" + "|".join(_NUM_PALABRA) + r")\b", norm)
        if m:
            hh, mm = _NUM_PALABRA[m.group(1)], 0
            ini, fin = m.span()

    if hh is None:
        return None

    # "y media" / "y cuarto" / "y veinte" justo después
    resto = norm[fin: fin + 15]
    m2 = re.match(r"\s*y\s+(media|cuarto|\d{1,2})", resto)
    if m2:
        val = m2.group(1)
        mm = 30 if val == "media" else 15 if val == "cuarto" else int(val)
        fin = fin + m2.end()

    spans.append((ini, fin))

    # aplicar franja AM/PM
    if franja == "pm" and hh < 12:
        hh += 12
    if franja == "am" and hh == 12:
        hh = 0

    if 0 <= hh <= 23 and 0 <= mm <= 59:
        return time(hh, mm)
    return None


# marcadores para cortar cada campo
_MARK_PROF = r"con\s+la\s+dra?a?\.?|con\s+el\s+dr\.?|con\s+la\s+doctora|con\s+el\s+doctor|profesional|con\s+la|con\s+el|\bcon\b|doctora|doctor|\bdra?a?\.?\b|\bdr\.?\b"
_MARK_ITEM = r"\bitems?\b|producto|servicio"
_MARK_PAC  = r"paciente|\bpara\b"

# conectores a recortar de los extremos de cada campo
_STOP = {"turno", "el", "la", "los", "las", "de", "del", "con", "para",
         "y", "a", "un", "una", "por", "que", "al", "le"}


def _limpiar_bordes(txt: str) -> str:
    toks = (txt or "").split()
    def _es_stop(t):
        return _norm(re.sub(r"[,;:\.\-]", "", t)) in _STOP
    # recorta conectores y puntuación de ambos extremos
    while toks and _es_stop(toks[0]):
        toks.pop(0)
    while toks and _es_stop(toks[-1]):
        toks.pop()
    out = " ".join(toks)
    return re.sub(r"^[\s,;:\.\-]+|[\s,;:\.\-]+$", "", out)


def _tomar(norm, orig, patron):
    """Busca `patron` en `norm` y devuelve el texto ORIGINAL que sigue,
    hasta el próximo marcador o el fin de la frase."""
    m = re.search(patron, norm)
    if not m:
        return None
    ini = m.end()
    # cortar en el próximo marcador de otro campo
    cortes = [_MARK_PAC, _MARK_PROF, _MARK_ITEM]
    fin = len(orig)
    for c in cortes:
        m2 = re.search(c, norm[ini:])
        if m2:
            fin = min(fin, ini + m2.start())
    txt = _limpiar_bordes(orig[ini:fin])
    return txt or None


def parse_turno(texto: str) -> dict:
    """
    Interpreta la frase dictada y devuelve los campos CRUDOS (texto):
        {
          'paciente':    str | None,
          'profesional': str | None,
          'item':        str | None,
          'fecha':       date | None,
          'hora':        time | None,
          'texto':       str,   # transcripción original
        }
    """
    texto = (texto or "").strip()
    norm = _norm(texto)

    # 1) fecha/hora primero, y las "borramos" para que no ensucien los nombres
    spans = []
    fecha = _extract_fecha(norm, spans)
    hora = _extract_hora(norm, spans)

    norm_limpio = _blank(norm, spans)
    orig_limpio = _blank(texto, spans)

    # 2) campos por marcadores
    paciente    = _tomar(norm_limpio, orig_limpio, _MARK_PAC)
    profesional = _tomar(norm_limpio, orig_limpio, _MARK_PROF)
    item        = _tomar(norm_limpio, orig_limpio, _MARK_ITEM)

    return {
        "paciente": paciente,
        "profesional": profesional,
        "item": item,
        "fecha": fecha,
        "hora": hora,
        "texto": texto,
    }


# ----------------------------------------------------------------------
#  Diálogo de grabación
# ----------------------------------------------------------------------
class _TranscribeWorker(QThread):
    done = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, audio):
        super().__init__()
        self.audio = audio

    def run(self):
        try:
            model = get_model()
            segments, _info = model.transcribe(
                self.audio, language="es", vad_filter=True
            )
            texto = " ".join(s.text.strip() for s in segments).strip()
            self.done.emit(texto)
        except Exception as e:
            self.error.emit(str(e))


class DictadoDialog(QDialog):
    """
    Graba mientras está abierto. Botón para detener → transcribe → parsea.
    Al aceptar, quedan disponibles:  self.texto  y  self.resultado (dict).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dictar turno")
        self.setMinimumWidth(380)

        self.texto = ""
        self.resultado = None
        self._frames = []
        self._stream = None
        self._worker = None

        lay = QVBoxLayout(self)
        self.lbl = QLabel("🔴  Grabando…  decí el turno y apretá «Detener».\n\n"
                          "Ej.: «paciente Marcelo Cardus, con la Dra. Daisy,\n"
                          "item Mela, mañana a las 9 y media».")
        self.lbl.setWordWrap(True)
        lay.addWidget(self.lbl)

        row = QHBoxLayout()
        self.btn_stop = QPushButton("⏹  Detener y cargar")
        self.btn_cancel = QPushButton("Cancelar")
        row.addWidget(self.btn_stop)
        row.addWidget(self.btn_cancel)
        lay.addLayout(row)

        self.btn_stop.clicked.connect(self._detener)
        self.btn_cancel.clicked.connect(self.reject)

        self._iniciar_grabacion()

    # ---- audio ----
    def _iniciar_grabacion(self):
        try:
            import sounddevice as sd
        except Exception as e:
            self.lbl.setText(f"No se pudo acceder al micrófono.\n{e}")
            self.btn_stop.setEnabled(False)
            return

        def _cb(indata, _frames, _t, _status):
            self._frames.append(indata.copy())

        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=_cb
            )
            self._stream.start()
        except Exception as e:
            self.lbl.setText(f"No se pudo iniciar la grabación.\n{e}")
            self.btn_stop.setEnabled(False)

    def _parar_stream(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _detener(self):
        self._parar_stream()
        if not self._frames:
            self.lbl.setText("No se grabó audio. Revisá el micrófono.")
            return

        audio = np.concatenate(self._frames, axis=0).flatten().astype(np.float32)
        self.btn_stop.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.lbl.setText("⏳  Transcribiendo…  (puede tardar unos segundos)")

        self._worker = _TranscribeWorker(audio)
        self._worker.done.connect(self._on_transcrito)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_transcrito(self, texto):
        self.texto = texto
        self.resultado = parse_turno(texto)
        self.accept()

    def _on_error(self, msg):
        self.lbl.setText(f"Error al transcribir:\n{msg}")
        self.btn_cancel.setEnabled(True)

    def reject(self):
        self._parar_stream()
        super().reject()

    def closeEvent(self, e):
        self._parar_stream()
        super().closeEvent(e)
