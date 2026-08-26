# -*- coding: utf-8 -*-
# services/whatsapp.py
#
# Lógica compartida de WhatsApp (números, links wa.me, mensajes, turnos).
#
# Este módulo NO automatiza el navegador: sólo arma los datos y el link
# https://wa.me/... que la app abre para que el operador envíe con Enter.
# Es 100% gratis y no depende de Selenium ni del DOM de WhatsApp Web.
#
# Si algún día se migra a la WhatsApp Cloud API oficial, sólo hay que
# agregar acá una función enviar_cloud_api(...) reutilizando
# normalizar_telefono() y construir_mensaje().

from __future__ import annotations

import re
from datetime import datetime, date, timedelta
from urllib.parse import quote

# Nombre de la clínica que aparece en el mensaje.
CLINICA_NOMBRE = "Clínica Margaritte"

# Código de país por defecto (Paraguay = 595).
CODIGO_PAIS = "595"

# Plantilla del recordatorio. Placeholders disponibles:
#   {tratamiento} {nombre} {apellido} {hora} {clinica} {emoji}
# ({emoji} = 🌸 si es mujer, 👔 si es hombre)
PLANTILLA_DEFECTO = (
    "👋 ¡Hola {tratamiento} *{nombre} {apellido}*! {emoji}\n\n"
    "Le escribimos de *{clinica}* 💖\n\n"
    "🗓️ Le recordamos su cita para *mañana*\n"
    "🕐 Horario: *{hora}* hs\n\n"
    "¿Nos confirma su asistencia?\n"
    "✅ Escriba *SÍ* para confirmar\n"
    "❌ Escriba *NO* para cancelar\n\n"
    "¡Muchas gracias! Le esperamos ✨"
)

# Plantilla para el resumen del día a cada profesional.
# Placeholders: {tratamiento} {nombre} {apellido} {fecha} {cantidad} {pacientes} {clinica}
# {tratamiento} = el título que viene antes del nombre (Dra., Lic., etc.);
# ya incluye un espacio al final cuando corresponde, así que va pegado a {nombre}.
PLANTILLA_PROFESIONAL_DEFECTO = (
    "👋 ¡Hola *{tratamiento}{nombre} {apellido}*! 🩺\n\n"
    "Le enviamos su agenda para *{fecha}* desde *{clinica}* 💖\n\n"
    "📋 *{cantidad} pacientes* agendados:\n\n"
    "{pacientes}\n\n"
    "¡Que tenga excelente jornada! ✨"
)


def normalizar_telefono(telefono) -> str:
    """Devuelve el teléfono en formato internacional sólo dígitos (ej: 595981123456).

    Cadena vacía si no hay número. Misma lógica que usaban los scripts viejos.
    """
    if not telefono:
        return ""
    tel = str(telefono).strip()
    tel = re.sub(r"[^\d+]", "", tel)
    if tel.startswith("+"):
        tel = tel[1:]
    tel = re.sub(r"\D", "", tel)
    if not tel:
        return ""
    if tel.startswith("0"):
        tel = CODIGO_PAIS + tel[1:]
    if not tel.startswith(CODIGO_PAIS):
        tel = CODIGO_PAIS + tel
    return tel


def telefono_valido(telefono_norm: str) -> bool:
    """True si el número normalizado tiene largo razonable (país + celular)."""
    return bool(telefono_norm) and len(telefono_norm) >= 11


def link_wa(telefono_norm: str, mensaje: str) -> str:
    """Arma el link de WhatsApp Web con el mensaje precargado.

    Usamos web.whatsapp.com/send directo (no wa.me): el redirect de wa.me a
    veces corrompe los emojis de 3-4 bytes (✅❌🌸) al reprocesar el texto.
    """
    return f"https://web.whatsapp.com/send?phone={telefono_norm}&text={quote(mensaje)}"


def link_wa_desktop(telefono_norm: str, mensaje: str) -> str:
    """Arma el URI de la app de escritorio de WhatsApp.

    Abre WhatsApp Desktop (Windows/macOS) en su ventana única — cada nuevo
    envío cambia el chat, no abre otra pestaña. Requiere tener WhatsApp
    Desktop instalado (registra el protocolo whatsapp://).
    """
    return f"whatsapp://send?phone={telefono_norm}&text={quote(mensaje)}"


def abrir_whatsapp(telefono_norm: str, mensaje: str,
                   preferir_desktop: bool = True) -> None:
    """Abre el chat en WhatsApp Desktop (default) o WhatsApp Web.

    Si el protocolo whatsapp:// no está registrado (no hay app de escritorio),
    cae automáticamente al link web.
    """
    import os
    import webbrowser

    if preferir_desktop:
        uri = link_wa_desktop(telefono_norm, mensaje)
        # os.startfile respeta los protocolos registrados en Windows;
        # si whatsapp:// no está registrado devuelve OSError y probamos web.
        try:
            if hasattr(os, "startfile"):
                os.startfile(uri)  # type: ignore[attr-defined]
                return
            webbrowser.open(uri)
            return
        except OSError:
            pass  # sin app de escritorio; fallback a web

    webbrowser.open(link_wa(telefono_norm, mensaje))


def _tratamiento(sexo) -> str:
    s = (sexo or "").strip().lower()
    return "Sr." if s.startswith("m") else "Sra."


# Títulos que pueden venir pegados al nombre del profesional en la base.
# La clave es el prefijo en minúsculas (sin punto); el valor es cómo se muestra.
_TITULOS_PROF = {
    "dra": "Dra.", "dr": "Dr.",
    "lic": "Lic.", "lcda": "Lcda.", "lica": "Lic.",
    "prof": "Prof.", "od": "Od.", "klga": "Klga.", "klgo": "Klgo.",
}
_TITULO_PROF_RE = re.compile(
    r"^\s*(" + "|".join(sorted(_TITULOS_PROF, key=len, reverse=True)) + r")\.?\s+",
    re.IGNORECASE,
)


def _separar_titulo_profesional(nombre) -> tuple[str, str]:
    """Separa el título del nombre de un profesional.

    'Dra. Daisy'  -> ('Dra.', 'Daisy')
    'Lic Solange' -> ('Lic.', 'Solange')
    'Juan'        -> ('',      'Juan')

    Sólo las profesionales que en la base empiezan con 'Dra' quedan como
    'Dra.'; las demás usan lo que diga antes de su nombre (o nada).
    """
    nombre = (nombre or "").strip()
    m = _TITULO_PROF_RE.match(nombre)
    if not m:
        return "", nombre
    titulo = _TITULOS_PROF[m.group(1).lower()]
    resto = nombre[m.end():].strip()
    return titulo, resto


def _emoji_genero(sexo) -> str:
    s = (sexo or "").strip().lower()
    return "👔" if s.startswith("m") else "🌸"


def construir_mensaje(nombre, apellido, sexo, hora_str,
                      plantilla: str = PLANTILLA_DEFECTO,
                      clinica: str = CLINICA_NOMBRE) -> str:
    """Genera el texto del recordatorio a partir de la plantilla."""
    try:
        return plantilla.format(
            tratamiento=_tratamiento(sexo),
            emoji=_emoji_genero(sexo),
            nombre=(nombre or "").strip().title(),
            apellido=(apellido or "").strip().title(),
            hora=hora_str or "",
            clinica=clinica,
        )
    except (KeyError, IndexError):
        # Plantilla con placeholders inválidos: devolvemos el texto crudo
        # para no romper el envío.
        return plantilla


def construir_mensaje_profesional(nombre, apellido, fecha, pacientes,
                                  plantilla: str = PLANTILLA_PROFESIONAL_DEFECTO,
                                  clinica: str = CLINICA_NOMBRE) -> str:
    """Arma el resumen del día para un profesional.

    `pacientes` es una lista de dicts con nombre, apellido, sexo, hora, item.
    """
    fecha_str = fecha.strftime("%d/%m/%Y") if hasattr(fecha, "strftime") else str(fecha)
    lineas = []
    for p in pacientes:
        s = (p.get("sexo") or "").strip().lower()
        emoji = "👨" if s.startswith("m") else "👩"
        nom = (p.get("nombre") or "").strip().title()
        ape = (p.get("apellido") or "").strip().title()
        linea = f"{emoji} *{p.get('hora','')}* — {nom} {ape}".rstrip()
        if p.get("item"):
            linea += f"  _({p['item']})_"
        lineas.append(linea)
    pac_txt = "\n".join(lineas) if lineas else "—"

    titulo, nombre_limpio = _separar_titulo_profesional(nombre)
    # El tratamiento lleva un espacio al final para pegarse a {nombre} sin
    # dejar un espacio sobrante cuando el profesional no tiene título.
    tratamiento = f"{titulo} " if titulo else ""

    try:
        return plantilla.format(
            tratamiento=tratamiento,
            nombre=nombre_limpio.title(),
            apellido=(apellido or "").strip().title(),
            fecha=fecha_str,
            cantidad=len(pacientes),
            pacientes=pac_txt,
            clinica=clinica,
        )
    except (KeyError, IndexError):
        return plantilla


def resumen_por_profesional(session, fecha: date | None = None,
                            estados=("Programada",)) -> list[dict]:
    """Devuelve un item por profesional con la lista de sus turnos del día.

    Cada item:
        idprofesional, nombre, apellido, telefono, telefono_norm, valido,
        pacientes: [{nombre, apellido, sexo, hora, item}, ...]
    """
    from models.agenda import Cita

    if fecha is None:
        fecha = (datetime.now() + timedelta(days=1)).date()

    dia_ini = datetime.combine(fecha, datetime.min.time())
    dia_fin = dia_ini + timedelta(days=1)

    q = (session.query(Cita)
         .filter(Cita.fecha_inicio >= dia_ini,
                 Cita.fecha_inicio < dia_fin))
    if estados:
        q = q.filter(Cita.estado.in_(list(estados)))
    q = q.order_by(Cita.idprofesional, Cita.fecha_inicio.asc())

    grupos: dict[int, dict] = {}
    for c in q.all():
        prof = c.profesional
        if not prof:
            continue
        idp = prof.idprofesional
        if idp not in grupos:
            tel_norm = normalizar_telefono(getattr(prof, "telefono", ""))
            grupos[idp] = {
                "idprofesional": idp,
                "nombre": prof.nombre or "",
                "apellido": prof.apellido or "",
                "telefono": prof.telefono or "",
                "telefono_norm": tel_norm,
                "valido": telefono_valido(tel_norm),
                "pacientes": [],
            }
        pac = c.paciente
        item = getattr(c, "item", None)
        grupos[idp]["pacientes"].append({
            "nombre": getattr(pac, "nombre", "") if pac else "",
            "apellido": getattr(pac, "apellido", "") if pac else "",
            "sexo": getattr(pac, "sexo", "") if pac else "",
            "hora": c.fecha_inicio.strftime("%H:%M") if c.fecha_inicio else "",
            "item": getattr(item, "nombre", "") if item else "",
        })
    return list(grupos.values())


def citas_para_recordar(session, fecha: date | None = None,
                        estados=("Programada",)) -> list[dict]:
    """Devuelve los turnos de una fecha listos para recordar.

    Cada item es un dict autónomo (no depende de la sesión abierta):
        idcita, idpaciente, nombre, apellido, sexo, telefono,
        telefono_norm, valido, hora, fecha_inicio, profesional, estado
    """
    from models.agenda import Cita

    if fecha is None:
        fecha = (datetime.now() + timedelta(days=1)).date()

    dia_ini = datetime.combine(fecha, datetime.min.time())
    dia_fin = dia_ini + timedelta(days=1)

    q = (session.query(Cita)
         .filter(Cita.fecha_inicio >= dia_ini,
                 Cita.fecha_inicio < dia_fin))
    if estados:
        q = q.filter(Cita.estado.in_(list(estados)))
    q = q.order_by(Cita.fecha_inicio.asc())

    resultado = []
    for c in q.all():
        pac = c.paciente
        prof = c.profesional
        tel_raw = getattr(pac, "telefono", None) if pac else None
        tel_norm = normalizar_telefono(tel_raw)
        hora = c.fecha_inicio.strftime("%H:%M") if c.fecha_inicio else ""
        resultado.append({
            "idcita": c.idcita,
            "idpaciente": c.idpaciente,
            "nombre": getattr(pac, "nombre", "") if pac else "",
            "apellido": getattr(pac, "apellido", "") if pac else "",
            "sexo": getattr(pac, "sexo", "") if pac else "",
            "telefono": tel_raw or "",
            "telefono_norm": tel_norm,
            "valido": telefono_valido(tel_norm),
            "hora": hora,
            "fecha_inicio": c.fecha_inicio,
            "profesional": (f"{getattr(prof, 'nombre', '')} "
                            f"{getattr(prof, 'apellido', '')}").strip() if prof else "",
            "estado": c.estado,
        })
    return resultado
