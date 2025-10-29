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
from selenium.webdriver.common.action_chains import ActionChains

# ===================== AJUSTES =====================
BASE_PROFILE_DIR = r"C:\selenium_ws_profile"
PROFILE_NAME     = "Default"
DEBUG_PORT       = 9224

QR_WAIT_SECONDS      = 60
CHAT_LOAD_TIMEOUT    = 35
RETRY_SENDS          = 3
LOG_FILE             = "envioWs.log"
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
    for _ in range(1,6):
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

def limpiar_editor(driver, el):
    try:
        driver.execute_script("""
            const el = arguments[0];
            el.focus();
            try {
                document.execCommand('selectAll', false, null);
                document.execCommand('delete', false, null);
            } catch(e) {}
        """, el)
    except Exception:
        pass

def shift_enter(driver):
    ActionChains(driver).key_down(Keys.SHIFT).send_keys(Keys.ENTER).key_up(Keys.SHIFT).perform()
    time.sleep(0.05)

def insertar_linea_js(driver, el, linea: str) -> bool:
    try:
        driver.execute_script(
            "arguments[0].focus(); document.execCommand('insertText', false, arguments[1]);",
            el, linea
        )
        return True
    except Exception:
        return False

def pegar_desde_clipboard(driver, el, texto: str):
    driver.execute_script("""
        const txt = arguments[1];
        const ta = document.createElement('textarea');
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        ta.value = txt;
        document.body.appendChild(ta);
        ta.focus(); ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        arguments[0].focus();
    """, el, texto)
    ActionChains(driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()

def escribir_mensaje(driver, el, texto: str):
    lines = texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ok_all = True
    for i, line in enumerate(lines):
        ok = insertar_linea_js(driver, el, line)
        ok_all = ok_all and ok
        if i < len(lines) - 1:
            shift_enter(driver)
    if not ok_all:
        limpiar_editor(driver, el)
        pegar_desde_clipboard(driver, el, "\n".join(lines))

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

def last_outgoing_texts(driver, n=5):
    try:
        els = driver.find_elements(
            By.XPATH,
            '//div[contains(@class,"message-out")]//div[contains(@class,"selectable-text")]'
        )
        return [e.text for e in els[-n:]] if els else []
    except Exception:
        return []

def _norm_txt(s: str) -> str:
    return " ".join((s or "").replace("\r\n","\n").replace("\r","\n").replace("\u00A0"," ").split())

def ya_enviado_en_historial(driver, mensaje: str) -> bool:
    tgt = _norm_txt(mensaje)
    for t in last_outgoing_texts(driver, n=5):
        if _norm_txt(t) == tgt:
            return True
    return False

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
    intento = 0
    while intento <= RETRY_SENDS:
        try:
            if intento > 0 and ya_enviado_en_historial(driver, mensaje):
                logging.info("El último mensaje coincide; evito duplicado.")
                return True

            composer = esperar_caja_mensaje(driver)
            limpiar_editor(driver, composer)
            escribir_mensaje(driver, composer, mensaje)

            before = contar_salientes(driver)
            if not click_boton_enviar(driver):
                composer.send_keys(Keys.ENTER)

            WebDriverWait(driver, 12).until(
                lambda d: contar_salientes(d) > before or ya_enviado_en_historial(d, mensaje)
            )
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
    session = None
    enviados_run = set()
    try:
        _guard = SingleInstance("envioWs")

        # DB
        engine = create_engine(DATABASE_URI, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Asegurar columna estado_notificacion en plan_sesion
        try:
            session.execute(text("ALTER TABLE plan_sesion ADD COLUMN IF NOT EXISTS estado_notificacion VARCHAR(20)"))
            session.commit()
        except Exception:
            session.rollback()

        manana = (datetime.datetime.now() + datetime.timedelta(days=1)).date()
        logging.info(f"Consultando sesiones Programadas para: {manana}")

        # Usa tus nombres de campos: fecha_programada, idsesion, idterapeuta
        query = text("""
            SELECT 
                ps.idsesion       AS idsesion,
                ps.fecha_programada AS fecha_programada,
                p.nombre, p.apellido, p.sexo, p.telefono,
                pr.nombre         AS prof_nombre,
                pr.apellido       AS prof_apellido
            FROM plan_sesion ps
            JOIN plan_sesiones pl   ON pl.idplan = ps.idplan
            JOIN paciente p         ON p.idpaciente = pl.idpaciente
            LEFT JOIN profesional pr ON pr.idprofesional = ps.idterapeuta
            WHERE CAST(ps.fecha_programada AS date) = :manana
              AND ps.estado = 'PROGRAMADA'
              AND COALESCE(ps.estado_notificacion, 'Pendiente') = 'Pendiente'
            ORDER BY ps.fecha_programada
        """)
        rows = session.execute(query, {'manana': manana}).fetchall()
        logging.info(f"Sesiones encontradas para notificar: {len(rows)}")
        if not rows:
            logging.info("No hay sesiones pendientes de notificar para mañana. Fin.")
            return

        # Selenium
        driver = build_driver_via_debug(BASE_PROFILE_DIR, PROFILE_NAME, DEBUG_PORT)
        try: driver.maximize_window()
        except Exception: pass

        logging.info("Abriendo WhatsApp Web…")
        driver.get("https://web.whatsapp.com/")

        logging.info("Verificando UI principal de WhatsApp…")
        SELECTORS = [
            (By.XPATH, '//*[@data-testid="chat-list"]'),
            (By.XPATH, '//*[@data-testid="chatlist-panel"]'),
            (By.XPATH, '//*[@data-testid="chatlist-search-input"]'),
            (By.XPATH, '//div[@aria-label="Lista de chats"]'),
            (By.XPATH, '//div[@aria-label="Chat list"]'),
            (By.CSS_SELECTOR, 'footer [contenteditable="true"][role="textbox"]'),
            (By.XPATH, '//*[@data-testid="conversation-panel-messages"]'),
            (By.CSS_SELECTOR, '#pane-side'),
            (By.XPATH, '//*[@id="pane-side"]'),
        ]
        try:
            WebDriverWait(driver, QR_WAIT_SECONDS).until(
                EC.any_of(*[EC.presence_of_element_located(s) for s in SELECTORS])
            )
            logging.info("UI principal detectada; sesión iniciada.")
        except TimeoutException:
            try: has_qr = bool(driver.find_elements(By.XPATH, '//*[@data-testid="qrcode"]'))
            except Exception: has_qr = False
            try:
                driver.save_screenshot("whatsapp_timeout.png")
                logging.info("Guardada captura: whatsapp_timeout.png")
            except Exception: pass
            if has_qr:
                logging.error("Aparece QR: la sesión no está iniciada.")
                raise RuntimeError("No se pudo loguear a WhatsApp (pide QR).")
            if not driver.current_url.startswith("https://web.whatsapp.com/"):
                raise RuntimeError("No se pudo confirmar la UI de WhatsApp.")

        cerrar_popup_si_existe(driver)

        for (idsesion, fecha_programada, nombre, apellido, sexo, telefono,
             prof_nom, prof_ape) in rows:

            telefono_norm = normalizar_telefono_py(telefono)
            if telefono_norm in enviados_run:
                logging.info(f"Ya procesado en esta corrida: {telefono_norm}. Omito.")
                continue
            if not telefono_norm.startswith("+595"):
                logging.warning(f"Teléfono inválido ({telefono}) para {nombre} {apellido}. Salteado.")
                continue

            tratamiento = "Sr." if (sexo or "").lower().startswith("m") else "Sra."
            hora_txt = (fecha_programada or datetime.datetime.now()).strftime("%H:%M")

            if (prof_nom or prof_ape):
                nombre_prof = " ".join([x.strip() for x in [prof_nom or "", prof_ape or ""] if x])
                prof_clause = f" con la profesional {nombre_prof}"
            else:
                prof_clause = " (profesional a confirmar)"

            mensaje = (
                f"{tratamiento} {nombre} {apellido}, soy el asistente virtual de *Clínica Margaritte* 🤖.\n"
                f"Le recordamos su cita para mañana a las {hora_txt}{prof_clause}.\n"
                "¿Podría confirmarnos su asistencia?\n"
                "*SI*\n"
                "*NO*\n"
                "Gracias por su tiempo y preferencia 💖"
            )

            # ====== CLAIM ATÓMICO: tomar la fila ======
            try:
                claim_sql = text("""
                    UPDATE plan_sesion
                       SET estado_notificacion = 'Enviando'
                     WHERE idsesion = :id
                       AND COALESCE(estado_notificacion, 'Pendiente') IN ('Pendiente','Fallido')
                    RETURNING 1
                """)
                claimed = session.execute(claim_sql, {'id': idsesion}).fetchone()
                session.commit()
                if not claimed:
                    logging.info(f"Sesión {idsesion} ya tomada por otro proceso. Omito.")
                    continue
            except Exception as db_e:
                logging.error(f"No pude tomar sesión {idsesion}: {db_e}")
                session.rollback()
                continue
            # ==========================================

            url = f"https://web.whatsapp.com/send?phone={telefono_norm}"
            logging.info(f"Abrir chat: {url}")
            driver.get(url)

            try:
                esperar_chat_cargado(driver)
            except TimeoutException:
                logging.error(f"El chat de {telefono_norm} no cargó a tiempo.")
                cerrar_popup_si_existe(driver, wait_time=0.2)
                # devolver a NULL para reintento posterior
                try:
                    session.execute(text(
                        "UPDATE plan_sesion SET estado_notificacion = NULL WHERE idsesion = :id"
                    ), {'id': idsesion})
                    session.commit()
                except Exception:
                    session.rollback()
                continue

            cerrar_popup_si_existe(driver)

            # Si el mismo mensaje ya está en el chat, no reenvíes
            if ya_enviado_en_historial(driver, mensaje):
                logging.info("Mensaje idéntico ya presente en el chat; no reenvío.")
                try:
                    session.execute(text(
                        "UPDATE plan_sesion SET estado_notificacion='Enviado' WHERE idsesion=:id"
                    ), {'id': idsesion})
                    session.commit()
                except Exception:
                    session.rollback()
                enviados_run.add(telefono_norm)
                sleep_jitter(1.0, 1.8)
                continue

            try:
                if enviar_mensaje_en_chat(driver, mensaje):
                    logging.info(f"Mensaje de recordatorio enviado a {telefono_norm}.")
                    enviados_run.add(telefono_norm)
                    try:
                        session.execute(text(
                            "UPDATE plan_sesion SET estado_notificacion='Enviado' WHERE idsesion=:id"
                        ), {'id': idsesion})
                        session.commit()
                        logging.info(f"Sesión {idsesion} marcada como 'Enviado'.")
                    except Exception as db_e:
                        logging.error(f"Error al actualizar estado de sesión {idsesion}: {db_e}")
                        session.rollback()
                else:
                    logging.error(f"No se confirmó envío a {telefono_norm}.")
                    try:
                        session.execute(text(
                            "UPDATE plan_sesion SET estado_notificacion='Fallido' WHERE idsesion=:id"
                        ), {'id': idsesion})
                        session.commit()
                        logging.info(f"Sesión {idsesion} marcada como 'Fallido'.")
                    except Exception as db_e:
                        logging.error(f"Error al actualizar estado (Fallido) de sesión {idsesion}: {db_e}")
                        session.rollback()
                    continue
            except Exception as e:
                logging.error(f"Fallo irrecuperable al enviar a {telefono_norm}: {e}")
                try:
                    session.execute(text(
                        "UPDATE plan_sesion SET estado_notificacion='Fallido' WHERE idsesion=:id"
                    ), {'id': idsesion})
                    session.commit()
                    logging.info(f"Sesión {idsesion} marcada como 'Fallido' por error irrecuperable.")
                except Exception as db_e:
                    logging.error(f"Error al actualizar estado (Fallido) de sesión {idsesion}: {db_e}")
                    session.rollback()
                continue

            sleep_jitter(3.5, 6.0)

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
