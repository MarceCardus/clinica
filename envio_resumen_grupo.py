import time
import datetime
import logging
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

def obtener_resumen_confirmaciones(session, fecha_cita):
    rows = session.execute(
        text("""
            SELECT p.nombre, p.apellido, c.estado
            FROM cita c
            JOIN paciente p ON c.idpaciente = p.idpaciente
            WHERE date(c.fecha_inicio) = :fecha_cita
        """), {'fecha_cita': fecha_cita}
    ).fetchall()

    confirmados = [f"{r.nombre} {r.apellido}" for r in rows if r.estado == "Confirmada"]
    cancelados = [f"{r.nombre} {r.apellido}" for r in rows if r.estado == "Cancelada"]
    sin_respuesta = [f"{r.nombre} {r.apellido}" for r in rows if r.estado == "Programada"]

    mensaje = (
    f"Resumen de confirmaciones - {fecha_cita.strftime('%d/%m/%Y')}\n\n"
    f"Confirmaron ({len(confirmados)}): {', '.join(confirmados) if confirmados else 'Ninguno'}\n"
    f"Cancelaron ({len(cancelados)}): {', '.join(cancelados) if cancelados else 'Ninguno'}\n"
    f"Sin respuesta ({len(sin_respuesta)}): {', '.join(sin_respuesta) if sin_respuesta else 'Ninguno'}"
    )
    return mensaje

def enviar_mensaje_grupo(driver, grupo_nombre, mensaje):
    driver.get("https://web.whatsapp.com/")
    time.sleep(8)  # Asegura que todo cargue

    try:
        print("Buscando el campo de búsqueda global...")
        # Busca el campo de búsqueda global (más tolerante a cambios)
        search_boxes = driver.find_elements(By.XPATH, '//div[@contenteditable="true" and @data-tab="3"]')
        if not search_boxes:
            print("No se encontró el campo de búsqueda. Revisa si WhatsApp Web cargó bien.")
            return
        search_box = search_boxes[0]
        search_box.clear()
        search_box.click()
        print(f"Escribiendo nombre de grupo: {grupo_nombre}")
        search_box.send_keys(grupo_nombre)
        time.sleep(3)
        search_box.send_keys(Keys.ENTER)
        time.sleep(4)

        print("Buscando caja de mensaje...")
        # Busca la caja de mensaje del chat
        msg_box = driver.find_element(By.XPATH, '//footer//div[@contenteditable="true"]')
        for line in mensaje.split("\n"):
            msg_box.send_keys(line)
            msg_box.send_keys(Keys.SHIFT + Keys.ENTER)
        msg_box.send_keys(Keys.ENTER)
        print("Resumen enviado al grupo correctamente.")
        time.sleep(3)
    except Exception as e:
        print(f"No se pudo enviar el mensaje al grupo: {e}")

def main():
    engine = create_engine(DATABASE_URI)
    Session = sessionmaker(bind=engine)
    session = Session()
    grupo_nombre = "Grupo Margaritte Clínica Estetica"   # Cambia por el nombre de tu grupo EXACTAMENTE
    fecha = (datetime.datetime.now() + datetime.timedelta(days=1)).date()

    # Armar mensaje resumen
    mensaje = obtener_resumen_confirmaciones(session, fecha)

    # Preparar selenium
    profile_dir = r'C:\selenium_ws_profile'
    options = Options()
    options.add_argument(f'--user-data-dir={profile_dir}')
    service = Service(executable_path='chromedriver.exe')
    driver = webdriver.Chrome(service=service, options=options)

    # Enviar al grupo
    enviar_mensaje_grupo(driver, grupo_nombre, mensaje)
    driver.quit()
    session.close()

if __name__ == "__main__":
    main()
