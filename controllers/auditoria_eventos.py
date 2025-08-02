import json
from datetime import datetime
from sqlalchemy import event
from sqlalchemy.orm import object_session
from sqlalchemy import inspect
from models.auditoria import Auditoria
import models.usuario_actual as usuario_id 
import datetime
import decimal

def default_json(obj):
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError(f"Tipo no serializable: {type(obj)}")


def get_data_only_columns(obj):
    return {col.name: getattr(obj, col.name) for col in obj.__table__.columns}

def get_current_user():
    # Primero intenta leer de Flask, si falla usa el global de escritorio
    try:
        from flask import g
        return g.user.idusuario
    except Exception:
        return usuario_id.usuario_id  # <- El usuario actual seteado por tu login

def registrar_auditoria(session, idusuario, modulo, accion, observaciones):
    nueva_auditoria = Auditoria(
        fechahora = datetime.datetime.now(),
        idusuario=idusuario,
        modulo=modulo,
        accion=accion,
        observaciones=json.dumps(observaciones, ensure_ascii=False, default=default_json)

    )
    session.add(nueva_auditoria)

def after_insert_listener(mapper, connection, target):
    session = object_session(target)
    if session is None:
        return
    registrar_auditoria(
        session,
        get_current_user(),
        target.__tablename__,
        'CREAR',
        {"nuevo": get_data_only_columns(target)}
    )

def after_update_listener(mapper, connection, target):
    session = object_session(target)
    if session is None:
        return
    changes = {}
    state = inspect(target)
    for attr in state.attrs:
        if attr.history.has_changes():
            changes[attr.key] = {
                "antes": attr.history.deleted,
                "despues": attr.history.added
            }
    if changes:
        registrar_auditoria(
            session,
            get_current_user(),
            target.__tablename__,
            'MODIFICAR',
            changes
        )

def after_delete_listener(mapper, connection, target):
    session = object_session(target)
    if session is None:
        return
    registrar_auditoria(
        session,
        get_current_user(),
        target.__tablename__,
        'ELIMINAR',
        {"borrado": get_data_only_columns(target)}
    )
