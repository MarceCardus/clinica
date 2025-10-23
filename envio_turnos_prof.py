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
from zoneinfo import ZoneInfo  # <-- IMPORTANTE: Para zona horaria correcta

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
QR_WAIT_SECONDS           = 30
CHAT_LOAD_TIMEOUT         = 35
BETWEEN_RECIPIENTS_WAIT   = (10, 20) # Reducido para agilizar
RETRY_SENDS               = 2

HEADER_PREFIX             = ""

BASE_PROFILE_DIR          = r"C:\selenium_ws_profile"
PROFILE_NAME              = "Default"
DEBUG_PORT                = 9223  # Puerto PROPIO para este script

LOG_FILE                  = "envio_turnos_prof.log"
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
        except Exception as e:
            logging.error(f"Error al intentar eliminar el archivo de bloqueo: {e}")

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
            for xp in ['.//button[@aria-label="Cerrar"]', './/button[.="Cerrar"]', './/button[.="OK"]', './/button[.="Aceptar"]', './/button[contains(.,"Entendido")]']:
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
        bubbles = driver.find_elements(By.XPATH, '(//div[contains(@class,"message-out")])')
        return len(bubbles)
    except:
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
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            btn.click()
            return True
        except: pass
    return False

def enviar_mensaje_en_chat(driver, mensaje: str) -> bool:
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
                if linea:
                    composer.send_keys(linea)
                if i < len(lines) - 1:
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
    
    # <-- DEFINIR ZONA HORARIA CORRECTA
    PYT_TZ = ZoneInfo("America/Asuncion")
    
    try:
        _guard = SingleInstance("envio_turnos_prof")

        engine = create_engine(DATABASE_URI, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()

        manana = (datetime.datetime.now(PYT_TZ) + datetime.timedelta(days=1)).date()
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
                   COALESCE(i.nombre, pt.nombre, prod.descripcion, '') AS tratamiento
            FROM cita c
            CROSS JOIN rango r -- Sintaxis un poco más clara que "JOIN ... ON TRUE"
            JOIN profesional pr ON c.idprofesional = pr.idprofesional
            JOIN paciente      pa ON c.idpaciente     = pa.idpaciente
            LEFT JOIN item       i  ON i.iditem       = c.iditem
            LEFT JOIN plan_tipo  pt ON pt.idplantipo  = c.idplantipo
            LEFT JOIN producto   prod ON prod.idproducto  = c.idproducto
            WHERE c.fecha_inicio >= r.d0_utc AND c.fecha_inicio < r.d1_utc
              AND c.estado IN ('Programada', 'Confirmada') -- Consideramos ambas
            ORDER BY pr.idprofesional, c.fecha_inicio
        """)
        rows = session.execute(query, {'manana': manana}).fetchall()
        logging.info(f"Citas encontradas: {len(rows)}")

        profesionales = {}
        for r in rows:
            (idprof, nprof, aprof, tel_prof, npac, apac, sexo, f_ini, tratamiento) = r
            d = profesionales.setdefault(idprof, {
                'nombre': (nprof or "").strip(),
                'apellido': (aprof or "").strip(),
                'telefono': tel_prof,
                'pacientes': []
            })
            
            # <-- HORA CORREGIDA USANDO ZONEINFO
            hora = f_ini.astimezone(PYT_TZ).strftime("%H:%M") 
            
            d['pacientes'].append({
                'nombre': npac, 'apellido': apac, 'sexo': (sexo or "").lower(),
                'hora': hora, 'tratamiento': (tratamiento or "").strip()
            })

        if not profesionales:
            logging.info("No hay turnos para mañana. Fin.")
            return

        driver, chrome_proc = build_driver_via_debug(BASE_PROFILE_DIR, PROFILE_NAME, DEBUG_PORT)
        logging.info("Abriendo WhatsApp Web…")
        driver.get("https://web.whatsapp.com/")
        
        # Espera manual para escanear QR si es necesario (el script se adherirá si ya está logueado)
        try:
             WebDriverWait(driver, QR_WAIT_SECONDS).until(
                EC.presence_of_element_located((By.XPATH, '//canvas[@aria-label="Scan me!"]'))
            )
             logging.info(f"Esperando {QR_WAIT_SECONDS} segundos para escaneo de QR...")
             time.sleep(QR_WAIT_SECONDS)
        except TimeoutException:
             logging.info("Canvas de QR no detectado, asumiendo que ya está logueado.")

        # Espera a que la interfaz principal cargue
        try:
            WebDriverWait(driver, CHAT_LOAD_TIMEOUT).until(
                EC.presence_of_element_located((By.ID, 'side'))
            )
            logging.info("WhatsApp Web cargado.")
        except TimeoutException:
            logging.error("No se pudo cargar la interfaz principal de WhatsApp Web a tiempo.")
            raise

        for id_prof, datos in profesionales.items():
            
            # <--- PASO 1 - CHEQUEAR SI YA SE ENVIÓ
            try:
                check_q = text("""
                    SELECT COUNT(*) FROM notificacion_profesional
                    WHERE idprofesional = :id_prof AND fecha_notificacion = :fecha
                """)
                resultado = session.execute(check_q, {'id_prof': id_prof, 'fecha': manana}).scalar_one()
                if resultado > 0:
                    logging.info(f"Notificación para {datos['nombre']} {datos['apellido']} ({id_prof}) para la fecha {manana} ya fue enviada. Omitiendo.")
                    continue
            except Exception as e:
                logging.error(f"Error al verificar la notificación para el profesional {id_prof}: {e}")
                continue # Mejor saltar que enviar doble
            
            nombre_prof = datos['nombre']; apellido_prof = datos['apellido']
            telefono_prof = normalizar_telefono_py(str(datos['telefono'] or "").strip())
            if not telefono_prof or not telefono_prof.startswith("+595"):
                logging.warning(f"{nombre_prof} {apellido_prof}: teléfono inválido ({datos['telefono']}).")
                continue

            header = f"{HEADER_PREFIX}{nombre_prof} {apellido_prof}, mañana tenés los siguientes pacientes:"
            pac_lines = []
            for pac in datos['pacientes']:
                emoji = "👨" if pac['sexo'].startswith("m") else "👩‍🦰"
                tto = pac['tratamiento'] if pac['tratamiento'] else "—"
                pac_lines.append(f"{emoji} *{pac['hora']}hs* - {pac['nombre']} {pac['apellido']} ({tto})")
            
            sep = "\n"
            mensaje = header + "\n\n" + sep.join(pac_lines)

            url = f"https://web.whatsapp.com/send?phone={telefono_prof}"
            logging.info(f"Abriendo chat con {nombre_prof} {apellido_prof}...")
            driver.get(url)

            try:
                esperar_chat_cargado(driver)
            except TimeoutException:
                logging.error(f"El chat de {telefono_prof} no cargó a tiempo.")
                # Chequear si es un número inválido
                try:
                    driver.find_element(By.XPATH, '//*[contains(text(),"El número de teléfono compartido")]')
                    logging.error("El número de teléfono es inválido según WhatsApp.")
                except:
                    pass # Era un timeout normal
                continue

            cerrar_popup_si_existe(driver)

            if enviar_mensaje_en_chat(driver, mensaje):
                logging.info(f"Enviado a {telefono_prof}.")

                # <--- PASO 2 - INSERTAR REGISTRO DE ENVÍO
                try:
                    insert_q = text("""
                        INSERT INTO notificacion_profesional (idprofesional, fecha_notificacion)
                        VALUES (:id_prof, :fecha)
                    """)
                    session.execute(insert_q, {'id_prof': id_prof, 'fecha': manana})
                    session.commit()
                    logging.info(f"Registro de notificación insertado para profesional {id_prof} para la fecha {manana}.")
                except Exception as e:
                    logging.error(f"¡FALLO CRÍTICO! El mensaje se envió pero no se pudo registrar en la BD para el prof {id_prof}: {e}")
                    logging.error("Esto podría causar un envío duplicado en el futuro. Revisar la BD.")
                    session.rollback()

            else:
                logging.error(f"No se confirmó envío a {telefono_prof}.")
            
            logging.info("Esperando antes del siguiente profesional...")
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
        if chrome_proc:
            try:
                chrome_proc.terminate()
            except: pass

if __name__ == "__main__":
    main()