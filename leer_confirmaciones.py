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
from threading import Lock

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
lock = Lock()

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
    if len(telefono) >= 9:
        return "+595" + telefono
    return telefono


def actualizar_confirmacion(session, idpaciente, respuesta, fecha_cita):
    """Actualiza el estado de la cita según la respuesta."""
    nuevo_estado = "Confirmada" if respuesta == "SI" else "Cancelada"
    session.execute(
        text(""" 
            UPDATE cita
            SET estado = :nuevo_estado
            WHERE idpaciente = :idpaciente
              AND date(fecha_inicio) = :fecha_cita
        """),
        {'nuevo_estado': nuevo_estado, 'idpaciente': idpaciente, 'fecha_cita': fecha_cita}
    )
    session.commit()

# --------------------------
# PRINCIPAL
# --------------------------
def main():
    logging.info("Iniciando lectura de confirmaciones...")
    engine = create_engine(DATABASE_URI)
    Session = sessionmaker(bind=engine)
    session = Session()

    manana = (datetime.datetime.now() + datetime.timedelta(days=1)).date()

    # Traer teléfonos de pacientes con cita para mañana
    pacientes = session.execute(
        text(""" 
            SELECT p.idpaciente, p.nombre, p.apellido, p.telefono
            FROM cita c
            JOIN paciente p ON c.idpaciente = p.idpaciente
            WHERE date(c.fecha_inicio) = :manana
        """),
        {'manana': manana}
    ).fetchall()

    logging.info(f"Pacientes con cita para mañana: {len(pacientes)}")

    profile_dir = r'C:\selenium_ws_profile'
    options = Options()
    options.add_argument(f'--user-data-dir={profile_dir}')
    service = Service(executable_path='chromedriver.exe')
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get("https://web.whatsapp.com/")
        logging.info("Esperando 15 segundos para cargar la sesión de WhatsApp Web...")
        time.sleep(15)

        for paciente in pacientes:
            idpaciente, nombre, apellido, telefono = paciente
            telefono_norm = normalizar_telefono_py(telefono)
            url = f"https://web.whatsapp.com/send?phone={telefono_norm}"
            driver.get(url)
            time.sleep(7)

            try:
                mensajes = driver.find_elements(By.XPATH, '//div[contains(@class,"message-in")]//span[@dir="ltr"]')
                if not mensajes:
                    continue

                ultimo = mensajes[-1].text.strip().lower()
                if ultimo in ("si", "sí", "sii", "síi", "s", "siii", "sip"):
                    actualizar_confirmacion(session, idpaciente, "SI", manana)
                    logging.info(f"{nombre} {apellido} CONFIRMÓ asistencia.")
                    print(f"{nombre} {apellido} CONFIRMÓ asistencia.")
                elif ultimo in ("no", "nop", "n"):
                    actualizar_confirmacion(session, idpaciente, "NO", manana)
                    logging.info(f"{nombre} {apellido} CANCELÓ asistencia.")
                    print(f"{nombre} {apellido} CANCELÓ asistencia.")
            except Exception as e:
                logging.error(f"Error leyendo mensaje de {nombre}: {e}")
                print(f"Error leyendo mensaje de {nombre}: {e}")

            time.sleep(2)

    except Exception as e:
        logging.error(f"Error en el proceso: {e}")
    finally:
        # Aseguramos que se cierre el navegador y libere cualquier recurso
        session.close()
        if driver:
            driver.quit()  # Aseguramos que el navegador se cierre
        logging.info("Finalizado correctamente.")


if __name__ == "__main__":
    main()
