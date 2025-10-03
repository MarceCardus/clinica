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
