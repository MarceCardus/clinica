# controllers/informe_stock.py
from sqlalchemy import func, case, or_
from models.item import Item, ItemTipo
from models.StockMovimiento import StockMovimiento


class StockController:
    """
    Consultas de stock basadas en la tabla unificada Item + movimientos.
    Respeta la bandera `Item.genera_stock`: si es False, el ítem no acumula stock
    (compras/ventas no generan movimientos) y, por defecto, no se listará.

    Parámetros comunes en métodos:
      - tipo: filtra por Item.tipo_insumo (ej. "Medicamento"). Usar "TODOS" o None para no filtrar.
      - categoria: filtra por Item.categoria (ej. "CONSUMO_INTERNO" / "USO_PROCEDIMIENTO"). "TODOS"/None = sin filtro.
      - activos: si True (default) sólo ítems activos.
      - solo_genera_stock: si True (default) oculta ítems con genera_stock=False.
      - buscar: texto libre para filtrar por nombre/descripcion/código.
    """

    def __init__(self, session):
        self.session = session

    # ----------------------- Helpers -----------------------
    def _base_query_stock(self):
        """
        Query base que calcula stock_actual = SUM(movimientos.cantidad) por ítem.
        Devuelve un query con columnas seleccionadas y el join/outerjoin listo.
        NO aplica filtros aún (se aplican en cada método público).
        """
        stock_actual = func.coalesce(func.sum(StockMovimiento.cantidad), 0).label("stock_actual")

        q = (
            self.session.query(
                Item.iditem,
                Item.nombre,
                Item.descripcion,
                Item.codigo_barra,
                Item.activo,
                Item.genera_stock,
                Item.unidad,
                Item.categoria,
                Item.tipo_insumo.label("tipo_insumo"),
                Item.stock_minimo,
                ItemTipo.nombre.label("tipo_general"),
                stock_actual,
                # Estado respecto al mínimo (si hay mínimo cargado)
                case(
                    (Item.stock_minimo.is_(None), None),
                    (func.coalesce(func.sum(StockMovimiento.cantidad), 0) < Item.stock_minimo, "BAJO"),
                    else_="OK"
                ).label("estado_minimo"),
            )
            .join(ItemTipo, Item.iditemtipo == ItemTipo.iditemtipo)
            .outerjoin(StockMovimiento, StockMovimiento.iditem == Item.iditem)
            .group_by(
                Item.iditem,
                Item.nombre,
                Item.descripcion,
                Item.codigo_barra,
                Item.activo,
                Item.genera_stock,
                Item.unidad,
                Item.categoria,
                Item.tipo_insumo,
                Item.stock_minimo,
                ItemTipo.nombre,
            )
        )
        return q

    def _aplicar_filtros_comunes(self, q, *, activos=True, solo_genera_stock=True, buscar=None):
        if activos:
            q = q.filter(Item.activo.is_(True))
        if solo_genera_stock:
            # Si el ítem no genera stock, ni siquiera mostramos en los informes por defecto.
            q = q.filter(Item.genera_stock.is_(True))
        if buscar:
            t = f"%{buscar.strip()}%"
            q = q.filter(
                or_(
                    Item.nombre.ilike(t),
                    Item.descripcion.ilike(t),
                    Item.codigo_barra.ilike(t),
                )
            )
        return q

    # ----------------------- Públicos -----------------------
    def get_stock_insumos(
        self,
        tipo: str | None = None,
        categoria: str | None = None,
        *,
        activos: bool = True,
        solo_genera_stock: bool = True,
        buscar: str | None = None,
        ordenar_por_tipo_desc: bool = False,
    ):
        """
        Devuelve stock de ítems cuyo tipo general sea INSUMO o AMBOS.
        - tipo: filtra por Item.tipo_insumo (p.ej. "Medicamento"). "TODOS"/None = sin filtro.
        - categoria: "CONSUMO_INTERNO" / "USO_PROCEDIMIENTO" / "AMBOS". "TODOS"/None = sin filtro.
        """
        q = self._base_query_stock()

        # Solo insumos o ambos
        q = q.filter(ItemTipo.nombre.in_(["INSUMO", "AMBOS"]))

        # Filtros de UI
        if tipo and tipo != "TODOS":
            q = q.filter(Item.tipo_insumo == tipo)
        if categoria and categoria != "TODOS":
            q = q.filter(Item.categoria == categoria)

        q = self._aplicar_filtros_comunes(q, activos=activos, solo_genera_stock=solo_genera_stock, buscar=buscar)

        # Orden
        if ordenar_por_tipo_desc:
            q = q.order_by(ItemTipo.nombre.desc(), Item.nombre.asc())
        else:
            q = q.order_by(ItemTipo.nombre.asc(), Item.nombre.asc())

        return q.all()

    def get_stock_productos(
        self,
        *,
        activos: bool = True,
        solo_genera_stock: bool = True,
        buscar: str | None = None,
        ordenar_por_tipo_desc: bool = False,
    ):
        """
        Stock de ítems cuyo tipo general sea PRODUCTO o AMBOS.
        Útil para ver productos físicos (que suelen "genera_stock = True").
        """
        q = self._base_query_stock()
        q = q.filter(ItemTipo.nombre.in_(["PRODUCTO", "AMBOS"]))
        q = self._aplicar_filtros_comunes(q, activos=activos, solo_genera_stock=solo_genera_stock, buscar=buscar)

        if ordenar_por_tipo_desc:
            q = q.order_by(ItemTipo.nombre.desc(), Item.nombre.asc())
        else:
            q = q.order_by(ItemTipo.nombre.asc(), Item.nombre.asc())

        return q.all()

    def get_stock_todos(
        self,
        *,
        activos: bool = True,
        solo_genera_stock: bool = True,
        buscar: str | None = None,
        ordenar_por_tipo_desc: bool = False,
    ):
        """
        Stock de TODOS los ítems (PRODUCTO/INSUMO/AMBOS).
        Respeta `solo_genera_stock`. Útil para un dashboard general.
        """
        q = self._base_query_stock()
        q = self._aplicar_filtros_comunes(q, activos=activos, solo_genera_stock=solo_genera_stock, buscar=buscar)

        if ordenar_por_tipo_desc:
            q = q.order_by(ItemTipo.nombre.desc(), Item.nombre.asc())
        else:
            q = q.order_by(ItemTipo.nombre.asc(), Item.nombre.asc())

        return q.all()
