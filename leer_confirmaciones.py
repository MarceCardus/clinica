import time
import datetime
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URI

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
# --- IMPORTACIONES NUEVAS ---
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# --------------------------
# CONFIGURACIÓN DE LOGS
# --------------------------
logging.basicConfig(
    filename="leer_confirmaciones.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# --------------------------
# FUNCIONES AUXILIARES
# --------------------------
# (Lock eliminado, no se usaba)

def normalizar_telefono_py(telefono):
    """Normaliza el formato del número telefónico (Paraguay)."""
    if not telefono:
        return ""
    telefono = (
        str(telefono)
        .strip()
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )
    if telefono.startswith("+595"):
        return telefono
    if telefono.startswith("595"):
        return "+" + telefono
    if telefono.startswith("0"):
        return "+595" + telefono[1:]
    if len(telefono) >= 9: # Asumimos que es un número local sin el 0
        return "+595" + telefono
    return telefono


def actualizar_confirmacion(session, idpaciente, respuesta, fecha_cita):
    """
    Actualiza el estado de la cita.
    OPTIMIZACIÓN: Se elimina el commit. El commit se hará al final del script.
    """
    nuevo_estado = "Confirmada" if respuesta == "SI" else "Cancelada"
    try:
        session.execute(
            text(""" 
                UPDATE cita
                SET estado = :nuevo_estado
                WHERE idpaciente = :idpaciente
                  AND date(fecha_inicio) = :fecha_cita
            """),
            {'nuevo_estado': nuevo_estado, 'idpaciente': idpaciente, 'fecha_cita': fecha_cita}
        )
    except Exception as e:
        logging.error(f"Error al preparar la actualización para {idpaciente}: {e}")
        # Revertimos cambios de esta sesión si algo falla
        session.rollback() 


# --------------------------
# PRINCIPAL
# --------------------------
def main():
    logging.info("Iniciando lectura de confirmaciones...")
    engine = create_engine(DATABASE_URI)
    Session = sessionmaker(bind=engine)
    session = Session()
    driver = None # Definimos driver aquí para que exista en el finally

    try:
        manana = (datetime.datetime.now() + datetime.timedelta(days=1)).date()

        # Traer teléfonos de pacientes con cita para mañana
        pacientes = session.execute(
            text(""" 
                SELECT p.idpaciente, p.nombre, p.apellido, p.telefono
                FROM cita c
                JOIN paciente p ON c.idpaciente = p.idpaciente
                WHERE date(c.fecha_inicio) = :manana
                  AND (c.estado IS NULL OR c.estado = 'Pendiente') -- Opcional: solo leer los no confirmados
            """),
            {'manana': manana}
        ).fetchall()

        if not pacientes:
            logging.info("No se encontraron pacientes con citas pendientes para mañana.")
            return # Salimos si no hay nada que hacer

        logging.info(f"Pacientes con cita para mañana: {len(pacientes)}")

        profile_dir = r'C:\selenium_ws_profile'
        options = Options()
        options.add_argument(f'--user-data-dir={profile_dir}')
        service = Service(executable_path='chromedriver.exe')
        driver = webdriver.Chrome(service=service, options=options)

        driver.get("https://web.whatsapp.com/")
        
        # --- OPTIMIZACIÓN: WebDriverWait ---
        # Esperamos un máximo de 30 segundos a que aparezca el panel lateral (ID="side")
        # Esto reemplaza a time.sleep(15)
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "side"))
            )
            logging.info("WhatsApp Web cargado (sesión iniciada).")
        except TimeoutException:
            logging.error("Error: WhatsApp Web tardó demasiado en cargar o no se inició sesión.")
            return # Salimos del script si no carga WA

        # Posibles respuestas
        respuestas_si = ("si", "sí", "sii", "síi", "s", "siii", "sip", "confirmo", "confirmado")
        respuestas_no = ("no", "nop", "n", "cancelo", "cancelar")

        for paciente in pacientes:
            idpaciente, nombre, apellido, telefono = paciente
            telefono_norm = normalizar_telefono_py(telefono)
            
            if not telefono_norm:
                logging.warning(f"Paciente {nombre} {apellido} (ID: {idpaciente}) no tiene teléfono.")
                continue

            url = f"https://web.whatsapp.com/send?phone={telefono_norm}"
            driver.get(url)

            try:
                # --- OPTIMIZACIÓN: WebDriverWait ---
                # Esperamos a que cargue el cuadro de texto del chat
                # Esto reemplaza a time.sleep(7)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//div[@title="Escribe un mensaje aquí"]'))
                )
                time.sleep(1) # Pequeña pausa para que rendericen los mensajes

            except TimeoutException:
                # Esto suele pasar si el número de teléfono es inválido
                logging.warning(f"No se pudo abrir el chat de {nombre} (Tel: {telefono_norm}). Probablemente número inválido.")
                continue

            try:
                # Buscamos todos los mensajes entrantes
                mensajes = driver.find_elements(By.XPATH, '//div[contains(@class,"message-in")]//span[@dir="ltr"]')
                if not mensajes:
                    logging.info(f"No hay mensajes entrantes de {nombre}.")
                    continue

                respuesta_encontrada = False
                
                # --- OPTIMIZACIÓN: Leer los últimos 3 mensajes ---
                # Iteramos en reversa (del más nuevo al más viejo)
                for mensaje in reversed(mensajes[-3:]): 
                    ultimo = mensaje.text.strip().lower()

                    if ultimo in respuestas_si:
                        actualizar_confirmacion(session, idpaciente, "SI", manana)
                        logging.info(f"{nombre} {apellido} CONFIRMÓ asistencia.")
                        print(f"{nombre} {apellido} CONFIRMÓ asistencia.")
                        respuesta_encontrada = True
                        break # Salimos del bucle de mensajes
                    
                    elif ultimo in respuestas_no:
                        actualizar_confirmacion(session, idpaciente, "NO", manana)
                        logging.info(f"{nombre} {apellido} CANCELÓ asistencia.")
                        print(f"{nombre} {apellido} CANCELÓ asistencia.")
                        respuesta_encontrada = True
                        break # Salimos del bucle de mensajes
                
                if not respuesta_encontrada:
                    logging.info(f"No se encontró respuesta (SI/NO) en los últimos mensajes de {nombre}.")

            except Exception as e:
                logging.error(f"Error leyendo mensaje de {nombre}: {e}")
                print(f"Error leyendo mensaje de {nombre}: {e}")

            time.sleep(2) # Pausa entre pacientes

        # --- OPTIMIZACIÓN: Commit Único ---
        # Hacemos commit de TODOS los cambios a la base de datos a la vez.
        session.commit()
        logging.info("Actualizaciones de la base de datos confirmadas (commit).")
        logging.info("Proceso finalizado correctamente.")

    except Exception as e:
        logging.error(f"Error CRÍTICO en el proceso: {e}")
        # Si algo falló, revertimos cualquier cambio que estuviera pendiente
        if session:
            session.rollback()
    
    finally:
        # Aseguramos que se cierre la sesión de la BD y el navegador
        if session:
            session.close()
        if driver:
            driver.quit()
        logging.info("Script terminado. Recursos cerrados.")


if __name__ == "__main__":
    main()