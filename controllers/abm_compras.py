# controllers/abm_compras.py

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.compra import Compra
from models.compra_detalle import CompraDetalle
from models.StockMovimiento import StockMovimiento
from models.proveedor import Proveedor
from models.item import Item

class CompraController:
    """
    Controlador para manejar la lógica de negocio de las Compras.
    Interactúa directamente con la base de datos.
    """
    def __init__(self, session: Session, usuario_id: int):
        self.session = session
        self.usuario_id = usuario_id

    def crear_compra(self, compra_data: dict) -> int:
        """
        Guarda una nueva compra y sus detalles.
        Además, crea los movimientos de stock si el ítem lo requiere.
        """
        try:
            # Crea la cabecera de la compra
            compra = Compra(
                fecha=compra_data["fecha"],
                idproveedor=compra_data["idproveedor"],
                idclinica=compra_data["idclinica"],
                tipo_comprobante=compra_data.get("tipo_comprobante"),
                nro_comprobante=compra_data.get("nro_comprobante"),
                condicion_compra=compra_data.get("condicion_compra"),
                observaciones=compra_data.get("observaciones"),
                montototal=0  # Se calcula después
            )
            self.session.add(compra)
            self.session.flush()  # Para obtener el ID de la compra antes de commit

            monto_total = 0
            # Itera sobre los detalles para guardarlos y calcular el total
            for det in compra_data["detalles"]:
                total_detalle = float(det["cantidad"]) * float(det["preciounitario"])
                monto_total += total_detalle

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

                # Verifica si el ítem debe generar movimiento de stock
                item = self.session.get(Item, det["iditem"])
                if item and getattr(item, "genera_stock", True):
                    movimiento = StockMovimiento(
                        fecha=compra_data["fecha"],
                        iditem=det["iditem"],
                        cantidad=det["cantidad"],
                        tipo="INGRESO",
                        motivo="Compra",
                        idorigen=compra.idcompra,
                        observacion=f"Compra ID {compra.idcompra}, Lote: {det.get('lote', '')}"
                    )
                    self.session.add(movimiento)

            # Actualiza el monto total en la cabecera y guarda todo
            compra.montototal = monto_total
            self.session.commit()
            return compra.idcompra

        except Exception:
            self.session.rollback()  # Si algo falla, deshace todo
            raise

    def anular_compra(self, idcompra: int):
        """
        Anula una compra existente y revierte el stock si corresponde.
        """
        try:
            compra = self.session.query(Compra).filter_by(idcompra=idcompra).first()
            if not compra:
                raise Exception("Compra no encontrada.")
            if getattr(compra, "anulada", False):
                raise Exception("La compra ya fue anulada.")

            # Genera un movimiento de EGRESO por cada detalle para revertir el stock
            detalles = self.session.query(CompraDetalle).filter_by(idcompra=idcompra).all()
            for det in detalles:
                item = self.session.get(Item, det.iditem)
                if item and getattr(item, "genera_stock", True):
                    movimiento = StockMovimiento(
                        fecha=datetime.now(),
                        iditem=det.iditem,
                        cantidad=det.cantidad,
                        tipo="EGRESO",
                        motivo="Anulación de compra",
                        idorigen=compra.idcompra,
                        observacion=f"Anulación compra ID {compra.idcompra}"
                    )
                    self.session.add(movimiento)

            # Marca la compra como anulada y guarda los cambios
            compra.anulada = True
            self.session.commit()
            return True

        except Exception:
            self.session.rollback()
            raise

    def obtener_compra(self, idcompra: int):
        """Obtiene una compra y sus detalles por ID."""
        compra = self.session.query(Compra).filter_by(idcompra=idcompra).first()
        detalles = self.session.query(CompraDetalle).filter_by(idcompra=idcompra).all()
        return compra, detalles

    def listar_compras(self, solo_no_anuladas=True):
        """Retorna una lista de todas las compras, las más recientes primero."""
        q = self.session.query(Compra)
        if solo_no_anuladas and hasattr(Compra, "anulada"):
            q = q.filter(Compra.anulada == False)
        return q.order_by(Compra.fecha.desc(), Compra.idcompra.desc()).all()

    def listar_compras_por_proveedor(self, proveedor_like: str, solo_no_anuladas=True):
        """Busca compras por el nombre de un proveedor."""
        patron = f"%{proveedor_like.strip()}%"
        q = (self.session.query(Compra)
               .join(Proveedor, Proveedor.idproveedor == Compra.idproveedor)
               .filter(func.lower(Proveedor.nombre).ilike(func.lower(patron))))
        
        if solo_no_anuladas and hasattr(Compra, "anulada"):
            q = q.filter(Compra.anulada == False)
            
        return q.order_by(Compra.fecha.desc(), Compra.idcompra.desc()).all()