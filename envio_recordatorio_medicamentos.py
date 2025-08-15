# envio_recordatorios_ws.py
import os
import sys
import time
import logging
import traceback
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
import urllib.parse
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
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# =========================
# LOGGING
# =========================
DELAY_BEFORE_QUIT_SECONDS = 20
logging.basicConfig(
    filename="envio_recordatorios.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# =========================
# UTILIDADES
# =========================
def normalizar_telefono_py(telefono: str) -> str:
    if not telefono:
        return ""
    t = str(telefono).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if t.startswith("+595"):
        return t
    if t.startswith("595"):
        return "+" + t
    if t.startswith("0"):
        return "+595" + t[1:]
    if not t.startswith("+"):
        return "+595" + t
    return t

def es_horario_habil(dt: datetime) -> bool:
    return dtime(8, 0) <= dt.time() <= dtime(17, 0)

def cerrar_popup_si_existe(driver, wait_time=2):
    """
    Cierra cualquier popup/modal que tape la caja de mensaje en WhatsApp Web.
    """
    try:
        time.sleep(wait_time)
        popups = driver.find_elements(By.XPATH, '//div[@role="dialog"]')
        for popup in popups:
            try:
                cerrar_btn = popup.find_element(By.XPATH, './/button[@aria-label="Cerrar"]')
                cerrar_btn.click()
                time.sleep(1)
                logging.info("Popup cerrado con botón 'Cerrar'.")
                return
            except Exception:
                botones = popup.find_elements(By.XPATH, './/button')
                for btn in botones:
                    txt = (btn.get_attribute('aria-label') or btn.text or "").strip().lower()
                    if txt in ("cerrar", "ok", "entendido", "close", "aceptar", "x"):
                        btn.click()
                        time.sleep(1)
                        logging.info(f"Popup cerrado con botón '{txt}'.")
                        return
    except Exception:
        logging.info("No se encontró popup para cerrar.")
        pass

def enviar_mensaje_whatsapp(driver, wait, numero: str, mensaje: str) -> bool:
    """
    Abre el chat con texto precargado y envía con ENTER.
    Devuelve True si el composer quedó vacío (se asume enviado).
    """
    # Armar URL (simple y efectivo: espacios -> %20, saltos de línea -> %0A)
    msg = urllib.parse.quote(mensaje, safe="")
    url = f"https://web.whatsapp.com/send?phone={numero.replace('+','')}&text={msg}"
    logging.info(f"Abrir chat: {url}")
    driver.get(url)

    cerrar_popup_si_existe(driver)

    # Esperar composer
    msg_box = None
    for intento in range(6):
        try:
            msg_box = wait.until(
                EC.presence_of_element_located((By.XPATH, '//footer//div[@contenteditable="true"]'))
            )
            break
        except Exception:
            cerrar_popup_si_existe(driver, wait_time=1)
            time.sleep(2)
    if not msg_box:
        logging.error("No se encontró la caja de mensaje (composer).")
        return False

    try:
        # Focus + ENTER
        driver.execute_script("arguments[0].focus();", msg_box)
        time.sleep(0.8)
        msg_box.send_keys(Keys.ENTER)
        time.sleep(1.6)

        # ¿Se vació el composer? (si sigue texto, no se envió)
        contenido = msg_box.get_attribute("textContent") or ""
        if not contenido.strip():
            logging.info("Mensaje enviado (composer vacío).")
            return True

        # Respaldo: intenta botón enviar
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//footer//button[@aria-label='Enviar']|//footer//span[@data-icon='send']"))
            )
            try:
                btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn)
            time.sleep(1.6)
            contenido = msg_box.get_attribute("textContent") or ""
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
    session: Session = SessionLocal()
    driver = None
    try:
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
            session.close()
            return

        # --- SELENIUM CONFIG ---
        profile_dir = r"C:\selenium_ws_profile"
        os.makedirs(profile_dir, exist_ok=True)

        options = Options()
        options.add_argument(f'--user-data-dir={profile_dir}')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--start-maximized')

        service = Service(executable_path='chromedriver.exe')
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 30)

        logging.info("Abriendo WhatsApp Web para iniciar sesión...")
        driver.get("https://web.whatsapp.com/")
        # Primera vez: tiempo para QR; luego ya entra directo.
        time.sleep(60)

        ventana_inicio_med = ahora - timedelta(hours=1)

        for rec in pendientes:
            try:
                # Datos básicos
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
                    # Enviar sólo si programado ∈ [ahora-1h, ahora]
                    if not (ventana_inicio_med <= programado <= ahora):
                        logging.info(f"[MED] fuera de ventana 1h (prog={programado}). Salteado.")
                        continue

                    indic = session.get(Indicacion, rec.idindicacion)
                    if not indic:
                        logging.warning(f"Indicación {rec.idindicacion} inexistente. Salteado.")
                        continue
                    insumo = session.get(Insumo, indic.idinsumo) if indic.idinsumo else None
                    nombre_med = insumo.nombre if (insumo and getattr(insumo, "nombre", None)) else "medicamento"

                    if not mensaje:
                        partes = [f"Recordatorio: tomar {nombre_med}"]
                        if getattr(indic, "dosis", None):
                            partes.append(str(indic.dosis))
                        if getattr(indic, "frecuencia_horas", None):
                            partes.append(f"cada {indic.frecuencia_horas} h")
                        mensaje = " ".join(partes).strip() + "."

                    # Hora en el mensaje
                    if programado <= ahora:
                        mensaje += f" Debiste tomarlo a las {hora_txt}."
                    else:
                        mensaje += f" Hora indicada: {hora_txt}."

                # ----- PROCEDIMIENTO -----
                elif getattr(rec, "idprocedimiento", None):
                    # Sólo se envía dentro del horario hábil actual (08–17)
                    if not es_horario_habil(ahora):
                        logging.info("[PROC] fuera del horario 08-17. Salteado.")
                        continue

                    proc = session.get(Procedimiento, rec.idprocedimiento)
                    if not proc:
                        logging.warning(f"Procedimiento {rec.idprocedimiento} inexistente. Salteado.")
                        continue
                    producto = session.get(Producto, getattr(proc, "idproducto", None)) if getattr(proc, "idproducto", None) else None
                    nombre_proc = producto.nombre if (producto and getattr(producto, "nombre", None)) else "control"
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
                    time.sleep(2)  # pequeño colchón para que WhatsApp termine el envío
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
        try:
            session.close()
        except Exception:
            pass
        # No cerramos el driver acá; el 'finally' esperará 20s y luego lo cerrará
        sys.exit(1)
    finally:
        try:
            session.close()
        except Exception:
            pass
        try:
            if driver:
                logging.info(f"Esperando {DELAY_BEFORE_QUIT_SECONDS}s antes de cerrar Chrome...")
                time.sleep(DELAY_BEFORE_QUIT_SECONDS)
                driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    procesar_recordatorios()
