# -*- coding: utf-8 -*-
"""
leer_confirmaciones.py
----------------------
Lee respuestas de confirmación de WhatsApp Web para las sesiones (plan_sesion) del día de mañana
y actualiza el estado de la CITA y un rastro en plan_sesion.parametros.

Cambios respecto a la versión previa:
- FIX: ps.estado es ENUM → usar sólo etiquetas válidas ('PROGRAMADA','REPROGRAMADA').
- Cálculo de "mañana" con zona horaria America/Asuncion (zoneinfo).
- WHERE de fecha robusto para timestamp/timestamptz (OR con AT TIME ZONE).
- Filtro de CITA: excluye Confirmada/Cancelada.
- Logs diagnósticos cuando no hay filas.
"""
import re
import json
import time
import datetime
import logging
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URI

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


# ===================== AJUSTES =====================

LOCAL_TZ = ZoneInfo("America/Asuncion")

BASE_PROFILE_DIR = r"C:\selenium_ws_profile"
PROFILE_NAME = "Default"

PAGELOAD_TIMEOUT = 60
CHAT_LOAD_TIMEOUT = 35
SEARCH_TIMEOUT = 20
LAST_MSG_TIMEOUT = 20

PATRON_SI = re.compile(r"\b(s[ií]|confirmo|sí)\b", re.IGNORECASE)
PATRON_NO = re.compile(r"\b(no|cancel[oó]|cancelo|cancelar)\b", re.IGNORECASE)

CSS_SIDE_SEARCH = "div[contenteditable='true'][data-tab='3']"
CSS_CHAT_HEADER = "header[role='button']"
CSS_MESSAGES_IN  = "div.message-in"
CSS_MSG_TEXT_SPAN = "span.selectable-text.copyable-text"


# ===================== LOGGING =====================

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


# ===================== DB =====================

def get_session():
    engine = create_engine(DATABASE_URI, pool_pre_ping=True, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()

def db_timezone(session) -> Optional[str]:
    try:
        return session.execute(text("SHOW TIME ZONE")).scalar_one_or_none()
    except Exception:
        return None

def sesiones_manana(session):
    """
    Devuelve filas para las sesiones programadas 'mañana' (hora local Asunción),
    que aún no estén confirmadas/canceladas en CITA.
    Columnas devueltas:
      idsesion, fecha_programada, idpaciente, nombre, apellido, telefono
    """
    ahora_py = datetime.datetime.now(LOCAL_TZ)
    manana = (ahora_py + datetime.timedelta(days=1)).date()

    sql = text("""
        SELECT
            ps.idsesion,
            ps.fecha_programada,
            p.idpaciente, p.nombre, p.apellido, p.telefono
        FROM plan_sesion ps
        JOIN plan_sesiones pl   ON pl.idplan = ps.idplan
        JOIN paciente p         ON p.idpaciente = pl.idpaciente
        LEFT JOIN cita c        ON c.idsesion = ps.idsesion
        WHERE (
                CAST(ps.fecha_programada AS date) = :manana
             OR CAST((ps.fecha_programada AT TIME ZONE 'America/Asuncion') AS date) = :manana
        )
          AND ps.estado IN ('PROGRAMADA','REPROGRAMADA')   -- ENUM válido
          AND COALESCE(c.estado, 'Pendiente') NOT IN ('Confirmada','Cancelada')
        ORDER BY ps.fecha_programada
    """)
    rows = session.execute(sql, {"manana": manana}).all()

    logging.info(f"Sesiones a verificar (mañana={manana}, TZ_Python={ahora_py.tzinfo}) = {len(rows)}")
    tz_db = db_timezone(session)
    if tz_db:
        logging.info(f"DB TimeZone = {tz_db}")

    if not rows:
        try:
            total_cast_simple = session.execute(text("""
                SELECT COUNT(*) FROM plan_sesion
                WHERE CAST(fecha_programada AS date) = :manana
                  AND estado IN ('PROGRAMADA','REPROGRAMADA')
            """), {"manana": manana}).scalar_one()
            total_cast_tz = session.execute(text("""
                SELECT COUNT(*) FROM plan_sesion
                WHERE CAST((fecha_programada AT TIME ZONE 'America/Asuncion') AS date) = :manana
                  AND estado IN ('PROGRAMADA','REPROGRAMADA')
            """), {"manana": manana}).scalar_one()
            logging.info(f"[DIAG] plan_sesion mañana (CAST simple) = {total_cast_simple} | (AT TIME ZONE) = {total_cast_tz}")
        except Exception as e:
            logging.warning(f"[DIAG] No se pudo hacer diagnóstico de conteo: {e}")

    return rows

def actualizar_confirmacion(session, idsesion: int, fecha_sesion: datetime.datetime,
                            respuesta: str, raw_text: str, msg_ref: Optional[str]):
    """
    respuesta: 'SI' o 'NO'
    Actualiza cita.estado y deja traza JSON en plan_sesion.parametros->confirmacion_ws.
    """
    nuevo_estado = "Confirmada" if respuesta.upper() == "SI" else "Cancelada"
    fecha_sesion_date = fecha_sesion.date()

    # 1) Actualizar CITA
    session.execute(
        text("""
            UPDATE cita
               SET estado = :nuevo_estado
             WHERE idsesion = :idsesion
               AND CAST(fecha_inicio AS date) = :f
        """),
        {"nuevo_estado": nuevo_estado, "idsesion": idsesion, "f": fecha_sesion_date}
    )

    # 2) Upsert JSON en plan_sesion.parametros
    payload = {
        "estado": nuevo_estado,
        "respuesta": respuesta,
        "texto": raw_text,
        "msg_ref": msg_ref,
        "ts": datetime.datetime.now(LOCAL_TZ).isoformat()
    }
    session.execute(
        text("""
            UPDATE plan_sesion
               SET parametros = COALESCE(parametros, '{}'::jsonb) || jsonb_build_object('confirmacion_ws', to_jsonb(:payload::json))
             WHERE idsesion = :idsesion
        """),
        {"payload": json.dumps(payload), "idsesion": idsesion}
    )


# ===================== SELENIUM / WHATSAPP =====================

def build_driver() -> webdriver.Chrome:
    opts = ChromeOptions()
    opts.add_argument(f"--user-data-dir={BASE_PROFILE_DIR}")
    opts.add_argument(f"--profile-directory={PROFILE_NAME}")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-sandbox")
    # opts.add_argument("--headless=new")  # si querés headless

    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(PAGELOAD_TIMEOUT)
    return driver

def abrir_whatsapp(driver: webdriver.Chrome):
    driver.get("https://web.whatsapp.com/")
    try:
        WebDriverWait(driver, PAGELOAD_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div#app"))
        )
        time.sleep(2)
    except TimeoutException:
        raise RuntimeError("No se pudo cargar WhatsApp Web (¿sesión no logueada?).")

def buscar_chat(driver: webdriver.Chrome, termino: str) -> bool:
    try:
        WebDriverWait(driver, SEARCH_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, CSS_SIDE_SEARCH))
        )
        buscador = driver.find_element(By.CSS_SELECTOR, CSS_SIDE_SEARCH)
        buscador.clear()
        buscador.send_keys(termino)
        time.sleep(1.2)

        resultados = driver.find_elements(By.CSS_SELECTOR, "div[role='listitem']")
        if not resultados:
            return False
        resultados[0].click()

        WebDriverWait(driver, CHAT_LOAD_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, CSS_CHAT_HEADER))
        )
        return True
    except Exception:
        return False

def leer_ultima_respuesta(driver: webdriver.Chrome) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    try:
        WebDriverWait(driver, LAST_MSG_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, CSS_MESSAGES_IN))
        )
    except TimeoutException:
        return (None, None, None)

    mensajes_in = driver.find_elements(By.CSS_SELECTOR, CSS_MESSAGES_IN)
    if not mensajes_in:
        return (None, None, None)

    ultimo = mensajes_in[-1]
    spans = ultimo.find_elements(By.CSS_SELECTOR, CSS_MSG_TEXT_SPAN)
    raw_text = " ".join(s.text for s in spans).strip() if spans else ""
    msg_id = ultimo.get_attribute("data-id") or ultimo.get_attribute("id")

    if raw_text:
        if PATRON_SI.search(raw_text):
            return ("SI", raw_text, msg_id)
        if PATRON_NO.search(raw_text):
            return ("NO", raw_text, msg_id)

    return (None, raw_text, msg_id)


# ===================== MAIN =====================

def main():
    setup_logging()
    logging.info("Iniciando lectura de confirmaciones (por plan_sesion)…")

    session = get_session()
    driver = None
    try:
        rows = sesiones_manana(session)
        if not rows:
            logging.info("No hay sesiones a verificar para mañana (o ya confirmadas).")
            return

        driver = build_driver()
        abrir_whatsapp(driver)

        for (idsesion, fecha_prog, idpac, nombre, apellido, telefono) in rows:
            tel = (telefono or "").strip()
            if not tel:
                logging.warning(f"idsesion={idsesion}: Paciente sin teléfono, omitido.")
                continue

            ok = buscar_chat(driver, tel)
            if not ok and tel.startswith("+"):
                ok = buscar_chat(driver, tel[1:])
            if not ok and tel.startswith("0"):
                ok = buscar_chat(driver, tel[1:])

            if not ok:
                logging.warning(f"idsesion={idsesion}: No se encontró chat para el teléfono '{tel}'.")
                continue

            resp, raw, msg_id = leer_ultima_respuesta(driver)

            if resp is None:
                logging.info(f"idsesion={idsesion}: Sin respuesta categorizable (último mensaje='{raw}').")
                continue

            try:
                actualizar_confirmacion(session, idsesion, fecha_prog, resp, raw or "", msg_id)
                session.commit()
                logging.info(f"idsesion={idsesion}: Actualizado => {resp} (msg_id={msg_id}).")
            except Exception as e:
                session.rollback()
                logging.error(f"idsesion={idsesion}: Error actualizando en DB: {e}")

    except Exception as e:
        logging.error(f"Error CRÍTICO: {e}")
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        try:
            session.close()
        except Exception:
            pass
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        logging.info("Recursos cerrados.")


if __name__ == "__main__":
    main()
