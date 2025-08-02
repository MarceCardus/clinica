from sqlalchemy import event
from models.base import Base
from models.auditoria import Auditoria
from models.barrio import Barrio  # <--- Agregá este import
from models.ciudad import Ciudad
from controllers.auditoria_eventos import after_insert_listener, after_update_listener, after_delete_listener

def inicializar_auditoria():
    MODELOS_EXCLUIR = {Auditoria, Barrio, Ciudad}  # <--- Ciudad excluida
    
    for mapper in Base.registry.mappers:
        modelo = mapper.class_
        
        if modelo not in MODELOS_EXCLUIR and hasattr(modelo, "__tablename__"):
            event.listen(modelo, 'after_insert', after_insert_listener)
            event.listen(modelo, 'after_update', after_update_listener)
            event.listen(modelo, 'after_delete', after_delete_listener)
