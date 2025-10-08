from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QDateEdit, QTextEdit, QTableWidget, QTableWidgetItem, QSplitter, QGroupBox, QFormLayout,
    QMessageBox, QDialog, QListWidget, QCompleter
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QDate, QEvent
from utils.db import SessionLocal
from models.proveedor import Proveedor
# from models.insumo import Insumo   # <- no se usa
from models.compra_detalle import CompraDetalle
from models.compra import Compra
from controllers.abm_compras import CompraController
from models.usuario_actual import usuario_id
from models.item import Item, ItemTipo
from decimal import Decimal


def _num(texto: str) -> Decimal:
    """Convierte '1.234.567' o '1234,50' a Decimal seguro."""
    if not texto:
        return Decimal(0)
    t = texto.replace('.', '').replace(' ', '')
    t = t.replace(',', '.')  # por si viene con coma decimal
    try:
        return Decimal(t)
    except Exception:
        return Decimal(0)


def _item_ro(texto, align=Qt.AlignLeft | Qt.AlignVCenter):
    it = QTableWidgetItem(texto)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    it.setTextAlignment(align)
    return it


def _item_editable(texto, align=Qt.AlignRight | Qt.AlignVCenter):
    it = QTableWidgetItem(texto)
    it.setTextAlignment(align)
    return it


class InsumoSelectDialog(QDialog):
    def __init__(self, insumos, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Insumo")
        self.selected = None
        layout = QVBoxLayout(self)
        self.listWidget = QListWidget()
        for insumo in insumos:
            self.listWidget.addItem(f"{insumo.iditem} - {insumo.nombre}")
        layout.addWidget(self.listWidget)
        self.listWidget.setCurrentRow(0)

        btn = QPushButton("Seleccionar")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
        self.listWidget.itemDoubleClicked.connect(self.accept)
        self.resize(350, 300)

    def accept(self):
        idx = self.listWidget.currentRow()
        if idx >= 0:
            self.selected = idx
            super().accept()


class ABMCompra(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.compras = []
        self.modo_nuevo = False
        self.setWindowTitle("Compras")
        self.resize(980, 540)
        self._setup_ui()
        self.cargar_proveedores()
        self.setup_focus()
        self.txt_filtro_prov.installEventFilter(self)
        self.proveedor.setFocus()  # Focus inicial en proveedor

        # Conectar botones principales
        self.btn_guardar.clicked.connect(self.guardar_compra)
        self.btn_anular.clicked.connect(self.anular_compra_actual)
        self.btn_anular.setEnabled(False)
        self.btn_cancelar.clicked.connect(self.cancelar)
        self.btn_primero.clicked.connect(self.ir_primero)
        self.btn_anterior.clicked.connect(self.ir_anterior)
        self.btn_siguiente.clicked.connect(self.ir_siguiente)
        self.btn_ultimo.clicked.connect(self.ir_ultimo)
        self.btn_eliminar.clicked.connect(self.eliminar_fila_grilla)
        self.btn_nuevo.clicked.connect(self.nuevo)
        self.cargar_compras()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        title_layout = QHBoxLayout()
        icono = QLabel()
        icono.setPixmap(QIcon("imagenes/compra.png").pixmap(32, 32))
        title_layout.addWidget(icono)
        title_label = QLabel("Compras")
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold; margin-left:8px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)

        filtro_layout = QHBoxLayout()
        self.txt_filtro_prov = QLineEdit()
        self.txt_filtro_prov.setPlaceholderText("Buscar compras por proveedor...")
        self.btn_filtro_prov = QPushButton(QIcon("imagenes/buscar.png"), "Buscar")
        self.btn_limpiar_filtro = QPushButton(QIcon("imagenes/cancelar.png"), "Quitar filtro")
        self.btn_filtro_prov.clicked.connect(self.aplicar_filtro_proveedor)
        self.btn_limpiar_filtro.clicked.connect(self._limpiar_filtro_proveedor)
        filtro_layout.addWidget(self.txt_filtro_prov)
        filtro_layout.addWidget(self.btn_filtro_prov)
        filtro_layout.addWidget(self.btn_limpiar_filtro)
        filtro_layout.addStretch()
        main_layout.addLayout(filtro_layout)

        splitter = QSplitter(Qt.Horizontal)

        # Panel izquierdo - Cabecera
        left_box = QGroupBox("Datos de la Compra")
        left_layout = QFormLayout()
        self.idcompra = QLineEdit()
        self.idcompra.setReadOnly(True)
        left_layout.addRow(QLabel("ID Compra:"), self.idcompra)
        self.fecha = QDateEdit(QDate.currentDate())
        self.fecha.setCalendarPopup(True)
        left_layout.addRow(QLabel("Fecha:"), self.fecha)
        self.proveedor = QComboBox()
        left_layout.addRow(QLabel("Proveedor:"), self.proveedor)
        self.comprobante = QComboBox()
        self.comprobante.addItems(["Factura", "Nota de Remisión"])
        left_layout.addRow(QLabel("Tipo Comprobante:"), self.comprobante)
        self.nro_comp = QLineEdit()
        left_layout.addRow(QLabel("N° Comprobante:"), self.nro_comp)
        self.observaciones = QTextEdit()
        left_layout.addRow(QLabel("Observaciones:"), self.observaciones)
        left_box.setLayout(left_layout)
        splitter.addWidget(left_box)
        self.lbl_estado = QLabel("Activo")
        self.lbl_estado.setStyleSheet("font-weight:bold; color: green; margin-bottom:6px;")
        left_layout.addRow(QLabel("Estado:"), self.lbl_estado)

        # Panel derecho - Detalle
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Buscador de insumo
        search_layout = QHBoxLayout()
        self.busca_insumo = QLineEdit()
        self.busca_insumo.setPlaceholderText("Buscar insumo")
        btn_buscar = QPushButton(QIcon("imagenes/buscar.png"), "")
        btn_buscar.setStyleSheet("""
            QPushButton {
                background-color: #e9ecef;
                border: 1px solid #ced4da;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #b6d4fe;
            }
        """)
        btn_buscar.clicked.connect(self.buscar_y_agregar_insumo)
        search_layout.addWidget(self.busca_insumo)
        search_layout.addWidget(btn_buscar)
        search_layout.addStretch()
        right_layout.addLayout(search_layout)

        # Grilla de insumos
        self.grilla = QTableWidget(0, 6)
        self.grilla.setHorizontalHeaderLabels([
            "Código", "Nombre", "Cantidad", "Precio", "IVA 10%", "Total"
        ])
        self.grilla.cellChanged.connect(self._on_grilla_cell_changed)
        right_layout.addWidget(self.grilla)

        # Botones detalle
        btns_detalle = QHBoxLayout()
        self.btn_agregar = QPushButton(QIcon("imagenes/agregar.png"), "Agregar")
        self.btn_agregar.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 4px 18px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.btn_eliminar = QPushButton(QIcon("imagenes/eliminar.png"), "Eliminar")
        self.btn_eliminar.setStyleSheet("""
            QPushButton {
                background-color: #ffc9c9;
                color: #dc3545;
                font-weight: bold;
                border-radius: 6px;
                padding: 4px 18px;
            }
            QPushButton:hover {
                background-color: #fa5252;
                color: white;
            }
        """)
        self.btn_agregar.clicked.connect(self.buscar_y_agregar_insumo)
        btns_detalle.addWidget(self.btn_agregar)
        btns_detalle.addWidget(self.btn_eliminar)
        btns_detalle.addStretch()
        right_layout.addLayout(btns_detalle)

        # Pie - totales y navegación
        pie_layout = QHBoxLayout()
        self.lbl_subtotal = QLabel("Total: 0")
        self.lbl_iva = QLabel("IVA: 0")
        pie_layout.addWidget(self.lbl_subtotal)
        pie_layout.addWidget(self.lbl_iva)
        pie_layout.addStretch()

        # Navegación
        self.btn_primero = QPushButton(QIcon("imagenes/primero.png"), "")
        self.btn_anterior = QPushButton(QIcon("imagenes/anterior.png"), "")
        self.btn_siguiente = QPushButton(QIcon("imagenes/siguiente.png"), "")
        self.btn_ultimo = QPushButton(QIcon("imagenes/ultimo.png"), "")
        for btn in [self.btn_primero, self.btn_anterior, self.btn_siguiente, self.btn_ultimo]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #007bff;
                    color: #007bff;
                    border-radius: 6px;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: #b6d4fe;
                }
            """)
            pie_layout.addWidget(btn)

        # Botones principales
        self.btn_nuevo = QPushButton(QIcon("imagenes/nuevo.png"), "Nuevo")
        self.btn_guardar = QPushButton(QIcon("imagenes/guardar.png"), "Guardar")
        self.btn_anular = QPushButton(QIcon("imagenes/eliminar.png"), "Anular")
        self.btn_cancelar = QPushButton(QIcon("imagenes/cancelar.png"), "Cancelar")

        botones = [
            (self.btn_nuevo, "#007bff", "white"),
            (self.btn_guardar, "#28a745", "white"),
            (self.btn_anular, "#dc3545", "white"),
            (self.btn_cancelar, "#ffc9c9", "#dc3545"),
        ]
        for btn, fondo, color in botones:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {fondo};
                    color: {color};
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 4px 18px;
                }}
                QPushButton:hover {{
                    background-color: #b6d4fe;
                }}
            """)
            pie_layout.addWidget(btn)

        right_layout.addLayout(pie_layout)
        splitter.addWidget(right_widget)
        splitter.setSizes([340, 800])

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        header = self.grilla.horizontalHeader()
        header.setStretchLastSection(True)
        self.grilla.setColumnWidth(0, 80)   # Código
        self.grilla.setColumnWidth(1, 260)  # Nombre
        self.grilla.setColumnWidth(2, 90)   # Cantidad
        self.grilla.setColumnWidth(3, 110)  # Precio
        self.grilla.setColumnWidth(4, 90)   # IVA

    # ---------- helpers de celda ----------
    def _set_or_text(self, row, col, texto, ro=True):
        """Crea la celda si no existe y setea el texto; ro=True => read-only."""
        it = self.grilla.item(row, col)
        if it is None:
            it = _item_ro(texto, Qt.AlignRight | Qt.AlignVCenter) if ro else _item_editable(texto)
            self.grilla.setItem(row, col, it)
        else:
            it.setText(texto)

    # ---------- datos ----------
    def cargar_proveedores(self):
        session = SessionLocal()
        self.proveedor.clear()
        try:
            proveedores = (
                session.query(Proveedor)
                .filter_by(estado=True)
                .order_by(Proveedor.nombre)
                .all()
            )
            for prov in proveedores:
                self.proveedor.addItem(prov.nombre, prov.idproveedor)

            # Completer DESPUÉS de cargar el combo
            nombres = [p.nombre for p in proveedores]
            self._compProv = QCompleter(nombres, self)
            self._compProv.setCaseSensitivity(Qt.CaseInsensitive)
            self.txt_filtro_prov.setCompleter(self._compProv)
        finally:
            session.close()

    def guardar_compra(self):
        if not self.modo_nuevo:
            QMessageBox.warning(self, "Acción inválida", "Debe presionar 'Nuevo' para registrar una nueva compra.")
            return

        if self.proveedor.currentData() is None:
            QMessageBox.warning(self, "Falta proveedor", "Debe seleccionar un proveedor.")
            return
        if self.grilla.rowCount() == 0:
            QMessageBox.warning(self, "Sin detalle", "Debe agregar al menos un insumo a la compra.")
            return

        detalles = []
        for row in range(self.grilla.rowCount()):
            iditem = int(self.grilla.item(row, 0).text())
            cantidad = _num(self.grilla.item(row, 2).text())
            precio = _num(self.grilla.item(row, 3).text())
            iva = _num(self.grilla.item(row, 4).text())
            detalles.append({
                "iditem": iditem,
                "cantidad": float(cantidad),
                "preciounitario": float(precio),
                "iva": float(iva),
            })

        compra_data = {
            "fecha": self.fecha.date().toPyDate(),
            "idproveedor": self.proveedor.currentData(),
            "idclinica": 1,
            "tipo_comprobante": self.comprobante.currentText(),
            "nro_comprobante": self.nro_comp.text(),
            "condicion_compra": None,
            "observaciones": self.observaciones.toPlainText(),
            "detalles": detalles
        }

        session = SessionLocal()
        try:
            controller = CompraController(session, usuario_id=usuario_id)
            idcompra = controller.crear_compra(compra_data)
            QMessageBox.information(self, "Compra guardada", f"Compra N° {idcompra} guardada correctamente.")
            self.modo_nuevo = False
            self.cargar_compras()
            idx = next((i for i, c in enumerate(self.compras) if c.idcompra == idcompra), None)
            if idx is not None:
                self.mostrar_compra(idx)
            else:
                self.ir_primero()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            session.rollback()
        finally:
            session.close()

    # ---------- UI state ----------
    def set_campos_enabled(self, estado: bool):
        self.fecha.setEnabled(estado)
        self.proveedor.setEnabled(estado)
        self.comprobante.setEnabled(estado)
        self.nro_comp.setEnabled(estado)
        self.observaciones.setEnabled(estado)
        self.grilla.setEnabled(estado)
        self.busca_insumo.setEnabled(estado)
        self.btn_agregar.setEnabled(estado)
        self.btn_eliminar.setEnabled(estado)

    def limpiar_formulario(self, editable=False):
        self.idcompra.clear()
        self.fecha.setDate(QDate.currentDate())
        self.proveedor.setCurrentIndex(0)
        self.comprobante.setCurrentIndex(0)
        self.nro_comp.clear()
        self.observaciones.clear()
        self.grilla.setRowCount(0)
        self.lbl_subtotal.setText("Total: 0")
        self.lbl_iva.setText("IVA: 0")
        self.idcompra_actual = None
        self.idx_actual = -1
        self.lbl_estado.setText("Activo")
        self.lbl_estado.setStyleSheet("font-weight:bold; color: green;")
        self.set_campos_enabled(editable)
        self.btn_guardar.setEnabled(editable)
        self.btn_cancelar.setEnabled(True)
        self.btn_anular.setEnabled(False)
        self.btn_nuevo.setEnabled(not editable)

    # ---------- navegación / carga ----------
    def cargar_compras(self, proveedor_like: str | None = None):
        session = SessionLocal()
        try:
            controller = CompraController(session, usuario_id=usuario_id)
            if proveedor_like:
                self.compras = controller.listar_compras_por_proveedor(proveedor_like, solo_no_anuladas=False)
            else:
                self.compras = controller.listar_compras(solo_no_anuladas=False)

            self.idx_actual = -1
            if self.compras:
                self.mostrar_compra(0)
            else:
                self.limpiar_formulario(editable=False)
                QMessageBox.information(self, "Sin resultados", "No se encontraron compras con ese criterio.")
        finally:
            session.close()

    def aplicar_filtro_proveedor(self):
        texto = (self.txt_filtro_prov.text() or "").strip()
        self.cargar_compras(texto if texto else None)

    def nuevo(self):
        self.modo_nuevo = True
        self.limpiar_formulario(editable=True)

    def cancelar(self):
        self.modo_nuevo = False
        self.limpiar_formulario(editable=False)

    def mostrar_compra(self, idx):
        if not self.compras or idx < 0 or idx >= len(self.compras):
            return

        compra = self.compras[idx]
        self.idcompra_actual = compra.idcompra

        self.fecha.setDate(QDate(compra.fecha.year, compra.fecha.month, compra.fecha.day))
        self.proveedor.setCurrentIndex(self.proveedor.findData(compra.idproveedor))
        self.comprobante.setCurrentText(compra.tipo_comprobante or "")
        self.nro_comp.setText(compra.nro_comprobante or "")
        self.observaciones.setPlainText(compra.observaciones or "")

        self.grilla.blockSignals(True)
        self.grilla.setRowCount(0)
        session = SessionLocal()
        try:
            detalles = session.query(CompraDetalle).filter_by(idcompra=compra.idcompra).all()
            for det in detalles:
                row = self.grilla.rowCount()
                self.grilla.insertRow(row)

                item = session.get(Item, det.iditem)
                nombre = item.nombre if item else ""

                cantidad = det.cantidad or 0
                precio = det.preciounitario or 0
                iva = det.iva or 0
                total = (cantidad or 0) * (precio or 0)

                # 0-1 read-only, 2-3 editables, 4-5 read-only
                self.grilla.setItem(row, 0, _item_ro(str(det.iditem)))
                self.grilla.setItem(row, 1, _item_ro(nombre))
                self.grilla.setItem(row, 2, _item_editable(f"{cantidad:,.0f}".replace(",", ".")))
                self.grilla.setItem(row, 3, _item_editable(f"{precio:,.0f}".replace(",", ".")))
                self.grilla.setItem(row, 4, _item_ro(f"{iva:,.0f}".replace(",", "."), Qt.AlignRight | Qt.AlignVCenter))
                self.grilla.setItem(row, 5, _item_ro(f"{total:,.0f}".replace(",", "."), Qt.AlignRight | Qt.AlignVCenter))
        finally:
            session.close()
            self.grilla.blockSignals(False)

        self.actualizar_totales()

        self.idx_actual = idx
        self.idcompra.setText(str(compra.idcompra))
        self.set_campos_enabled(False)
        self.btn_guardar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.btn_anular.setEnabled(not bool(getattr(compra, "anulada", False)))
        self.btn_nuevo.setEnabled(True)

        if getattr(compra, "anulada", False):
            self.lbl_estado.setText("Anulado")
            self.lbl_estado.setStyleSheet("font-weight:bold; color: red;")
        else:
            self.lbl_estado.setText("Activo")
            self.lbl_estado.setStyleSheet("font-weight:bold; color: green;")

    def ir_primero(self):
        if self.compras:
            self.mostrar_compra(len(self.compras) - 1)

    def ir_anterior(self):
        # Anterior en el tiempo (más antiguo que el actual)
        if self.compras and self.idx_actual < len(self.compras) - 1:
            self.mostrar_compra(self.idx_actual + 1)

    def ir_siguiente(self):
        # Siguiente en el tiempo (más reciente que el actual)
        if self.compras and self.idx_actual > 0:
            self.mostrar_compra(self.idx_actual - 1)

    def ir_ultimo(self):
        if self.compras:
            self.mostrar_compra(0)

    # ---------- acciones ----------
    def eliminar_fila_grilla(self):
        row = self.grilla.currentRow()
        if row >= 0:
            respuesta = QMessageBox.question(
                self, "Eliminar ítem",
                "¿Seguro que desea eliminar el insumo seleccionado?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if respuesta == QMessageBox.Yes:
                self.grilla.removeRow(row)
                self.actualizar_totales()
        else:
            QMessageBox.information(self, "Atención", "Debe seleccionar una fila para eliminar.")

    # ---------- UX ----------
    def setup_focus(self):
        self.proveedor.installEventFilter(self)
        self.comprobante.installEventFilter(self)
        self.nro_comp.installEventFilter(self)
        self.observaciones.installEventFilter(self)
        self.busca_insumo.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if obj == self.proveedor:
                self.comprobante.setFocus()
                return True
            elif obj == self.comprobante:
                self.nro_comp.setFocus()
                return True
            elif obj == self.nro_comp:
                self.observaciones.setFocus()
                return True
            elif obj == self.observaciones:
                self.busca_insumo.setFocus()
                return True
            elif obj == self.busca_insumo:
                self.buscar_y_agregar_insumo()
                return True
            elif obj == self.txt_filtro_prov:
                self.aplicar_filtro_proveedor()
                return True   # este 'return True' debe quedar dentro del elif
        return super().eventFilter(obj, event)

    # ---------- búsqueda/agregado de insumos ----------
    def buscar_insumos(self, texto):
        session = SessionLocal()
        try:
            items = (
                session.query(Item)
                .join(ItemTipo)
                .filter(
                    Item.activo == True,
                    Item.nombre.ilike(f"%{texto}%")
                )
                .order_by(ItemTipo.nombre.desc(), Item.nombre.asc())  # ← AQUÍ
                .all()
            )
            return items
        finally:
            session.close()


    def buscar_y_agregar_insumo(self):
        texto = self.busca_insumo.text().strip()
        if not texto:
            return
        insumos = self.buscar_insumos(texto)
        if not insumos:
            QMessageBox.information(self, "Sin resultados", "No se encontró ningún insumo.")
        elif len(insumos) == 1:
            self.agregar_insumo_a_grilla(insumos[0])
        else:
            dlg = InsumoSelectDialog(insumos, self)
            if dlg.exec_() and dlg.selected is not None:
                self.agregar_insumo_a_grilla(insumos[dlg.selected])
        self.busca_insumo.clear()

    def agregar_insumo_a_grilla(self, insumo):
        # Etiqueta opcional: marcar si no genera stock
        etiqueta = " (no genera stock)" if not getattr(insumo, "genera_stock", True) else ""
        nombre_mostrado = f"{insumo.nombre}{etiqueta}"

        # Evitar duplicados
        for row in range(self.grilla.rowCount()):
            if self.grilla.item(row, 0) and self.grilla.item(row, 0).text() == str(insumo.iditem):
                cant_item = self.grilla.item(row, 2)
                cant_actual = _num(cant_item.text()) if cant_item and cant_item.text() else Decimal(0)
                cant_item.setText(str(int(cant_actual) + 1))
                self.grilla.setCurrentCell(row, 2)
                return

        row = self.grilla.rowCount()
        self.grilla.insertRow(row)
        self.grilla.setItem(row, 0, _item_ro(str(insumo.iditem)))
        it_nombre = _item_ro(nombre_mostrado)
        if not getattr(insumo, "genera_stock", True):
            it_nombre.setToolTip("Este ítem no genera movimientos de stock")
        self.grilla.setItem(row, 1, it_nombre)
        self.grilla.setItem(row, 2, _item_editable("1"))
        self.grilla.setItem(row, 3, _item_editable("0"))
        self.grilla.setItem(row, 4, _item_ro("0", Qt.AlignRight | Qt.AlignVCenter))
        self.grilla.setItem(row, 5, _item_ro("0", Qt.AlignRight | Qt.AlignVCenter))

        self.grilla.setCurrentCell(row, 2)
        self.grilla.editItem(self.grilla.item(row, 2))
        self.grilla.setFocus()
        self.grilla.item(row, 2).setSelected(True)

    def anular_compra_actual(self):
        if not hasattr(self, 'idcompra_actual') or self.idcompra_actual is None:
            QMessageBox.warning(self, "Atención", "No hay compra cargada para anular.")
            return

        respuesta = QMessageBox.question(
            self, "Confirmar anulación",
            "¿Está seguro que desea anular esta compra?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if respuesta == QMessageBox.No:
            return

        session = SessionLocal()
        try:
            idx_actual = self.idx_actual
            filtro = (self.txt_filtro_prov.text() or "").strip() or None

            controller = CompraController(session, usuario_id=usuario_id)
            controller.anular_compra(self.idcompra_actual)

            QMessageBox.information(self, "Éxito", "Compra anulada correctamente.")

            # Recargar respetando filtro y mantener posición
            self.cargar_compras(filtro)
            if self.compras:
                self.mostrar_compra(min(idx_actual, len(self.compras) - 1))
            else:
                self.limpiar_formulario(editable=False)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            session.rollback()
        finally:
            session.close()

    # ---------- eventos ----------
    def keyPressEvent(self, event):
        # Si el foco está en la grilla de insumos
        if self.grilla.hasFocus():
            current_row = self.grilla.currentRow()
            current_col = self.grilla.currentColumn()
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if current_col == 2:  # Cantidad
                    self.grilla.setCurrentCell(current_row, 3)
                    self.grilla.editItem(self.grilla.item(current_row, 3))
                    self.grilla.item(current_row, 3).setSelected(True)
                    return
                elif current_col == 3:  # Precio unitario
                    self.calcular_iva_total_row(current_row)
                    self.actualizar_totales()  # Actualiza labels de totales
                    self.busca_insumo.setFocus()  # Vuelve a buscar insumo
                    return
        super().keyPressEvent(event)

    def calcular_iva_total_row(self, row):
        try:
            self.grilla.blockSignals(True)
            cantidad_item = self.grilla.item(row, 2)
            precio_item = self.grilla.item(row, 3)

            cantidad = _num(cantidad_item.text()) if cantidad_item and cantidad_item.text() else Decimal(0)
            precio = _num(precio_item.text()) if precio_item and precio_item.text() else Decimal(0)

            total = (precio * cantidad).quantize(Decimal("1"))
            iva = (total / Decimal(11)).quantize(Decimal("1")) if total > 0 else Decimal(0)

            # col 3 es editable, 4 y 5 son read-only
            self._set_or_text(row, 3, f"{int(precio):,}".replace(",", "."), ro=False)
            self._set_or_text(row, 4, f"{int(iva):,}".replace(",", "."), ro=True)
            self._set_or_text(row, 5, f"{int(total):,}".replace(",", "."), ro=True)
        except Exception as e:
            print(f"Error en calcular_iva_total_row: {e}")
            self._set_or_text(row, 4, "0", ro=True)
            self._set_or_text(row, 5, "0", ro=True)
        finally:
            self.grilla.blockSignals(False)

    def actualizar_totales(self):
        subtotal = Decimal(0)
        iva_total = Decimal(0)
        for row in range(self.grilla.rowCount()):
            cantidad = _num(self.grilla.item(row, 2).text())
            precio = _num(self.grilla.item(row, 3).text())
            iva = _num(self.grilla.item(row, 4).text())
            subtotal += (precio * cantidad)
            iva_total += iva
        self.lbl_subtotal.setText(f"Total: {int(round(subtotal)):,}".replace(",", "."))
        self.lbl_iva.setText(f"IVA: {int(round(iva_total)):,}".replace(",", "."))

    def _on_grilla_cell_changed(self, row, column):
        if column in (2, 3):  # Cantidad o Precio
            self.calcular_iva_total_row(row)
            self.actualizar_totales()

    def _limpiar_filtro_proveedor(self):
        self.txt_filtro_prov.clear()
        self.cargar_compras()
