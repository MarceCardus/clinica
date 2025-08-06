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

# CONFIGURAR LOGGING
logging.basicConfig(
    filename="envioWs.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s"
)

def normalizar_telefono_py(telefono):
    """Normaliza el teléfono para Paraguay (elimina espacios y signos)."""
    if not telefono:
        return ""
    telefono = str(telefono).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if telefono.startswith("+595"):
        return telefono
    if telefono.startswith("595"):
        return "+" + telefono
    if telefono.startswith("0"):
        return "+595" + telefono[1:]
    # Si ya tiene más de 10 dígitos pero no empieza con +, asume que le falta el "+"
    if len(telefono) >= 9:
        return "+595" + telefono
    return telefono

def clasificar_respuesta(texto):
    texto = texto.lower().strip()
    positivos = ["si", "sí", "ok", "dale", "voy", "perfecto", "listo", "de una", "seguro", "presente", "👍", "👏", "👌"]
    negativos = ["no", "no voy", "cancelo", "no puedo", "no podré", "no asistiré", "❌", "🚫"]

    for p in positivos:
        if p in texto:
            return "Confirmada"
    for n in negativos:
        if n in texto:
            return "Cancelada"
    if texto in ["👍", "👌", "👏", "😅"]:
        return "Confirmada"
    if texto in ["❌", "🚫"]:
        return "Cancelada"
    return None  # No se pudo interpretar

def cerrar_popup_si_existe(driver, wait_time=2):
    """Cierra cualquier popup o modal que tape la caja de mensaje en WhatsApp Web."""
    try:
        time.sleep(wait_time)
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

        # Consulta: citas para mañana (traer idcita para actualizar)
        query = text("""
            SELECT c.idcita, c.fecha_inicio, p.nombre, p.apellido, p.sexo, p.telefono
            FROM cita c
            JOIN paciente p ON c.idpaciente = p.idpaciente
            WHERE date(c.fecha_inicio) = :manana AND c.estado = 'Programada'
        """)
        result = session.execute(query, {'manana': manana})

        rows = list(result)
        logging.info(f"Cantidad de citas encontradas: {len(rows)}")
        if not rows:
            logging.info("No hay turnos para mañana, cerrando script.")
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

        for row in rows:
            idcita, fecha_inicio, nombre, apellido, sexo, telefono = row

            logging.info(f"Procesando cita: {fecha_inicio} - {nombre} {apellido} ({telefono})")

            tratamiento = "Sr." if sexo and sexo.lower().startswith("m") else "Sra."
            hora_cita = fecha_inicio.strftime("%H:%M")
            telefono_norm = normalizar_telefono_py(telefono)
            if not telefono_norm or not telefono_norm.startswith("+595"):
                logging.warning(f"Teléfono inválido para {nombre} {apellido}: {telefono}. Saltando.")
                continue

            mensaje = (
                f" {tratamiento} {nombre} {apellido}, soy el asistente virtual de *Clínica Margaritte*  🤖.\n"
                f"Le recordamos su cita para mañana a las {hora_cita}.\n"
                "¿Podría confirmarnos su asistencia?\n"
                "Responda por favor:\n"
                "✅ *SI* para confirmar\n"
                "❌ *NO* para cancelar\n"
                "Gracias por su tiempo y preferencia 💖"
            )

            # Codificar el mensaje para la URL
            mensaje_url = mensaje.replace(" ", "%20").replace("\n", "%0A")
            url = f"https://web.whatsapp.com/send?phone={telefono_norm}&text={mensaje_url}"
            logging.info(f"Abrir chat: {url}")
            driver.get(url)
            logging.info("Esperando que cargue el chat...")

            cerrar_popup_si_existe(driver)  # Cierra cualquier popup

            try:
                # Esperar hasta 5 veces si no encuentra la caja de texto
                msg_box = None
                for intento in range(5):
                    try:
                        msg_box = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, '//footer//div[@contenteditable="true"]'))
                        )
                        break
                    except Exception:
                        cerrar_popup_si_existe(driver, wait_time=1)
                        time.sleep(2)
                if not msg_box:
                    raise TimeoutException("No se encontró la caja de mensaje después de varios intentos.")

                driver.execute_script("arguments[0].focus();", msg_box)
                time.sleep(1)
                msg_box.send_keys(Keys.ENTER)
                logging.info(f"Mensaje enviado a {telefono_norm}: {mensaje}")
                time.sleep(7)

                # -- Leer y analizar la respuesta del paciente --
                try:
                    mensajes = driver.find_elements(By.XPATH, '//div[contains(@class,"message-in")]')
                    respuestas_paciente = []
                    for msg in mensajes[-5:]:
                        try:
                            texto = msg.find_element(By.XPATH, './/span[contains(@class,"selectable-text")]').text
                            if texto.strip():
                                respuestas_paciente.append(texto)
                        except Exception:
                            pass  # No es texto (puede ser sticker)

                    if respuestas_paciente:
                        respuesta = respuestas_paciente[-1]
                        nuevo_estado = clasificar_respuesta(respuesta)
                        logging.info(f"Respuesta paciente ({telefono_norm}): {respuesta} -> {nuevo_estado if nuevo_estado else 'Ambigua'}")

                        # Si reconociste la respuesta, actualizar la cita
                        if nuevo_estado:
                            session.execute(
                                text("""
                                    UPDATE cita
                                    SET estado = :nuevo_estado, modificado_en = :ahora
                                    WHERE idcita = :idcita
                                """),
                                {
                                    'nuevo_estado': nuevo_estado,
                                    'ahora': datetime.datetime.now(),
                                    'idcita': idcita
                                }
                            )
                            session.commit()
                    else:
                        logging.info(f"No hay respuesta del paciente ({telefono_norm}) aún.")
                except Exception as e:
                    logging.error(f"Error al leer respuesta o actualizar cita de {telefono_norm}: {e}")
                    logging.error(traceback.format_exc())

            except TimeoutException:
                logging.error(f"No se encontró la caja de mensaje para {telefono_norm}. El chat puede no existir o el número no está en WhatsApp.")
            except Exception as e:
                logging.error(f"Error al enviar mensaje a {telefono_norm}: {e}")
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
