# email_sender.py
"""
Módulo reutilizable para el envío de correos electrónicos.
Utiliza credenciales definidas en un archivo .env.
Soporta el envío de archivos adjuntos.
"""

import os
import sys
import smtplib
from email.message import EmailMessage
from pathlib import Path

# --- Dependencia ---
# Asegúrate de instalar python-dotenv:
# pip install python-dotenv
try:
    from dotenv import load_dotenv
except ImportError:
    print("Advertencia: `python-dotenv` no está instalado. El script esperará variables de entorno globales.")
    print("Para instalarlo, ejecuta: pip install python-dotenv")
    def load_dotenv(*args, **kwargs):
        pass # Función vacía si no está instalada

# --- Carga de Variables de Entorno ---

def load_env_config():
    """
    Carga el archivo .env desde la carpeta del script o ejecutable.
    Esto permite que la configuración funcione tanto en desarrollo como en producción
    (cuando se empaqueta con PyInstaller).
    """
    # Determina el directorio base (funciona para .py y para ejecutable)
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    
    # Carga el .env que está junto al script/ejecutable
    dotenv_path = base_dir / ".env"
    
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path, override=False)
    else:
        # Como fallback, intenta cargar desde el directorio actual
        load_dotenv(override=False)

# Cargar la configuración tan pronto como se importa el módulo
load_env_config()


# --- Función Principal de Envío ---

def send_email_with_attachment(subject: str, body: str, to_addr: str, attachment_path: str = None):
    """
    Envía un correo electrónico usando la configuración del archivo .env.
    Opcionalmente, puede adjuntar un archivo.

    Args:
        subject (str): El asunto del correo.
        body (str): El cuerpo del mensaje (texto plano).
        to_addr (str): La dirección del destinatario.
        attachment_path (str, optional): La ruta al archivo que se adjuntará. Defaults to None.
    
    Raises:
        ValueError: Si faltan variables de entorno para la configuración de SMTP.
        Exception: Si ocurre un error durante la conexión o el envío con el servidor SMTP.
    """
    # Carga las credenciales desde las variables de entorno
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    sender = os.getenv("SMTP_FROM", user)
    use_tls = os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes", "y")

    if not all([host, user, password, sender]):
        raise ValueError("Configuración SMTP incompleta. Revisa tu archivo .env y asegúrate de que contenga: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM")

    # Creación del mensaje
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    # Lógica para adjuntar el archivo si se proporciona una ruta
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            file_data = f.read()
            file_name = os.path.basename(attachment_path)
            
            # Determinar el tipo de archivo (puedes expandir esto si necesitas otros tipos)
            maintype, subtype = 'application', 'octet-stream' # Tipo genérico
            if file_name.endswith('.pdf'):
                subtype = 'pdf'
            elif file_name.endswith('.txt'):
                maintype = 'text'
                subtype = 'plain'

            msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=file_name)
    
    # Envío del correo
    try:
        # Conexión con TLS (para puerto 587)
        if use_tls:
            with smtplib.SMTP(host, port) as s:
                s.starttls()
                s.login(user, password)
                s.send_message(msg)
        # Conexión con SSL (para puerto 465)
        else:
            with smtplib.SMTP_SSL(host, port) as s:
                s.login(user, password)
                s.send_message(msg)
        
        print(f"✅ Correo enviado exitosamente a {to_addr}")

    except Exception as e:
        print(f"❌ Error al enviar el correo: {e}")
        # Re-lanzamos la excepción para que el programa que llamó a esta función
        # (tu app PyQt) sepa que algo salió mal.
        raise


# --- Bloque de Prueba ---
# Este código solo se ejecuta si corres este archivo directamente (ej: python email_sender.py)
# Es muy útil para probar que tu configuración .env es correcta sin tener que abrir la app.
if __name__ == "__main__":
    print("--- Iniciando prueba del módulo de envío de correos ---")
    
    # Lee el destinatario de prueba desde el .env o usa uno por defecto
    test_recipient = os.getenv("SMTP_TEST_RECIPIENT", "correo_de_prueba@ejemplo.com")

    print(f"Destinatario de prueba: {test_recipient}")
    
    try:
        # Prueba 1: Enviar un correo simple sin adjuntos
        print("\n1. Probando envío de correo simple...")
        send_email_with_attachment(
            subject="Prueba de Correo Simple",
            body="Hola,\n\nSi recibes esto, la configuración de tu correo funciona correctamente.\n\nSaludos.",
            to_addr=test_recipient
        )

        # Prueba 2: Crear un archivo de prueba y enviarlo como adjunto
        print("\n2. Probando envío con archivo adjunto...")
        test_file_path = "informe_de_prueba.txt"
        with open(test_file_path, "w") as f:
            f.write("Este es un archivo de prueba para el adjunto.")
        
        send_email_with_attachment(
            subject="Prueba de Correo con Adjunto",
            body="Hola,\n\nEste correo debería contener un archivo adjunto llamado 'informe_de_prueba.txt'.",
            to_addr=test_recipient,
            attachment_path=test_file_path
        )

        # Limpiar el archivo de prueba
        os.remove(test_file_path)

    except Exception as e:
        print(f"\n--- La prueba falló. ---")
        print("Por favor, revisa tus credenciales en el archivo .env y tu conexión a internet.")

    else:
        print("\n--- ¡Todas las pruebas finalizaron con éxito! ---")