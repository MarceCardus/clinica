import time
import datetime
import os
import logging
import traceback
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URI

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# CONFIGURACIÓN DEL LOGGING
logging.basicConfig(
    filename="envioWs.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s"
)

def cerrar_popup_si_existe(driver, wait_time=2):
    """
    Cierra cualquier popup o modal que tape la caja de mensaje en WhatsApp Web.
    """
    try:
        time.sleep(wait_time)
        # Busca popups que puedan estar presentes (role="dialog")
        popups = driver.find_elements(By.XPATH, '//div[@role="dialog"]')
        for popup in popups:
            try:
                cerrar_btn = popup.find_element(By.XPATH, './/button[@aria-label="Cerrar"]')
                cerrar_btn.click()
                time.sleep(1)
                logging.info("Se cerró un popup/modal con botón 'Cerrar'.")
                return
            except Exception:
                botones = popup.find_elements(By.XPATH, './/button')
                for btn in botones:
                    txt = btn.get_attribute('aria-label') or btn.text
                    if txt and txt.strip().lower() in ("cerrar", "ok", "entendido", "close", "aceptar", "x"):
                        btn.click()
                        time.sleep(1)
                        logging.info(f"Se cerró un popup/modal con botón '{txt}'.")
                        return
    except Exception as e:
        logging.info("No se encontró popup a cerrar (o no pudo cerrarse).")
        pass

def main():
    try:
        logging.info("Arrancando script...")

        # Configurar conexión SQLAlchemy
        engine = create_engine(DATABASE_URI)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Calcular la fecha de mañana
        manana = (datetime.datetime.now() + datetime.timedelta(days=1)).date()

        # Consulta: pacientes agrupados por profesional
        query = text("""
            SELECT pr.idprofesional, pr.nombre as nombre_prof, pr.apellido as apellido_prof, pr.telefono as telefono_prof,
                   pa.nombre as nombre_pac, pa.apellido as apellido_pac, pa.sexo, c.fecha_inicio
            FROM cita c
            JOIN profesional pr ON c.idprofesional = pr.idprofesional
            JOIN paciente pa ON c.idpaciente = pa.idpaciente
            WHERE date(c.fecha_inicio) = :manana
            ORDER BY pr.idprofesional, c.fecha_inicio
        """)
        result = session.execute(query, {'manana': manana}).fetchall()

        # Agrupar los pacientes por profesional
        profesionales = dict()
        for row in result:
            idprof, nombre_prof, apellido_prof, telefono_prof, nombre_pac, apellido_pac, sexo, fecha_inicio = row
            if idprof not in profesionales:
                profesionales[idprof] = {
                    'nombre': nombre_prof,
                    'apellido': apellido_prof,
                    'telefono': telefono_prof,
                    'pacientes': []
                }
            profesionales[idprof]['pacientes'].append({
                'nombre': nombre_pac,
                'apellido': apellido_pac,
                'sexo': sexo,
                'hora': fecha_inicio.strftime("%H:%M")
            })

        logging.info(f"Profesionales con turnos mañana: {len(profesionales)}")
        if not profesionales:
            logging.info("No hay turnos para enviar, cerrando script.")
            session.close()
            return

        # --- SELENIUM CONFIG ---
        profile_dir = r'C:\selenium_ws_profile'
        if not os.path.exists(profile_dir):
            os.makedirs(profile_dir)

        options = Options()
        options.add_argument(f'--user-data-dir={profile_dir}')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        service = Service(executable_path='chromedriver.exe')
        driver = webdriver.Chrome(service=service, options=options)

        logging.info("Abriendo WhatsApp Web...")
        driver.get("https://web.whatsapp.com/")
        logging.info("Esperando 60 segundos para escanear el QR (sólo la primera vez)...")
        time.sleep(60)

        for prof_id, datos in profesionales.items():
            nombre_prof = datos['nombre']
            apellido_prof = datos['apellido']
            telefono_prof = str(datos['telefono']).strip()
            if not telefono_prof:
                logging.warning(f"Profesional {nombre_prof} {apellido_prof} NO tiene teléfono cargado. Saltando.")
                continue

            # Formato teléfono Paraguay
            if telefono_prof.startswith("0"):
                telefono_prof = "+595" + telefono_prof[1:]
            elif not telefono_prof.startswith("+"):
                telefono_prof = "+595" + telefono_prof

            # Armar el mensaje del día para el profesional
            mensaje = f"{nombre_prof} {apellido_prof}, mañana tenés los siguientes pacientes:\n\n"
            for pac in datos['pacientes']:
                emoji = "👨" if pac['sexo'] and pac['sexo'].lower().startswith("m") else "👩‍🦰"
                mensaje += f"{emoji} {pac['nombre']} {pac['apellido']} a las {pac['hora']}\n"
            mensaje = mensaje.strip()

            url = f"https://web.whatsapp.com/send?phone={telefono_prof}&text={mensaje.replace(' ', '%20').replace(chr(10), '%0A')}"
            logging.info(f"Abrir chat: {url}")
            driver.get(url)
            logging.info("Esperando que cargue el chat...")

            cerrar_popup_si_existe(driver)  # <<--- NUEVO: intenta cerrar popups antes de escribir

            try:
                # Espera que el chat esté listo y el input esté disponible, intenta varias veces si falla
                msg_box = None
                for intento in range(5):
                    try:
                        msg_box = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, '//footer//div[@contenteditable="true"]'))
                        )
                        break
                    except Exception:
                        cerrar_popup_si_existe(driver, wait_time=1)  # vuelve a intentar cerrar popup si falló
                        time.sleep(2)
                if not msg_box:
                    raise TimeoutException("No se encontró la caja de mensaje después de varios intentos.")

                # Click en el input solo si está visible y clickable
                driver.execute_script("arguments[0].focus();", msg_box)
                time.sleep(1)
                msg_box.send_keys(Keys.ENTER)
                logging.info(f"Mensaje enviado a {telefono_prof}")
                time.sleep(7)
            except TimeoutException:
                logging.error(f"No se encontró la caja de mensaje para {telefono_prof}. El chat puede no existir o el número no está en WhatsApp.")
            except Exception as e:
                logging.error(f"Error al enviar mensaje a {telefono_prof}: {e}")
                logging.error(traceback.format_exc())

        logging.info("Todos los mensajes han sido enviados o procesados.")
        session.close()
        driver.quit()
    except Exception as e:
        logging.error("Ocurrió un error general en el script: %s", str(e))
        logging.error(traceback.format_exc())
        try:
            session.close()
        except:
            pass
        try:
            driver.quit()
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
