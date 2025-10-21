# services/inf_produccion_prof_service.py
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from utils.db import SessionLocal


def get_produccion_por_dia(inicio: date, fin: date, idprofesional: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Lee la vista vw_produccion_prof_dia y filtra por rango y (opcional) profesional.
    Espera que la vista tenga columnas: idprofesional, dia (date), atenciones, pacientes_unicos.
    """
    params = {"ini": inicio, "fin": fin}
    q = """
        SELECT p.idprofesional, p.dia, p.atenciones, p.pacientes_unicos
        FROM vw_produccion_prof_dia p
        WHERE p.dia BETWEEN :ini AND :fin
    """
    if idprofesional:
        q += " AND p.idprofesional = :pid "
        params["pid"] = idprofesional

    q += " ORDER BY p.dia, p.idprofesional;"

    s = SessionLocal()
    try:
        rows = s.execute(text(q), params).mappings().all()
        return [dict(r) for r in rows]
    finally:
        s.close()


def get_produccion_resumen_mes(ano: int, mes: int, idprofesional: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Resumen mensual por profesional (suma del mes sobre la vista diaria).
    """
    from calendar import monthrange
    ini = date(ano, mes, 1)
    fin = date(ano, mes, monthrange(ano, mes)[1])

    params = {"ini": ini, "fin": fin}
    q = """
        SELECT
          p.idprofesional,
          SUM(p.atenciones)       AS atenciones_mes,
          SUM(p.pacientes_unicos) AS pacientes_unicos_mes
        FROM vw_produccion_prof_dia p
        WHERE p.dia BETWEEN :ini AND :fin
    """
    if idprofesional:
        q += " AND p.idprofesional = :pid "
        params["pid"] = idprofesional

    q += " GROUP BY p.idprofesional ORDER BY p.idprofesional;"

    s = SessionLocal()
    try:
        rows = s.execute(text(q), params).mappings().all()
        return [dict(r) for r in rows]
    finally:
        s.close()


def get_produccion_detallado(inicio: date, fin: date, idprofesional: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Detalle de sesiones por profesional (excluye CANCELADO).
    Usa:
      - Profesional: ps.idterapeuta -> profesional.idprofesional
      - Fecha: COALESCE(ps.fecha_realizada, ps.fecha_programada)
      - Observaciones: ps.notas
      - Procedimiento: aparato.nombre (si hay) / 'Masaje' (si hizo_masaje) /
                      item.nombre (del plan) / plantipo.nombre como fallback
    Devuelve: fecha, idprofesional, profesional, idpaciente, paciente, procedimiento, observaciones, estado
    """
    params: Dict[str, Any] = {
        "ini": inicio,
        "fin": fin,
        "cancelado": "CANCELADA",  # tu Enum SesionEstado tiene CANCELADA
    }

    q = """
        SELECT
            COALESCE(ps.fecha_realizada, ps.fecha_programada)::timestamp AS fecha_ts,
            pr.idprofesional                                           AS idprofesional,
            (pr.apellido || ', ' || pr.nombre)                         AS profesional,
            pa.idpaciente                                              AS idpaciente,
            (pa.apellido || ', ' || pa.nombre)                         AS paciente,
            -- Procedimiento priorizando aparato > masaje > item plan > tipo plan
            COALESCE(
                ap.nombre,
                CASE WHEN ps.hizo_masaje THEN 'Masaje' ELSE NULL END,
                itpl.nombre,
                pt.nombre,
                ''
            )                                                          AS procedimiento,
            COALESCE(ps.notas, '')                                     AS observaciones,
            ps.estado::text                                            AS estado
        FROM plan_sesion ps
        JOIN plan_sesiones pl   ON pl.idplan = ps.idplan
        JOIN paciente pa        ON pa.idpaciente = pl.idpaciente
        LEFT JOIN plan_tipo pt  ON pt.idplantipo = pl.idplantipo
        LEFT JOIN item itpl     ON itpl.iditem = pl.iditem_procedimiento
        LEFT JOIN aparato ap    ON ap.idaparato = ps.idaparato
        JOIN profesional pr     ON pr.idprofesional = ps.idterapeuta
        WHERE COALESCE(ps.fecha_realizada, ps.fecha_programada) BETWEEN :ini AND :fin
          AND (ps.estado IS NULL OR ps.estado::text <> :cancelado)
    """

    if idprofesional:
        q += " AND ps.idterapeuta = :pid "
        params["pid"] = idprofesional

    q += " ORDER BY fecha_ts ASC, pa.apellido ASC, pa.nombre ASC;"

    s = SessionLocal()
    try:
        rows = s.execute(text(q), params).mappings().all()
        # Normalizo la fecha a date/string amigable para la UI
        out: List[Dict[str, Any]] = []
        for r in rows:
            fecha = r["fecha_ts"]
            out.append({
                "fecha": fecha,  # tu diálogo lo formatea con strftime si es datetime
                "idprofesional": r["idprofesional"],
                "profesional": r["profesional"],
                "idpaciente": r["idpaciente"],
                "paciente": r["paciente"],
                "procedimiento": r["procedimiento"] or "",
                "observaciones": (r["observaciones"] or "").strip(),
                "estado": r["estado"] or "",
            })
        return out
    finally:
        s.close()
