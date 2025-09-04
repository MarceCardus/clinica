# controllers/generador_recordatorios.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session


def validar_indicacion_medicamento(indicacion) -> List[str]:
    """
    Valida campos mínimos para una indicación de tipo MEDICAMENTO.
    Ahora sólo valida contra iditem.
    """
    errores: List[str] = []

    if not getattr(indicacion, "iditem", None):
        errores.append("Debe seleccionar un medicamento.")
    if not getattr(indicacion, "dosis", None):
        errores.append("Falta la dosis.")
    if not getattr(indicacion, "frecuencia_horas", None):
        errores.append("Falta la frecuencia (horas).")
    if not getattr(indicacion, "duracion_dias", None):
        errores.append("Falta la duración (días).")
    if not getattr(indicacion, "hora_inicio", None):
        errores.append("Falta la hora de inicio.")
    return errores


def _get_item_name(session: Session, indicacion) -> str:
    """
    Obtiene el nombre del Item asociado a la indicación (si está relacionado o por iditem).
    """
    rel = getattr(indicacion, "item", None)
    if rel and getattr(rel, "nombre", None):
        return rel.nombre

    try:
        from models.item import Item
        it = session.get(Item, getattr(indicacion, "iditem", None))
        return it.nombre if it else ""
    except Exception:
        return ""


def generar_recordatorios_medicamento(session: Session, indicacion) -> None:
    """
    Genera objetos RecordatorioPaciente a partir de una indicación de MEDICAMENTO.
    - No hace commit (lo hace el caller).
    - Usa DateTime = fecha + hora_inicio.
    - Setea idindicacion para poder borrarlos luego.
    """
    if not getattr(indicacion, "recordatorio_activo", False):
        return

    if not (getattr(indicacion, "fecha", None)
            and getattr(indicacion, "hora_inicio", None)
            and getattr(indicacion, "frecuencia_horas", None)
            and getattr(indicacion, "duracion_dias", None)):
        return

    from models.recordatorio_paciente import RecordatorioPaciente

    nombre_item = _get_item_name(session, indicacion)
    dosis_txt = (getattr(indicacion, "dosis", "") or "").strip()

    if nombre_item and dosis_txt:
        msg_base = f"Recordatorio: tomar {nombre_item} {dosis_txt}"
    elif nombre_item:
        msg_base = f"Recordatorio: tomar {nombre_item}"
    elif dosis_txt:
        msg_base = f"Recordatorio: {dosis_txt}"
    else:
        msg_base = "Recordatorio de medicación"

    inicio = datetime.combine(indicacion.fecha, indicacion.hora_inicio)
    cada_horas = max(1, int(indicacion.frecuencia_horas))
    total_horas = max(0, int(indicacion.duracion_dias)) * 24
    if total_horas == 0:
        return

    objs = [
        RecordatorioPaciente(
            idpaciente=indicacion.idpaciente,
            idindicacion=indicacion.idindicacion,
            fecha_recordatorio=inicio + timedelta(hours=h),
            mensaje=(msg_base + " ahora.").strip(),
            estado="pendiente",
        )
        for h in range(0, total_horas, cada_horas)
    ]

    session.bulk_save_objects(objs)


def eliminar_recordatorios_de_indicacion(session: Session, idindicacion: int) -> None:
    """
    Borra los recordatorios asociados a una indicación.
    No hace commit; lo maneja el caller.
    """
    from models.recordatorio_paciente import RecordatorioPaciente
    session.query(RecordatorioPaciente).filter(
        RecordatorioPaciente.idindicacion == idindicacion
    ).delete(synchronize_session=False)
