# controllers/ventas_controller.py
from sqlalchemy import select, update, func
from utils.db import SessionLocal
from controllers.ventas_service import registrar_venta
from models.venta import Venta
from models.cobro import Cobro
from models.cobro_venta import CobroVenta   # o el nombre que uses

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
            nro_factura=venta_data.get("nro_factura"),
        )
        return v.idventa

    def listar_ventas(self, solo_no_anuladas: bool = False):
        q = select(Venta).order_by(Venta.idventa)
        if solo_no_anuladas:
            q = q.where(Venta.estadoventa != "Anulada")
        return self.session.execute(q).scalars().all()

    def _venta_tiene_cobros_activos(self, idventa: int) -> bool:
        """
        Devuelve True si la venta tiene al menos un cobro con estado distinto de 'ANULADO'.
        """
        row = self.session.execute(
            select(1)
            .select_from(CobroVenta)
            .join(Cobro, Cobro.idcobro == CobroVenta.idcobro)
            .where(
                CobroVenta.idventa == int(idventa),
                func.lower(Cobro.estado) != "anulado"
            )
            .limit(1)
        ).first()
        return bool(row)

    def anular_venta(self, idventa: int):
        # validación: no permitir si tiene cobros activos
        if self._venta_tiene_cobros_activos(idventa):
            raise Exception("No se puede anular: la venta tiene cobros asociados (no anulados).")

        self.session.execute(
            update(Venta).where(Venta.idventa == idventa).values(estadoventa="Anulada")
        )
        self.session.commit()
