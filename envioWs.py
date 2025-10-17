# -*- coding: utf-8 -*-
import os
import sys
import time
import datetime
import random
import logging
import traceback
import subprocess
import tempfile
import atexit

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URI

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ===================== AJUSTES =====================
BASE_PROFILE_DIR = r"C:\selenium_ws_profile"
PROFILE_NAME     = "Default"
DEBUG_PORT       = 9224  # <-- puerto propio de envioWs

QR_WAIT_SECONDS          = 30
CHAT_LOAD_TIMEOUT        = 35
RETRY_SENDS              = 2
LOG_FILE                 = "envioWs.log"
# ===================================================

# ---------- LOG a archivo y consola ----------
logging.basicConfig(
    filename=LOG_FILE,
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
logging.getLogger("").addHandler(console)

def sleep_jitter(a, b): time.sleep(random.uniform(a, b))

# ---------- Mutex (evita doble instancia) ----------
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

# ---------- Normalizador ----------
def normalizar_telefono_py(telefono: str) -> str:
    if not telefono: return ""
    t = str(telefono).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if t.startswith("+595"): return t
    if t.startswith("595"):  return "+" + t
    if t.startswith("0"):    return "+595" + t[1:]
    if not t.startswith("+"): return "+595" + t
    return t

# ---------- Sanitizar mensaje ----------
def sanitizar_mensaje(mensaje: str) -> str:
    """Elimina caracteres fuera del Basic Multilingual Plane (BMP)"""
    return ''.join(char for char in mensaje if ord(char) <= 0xFFFF)

# ---------- Clasificador simple de respuesta ----------
POSITIVOS = {"si", "sí", "ok", "dale", "voy", "perfecto", "listo", "de una", "seguro", "presente", "👍", "👏", "👌"}
NEGATIVOS = {"no", "no voy", "cancelo", "no puedo", "no podré", "no asistire", "no asistiré", "❌", "🚫"}

def clasificar_respuesta(texto: str):
    t = (texto or "").strip().lower()
    if any(p in t for p in POSITIVOS): return "Confirmada"
    if any(n in t for n in NEGATIVOS): return "Cancelada"
    return None

# ---------- Chrome (depuración remota) ----------
def find_chrome_binary():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if p and os.path.exists(p): return p
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
            last = e; time.sleep(1.0)
    raise RuntimeError(f"No se pudo adherir a Chrome con depuración remota: {last}")

# ---------- WhatsApp helpers ----------
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
            EC.presence_of_element_located((By.XPATH, '//header//*[@data-testid="conversation-info-header-chat-title"]')),
            EC.presence_of_element_located((By.XPATH, '//footer//*[@role="textbox" and @contenteditable="true"]'))
        )
    )
    time.sleep(0.8)

def esperar_caja_mensaje(driver):
    XPATHS = [
        '//footer//div[@contenteditable="true" and @data-lexical-editor="true"]',
        '//footer//*[@role="textbox" and @contenteditable="true"]',
        '//footer//div[@contenteditable="true" and @data-tab="10"]',
        '(//div[@contenteditable="true"])[last()]'
    ]
    last = None
    for xp in XPATHS:
        try:
            el = WebDriverWait(driver, CHAT_LOAD_TIMEOUT).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            el.click()
            return el
        except Exception as e:
            last = e
    raise last or TimeoutException("No se encontró el editor de mensajes.")

def contar_salientes(driver) -> int:
    try:
        bubbles = driver.find_elements(
            By.XPATH,
            '(//div[contains(@class,"message-out")]//div[@data-pre-plain-text])'
            ' | (//div[@data-pre-plain-text][ancestor::div[contains(@class,"message-out")]])'
            ' | (//div[contains(@class,"message-out")])'
        )
        return len(bubbles)
    except Exception:
        return 0

def click_boton_enviar(driver) -> bool:
    XPATHS_BTN = [
        '//button[@aria-label="Enviar"]',
        '//button[@aria-label="Send"]',
        '//button[@data-testid="send"]',
        '//button[@data-testid="compose-btn-send"]',
        '//span[@data-icon="send"]/ancestor::button',
        '//button[.//span[@data-icon="send"]]'
    ]
    for xp in XPATHS_BTN:
        try:
            btn = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.XPATH, xp)))
            driver.execute_script("arguments[0].scrollIntoView({block:\'center'});", btn)
            btn.click()
            return True
        except: pass
    return False

def enviar_mensaje_en_chat(driver, mensaje: str) -> bool:
    mensaje = sanitizar_mensaje(mensaje)
    composer = esperar_caja_mensaje(driver)
    intento = 0
    while intento <= RETRY_SENDS:
        try:
            driver.execute_script("""
                const el = arguments[0];
                el.focus();
                try {
                  document.execCommand('selectAll', false, null);
                  document.execCommand('delete', false, null);
                } catch(e) {}
            """, composer)
            lines = mensaje.splitlines()
            for i, linea in enumerate(lines):
                if linea: composer.send_keys(linea)
                if i < len(lines) - 1:
                    composer.send_keys(Keys.SHIFT, Keys.ENTER)
                    time.sleep(0.02)
            before = contar_salientes(driver)
            if not click_boton_enviar(driver):
                composer.send_keys(Keys.ENTER)
                time.sleep(0.2)
                composer.send_keys(Keys.ENTER)
            WebDriverWait(driver, 12).until(lambda d: contar_salientes(d) > before)
            logging.info("Mensaje confirmado como enviado.")
            return True
        except Exception as e:
            logging.warning(f"Reintento {intento+1} falló: {e}")
            intento += 1
            time.sleep(1.0)
    logging.error("No se confirmó el envío tras reintentos.")
    return False

def obtener_ultima_respuesta_entrante(driver) -> str | None:
    XPATHS = [
        '(//div[contains(@class,"message-in")]//*[self::span or self::div][@dir="ltr" or @role="paragraph"])[last()]',
        '(//div[contains(@class,"message-in")]//div[@data-lexical-text="true"])[last()]',
        '(//div[contains(@class,"message-in")]//*[contains(@class,"selectable-text")])[last()]',
    ]
    for xp in XPATHS:
        try:
            el = WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.XPATH, xp)))
            txt = (el.text or "").strip()
            if txt: return txt
        except: pass
    return None

# ---------- Principal ----------
def main():
    _guard = None
    driver = None
    session = None
    enviados_run = set()   # <- números ya procesados en ESTA corrida
    try:
        _guard = SingleInstance("envioWs")

        # DB
        engine = create_engine(DATABASE_URI, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()

        manana = (datetime.datetime.now() + datetime.timedelta(days=1)).date()
        logging.info(f"Consultando citas Programadas para: {manana}")

        query = text("""
            SELECT c.idcita, c.fecha_inicio, p.nombre, p.apellido, p.sexo, p.telefono
            FROM cita c
            JOIN paciente p ON c.idpaciente = p.idpaciente
            WHERE CAST(c.fecha_inicio AS date) = :manana
              AND c.estado = 'Programada'
            ORDER BY c.fecha_inicio
        """)
        rows = session.execute(query, {'manana': manana}).fetchall()
        logging.info(f"Citas encontradas: {len(rows)}")

        if not rows:
            logging.info("No hay turnos para mañana. Fin.")
            return

        # Selenium: depuración remota
        driver = build_driver_via_debug(BASE_PROFILE_DIR, PROFILE_NAME, DEBUG_PORT)

        logging.info("Abriendo WhatsApp Web…")
        driver.get("https://web.whatsapp.com/")
        time.sleep(QR_WAIT_SECONDS)  # Si el perfil ya está logueado, no pide QR
        cerrar_popup_si_existe(driver)

        for idcita, fecha_inicio, nombre, apellido, sexo, telefono in rows:
            telefono_norm = normalizar_telefono_py(telefono)
            if telefono_norm in enviados_run:
                logging.info(f"Ya procesado en esta corrida: {telefono_norm}. Omito.")
                continue

            if not telefono_norm.startswith("+595"):
                logging.warning(f"Teléfono inválido ({telefono}) para {nombre} {apellido}. Salteado.")
                continue

            tratamiento = "Sr." if (sexo or "").lower().startswith("m") else "Sra."
            hora_cita = fecha_inicio.strftime("%H:%M")

            mensaje = (
                f"{tratamiento} {nombre} {apellido}, soy el asistente virtual de *Clínica Margaritte* 🤖.\n"
                f"Le recordamos su cita para mañana a las {hora_cita}.\n"
                "¿Podría confirmarnos su asistencia?\n"
                "Responda por favor:\n"
                "*SI*\n"
                "*NO*\n"
                "Gracias por su tiempo y preferencia 💖"
            )

            url = f"https://web.whatsapp.com/send?phone={telefono_norm}"
            logging.info(f"Abrir chat: {url}")
            driver.get(url)

            try:
                esperar_chat_cargado(driver)
            except TimeoutException:
                logging.error(f"El chat de {telefono_norm} no cargó a tiempo.")
                continue

            cerrar_popup_si_existe(driver)

            # evitar duplicado: si el último saliente ya es igual al que voy a enviar
            ultimo = obtener_ultima_respuesta_entrante(driver)
            if _norm_min(ultimo) == _norm_min(mensaje):
                logging.info(f"Ya hay un recordatorio idéntico como último mensaje para {telefono_norm}. Omito envío.")
                continue

            if enviar_mensaje_en_chat(driver, mensaje):
                logging.info(f"Mensaje de recordatorio enviado a {telefono_norm}.")
                enviados_run.add(telefono_norm)
            else:
                logging.error(f"No se confirmó envío a {telefono_norm}.")
                continue

            logging.info(f"Proceso finalizado.")

    except Exception as e:
        logging.error(f"Error general: {e}")
        logging.error(traceback.format_exc())
        sys.exit(1)
    finally:
        try:
            if session: session.close()
        except: pass
        try:
            if driver: driver.quit()
        except: pass

if __name__ == "__main__":
    main()
