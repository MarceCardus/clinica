# abm_compras.py
from datetime import datetime
from sqlalchemy.orm import Session
from models.compra import Compra
from models.compra_detalle import CompraDetalle
from models.StockMovimiento import StockMovimiento

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
                    iditem=det["iditem"],  # SOLO iditem
                    cantidad=det["cantidad"],
                    preciounitario=det["preciounitario"],
                    iva=det.get("iva", 0),
                    fechavencimiento=det.get("fechavencimiento"),
                    lote=det.get("lote"),
                    observaciones=det.get("observaciones")
                )
                self.session.add(compra_det)

                # Ingreso a stock
                stock_mov = StockMovimiento(
                    fecha=compra_data["fecha"],
                    iditem=det["iditem"],
                    cantidad=det["cantidad"],
                    tipo="INGRESO",
                    motivo="Compra",
                    idorigen=compra.idcompra,
                    observacion=f"Compra ID {compra.idcompra}, Lote: {det.get('lote', '')}, Obs: {det.get('observaciones', '')}"
                )
                self.session.add(stock_mov)

            compra.montototal = monto_total

            self.session.commit()
            return compra.idcompra

        except Exception as e:
            self.session.rollback()
            raise e

    def anular_compra(self, idcompra: int):
        """Anula una compra, realiza EGRESO en stock y actualiza auditoría."""
        try:
            compra = self.session.query(Compra).filter_by(idcompra=idcompra).first()
            if not compra:
                raise Exception("Compra no encontrada")
            if getattr(compra, "anulada", False):
                raise Exception("La compra ya fue anulada")

            detalles = self.session.query(CompraDetalle).filter_by(idcompra=idcompra).all()

            for det in detalles:
                stock_mov = StockMovimiento(
                    fecha=datetime.now(),
                    idinsumo=det.idinsumo,
                    cantidad=det.cantidad,
                    tipo="EGRESO",
                    motivo="Anulación de compra",
                    idorigen=compra.idcompra,
                    observacion=f"Anulación compra ID {compra.idcompra}, Lote: {getattr(det, 'lote', '')}, Obs: {getattr(det, 'observaciones', '')}"
                )
                self.session.add(stock_mov)

            compra.anulada = True
            self.session.commit()
            return True

        except Exception as e:
            self.session.rollback()
            raise e

    def obtener_compra(self, idcompra: int):
        compra = self.session.query(Compra).filter_by(idcompra=idcompra).first()
        detalles = self.session.query(CompraDetalle).filter_by(idcompra=idcompra).all()
        return compra, detalles

    def listar_compras(self, solo_no_anuladas=True):
        query = self.session.query(Compra)
        if solo_no_anuladas and hasattr(Compra, "anulada"):
            query = query.filter_by(anulada=False)
        return query.order_by(Compra.idcompra).all()
