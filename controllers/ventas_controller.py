# controllers/ventas_controller.py
from sqlalchemy import select, update
from utils.db import SessionLocal
from controllers.ventas_service import registrar_venta
from models.venta import Venta

class VentasController:
    def __init__(self, session, usuario_id):
        self.session = session
        self.usuario_id = usuario_id

    def crear_venta(self, venta_data: dict) -> int:
        v = registrar_venta(
            session=self.session,
            fecha=venta_data.get("fecha"),
            idpaciente=venta_data.get("idpaciente"),
            idprofesional=venta_data.get("idprofesional"),
            idclinica=venta_data.get("idclinica"),
            estadoventa="Cerrada",
            observaciones=venta_data.get("observaciones"),
            items=venta_data.get("items", []),
            nro_factura=venta_data.get("nro_factura"),   # ← agregar
        )
        return v.idventa

    def listar_ventas(self, solo_no_anuladas: bool = False):
        q = select(Venta).order_by(Venta.idventa)
        # si luego agregás flag de anulado, podés filtrar aquí
        return self.session.execute(q).scalars().all()

    def anular_venta(self, idventa: int):
        # si no tenés columna "anulada", podés cambiar estadoventa a "Anulada"
        self.session.execute(
            update(Venta).where(Venta.idventa == idventa).values(estadoventa="Anulada")
        )
        self.session.commit()
