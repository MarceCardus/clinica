import time
import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URI

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

def normalizar_telefono_py(telefono):
    if not telefono:
        return ""
    telefono = str(telefono).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
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

def main():
    engine = create_engine(DATABASE_URI)
    Session = sessionmaker(bind=engine)
    session = Session()
    manana = (datetime.datetime.now() + datetime.timedelta(days=1)).date()

    # Traer teléfonos de pacientes con cita para mañana
    pacientes = session.execute(
        text("""
            SELECT p.idpaciente,p.nombre, p.apellido, p.telefono
            FROM cita c
            JOIN paciente p ON c.idpaciente = p.idpaciente
            WHERE date(c.fecha_inicio) = :manana
        """), {'manana': manana}
    ).fetchall()

    profile_dir = r'C:\selenium_ws_profile'
    options = Options()
    options.add_argument(f'--user-data-dir={profile_dir}')
    service = Service(executable_path='chromedriver.exe')
    driver = webdriver.Chrome(service=service, options=options)
    driver.get("https://web.whatsapp.com/")
    time.sleep(15)  # Esperar a que cargue la sesión

    for paciente in pacientes:
        idpaciente, nombre, apellido, telefono = paciente
        telefono_norm = normalizar_telefono_py(telefono)
        url = f"https://web.whatsapp.com/send?phone={telefono_norm}"
        driver.get(url)
        time.sleep(7)

        # Buscar los mensajes del chat
        try:
            mensajes = driver.find_elements(By.XPATH, '//div[contains(@class,"message-in")]//span[@dir="ltr"]')
            if not mensajes:
                continue
            ultimo = mensajes[-1].text.strip().lower()
            if ultimo in ("si", "sí", "sii", "síi","s", "siii", "sip"):
                actualizar_confirmacion(session, idpaciente, "SI", manana)
                print(f"{nombre} {apellido} CONFIRMÓ asistencia.")
            elif ultimo in ("no", "nop", "n"):
                actualizar_confirmacion(session, idpaciente, "NO", manana)
                print(f"{nombre} {apellido} CANCELÓ asistencia.")
        except Exception as e:
            print(f"Error leyendo mensaje de {nombre}: {e}")

        time.sleep(2)

    session.close()
    driver.quit()

if __name__ == "__main__":
    main()
