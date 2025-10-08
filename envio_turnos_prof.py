# -*- coding: utf-8 -*-
import os
import sys
import time
import random
import logging
import traceback
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
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===================== AJUSTES =====================
QR_WAIT_SECONDS               = 30
CHAT_LOAD_TIMEOUT             = 35
AFTER_SEND_WAIT               = (8, 15)
BETWEEN_RECIPIENTS_WAIT       = (15, 30)
RETRY_SENDS                   = 2

INSERT_BLANK_LINE_BETWEEN     = False
HEADER_PREFIX                 = ""

BASE_PROFILE_DIR              = r"C:\selenium_ws_profile"
PROFILE_NAME                  = "Default"
DEBUG_PORT                    = 9223  # Puerto PROPIO para este script

FORCE_CLOSE_DEBUG_CHROME      = False  # No matar Chrome compartido

LOG_FILE                      = "envio_turnos_prof.log"
# ===================================================

# ---------- LOG ----------
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

def normalizar_telefono_py(telefono: str) -> str:
    if not telefono: return ""
    t = str(telefono).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if t.startswith("+595"): return t
    if t.startswith("595"):  return "+" + t
    if t.startswith("0"):    return "+595" + t[1:]
    if not t.startswith("+"): return "+595" + t
    return t

# ---------- Chrome paths ----------
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

# ---------- Lanzar / pegarse a Chrome con Remote Debug ----------
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
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc

def attach_driver_to_debugger(port: int) -> webdriver.Chrome:
    opts = ChromeOptions()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(90)
    return driver

def build_driver_via_debug(profile_dir: str, profile_name: str, port: int, wait_boot: float = 2.5):
    try:
        logging.info(f"Intentando adherirse a Chrome en 127.0.0.1:{port}…")
        drv = attach_driver_to_debugger(port)
        logging.info("Adherido a Chrome existente.")
        return drv, None
    except Exception as e:
        logging.info(f"No hay Chrome escuchando en {port}: {e}")

    logging.info("Lanzando Chrome con depuración remota…")
    proc = launch_chrome_with_debug(profile_dir, profile_name, port)
    time.sleep(wait_boot)

    for i in range(1, 6):
        try:
            drv = attach_driver_to_debugger(port)
            logging.info("Adherido a Chrome lanzado por el script.")
            return drv, proc
        except Exception as e:
            logging.info(f"Aún no disponible (intento {i}): {e}")
            time.sleep(1.0)

    try: proc.terminate()
    except: pass
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
            driver.execute_script("arguments[0].scrollIntoView({block:\'center\'});", btn)
            btn.click()
            return True
        except: pass
    return False

def insertar_linea_js(driver, composer, linea: str):
    driver.execute_script("""
        const el = arguments[0];
        const s  = arguments[1];
        el.focus();
        try {
          if (!document.execCommand('insertText', false, s)) {
            const esc = s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
            document.execCommand('insertHTML', false, esc);
          }
        } catch(e) {}
    """, composer, linea)

def enviar_mensaje_en_chat(driver, mensaje: str) -> bool:
    composer = esperar_caja_mensaje(driver)

    intento = 0
    while intento <= RETRY_SENDS:
        try:
            # limpiar editor
            driver.execute_script("""
                const el = arguments[0];
                el.focus();
                try {
                  document.execCommand('selectAll', false, null);
                  document.execCommand('delete', false, null);
                } catch(e) {}
            """, composer)

            # construir texto: líneas y párrafos
            paragraphs = mensaje.split("\n\n")   # doble salto = nuevo párrafo
            for p_idx, para in enumerate(paragraphs):
                lines = para.split("\n")
                for l_idx, line in enumerate(lines):
                    insertar_linea_js(driver, composer, line)
                    if l_idx < len(lines) - 1:
                        composer.send_keys(Keys.SHIFT, Keys.ENTER)
                if p_idx < len(paragraphs) - 1:
                    composer.send_keys(Keys.SHIFT, Keys.ENTER)
                    composer.send_keys(Keys.SHIFT, Keys.ENTER)

            time.sleep(0.2)

            before = contar_salientes(driver)

            if not click_boton_enviar(driver):
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
    _guard = None
    driver = None
    chrome_proc = None
    session = None
    try:
        _guard = SingleInstance("envio_turnos_prof")

        engine = create_engine(DATABASE_URI, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()

        manana = (datetime.datetime.now() + datetime.timedelta(days=1)).date()
        logging.info(f"Buscando turnos para: {manana}")

        query = text("""
            WITH rango AS (
              SELECT
                (TIMESTAMP :manana AT TIME ZONE 'America/Asuncion') AS d0_utc,
                ((TIMESTAMP :manana + INTERVAL '1 day') AT TIME ZONE 'America/Asuncion') AS d1_utc
            )
            SELECT pr.idprofesional,
                   pr.nombre   AS nombre_prof,
                   pr.apellido AS apellido_prof,
                   pr.telefono AS telefono_prof,
                   pa.nombre   AS nombre_pac,
                   pa.apellido AS apellido_pac,
                   COALESCE(pa.sexo,'') AS sexo,
                   c.fecha_inicio,
                   CASE
                       WHEN c.iditem IS NOT NULL THEN 'ITEM'
                       WHEN c.idplantipo IS NOT NULL THEN 'PLAN'
                       ELSE 'PROD'
                   END AS origen,
                   COALESCE(NULLIF(i.nombre, ''), NULLIF(pt.nombre, ''), NULLIF(prod.descripcion, '')) AS tratamiento
            FROM cita c
            JOIN rango r ON TRUE
            JOIN profesional pr ON c.idprofesional = pr.idprofesional
            JOIN paciente    pa ON c.idpaciente     = pa.idpaciente
            LEFT JOIN item       i   ON i.iditem      = c.iditem
            LEFT JOIN plan_tipo  pt  ON pt.idplantipo = c.idplantipo
            LEFT JOIN producto   prod ON prod.idproducto = c.idproducto
            WHERE c.fecha_inicio >= r.d0_utc AND c.fecha_inicio < r.d1_utc
            ORDER BY pr.idprofesional, c.fecha_inicio
        """)
        rows = session.execute(query, {'manana': manana}).fetchall()
        logging.info(f"Citas encontradas: {len(rows)}")

        profesionales = {}
        for r in rows:
            (idprof, nprof, aprof, tel_prof,
             npac, apac, sexo, f_ini, origen, tratamiento) = r

            d = profesionales.setdefault(idprof, {
                'nombre': (nprof or "").strip(),
                'apellido': (aprof or "").strip(),
                'telefono': tel_prof,
                'pacientes': []
            })
            hora = f_ini.strftime("%H:%M") if hasattr(f_ini, "strftime") else str(f_ini)[11:16]
            d['pacientes'].append({
                'nombre': npac,
                'apellido': apac,
                'sexo': (sexo or "").lower(),
                'hora': hora,
                'origen': origen,
                'tratamiento': (tratamiento or "").strip()
            })

        for pid, d in profesionales.items():
            logging.info(f"{d['nombre']} {d['apellido']}: {len(d['pacientes'])} pacientes")

        if not profesionales:
            logging.info("No hay turnos para mañana. Fin.")
            return

        driver, chrome_proc = build_driver_via_debug(BASE_PROFILE_DIR, PROFILE_NAME, DEBUG_PORT)
        logging.info("Abriendo WhatsApp Web…")
        driver.get("https://web.whatsapp.com/")
        time.sleep(QR_WAIT_SECONDS)

        for _, datos in profesionales.items():
            nombre_prof = datos['nombre']; apellido_prof = datos['apellido']
            telefono_prof = normalizar_telefono_py(str(datos['telefono'] or "").strip())
            if not telefono_prof or not telefono_prof.startswith("+595"):
                logging.warning(f"{nombre_prof} {apellido_prof}: teléfono inválido ({datos['telefono']}).")
                continue

            header = f"{HEADER_PREFIX}{nombre_prof} {apellido_prof}, mañana tenés los siguientes pacientes:"
            pac_lines = []
            for pac in datos['pacientes']:
                emoji = "👨" if pac['sexo'].startswith("m") else "👩‍🦰"
                if pac['origen'] == 'PLAN' and pac['tratamiento']:
                    tto = f"Plan: {pac['tratamiento']}"
                else:
                    tto = pac['tratamiento'] if pac['tratamiento'] else "—"
                pac_lines.append(f"{emoji} {pac['nombre']} {pac['apellido']}: {tto} a las {pac['hora']}")
            sep = "\n\n" if INSERT_BLANK_LINE_BETWEEN else "\n"
            mensaje = header + "\n" + sep.join(pac_lines)

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
                logging.info("Segundo intento tras refresco suave…")
                time.sleep(1.0)
                cerrar_popup_si_existe(driver)
                if not enviar_mensaje_en_chat(driver, mensaje):
                    logging.error(f"No se confirmó envío a {telefono_prof}.")
                else:
                    logging.info(f"Enviado a {telefono_prof} (2° intento).")
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
        if FORCE_CLOSE_DEBUG_CHROME:
            pass

if __name__ == "__main__":
    main()
