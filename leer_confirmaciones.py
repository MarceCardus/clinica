# -*- coding: utf-8 -*-
import os
import sys
import time
import random
import logging
import traceback
import datetime
import subprocess
import re

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URI

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ===================== AJUSTES =====================
BASE_PROFILE_DIR = r"C:\selenium_ws_profile"   # mismo perfil que usás para envío
PROFILE_NAME     = "Default"                    # o "Profile 1"
DEBUG_PORT       = 9222

QR_WAIT_SECONDS  = 30
CHAT_LOAD_TIMEOUT = 35
RETRY_READS       = 2
LOG_FILE          = "leer_confirmaciones.log"
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

# ---------- Normalizador ----------
def normalizar_telefono_py(telefono):
    if not telefono:
        return ""
    t = str(telefono).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if t.startswith("+595"): return t
    if t.startswith("595"):  return "+" + t
    if t.startswith("0"):    return "+595" + t[1:]
    if not t.startswith("+"): return "+595" + t
    return t

# ---------- Chrome helpers (misma estrategia que envioWs.py) ----------
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
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(90)
    return driver

def build_driver_via_debug(profile_dir: str, profile_name: str, port: int, wait_boot: float = 2.5) -> webdriver.Chrome:
    # 1) Intentar adherirse
    try:
        logging.info(f"Intentando adherirse a Chrome en 127.0.0.1:{port}…")
        drv = attach_driver_to_debugger(port)
        logging.info("Adherido a Chrome existente.")
        return drv
    except Exception as e:
        logging.info(f"No hay Chrome escuchando en {port}: {e}")

    # 2) Lanzar y adherirse
    logging.info("Lanzando Chrome con depuración remota…")
    launch_chrome_with_debug(profile_dir, profile_name, port)
    time.sleep(wait_boot)

    last = None
    for i in range(1, 6):
        try:
            drv = attach_driver_to_debugger(port)
            logging.info("Adherido a Chrome lanzado por el script.")
            return drv
        except Exception as e:
            last = e
            logging.info(f"Aún no disponible (intento {i}): {e}")
            time.sleep(1.0)
    raise RuntimeError(f"No se pudo adherir a Chrome con depuración remota: {last}")

# ---------- WhatsApp helpers ----------
def esperar_whatsapp_listo(driver):
    """Esperar header o caja de mensaje después de abrir WA Web."""
    WebDriverWait(driver, 30).until(
        EC.any_of(
            EC.presence_of_element_located((By.XPATH, '//header//*[@data-testid="conversation-info-header-chat-title"]')),
            EC.presence_of_element_located((By.XPATH, '//footer//*[@role="textbox" and @contenteditable="true"]')),
            EC.presence_of_element_located((By.XPATH, '//div[@data-testid="chat-list-search"]'))
        )
    )

def esperar_chat_cargado(driver):
    WebDriverWait(driver, CHAT_LOAD_TIMEOUT).until(
        EC.any_of(
            EC.presence_of_element_located((By.XPATH, '//header//*[@data-testid="conversation-info-header-chat-title"]')),
            EC.presence_of_element_located((By.XPATH, '//footer//*[@role="textbox" and @contenteditable="true"]'))
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
                    btn = popup.find_element(By.XPATH, xp)
                    btn.click(); time.sleep(0.3); return
                except: pass
    except: pass

def obtener_ultimo_mensaje_entrante(driver) -> str | None:
    """
    Intenta leer el texto del último mensaje ENTRANTE.
    Varias rutas por cambios de DOM.
    """
    XPATHS = [
        # spans de textos en burbujas entrantes
        '(//div[contains(@class,"message-in")]//*[self::span or self::div][@dir="ltr" or @role="paragraph"])[last()]',
        '(//div[contains(@class,"message-in")]//div[@data-lexical-text="true"])[last()]',
        '(//div[contains(@class,"message-in")]//*[contains(@class,"selectable-text")])[last()]',
        # fallback general al último texto visible en chat (podría tomar saliente si no hay entrantes)
        '(//*[self::span or self::div][@dir="ltr" or @role="paragraph"])[last()]',
    ]
    last_exc = None
    for xp in XPATHS:
        try:
            el = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, xp))
            )
            txt = (el.text or "").strip()
            if txt:
                return txt
        except Exception as e:
            last_exc = e
    logging.debug(f"No se pudo determinar el último mensaje entrante: {last_exc}")
    return None

AFFIRM_RE = re.compile(r'^(si|sí|sii+|sip|s)\W*$', re.IGNORECASE)
NEGAT_RE  = re.compile(r'^(no|nop|n)\W*$', re.IGNORECASE)

def clasificar_respuesta(txt: str) -> str | None:
    t = (txt or "").strip().lower()
    # quitar emojis y acentos/espacios sobrantes básicos
    t = t.replace("í", "i").replace("sí", "si")
    t = re.sub(r'[\u2700-\u27BF\u1F300-\u1FAD6]+', '', t)  # limpiar rango emojis simple
    t = t.strip()

    if AFFIRM_RE.match(t): return "SI"
    if NEGAT_RE.match(t):  return "NO"
    return None

# ---------- DB helpers ----------
def actualizar_confirmacion(session, idpaciente, respuesta, fecha_cita):
    # Mapear a tu dominio de estados
    nuevo_estado = "Confirmada" if respuesta == "SI" else "Cancelada"
    session.execute(
        text("""
            UPDATE cita
            SET estado = :nuevo_estado
            WHERE idpaciente = :idpaciente
              AND CAST(fecha_inicio AS date) = :fecha_cita
              AND (estado IS DISTINCT FROM :nuevo_estado)
        """),
        {'nuevo_estado': nuevo_estado, 'idpaciente': idpaciente, 'fecha_cita': fecha_cita}
    )
    session.commit()

def obtener_pacientes_de_manana(session, fecha_manana):
    rows = session.execute(
        text("""
            SELECT p.idpaciente, p.nombre, p.apellido, p.telefono
            FROM cita c
            JOIN paciente p ON c.idpaciente = p.idpaciente
            WHERE CAST(c.fecha_inicio AS date) = :manana
            GROUP BY p.idpaciente, p.nombre, p.apellido, p.telefono
            ORDER BY p.apellido, p.nombre
        """),
        {'manana': fecha_manana}
    ).fetchall()
    return rows

# ---------- Principal ----------
def main():
    driver = None
    session = None
    try:
        # --- DB con pool_pre_ping para resiliencia ---
        engine = create_engine(DATABASE_URI, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()

        manana = (datetime.datetime.now() + datetime.timedelta(days=1)).date()
        logging.info(f"Leyendo confirmaciones para citas del: {manana}")

        pacientes = obtener_pacientes_de_manana(session, manana)
        logging.info(f"Pacientes con cita mañana: {len(pacientes)}")

        if not pacientes:
            logging.info("No hay pacientes para mañana. Fin.")
            return

        # --- Chrome con depuración remota (igual que envioWs) ---
        driver = build_driver_via_debug(BASE_PROFILE_DIR, PROFILE_NAME, DEBUG_PORT)

        logging.info("Abriendo WhatsApp Web…")
        driver.get("https://web.whatsapp.com/")
        try:
            esperar_whatsapp_listo(driver)
        except TimeoutException:
            logging.error("WhatsApp Web no cargó a tiempo.")
            return
        time.sleep(QR_WAIT_SECONDS)  # si ya está logueado, no molesta

        for idpaciente, nombre, apellido, telefono in pacientes:
            telefono_norm = normalizar_telefono_py(telefono)
            if not telefono_norm.startswith("+595"):
                logging.warning(f"{nombre} {apellido}: teléfono inválido ({telefono}).")
                continue

            url = f"https://web.whatsapp.com/send?phone={telefono_norm}"
            logging.info(f"Abrir chat: {url}")
            driver.get(url)

            # Esperar chat y cerrar popups
            try:
                esperar_chat_cargado(driver)
            except TimeoutException:
                logging.error(f"Chat de {telefono_norm} no cargó a tiempo.")
                continue

            cerrar_popup_si_existe(driver)

            # Reintentos de lectura del último mensaje entrante
            intento = 0
            ultimo_txt = None
            while intento <= RETRY_READS:
                try:
                    ultimo_txt = obtener_ultimo_mensaje_entrante(driver)
                    if ultimo_txt:
                        break
                except Exception as e:
                    logging.info(f"Intento {intento+1} lectura falló: {e}")
                intento += 1
                time.sleep(1.0)

            if not ultimo_txt:
                logging.info(f"{nombre} {apellido}: sin mensajes para analizar.")
                continue

            clasif = clasificar_respuesta(ultimo_txt)
            logging.info(f"{nombre} {apellido}: último entrante='{ultimo_txt}' -> {clasif}")

            if clasif == "SI":
                actualizar_confirmacion(session, idpaciente, "SI", manana)
                logging.info(f"{nombre} {apellido} CONFIRMÓ asistencia.")
            elif clasif == "NO":
                actualizar_confirmacion(session, idpaciente, "NO", manana)
                logging.info(f"{nombre} {apellido} CANCELÓ asistencia.")
            else:
                logging.info(f"{nombre} {apellido}: respuesta no reconocida (sin cambios).")

            sleep_jitter(1.0, 2.0)

        logging.info("Lectura de confirmaciones finalizada.")

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
