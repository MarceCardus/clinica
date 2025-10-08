# -*- coding: utf-8 -*-
import os
import time
import random
import logging
import datetime
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
DEBUG_PORT       = 9225  # Puerto propio para este script

QR_WAIT_SECONDS   = 30
CHAT_LOAD_TIMEOUT = 35
RETRY_SENDS       = 2
LOG_FILE          = "envio_resumen_grupo.log"
# ===================================================

# ---------- LOG ----------
logging.basicConfig(
    filename=LOG_FILE,
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
logging.getLogger("").addHandler(console)

def sleep_jitter(a,b): time.sleep(random.uniform(a,b))

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

# ---------- WhatsApp helpers ----------
def esperar_whatsapp_listo(driver):
    WebDriverWait(driver, 30).until(
        EC.any_of(
            EC.presence_of_element_located((By.XPATH, '//div[@data-testid="chat-list-search"]')),
            EC.presence_of_element_located((By.XPATH, '//footer//*[@role="textbox" and @contenteditable="true"]')),
            EC.presence_of_element_located((By.XPATH, '//header//*[@data-testid="conversation-info-header-chat-title"]'))
        )
    )

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

def buscar_y_abrir_chat_por_nombre(driver, nombre_chat: str) -> bool:
    """
    Busca en el buscador global de chats y ENTER sobre el primer resultado.
    """
    XPATHS_SEARCH = [
        '//div[@data-testid="chat-list-search"]//div[@contenteditable="true"]',
        '//div[@role="textbox" and @contenteditable="true" and @aria-label]',
        '(//div[@contenteditable="true"])[1]'
    ]
    search = None
    for xp in XPATHS_SEARCH:
        try:
            search = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xp)))
            break
        except: pass
    if not search:
        logging.error("No se encontró el buscador de chats.")
        return False

    try:
        search.click()
        for _ in range(40): search.send_keys(Keys.BACKSPACE)  # limpiar si quedó texto
        search.send_keys(nombre_chat)
        time.sleep(2.0)
        search.send_keys(Keys.ENTER)
        esperar_chat_cargado(driver)
        return True
    except Exception as e:
        logging.error(f"No se pudo abrir el chat '{nombre_chat}': {e}")
        return False

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
            driver.execute_script("arguments[0].scrollIntoView({block:\'center\'});", btn)
            btn.click()
            return True
        except: pass
    return False

def enviar_mensaje_en_chat(driver, mensaje: str) -> bool:
    box = esperar_caja_mensaje(driver)
    try:
        box.click()
        box.send_keys(Keys.CONTROL, 'a'); box.send_keys(Keys.DELETE)
        time.sleep(0.12)
        lines = mensaje.splitlines()
        for i, linea in enumerate(lines):
            if linea: box.send_keys(linea)
            if i < len(lines)-1:
                box.send_keys(Keys.SHIFT, Keys.ENTER)
                time.sleep(0.02)
        before = contar_salientes(driver)
        if not click_boton_enviar(driver):
            box.send_keys(Keys.ENTER)
        WebDriverWait(driver, 12).until(lambda d: contar_salientes(d) > before)
        logging.info("Mensaje confirmado como enviado.")
        return True
    except Exception as e:
        logging.error(f"Fallo al enviar: {e}")
        return False

# ---------- App ----------
def obtener_resumen_confirmaciones(session, fecha_cita: datetime.date) -> str:
    rows = session.execute(
        text("""
            SELECT p.nombre, p.apellido, c.estado
            FROM cita c
            JOIN paciente p ON c.idpaciente = p.idpaciente
            WHERE CAST(c.fecha_inicio AS date) = :fecha_cita
        """), {'fecha_cita': fecha_cita}
    ).fetchall()

    confirmados    = [f"{r.nombre} {r.apellido}" for r in rows if (r.estado or "").lower() == "confirmada"]
    cancelados     = [f"{r.nombre} {r.apellido}" for r in rows if (r.estado or "").lower() == "cancelada"]
    sin_respuesta  = [f"{r.nombre} {r.apellido}" for r in rows if (r.estado or "").lower() in ("", "programada", "pendiente")]

    mensaje = (
        f"📋 *Resumen de confirmaciones* – {fecha_cita.strftime('%d/%m/%Y')}\n\n"
        f"✅ Confirmaron ({len(confirmados)}): {', '.join(confirmados) if confirmados else 'Ninguno'}\n"
        f"❌ Cancelaron ({len(cancelados)}): {', '.join(cancelados) if cancelados else 'Ninguno'}\n"
        f"⏳ Sin respuesta ({len(sin_respuesta)}): {', '.join(sin_respuesta) if sin_respuesta else 'Ninguno'}"
    )
    return mensaje

def main():
    _guard = None
    driver = None
    session = None
    try:
        _guard = SingleInstance("envio_resumen_grupo")

        engine = create_engine(DATABASE_URI, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()

        grupo_nombre = "Grupo Margaritte Clínica Estetica"  # <-- Ajustar si cambia el nombre
        fecha = (datetime.datetime.now() + datetime.timedelta(days=1)).date()

        mensaje = obtener_resumen_confirmaciones(session, fecha)
        logging.info("\n" + mensaje)

        driver = build_driver_via_debug(BASE_PROFILE_DIR, PROFILE_NAME, DEBUG_PORT)
        driver.get("https://web.whatsapp.com/")
        try:
            esperar_whatsapp_listo(driver)
        except TimeoutException:
            logging.error("WhatsApp Web no cargó a tiempo.")
            return
        time.sleep(QR_WAIT_SECONDS)
        cerrar_popup_si_existe(driver)

        if not buscar_y_abrir_chat_por_nombre(driver, grupo_nombre):
            logging.error(f"No se pudo abrir el grupo '{grupo_nombre}'.")
            return
        cerrar_popup_si_existe(driver)

        if not enviar_mensaje_en_chat(driver, mensaje):
            logging.error("No se pudo confirmar el envío al grupo.")
        else:
            logging.info("Mensaje enviado correctamente al grupo.")

    except Exception as e:
        logging.error(f"Error general: {e}")
        raise
    finally:
        try:
            if session: session.close()
        except: pass
        try:
            if driver: driver.quit()
        except: pass

if __name__ == "__main__":
    main()
