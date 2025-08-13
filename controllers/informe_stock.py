# controllers/informe_stock.py

from sqlalchemy import func, case
from models.insumo import Insumo
from models.StockMovimiento import StockMovimiento

class StockController:
    def __init__(self, session):
        self.session = session

    def get_stock_insumos(self, tipo=None, categoria=None):
        query = self.session.query(
            Insumo.idinsumo,
            Insumo.nombre,
            Insumo.tipo,
            Insumo.categoria,
            Insumo.unidad,
            func.coalesce(
                func.sum(
                    case(
                        (StockMovimiento.tipo == 'INGRESO', StockMovimiento.cantidad),
                        (StockMovimiento.tipo == 'EGRESO', -StockMovimiento.cantidad),
                        else_=0
                    )
                ), 0
            ).label('stock_actual')
        ).outerjoin(StockMovimiento, StockMovimiento.idinsumo == Insumo.idinsumo)

        if tipo and tipo != "TODOS":
            query = query.filter(Insumo.tipo == tipo)
        if categoria and categoria != "TODOS":
            query = query.filter(Insumo.categoria == categoria)

        query = query.group_by(Insumo.idinsumo, Insumo.nombre, Insumo.tipo, Insumo.categoria, Insumo.unidad)
        query = query.order_by(Insumo.nombre)
        return query.all()