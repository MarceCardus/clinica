# -*- coding: utf-8 -*-
import os
import sys
import time
import random
import logging
import traceback
import datetime
import subprocess
import shutil

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URI

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===================== AJUSTES =====================
QR_WAIT_SECONDS          = 30
CHAT_LOAD_TIMEOUT        = 35
AFTER_SEND_WAIT          = (8, 15)
BETWEEN_RECIPIENTS_WAIT  = (15, 30)
RETRY_SENDS              = 2

BASE_PROFILE_DIR = r"C:\selenium_ws_profile"        # tu perfil de WhatsApp
PROFILE_NAME     = "Default"                        # o "Profile 1"
DEBUG_PORT       = 9222                             # puerto de depuración remota

LOG_FILE         = "envioWs.log"
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

def sleep_jitter(rng_tuple): time.sleep(random.uniform(*rng_tuple))

def normalizar_telefono_py(telefono: str) -> str:
    if not telefono: return ""
    t = str(telefono).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if t.startswith("+595"): return t
    if t.startswith("595"):  return "+" + t
    if t.startswith("0"):    return "+595" + t[1:]
    if not t.startswith("+"): return "+595" + t
    return t

# ---------- Chrome Paths ----------
def find_chrome_binary():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    # último recurso: confiar en PATH
    return "chrome.exe"

# ---------- Lanzar/pegarse a Chrome con Remote Debug ----------
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
    # Lanzamos Chrome SIN bloquear el script
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def attach_driver_to_debugger(port: int) -> webdriver.Chrome:
    """
    Se adhiere a una instancia de Chrome ya abierta en 127.0.0.1:port.
    (NO se pasa user-data-dir aquí, eso lo maneja la instancia ya abierta)
    """
    opts = ChromeOptions()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    # Importantísimo: NO pasar --user-data-dir ni --profile-directory aquí.
    # Selenium Manager resolverá el driver compatible.
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(90)
    return driver

def build_driver_via_debug(profile_dir: str, profile_name: str, port: int, wait_boot: float = 2.5) -> webdriver.Chrome:
    """
    1) Intenta adherirse a Chrome en 127.0.0.1:port
    2) Si no hay nadie escuchando, lanza Chrome con ese perfil y puerto y luego se adhiere
    """
    # Intento 1: ya hay Chrome con debugger
    try:
        logging.info(f"Intentando adherirse a Chrome en 127.0.0.1:{port}…")
        drv = attach_driver_to_debugger(port)
        logging.info("Adherido a Chrome existente.")
        return drv
    except Exception as e:
        logging.info(f"No hay Chrome escuchando en {port}: {e}")

    # Intento 2: lanzamos Chrome y esperamos un toque
    logging.info("Lanzando Chrome con depuración remota…")
    launch_chrome_with_debug(profile_dir, profile_name, port)
    time.sleep(wait_boot)

    # Ahora nos adherimos
    for i in range(1, 6):
        try:
            drv = attach_driver_to_debugger(port)
            logging.info("Adherido a Chrome lanzado por el script.")
            return drv
        except Exception as e:
            logging.info(f"Aún no disponible (intento {i}): {e}")
            time.sleep(1.0)

    raise RuntimeError("No se pudo adherir a Chrome con depuración remota.")

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
                    btn = popup.find_element(By.XPATH, xp)
                    btn.click(); time.sleep(0.3); return
                except: pass
    except: pass

def esperar_chat_cargado(driver):
    WebDriverWait(driver, 25).until(
        EC.any_of(
            EC.presence_of_element_located((By.XPATH, '//header//*[@data-testid="conversation-info-header-chat-title"]')),
            EC.presence_of_element_located((By.XPATH, '//footer//*[@role="textbox" and @contenteditable="true"]'))
        )
    )

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
    composer = esperar_caja_mensaje(driver)
    intento = 0
    while intento <= RETRY_SENDS:
        try:
            composer.click()
            composer.send_keys(Keys.CONTROL, 'a'); composer.send_keys(Keys.DELETE)
            time.sleep(0.12)

            lines = mensaje.splitlines()
            for i, linea in enumerate(lines):
                if linea: composer.send_keys(linea)
                if i < len(lines) - 1:
                    composer.send_keys(Keys.SHIFT, Keys.ENTER)
                    time.sleep(0.02)

            before = contar_salientes(driver)

            sent = click_boton_enviar(driver)
            if not sent:
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

# ---------- Principal ----------
def main():
    driver = None
    session = None
    try:
        # --- DB ---
        engine = create_engine(DATABASE_URI, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()

        manana = (datetime.datetime.now() + datetime.timedelta(days=1)).date()
        logging.info(f"Buscando turnos para: {manana}")

        query = text("""
            SELECT pr.idprofesional,
                   pr.nombre   AS nombre_prof,
                   pr.apellido AS apellido_prof,
                   pr.telefono AS telefono_prof,
                   pa.nombre   AS nombre_pac,
                   pa.apellido AS apellido_pac,
                   COALESCE(pa.sexo,'') AS sexo,
                   c.fecha_inicio
            FROM cita c
            JOIN profesional pr ON c.idprofesional = pr.idprofesional
            JOIN paciente    pa ON c.idpaciente     = pa.idpaciente
            WHERE CAST(c.fecha_inicio AS date) = :manana
            ORDER BY pr.idprofesional, c.fecha_inicio
        """)
        rows = session.execute(query, {'manana': manana}).fetchall()
        logging.info(f"Citas encontradas: {len(rows)}")

        profesionales = {}
        for r in rows:
            idprof, nprof, aprof, tel_prof, npac, apac, sexo, f_ini = r
            d = profesionales.setdefault(idprof, {
                'nombre': (nprof or "").strip(),
                'apellido': (aprof or "").strip(),
                'telefono': tel_prof,
                'pacientes': []
            })
            hora = f_ini.strftime("%H:%M") if hasattr(f_ini, "strftime") else str(f_ini)[11:16]
            d['pacientes'].append({'nombre': npac, 'apellido': apac, 'sexo': (sexo or "").lower(), 'hora': hora})

        for pid, d in profesionales.items():
            logging.info(f"{d['nombre']} {d['apellido']}: {len(d['pacientes'])} pacientes")

        if not profesionales:
            logging.info("No hay turnos para mañana. Fin.")
            return

        # --- Selenium: adherirse/lanzar Chrome con depuración remota ---
        driver = build_driver_via_debug(BASE_PROFILE_DIR, PROFILE_NAME, DEBUG_PORT)

        logging.info("Abriendo WhatsApp Web…")
        driver.get("https://web.whatsapp.com/")
        time.sleep(QR_WAIT_SECONDS)  # si ya quedó logueado en ese perfil, no pedirá QR

        for _, datos in profesionales.items():
            nombre_prof = datos['nombre']; apellido_prof = datos['apellido']
            telefono_prof = normalizar_telefono_py(str(datos['telefono'] or "").strip())
            if not telefono_prof or not telefono_prof.startswith("+595"):
                logging.warning(f"{nombre_prof} {apellido_prof}: teléfono inválido ({datos['telefono']}).")
                continue

            lineas = [f"{nombre_prof} {apellido_prof}, mañana tenés los siguientes pacientes:", ""]
            for pac in datos['pacientes']:
                emoji = "👨" if pac['sexo'].startswith("m") else "👩‍🦰"
                lineas.append(f"{emoji} {pac['nombre']} {pac['apellido']} a las {pac['hora']}")
            mensaje = "\n".join(lineas)

            url = f"https://web.whatsapp.com/send?phone={telefono_prof}"
            logging.info(f"Abrir chat: {url}")
            driver.get(url)

            try:
                esperar_chat_cargado(driver)
            except TimeoutException:
                logging.error("El chat no cargó a tiempo.")
                continue

            cerrar_popup_si_existe(driver)

            if not enviar_mensaje_en_chat(driver, mensaje):
                logging.error(f"No se confirmó envío a {telefono_prof}.")
            else:
                logging.info(f"Enviado a {telefono_prof}.")

            sleep_jitter(AFTER_SEND_WAIT)
            sleep_jitter(BETWEEN_RECIPIENTS_WAIT)

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
            if driver: driver.quit()
        except: pass

if __name__ == "__main__":
    main()
