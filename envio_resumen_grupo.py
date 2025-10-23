# -*- coding: utf-8 -*-
import os
# import sys  <-- MODIFICADO: Eliminado por no usarse
import time
# import random  <-- MODIFICADO: Eliminado por no usarse
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

QR_WAIT_SECONDS   = 60 # <-- MODIFICADO: Aumentado a 60s por si tienes que escanear QR
CHAT_LOAD_TIMEOUT = 35
# RETRY_SENDS       = 2 <-- MODIFICADO: Eliminado por no usarse
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

# def sleep_jitter(a,b): time.sleep(random.uniform(a,b)) <-- MODIFICADO: Eliminado por no usarse

# ---------- Utils ----------
def _is_process_running(pid: int) -> bool:
    """Chequeo simple de si un PID existe (Windows/Linux). Sin dependencias externas."""
    if pid <= 0:
        return False
    try:
        # En Windows, abrir proceso con signal 0 no existe, pero os.kill funciona desde Py3.8
        # En Linux/Mac, os.kill(pid, 0) no mata, solo valida existencia.
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        # En algunos Windows duros, os.kill puede no estar permitido; asumimos no corre.
        return False

# ---------- Mutex ----------
class SingleInstance:
    """
    Lock con PID. Si existe y el proceso ya no vive, se limpia el lock.
    """
    def __init__(self, name):
        self.lock_path = os.path.join(tempfile.gettempdir(), f"{name}.lock")
        if os.path.exists(self.lock_path):
            try:
                with open(self.lock_path, "r", encoding="utf-8") as f:
                    old_pid_txt = f.read().strip()
                old_pid = int(old_pid_txt) if old_pid_txt.isdigit() else -1
            except Exception:
                old_pid = -1

            if old_pid > 0 and _is_process_running(old_pid):
                raise RuntimeError(f"Ya hay otra instancia ejecutándose (PID {old_pid}): {self.lock_path}")
            else:
                # Lock huérfano
                try:
                    os.remove(self.lock_path)
                except Exception:
                    pass

        with open(self.lock_path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))

        atexit.register(self.release)

    def release(self):
        try:
            if os.path.exists(self.lock_path):
                os.remove(self.lock_path)
        except Exception as e:
            logging.warning(f"No se pudo eliminar el archivo de bloqueo: {e}")

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
    # DEVUELVO el proceso para poder terminarlo luego si lo lanzamos nosotros
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc

def attach_driver_to_debugger(port: int) -> webdriver.Chrome:
    opts = ChromeOptions()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    drv = webdriver.Chrome(options=opts)
    drv.set_page_load_timeout(90)
    return drv

def build_driver_via_debug(profile_dir: str, profile_name: str, port: int, wait_boot=2.5):
    """
    Intenta adjuntarse a Chrome. Si no hay, lo lanza y devuelve (driver, chrome_proc | None).
    """
    chrome_proc = None
    try:
        logging.info(f"Intentando adherirse a Chrome en 127.0.0.1:{port}…")
        drv = attach_driver_to_debugger(port)
        return drv, chrome_proc
    except Exception as e:
        logging.info(f"No hay Chrome escuchando en {port}: {e}")

    logging.info("Lanzando Chrome con depuración remota…")
    chrome_proc = launch_chrome_with_debug(profile_dir, profile_name, port)
    time.sleep(wait_boot)

    last = None
    for _ in range(6):
        try:
            drv = attach_driver_to_debugger(port)
            return drv, chrome_proc
        except Exception as e:
            last = e
            time.sleep(1)

    # Si no pudimos adjuntarnos, intentemos matar el Chrome que lanzamos
    try:
        if chrome_proc and chrome_proc.poll() is None:
            chrome_proc.terminate()
    except Exception:
        pass

    raise RuntimeError(f"No se pudo adherir a Chrome con depuración remota: {last}")

# ---------- WhatsApp helpers ----------

# <-- MODIFICADO: Función mejorada para detectar QR
def esperar_login_o_qr(driver, qr_wait_timeout=60):
    """
    Espera a que WhatsApp cargue. Detecta si la sesión está iniciada (lista de chats)
    o si pide escanear un código QR.
    """
    XPATH_LISTA_CHATS = '//div[@data-testid="chat-list-search"]'
    XPATH_QR_CODE = '//div[@data-testid="qr-code"]'
    
    try:
        WebDriverWait(driver, 30).until(
            EC.any_of(
                # 1. Ya está logueado (espera lista de chats)
                EC.presence_of_element_located((By.XPATH, XPATH_LISTA_CHATS)),
                
                # 2. Pide QR
                EC.presence_of_element_located((By.XPATH, XPATH_QR_CODE))
            )
        )
        
        # Si estamos aquí, encontró algo. Verifiquemos si es el QR.
        try:
            driver.find_element(By.XPATH, XPATH_QR_CODE)
            # Si lo encuentra, significa que debemos esperar
            logging.warning(f"Se detectó Código QR. Esperando {qr_wait_timeout} segundos para escaneo manual...")
            
            # Ahora esperamos a que el QR desaparezca y aparezca la lista de chats
            WebDriverWait(driver, qr_wait_timeout).until(
                EC.presence_of_element_located((By.XPATH, XPATH_LISTA_CHATS))
            )
            logging.info("Escaneo de QR exitoso. WhatsApp cargado.")
            
        except:
            # Si falla en encontrar el QR, es porque ya estaba logueado
            logging.info("WhatsApp Web ya está cargado (sesión activa).")
            
    except TimeoutException:
        # Si falla la espera inicial (ni QR ni chats) o la espera del escaneo
        logging.error("No se pudo cargar WhatsApp Web (ni QR ni lista de chats) o no se escaneó el QR a tiempo.")
        raise # Volvemos a lanzar la excepción para que el main() falle


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
        
        # <-- MODIFICADO: Reemplazado time.sleep(2.0) por una espera explícita
        try:
            # Esperar a que aparezca el primer resultado en la lista de búsqueda
            WebDriverWait(driver, 7).until(
                EC.presence_of_element_located((
                    By.XPATH, 
                    "//div[@aria-label='Resultados de búsqueda']//span[@title]"
                ))
            )
            time.sleep(0.3) # Pequeña pausa para que se asiente
        except TimeoutException:
            logging.warning(f"No aparecieron resultados de búsqueda para '{nombre_chat}', se intentará ENTER de todas formas.")
        
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
        '//button[.//span[@data-icon="send"])]'
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

    confirmados   = [f"{r.nombre} {r.apellido}" for r in rows if (r.estado or "").lower() == "confirmada"]
    cancelados    = [f"{r.nombre} {r.apellido}" for r in rows if (r.estado or "").lower() == "cancelada"]
    sin_respuesta = [f"{r.nombre} {r.apellido}" for r in rows if (r.estado or "").lower() in ("", "programada", "pendiente")]

    mensaje = (
        f"📋 *Resumen de confirmaciones* – {fecha_cita.strftime('%d/%m/%Y')}\n\n"
        f"✅ Confirmaron ({len(confirmados)}): {', '.join(confirmados) if confirmados else 'Ninguno'}\n"
        f"❌ Cancelaron ({len(cancelados)}): {', '.join(cancelados) if cancelados else 'Ninguno'}\n"
        f"⏳ Sin respuesta ({len(sin_respuesta)}): {', '.join(sin_respuesta) if sin_respuesta else 'Ninguno'}"
    )
    return mensaje

def main():
    guard = None
    driver = None
    chrome_proc = None
    session = None
    try:
        guard = SingleInstance("envio_resumen_grupo")

        # pool_pre_ping=True evita errores por conexiones inactivas cerradas por el servidor
        engine = create_engine(DATABASE_URI, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()

        grupo_nombre = "Grupo Margaritte Clínica Estetica"  # <-- Ajustar si cambia el nombre
        fecha = (datetime.datetime.now() + datetime.timedelta(days=1)).date()

        mensaje = obtener_resumen_confirmaciones(session, fecha)
        logging.info("\n" + mensaje)

        driver, chrome_proc = build_driver_via_debug(BASE_PROFILE_DIR, PROFILE_NAME, DEBUG_PORT)
        driver.get("https://web.whatsapp.com/")
        try:
            # <-- MODIFICADO: Se llama a la nueva función que maneja el QR
            esperar_login_o_qr(driver, QR_WAIT_SECONDS)
        except TimeoutException:
            logging.error("WhatsApp Web no cargó a tiempo (ni login ni QR).")
            return
        
        # <-- MODIFICADO: Se eliminó el time.sleep(QR_WAIT_SECONDS) redundante
        
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
        # re-raise opcional si querés que falle en Scheduler
        # raise
    finally:
        # CIERRES ROBUSTOS
        try:
            if session:
                session.close()
        except Exception as e:
            logging.warning(f"Fallo cerrando sesión DB: {e}")

        try:
            if driver:
                driver.quit()
        except Exception as e:
            logging.warning(f"Fallo cerrando WebDriver: {e}")

        # Si ESTE script lanzó el Chrome (tenemos chrome_proc), lo cerramos.
        try:
            if chrome_proc and chrome_proc.poll() is None:
                chrome_proc.terminate()
                # Por si no termina:
                try:
                    chrome_proc.wait(timeout=5)
                except Exception:
                    chrome_proc.kill()
        except Exception as e:
            logging.warning(f"Fallo terminando Chrome lanzado por el script: {e}")

        # Soltar lock explícitamente (además de atexit)
        try:
            if guard:
                guard.release()
        except Exception:
            pass

if __name__ == "__main__":
    main()