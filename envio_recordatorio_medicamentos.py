# -*- coding: utf-8 -*-
import os
import sys
import time
import logging
import traceback
import urllib.parse
import subprocess
import tempfile
import atexit
from datetime import datetime, timedelta, time as dtime

# --- MODELOS CARGADOS ANTES DE configure_mappers ---
import models
import models.departamento
import models.ciudad
import models.barrio
import models.paciente
import models.recordatorio_paciente
import models.profesional
import models.insumo
import models.producto
import models.indicacion
import models.tipoproducto
import models.especialidad
import models.procedimiento
from sqlalchemy.orm import configure_mappers
configure_mappers()

from sqlalchemy import or_
from sqlalchemy.orm import Session
from utils.db import SessionLocal

from models.recordatorio_paciente import RecordatorioPaciente
from models.paciente import Paciente
from models.producto import Producto
from models.indicacion import Indicacion
from models.insumo import Insumo
from models.procedimiento import Procedimiento

# --- SELENIUM ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# =========================
# AJUSTES
# =========================
BASE_PROFILE_DIR = r"C:\selenium_ws_profile"
PROFILE_NAME     = "Default"
DEBUG_PORT       = 9226  # Puerto propio

QR_WAIT_SECONDS           = 30
CHAT_LOAD_TIMEOUT         = 35
DELAY_BEFORE_QUIT_SECONDS = 10

LOG_FILE = "envio_recordatorios.log"
# =========================

# ---------- LOG ----------
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
logging.getLogger("").addHandler(console)

# ---------- Mutex ----------
class SingleInstance:
    def __init__(self, name):
        self.lock_path = os.path.join(tempfile.gettempdir(), f"{name}.lock")
        if os.path.exists(self.lock_path):
            raise RuntimeError(f"Ya hay otra instancia ejecutándose: {self.lock_path}")
        open(self.lock_path, "w").close()
        atexit.register(self.release)
    def release(self):
        try:
            if os.path.exists(self.lock_path):
                os.remove(self.lock_path)
        except: pass

# ---------- Chrome (depuración remota) ----------
def find_chrome_binary():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return "chrome.exe"

def launch_chrome_with_debug(profile_dir: str, profile_name: str, port: int):
    os.makedirs(profile_dir, exist_ok=True)
    chrome = find_chrome_binary()
    cmd = [
        chrome,
        f'--user-data-dir={profile_dir}',
        f'--profile-directory={profile_name}',
        f'--remote-debugging-port={port}',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-dev-shm-usage',
        '--disable-gpu',
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def attach_driver_to_debugger(port: int) -> webdriver.Chrome:
    opts = ChromeOptions()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    drv = webdriver.Chrome(options=opts)
    drv.set_page_load_timeout(90)
    return drv

def build_driver_via_debug(profile_dir: str, profile_name: str, port: int, wait_boot=2.5):
    try:
        logging.info(f"Intentando adherirse a Chrome en 127.0.0.1:{port}…")
        return attach_driver_to_debugger(port)
    except Exception as e:
        logging.info(f"No hay Chrome escuchando en {port}: {e}")
    logging.info("Lanzando Chrome con depuración remota…")
    launch_chrome_with_debug(profile_dir, profile_name, port)
    time.sleep(wait_boot)
    last = None
    for i in range(1,6):
        try:
            return attach_driver_to_debugger(port)
        except Exception as e:
            last = e; time.sleep(1)
    raise RuntimeError(f"No se pudo adherir a Chrome con depuración remota: {last}")

# ---------- Utils ----------
def normalizar_telefono_py(telefono: str) -> str:
    if not telefono: return ""
    t = str(telefono).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if t.startswith("+595"): return t
    if t.startswith("595"):  return "+" + t
    if t.startswith("0"):    return "+595" + t[1:]
    if not t.startswith("+"): return "+595" + t
    return t

def es_horario_habil(dt: datetime) -> bool:
    return dtime(8, 0) <= dt.time() <= dtime(17, 0)

def cerrar_popup_si_existe(driver, wait_time=0.8):
    try:
        time.sleep(wait_time)
        popups = driver.find_elements(By.XPATH, '//div[@role="dialog"]')
        for popup in popups:
            for xp in ['.//button[@aria-label="Cerrar"]',
                       './/button[.="Cerrar"]',
                       './/button[.="OK"]',
                       './/button[.="Aceptar"]',
                       './/button[contains(.,"Entendido")]']:
                try:
                    popup.find_element(By.XPATH, xp).click()
                    time.sleep(0.3); return
                except: pass
    except: pass

def esperar_chat_cargado(driver):
    WebDriverWait(driver, CHAT_LOAD_TIMEOUT).until(
        EC.any_of(
            # XPATH CRÍTICO: Título del chat
            EC.presence_of_element_located((By.XPATH, '//header//*[@data-testid="conversation-info-header-chat-title"]')),
            # XPATH CRÍTICO: Caja de texto del footer
            EC.presence_of_element_located((By.XPATH, '//footer//*[@role="textbox" and @contenteditable="true"]'))
        )
    )
    time.sleep(0.8)

def enviar_mensaje_whatsapp(driver, wait, numero: str, mensaje: str) -> bool:
    msg = urllib.parse.quote(mensaje, safe="")
    url = f"https://web.whatsapp.com/send?phone={numero.replace('+','')}&text={msg}"
    logging.info(f"Abrir chat: {url}")
    driver.get(url)

    try:
        esperar_chat_cargado(driver)
    except TimeoutException:
        logging.error("El chat no cargó a tiempo.")
        return False

    cerrar_popup_si_existe(driver)

    box = None
    for _ in range(6):
        try:
            # XPATH CRÍTICO: Caja de texto
            box = wait.until(EC.element_to_be_clickable((By.XPATH, '//footer//div[@contenteditable="true"]')))
            break
        except Exception:
            cerrar_popup_si_existe(driver, wait_time=0.8)
            time.sleep(1.0)
    if not box:
        logging.error("No se encontró la caja de mensaje.")
        return False

    try:
        driver.execute_script("arguments[0].focus();", box)
        time.sleep(0.5)
        box.send_keys(Keys.ENTER)
        time.sleep(1.2)

        contenido = box.get_attribute("textContent") or ""
        if not contenido.strip():
            logging.info("Mensaje enviado (composer vacío).")
            return True

        # Fallback: botón enviar
        try:
            # XPATH CRÍTICO: Botón de enviar
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//footer//button[@aria-label='Enviar']|//footer//span[@data-icon='send']"))
            )
            try: btn.click()
            except Exception: driver.execute_script("arguments[0].click();", btn)
            time.sleep(1.2)
            contenido = box.get_attribute("textContent") or ""
            ok = not contenido.strip()
            logging.info(f"Envio por botón: {'ok' if ok else 'falló'}")
            return ok
        except Exception:
            logging.error("No se pudo hacer click en botón Enviar.")
            return False

    except TimeoutException:
        logging.error("Timeout interactuando con la caja de mensaje.")
        return False
    except Exception as e:
        logging.error(f"Error al enviar: {e}")
        logging.error(traceback.format_exc())
        return False

# =========================
# PROCESO PRINCIPAL
# =========================
def procesar_recordatorios():
    _guard = None
    session: Session = None
    driver = None
    try:
        _guard = SingleInstance("envio_recordatorios_ws")

        session = SessionLocal()

        ahora = datetime.now()
        logging.info(f"Buscando recordatorios pendientes a las {ahora}.")

        pendientes = (
            session.query(RecordatorioPaciente)
            .filter(RecordatorioPaciente.fecha_recordatorio <= ahora)
            .filter(or_(RecordatorioPaciente.estado != 'realizado', RecordatorioPaciente.estado.is_(None)))
            .all()
        )
        logging.info(f"Recordatorios candidatos: {len(pendientes)}")
        if not pendientes:
            return

        driver = build_driver_via_debug(BASE_PROFILE_DIR, PROFILE_NAME, DEBUG_PORT)
        
        # --- MEJORA ---
        # Usamos la constante CHAT_LOAD_TIMEOUT para el 'wait' principal
        wait = WebDriverWait(driver, CHAT_LOAD_TIMEOUT)
        # --- FIN MEJORA ---

        logging.info("Abriendo WhatsApp Web para iniciar sesión…")
        driver.get("https://web.whatsapp.com/")

        # --- MEJORA ---
        # Reemplazamos el time.sleep() estático por una espera explícita
        # Esperamos que cargue la interfaz principal (p.ej. la barra de búsqueda de chats)
        try:
            logging.info(f"Esperando que cargue la interfaz principal de WhatsApp ({QR_WAIT_SECONDS}s)...")
            # Usamos un WebDriverWait dedicado para esta espera inicial con su propio timeout
            WebDriverWait(driver, QR_WAIT_SECONDS).until(
                # XPATH CRÍTICO: Barra de búsqueda principal de chats
                EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true" and @data-tab="3"]'))
            )
            logging.info("WhatsApp Web cargado.")
            time.sleep(1.5) # Damos un pequeño respiro extra para que todo "asiente"
        except TimeoutException:
            logging.error(f"No se pudo cargar la interfaz principal de WhatsApp en {QR_WAIT_SECONDS}s.")
            logging.warning("Esto puede ser normal si se necesita escanear el QR. El script continuará...")
        # time.sleep(QR_WAIT_SECONDS)  # <-- Línea original eliminada
        # --- FIN MEJORA ---

        ventana_inicio_med = ahora - timedelta(hours=1)

        for rec in pendientes:
            try:
                paciente = session.query(Paciente).filter_by(idpaciente=rec.idpaciente).first()
                if not paciente or not paciente.telefono:
                    logging.warning(f"Paciente sin teléfono válido (ID {rec.idpaciente}). Salteado.")
                    continue
                numero = normalizar_telefono_py(paciente.telefono)

                programado: datetime = rec.fecha_recordatorio
                hora_txt = programado.strftime("%H:%M")
                mensaje = rec.mensaje or ""

                # ----- INDICACIÓN (MEDICAMENTO) -----
                if getattr(rec, "idindicacion", None):
                    if not (ventana_inicio_med <= programado <= ahora):
                        logging.info(f"[MED] fuera de ventana 1h (prog={programado}). Salteado.")
                        continue

                    indic = session.get(Indicacion, rec.idindicacion)
                    if not indic:
                        logging.warning(f"Indicación {rec.idindicacion} inexistente. Salteado.")
                        continue
                    insumo = session.get(Insumo, indic.idinsumo) if indic.idinsumo else None
                    nombre_med = getattr(insumo, "nombre", None) or "medicamento"

                    if not mensaje:
                        partes = [f"Recordatorio: tomar {nombre_med}"]
                        if getattr(indic, "dosis", None): partes.append(str(indic.dosis))
                        if getattr(indic, "frecuencia_horas", None): partes.append(f"cada {indic.frecuencia_horas} h")
                        mensaje = " ".join(partes).strip() + "."
                    mensaje += f" Hora indicada: {hora_txt}." if programado > ahora else f" Debiste tomarlo a las {hora_txt}."

                # ----- PROCEDIMIENTO -----
                elif getattr(rec, "idprocedimiento", None):
                    if not es_horario_habil(ahora):
                        logging.info("[PROC] fuera del horario 08-17. Salteado.")
                        continue
                    proc = session.get(Procedimiento, rec.idprocedimiento)
                    if not proc:
                        logging.warning(f"Procedimiento {rec.idprocedimiento} inexistente. Salteado.")
                        continue
                    producto = session.get(Producto, getattr(proc, "idproducto", None)) if getattr(proc, "idproducto", None) else None
                    nombre_proc = getattr(producto, "nombre", None) or "control"
                    sugerido = getattr(producto, "mensaje_recordatorio", None) if producto else None
                    if not mensaje:
                        mensaje = (sugerido or f"Recordatorio de control: {nombre_proc}.").strip()
                    mensaje += f" Hora programada: {hora_txt}."

                # ----- GENÉRICO -----
                else:
                    if not mensaje:
                        mensaje = f"Tienes un recordatorio pendiente de tu clínica. Hora programada: {hora_txt}."

                ok = enviar_mensaje_whatsapp(driver, wait, numero, mensaje)
                if ok:
                    time.sleep(1.0)
                    rec.estado = 'realizado'
                    rec.fecha_envio = datetime.now()
                    session.commit()
                    logging.info(f"Recordatorio {getattr(rec, 'id', '?')} enviado a {numero}.")
                else:
                    session.rollback()
                    logging.error(f"No se pudo enviar a {numero} (rec {getattr(rec, 'id', '?')}).")

            except Exception as e_item:
                session.rollback()
                logging.error(f"Error procesando recordatorio {getattr(rec, 'id', '?')}: {e_item}")
                logging.error(traceback.format_exc())

        logging.info("Proceso finalizado.")

    except Exception as e:
        logging.error(f"Error general: {e}")
        logging.error(traceback.format_exc())
        sys.exit(1)
    finally:
        try:
            if session: session.close()
        except: pass
        try:
            if driver:
                logging.info(f"Esperando {DELAY_BEFORE_QUIT_SECONDS}s antes de cerrar Chrome…")
                time.sleep(DELAY_BEFORE_QUIT_SECONDS)
                
                # --- NOTA ---
                # driver.quit() cierra el navegador por completo.
                # Si prefieres que Chrome quede ABIERTO (para que el script se conecte
                # más rápido la próxima vez), puedes comentar la siguiente línea:
                driver.quit()
                # --- FIN NOTA ---
                
        except: pass

if __name__ == "__main__":
    procesar_recordatorios()