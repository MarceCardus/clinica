import json

from datetime import datetime, timedelta
from models.indicacion import Indicacion
from models.recordatorio import Recordatorio
from sqlalchemy.orm import Session

def generar_recordatorios_medicamento(session: Session, indicacion: Indicacion):
    if not indicacion.hora_inicio or not indicacion.frecuencia_horas or not indicacion.duracion_dias:
        return  # No es suficiente info

    fecha_base = datetime.combine(indicacion.fecha, indicacion.hora_inicio)
    fecha_final = fecha_base + timedelta(days=indicacion.duracion_dias)
    total_tomas = (24 // indicacion.frecuencia_horas) * indicacion.duracion_dias
    recordatorios = []
    for i in range(total_tomas):
        recordatorio_dt = fecha_base + timedelta(hours=i * indicacion.frecuencia_horas)
        if recordatorio_dt >= fecha_final:
            break
        mensaje = f"Recordatorio: tomar {indicacion.insumo.nombre if indicacion.insumo else ''} {indicacion.dosis or ''} ahora."
        recordatorio = Recordatorio(
            idindicacion=indicacion.idindicacion,
            fecha_hora=recordatorio_dt,
            mensaje=mensaje
        )
        recordatorios.append(recordatorio)
    session.add_all(recordatorios)
    session.commit()
    print(f"{len(recordatorios)} recordatorios generados para la indicación {indicacion.idindicacion}.")

def generar_recordatorios_control(session: Session, indicacion: Indicacion):
    if not indicacion.esquema_control:
        return
    esquema = indicacion.esquema_control  # Puede ser dict o string en JSON
    if isinstance(esquema, str):
        esquema = json.loads(esquema)
    fecha_base = datetime.combine(indicacion.fecha, indicacion.hora_inicio or datetime.min.time())
    recordatorios = []
    for control in esquema:
        dias_offset = control.get("dias", 0)
        descripcion = control.get("descripcion", "")
        recordatorio_dt = fecha_base + timedelta(days=dias_offset)
        mensaje = f"Recordatorio: Control programado de {indicacion.producto.nombre if indicacion.producto else ''} {descripcion}."
        recordatorio = Recordatorio(
            idindicacion=indicacion.idindicacion,
            fecha_hora=recordatorio_dt,
            mensaje=mensaje
        )
        recordatorios.append(recordatorio)
    session.add_all(recordatorios)
    session.commit()
    print(f"{len(recordatorios)} recordatorios generados para los controles de la indicación {indicacion.idindicacion}.")

def eliminar_recordatorios_de_indicacion(session, idindicacion):
    session.query(Recordatorio).filter_by(idindicacion=idindicacion).delete()
    session.commit()

def validar_indicacion_medicamento(indicacion):
    errores = []
    if not indicacion.hora_inicio:
        errores.append("Falta la hora de inicio.")
    if not indicacion.frecuencia_horas:
        errores.append("Falta la frecuencia (horas).")
    if not indicacion.duracion_dias:
        errores.append("Falta la duración (días).")
    if not indicacion.dosis:
        errores.append("Falta la dosis.")
    if not indicacion.idinsumo:
        errores.append("Debe seleccionar un medicamento.")
    return errores


def eliminar_recordatorios_futuros(session, idindicacion):
    ahora = datetime.now()
    session.query(Recordatorio).filter(
        Recordatorio.idindicacion == idindicacion,
        Recordatorio.fecha_hora > ahora,
        Recordatorio.enviado == False
    ).delete()
    session.commit()