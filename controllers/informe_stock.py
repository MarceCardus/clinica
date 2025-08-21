# controllers/informe_stock.py
from sqlalchemy import func, case
from models.item import Item, ItemTipo
from models.StockMovimiento import StockMovimiento

class StockController:
    def __init__(self, session):
        self.session = session

    def get_stock_insumos(self, tipo=None, categoria=None):
        # Solo items cuyo tipo sea INSUMO o AMBOS
        query = self.session.query(
            Item.iditem,
            Item.nombre,
            Item.tipo_insumo.label('tipo'),
            Item.categoria,
            Item.unidad,
            func.coalesce(func.sum(StockMovimiento.cantidad), 0).label('stock_actual')
        ).outerjoin(StockMovimiento, StockMovimiento.iditem == Item.iditem)

        # Filtrar por tipo de item (solo insumos o ambos)
        query = query.join(ItemTipo, Item.iditemtipo == ItemTipo.iditemtipo)
        query = query.filter(ItemTipo.nombre.in_(["INSUMO", "AMBOS"]))

        if tipo and tipo != "TODOS":
            query = query.filter(Item.tipo_insumo == tipo)
        if categoria and categoria != "TODOS":
            query = query.filter(Item.categoria == categoria)

        query = query.group_by(Item.iditem, Item.nombre, Item.tipo_insumo, Item.categoria, Item.unidad)
        query = query.order_by(Item.nombre)
        return query.all()