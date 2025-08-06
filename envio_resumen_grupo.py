import time
import datetime
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URI  # Asegúrate de que esto apunte a tu cadena de conexión

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# --- Configuración logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


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
    logging.info("Abriendo WhatsApp Web. Esperando que cargue la página...")
    time.sleep(10)  # Aumentá si tu internet es muy lento

    try:
        # Busca el campo de búsqueda global
        logging.info("Buscando campo de búsqueda de chats...")
        search_boxes = driver.find_elements(By.XPATH, '//div[@contenteditable="true" and @data-tab="3"]')
        if not search_boxes:
            logging.error("No se encontró el campo de búsqueda. ¿WhatsApp Web cargó bien?")
            return
        search_box = search_boxes[0]
        search_box.clear()
        search_box.click()
        logging.info(f"Escribiendo nombre de grupo: {grupo_nombre}")
        search_box.send_keys(grupo_nombre)
        time.sleep(3)
        search_box.send_keys(Keys.ENTER)
        time.sleep(4)

        # Busca la caja de mensaje
        logging.info("Buscando caja de mensaje del chat...")
        msg_box = driver.find_element(By.XPATH, '//footer//div[@contenteditable="true"]')
        for line in mensaje.split("\n"):
            msg_box.send_keys(line)
            msg_box.send_keys(Keys.SHIFT + Keys.ENTER)  # Salto de línea
        msg_box.send_keys(Keys.ENTER)
        logging.info("Mensaje enviado correctamente al grupo.")
        time.sleep(3)
    except Exception as e:
        logging.error(f"No se pudo enviar el mensaje al grupo: {e}")


def main():
    # 1. Configuración DB y WhatsApp
    engine = create_engine(DATABASE_URI)
    Session = sessionmaker(bind=engine)
    session = Session()
    grupo_nombre = "Grupo Margaritte Clínica Estetica"   # <--- Cambia por el nombre exacto de tu grupo
    fecha = (datetime.datetime.now() + datetime.timedelta(days=1)).date()

    # 2. Armar mensaje resumen de confirmaciones
    logging.info(f"Obteniendo resumen de confirmaciones para el {fecha.strftime('%d/%m/%Y')}")
    mensaje = obtener_resumen_confirmaciones(session, fecha)
    logging.info("\n" + mensaje)

    # 3. Preparar selenium con perfil persistente para WhatsApp
    profile_dir = r'C:\selenium_ws_profile'  # <--- Usá siempre la misma carpeta para mantener la sesión
    options = Options()
    options.add_argument(f'--user-data-dir={profile_dir}')
    # Opcional: options.add_argument("--headless=new")  # Si querés sin ventana (no recomendado para WhatsApp)
    service = Service(executable_path='chromedriver.exe')  # <--- Ruta a tu chromedriver.exe
    driver = webdriver.Chrome(service=service, options=options)

    try:
        # 4. Enviar mensaje al grupo
        enviar_mensaje_grupo(driver, grupo_nombre, mensaje)
    finally:
        # 5. Cerrar todo correctamente
        driver.quit()
        session.close()
        logging.info("Finalizado.")

if __name__ == "__main__":
    main()
