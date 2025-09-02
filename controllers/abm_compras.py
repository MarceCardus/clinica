# controllers/abm_compras.py
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.compra import Compra
from models.compra_detalle import CompraDetalle
from models.StockMovimiento import StockMovimiento
from models.proveedor import Proveedor

class CompraController:
    def __init__(self, session: Session, usuario_id: int):
        self.session = session
        self.usuario_id = usuario_id

    def crear_compra(self, compra_data: dict):
        """Guarda una nueva compra y suma stock."""
        try:
            compra = Compra(
                fecha=compra_data["fecha"],
                idproveedor=compra_data["idproveedor"],
                idclinica=compra_data["idclinica"],
                tipo_comprobante=compra_data.get("tipo_comprobante"),
                nro_comprobante=compra_data.get("nro_comprobante"),
                condicion_compra=compra_data.get("condicion_compra"),
                observaciones=compra_data.get("observaciones"),
                montototal=0
            )
            self.session.add(compra)
            self.session.flush()

            monto_total = 0
            for det in compra_data["detalles"]:
                total = float(det["cantidad"]) * float(det["preciounitario"])
                monto_total += total

                compra_det = CompraDetalle(
                    idcompra=compra.idcompra,
                    iditem=det["iditem"],
                    cantidad=det["cantidad"],
                    preciounitario=det["preciounitario"],
                    iva=det.get("iva", 0),
                    fechavencimiento=det.get("fechavencimiento"),
                    lote=det.get("lote"),
                    observaciones=det.get("observaciones")
                )
                self.session.add(compra_det)

                self.session.add(StockMovimiento(
                    fecha=compra_data["fecha"],
                    iditem=det["iditem"],
                    cantidad=det["cantidad"],
                    tipo="INGRESO",
                    motivo="Compra",
                    idorigen=compra.idcompra,
                    observacion=f"Compra ID {compra.idcompra}, Lote: {det.get('lote', '')}, Obs: {det.get('observaciones', '')}"
                ))

            compra.montototal = monto_total
            self.session.commit()
            return compra.idcompra

        except Exception:
            self.session.rollback()
            raise

    def anular_compra(self, idcompra: int):
        """Anula una compra, registra EGRESO en stock."""
        try:
            compra = self.session.query(Compra).filter_by(idcompra=idcompra).first()
            if not compra:
                raise Exception("Compra no encontrada")
            if getattr(compra, "anulada", False):
                raise Exception("La compra ya fue anulada")

            detalles = self.session.query(CompraDetalle).filter_by(idcompra=idcompra).all()
            for det in detalles:
                self.session.add(StockMovimiento(
                    fecha=datetime.now(),
                    iditem=det.iditem,
                    cantidad=det.cantidad,
                    tipo="EGRESO",
                    motivo="Anulación de compra",
                    idorigen=compra.idcompra,
                    observacion=f"Anulación compra ID {compra.idcompra}, Lote: {getattr(det, 'lote', '')}, Obs: {getattr(det, 'observaciones', '')}"
                ))

            compra.anulada = True
            self.session.commit()
            return True

            # (Si tenés tabla auditoría, acá es buen lugar para insertar el registro.)

        except Exception:
            self.session.rollback()
            raise

    def obtener_compra(self, idcompra: int):
        compra = self.session.query(Compra).filter_by(idcompra=idcompra).first()
        detalles = self.session.query(CompraDetalle).filter_by(idcompra=idcompra).all()
        return compra, detalles

    def listar_compras(self, solo_no_anuladas=True):
        """Listado general (orden reciente primero)."""
        q = self.session.query(Compra)
        if solo_no_anuladas and hasattr(Compra, "anulada"):
            q = q.filter(Compra.anulada == False)
        return q.order_by(Compra.fecha.desc(), Compra.idcompra.desc()).all()

    def listar_compras_por_proveedor(self, proveedor_like: str, solo_no_anuladas=True):
        """Búsqueda tipo ventas->clientes: por nombre de proveedor (ilike)."""
        patron = f"%{proveedor_like.strip()}%"
        q = (self.session.query(Compra)
             .join(Proveedor, Proveedor.idproveedor == Compra.idproveedor)
             .filter(func.lower(Proveedor.nombre).ilike(func.lower(patron))))
        if solo_no_anuladas and hasattr(Compra, "anulada"):
            q = q.filter(Compra.anulada == False)
        return q.order_by(Compra.fecha.desc(), Compra.idcompra.desc()).all()
