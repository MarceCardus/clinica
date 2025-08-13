from datetime import datetime, timedelta
from sqlalchemy.orm import Session

def validar_indicacion_medicamento(indicacion) -> list[str]:
    errores = []
    if not getattr(indicacion, "idinsumo", None):
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

def generar_recordatorios_medicamento(session: Session, indicacion):
    """
    Crea recordatorios en recordatorio_paciente a partir de una indicación.
    Usa DateTime (fecha + hora) y setea idindicacion.
    """
    if not (indicacion.hora_inicio and indicacion.frecuencia_horas and indicacion.duracion_dias):
        return  # Falta info mínima

    from models.recordatorio_paciente import RecordatorioPaciente
    from models.insumo import Insumo

    nombre_insumo = ""
    if indicacion.idinsumo:
        ins = session.get(Insumo, indicacion.idinsumo)
        nombre_insumo = ins.nombre if ins else ""

    dosis = (indicacion.dosis or "").strip()
    msg_base = f"Recordatorio: tomar {nombre_insumo} {dosis}".strip()

    inicio = datetime.combine(indicacion.fecha, indicacion.hora_inicio)
    cada_horas = max(1, int(indicacion.frecuencia_horas))
    total_horas = max(0, int(indicacion.duracion_dias)) * 24

    objs = []
    for h in range(0, total_horas, cada_horas):
        objs.append(RecordatorioPaciente(
            idpaciente=indicacion.idpaciente,
            idindicacion=indicacion.idindicacion,
            fecha_recordatorio=inicio + timedelta(hours=h),
            mensaje=(msg_base + " ahora.").strip(),
            estado="pendiente",
        ))

    session.bulk_save_objects(objs)
    session.commit()

def eliminar_recordatorios_de_indicacion(session: Session, idindicacion: int):
    from models.recordatorio_paciente import RecordatorioPaciente
    session.query(RecordatorioPaciente)\
        .filter(RecordatorioPaciente.idindicacion == idindicacion)\
        .delete(synchronize_session=False)
    session.commit()
