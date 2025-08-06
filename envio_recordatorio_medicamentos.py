import time
from datetime import datetime
from sqlalchemy.orm import Session
from utils.db import SessionLocal
from models.recordatorio_paciente import RecordatorioPaciente
from models.paciente import Paciente
from models.producto import Producto

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
    return telefono

def enviar_mensaje_whatsapp(numero, mensaje, driver):
    try:
        url = f"https://web.whatsapp.com/send?phone={numero.replace('+', '')}&text={mensaje}"
        driver.get(url)
        time.sleep(8)  # Esperar a que cargue el chat
        input_box = driver.find_element(By.XPATH, "//div[@title='Escribe un mensaje aquí']")
        input_box.send_keys(Keys.ENTER)
        print(f"Mensaje enviado a {numero}")
        time.sleep(2)
        return True
    except Exception as e:
        print(f"Error enviando WhatsApp a {numero}: {e}")
        return False

def procesar_recordatorios_medicamentos():
    session: Session = SessionLocal()
    ahora = datetime.now()
    print(f"[{ahora}] Buscando recordatorios de medicamentos pendientes...")

    recordatorios = (
        session.query(RecordatorioPaciente)
        .filter(RecordatorioPaciente.fecha_recordatorio <= ahora)
        .filter(RecordatorioPaciente.estado != 'realizado')
        .all()
    )
    print(f"Se encontraron {len(recordatorios)} recordatorio(s) pendiente(s).")

    # Usá el perfil de Chrome que mantiene la sesión de WhatsApp Web
    profile_dir = r'C:\selenium_ws_profile'
    options = Options()
    options.add_argument(f'--user-data-dir={profile_dir}')
    service = Service(executable_path='chromedriver.exe')
    driver = webdriver.Chrome(service=service, options=options)
    driver.get("https://web.whatsapp.com/")
    print("Esperando que cargue WhatsApp Web (15 seg)...")
    time.sleep(15)

    for rec in recordatorios:
        producto = session.query(Producto).filter_by(idproducto=rec.idproducto).first()
        if not producto or not producto.tipo or producto.tipo.lower() != "medicamento":
            continue
        paciente = session.query(Paciente).filter_by(idpaciente=rec.idpaciente).first()
        if not paciente or not paciente.telefono:
            print(f"Paciente sin teléfono válido (ID {rec.idpaciente}).")
            continue
        numero = normalizar_telefono_py(paciente.telefono)
        mensaje = rec.mensaje or f"Recordatorio: tomar tu medicamento '{producto.nombre}' según lo indicado."
        exito = enviar_mensaje_whatsapp(numero, mensaje, driver)
        if exito:
            rec.estado = 'realizado'
            rec.fecha_envio = datetime.now()
            session.commit()
            print(f"Recordatorio enviado y marcado como realizado.")
        else:
            print(f"NO se pudo enviar a {numero}.")
    driver.quit()
    session.close()
    print("Proceso terminado.")

if __name__ == '__main__':
    procesar_recordatorios_medicamentos()
