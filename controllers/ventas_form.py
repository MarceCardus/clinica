# controllers/abm_ventas_form.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QDateEdit, QTextEdit, QTableWidget, QTableWidgetItem, QSplitter, QGroupBox, QFormLayout,
    QMessageBox, QListWidget, QDialog,QSizePolicy,QHeaderView,QCompleter ,QMdiSubWindow
)
from PyQt5.QtGui import QIcon, QRegularExpressionValidator
from PyQt5.QtCore import Qt, QDate, QEvent, QRegularExpression,QSize,QTimer
from decimal import Decimal
from sqlalchemy import select, or_
from utils.db import SessionLocal
from controllers.ventas_controller import VentasController
from models.paciente import Paciente
from models.profesional import Profesional
from models.clinica import Clinica
from models.paquete import Paquete
from models.venta_detalle import VentaDetalle
from models.venta import Venta
from models.item import Item
from models.item import ItemTipo

# --- Diálogo de selección genérico (producto o paquete)
class ItemSelectDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar ítem")
        self.selected = None
        layout = QVBoxLayout(self)
        self.listWidget = QListWidget()
        for it in items:
            # it: (tipo, id, nombre, precio)
            tipo, _id, nombre, pv = it
            pref = "P" if tipo == "producto" else "Q"
            self.listWidget.addItem(f"{pref}{_id} - {nombre} - {pv:,.0f}".replace(",", "."))
        layout.addWidget(self.listWidget)
        self.listWidget.setCurrentRow(0)
        btn = QPushButton("Seleccionar")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
        self.listWidget.itemDoubleClicked.connect(self.accept)
        self.resize(420, 330)

    def accept(self):
        idx = self.listWidget.currentRow()
        if idx >= 0:
            self.selected = idx
            super().accept()


class ABMVenta(QWidget):
    def __init__(self, usuario_id=None, parent=None):
        super().__init__(parent)
        self.usuario_id = usuario_id
        self.session = SessionLocal()

        self.ventas = []
        self.modo_nuevo = False
        self.idventa_actual = None
        self.idx_actual = -1

        self.setWindowTitle("Ventas")
        self.resize(980, 540)        # <<< igual que Compras

        self._setup_ui()             # <<< crea los widgets
        self.grilla.itemChanged.connect(self._on_item_changed)
        # --- Conexiones (después del setup) ---
        self.btn_eliminar.clicked.connect(self.eliminar_fila_grilla)
        self.btn_guardar.clicked.connect(self.guardar_venta)
        self.btn_anular.clicked.connect(self.anular_venta_actual)
        self.btn_anular.setEnabled(False)
        self.btn_cancelar.clicked.connect(self.cancelar)
        self.btn_primero.clicked.connect(self.ir_primero)
        self.btn_anterior.clicked.connect(self.ir_anterior)
        self.btn_siguiente.clicked.connect(self.ir_siguiente)
        self.btn_ultimo.clicked.connect(self.ir_ultimo)
        self.btn_nuevo.clicked.connect(self.nuevo)
        self.btn_buscar.clicked.connect(self.buscar_y_agregar_item)

        # Datos
        self.cargar_maestros()
        self.setup_focus()
        self.cbo_paciente.setFocus()
        self.cargar_ventas()

    
    # Localiza el QMdiSubWindow real (si existe)
    def _mdi_subwindow(self):
        w = self.parentWidget()
        while w and not isinstance(w, QMdiSubWindow):
            w = w.parentWidget()
        return w

   
    def _mask_vacia(self, txt: str) -> bool:
        # Considera vacío si viene None, cadena vacía o solo guiones/underscores
        return ((txt or "").replace("_", "").replace("-", "").strip() == "")

    def _pintar_estado(self, v: Venta):
        est = (getattr(v, "estadoventa", "") or "").strip().lower()
        anulada = getattr(v, "anulada", False)

        if est == "anulada" or anulada:
            self.lbl_estado.setText("Anulada")
            self.lbl_estado.setStyleSheet("font-weight:bold; color:#dc3545; margin-bottom:6px;")
            self.btn_anular.setEnabled(False)
            self.set_campos_enabled(False)

        elif est in ("cerrada", "cerrado"):
            self.lbl_estado.setText("Generada")
            self.lbl_estado.setStyleSheet("font-weight:bold; color:#0d6efd; margin-bottom:6px;")
            self.btn_anular.setEnabled(True)   # si permitís anular una cerrada, dejá True
            self.set_campos_enabled(False)

        else:
            self.lbl_estado.setText("Cobrada")
            self.lbl_estado.setStyleSheet("font-weight:bold; color: green; margin-bottom:6px;")
            self.btn_anular.setEnabled(True)
    
    def _enable_search_on_combobox(self, combo: QComboBox):
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        # armar lista de textos visibles para el completer
        items = [combo.itemText(i) for i in range(combo.count())]
        comp = QCompleter(items, combo)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        combo.setCompleter(comp)

    # ---------- UI ----------
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Título (igual a Compras)
        title_layout = QHBoxLayout()
        icono = QLabel(); icono.setPixmap(QIcon("imagenes/venta.png").pixmap(32,32))
        title_layout.addWidget(icono)
        title_label = QLabel("Ventas")
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold; margin-left:8px;")
        title_layout.addWidget(title_label); title_layout.addStretch()
        main_layout.addLayout(title_layout)

        splitter = QSplitter(Qt.Horizontal)

        # Izquierda
        left_box = QGroupBox("Datos de la Venta")
        left_layout = QFormLayout()
        self.idventa = QLineEdit(); self.idventa.setReadOnly(True)
        left_layout.addRow(QLabel("ID Venta:"), self.idventa)

        self.fecha = QDateEdit(QDate.currentDate()); self.fecha.setCalendarPopup(True)
        left_layout.addRow(QLabel("Fecha:"), self.fecha)

        self.txt_nro_factura = QLineEdit()
        left_layout.addRow(QLabel("N° Factura:"), self.txt_nro_factura)

        self.cbo_paciente = QComboBox(); left_layout.addRow(QLabel("Paciente:"), self.cbo_paciente)
        self.cbo_profesional = QComboBox(); left_layout.addRow(QLabel("Profesional:"), self.cbo_profesional)
        self.cbo_clinica = QComboBox(); left_layout.addRow(QLabel("Clínica:"), self.cbo_clinica)

        self.observaciones = QTextEdit(); left_layout.addRow(QLabel("Observaciones:"), self.observaciones)

        self.lbl_estado = QLabel("Activo")
        self.lbl_estado.setStyleSheet("font-weight:bold; color: green; margin-bottom:6px;")
        left_layout.addRow(QLabel("Estado:"), self.lbl_estado)

        left_box.setLayout(left_layout)
        splitter.addWidget(left_box)

        # Derecha
        right_widget = QWidget(); right_layout = QVBoxLayout(right_widget)

        # Buscador
        search_layout = QHBoxLayout()
        self.cbo_tipo = QComboBox(); self.cbo_tipo.addItems(["producto", "paquete"])
        self.busca_item = QLineEdit(); self.busca_item.setPlaceholderText("Buscar producto o paquete")
        self.btn_buscar = QPushButton(QIcon("imagenes/buscar.png"), "")
        search_layout.addWidget(self.cbo_tipo)
        search_layout.addWidget(self.busca_item)
        search_layout.addWidget(self.btn_buscar)
        search_layout.addStretch()
        right_layout.addLayout(search_layout)

        # Grilla
        self.grilla = QTableWidget(0, 7)
        self.grilla.setHorizontalHeaderLabels(["Código","Nombre","Tipo","Cantidad","Precio","Total","IVA 10%"])
        right_layout.addWidget(self.grilla)

        # Botones detalle
        btns_detalle = QHBoxLayout()
        self.btn_agregar  = QPushButton(QIcon("imagenes/agregar.png"), "Agregar")
        self.btn_eliminar = QPushButton(QIcon("imagenes/eliminar.png"), "Eliminar")
        btns_detalle.addWidget(self.btn_agregar)
        btns_detalle.addWidget(self.btn_eliminar)
        btns_detalle.addStretch()
        right_layout.addLayout(btns_detalle)

        # Pie
        pie_layout = QHBoxLayout()
        self.lbl_total = QLabel("Total: 0    IVA10: 0")
        pie_layout.addWidget(self.lbl_total); pie_layout.addStretch()
        self.btn_primero   = QPushButton(QIcon("imagenes/primero.png"), "")
        self.btn_anterior  = QPushButton(QIcon("imagenes/anterior.png"), "")
        self.btn_siguiente = QPushButton(QIcon("imagenes/siguiente.png"), "")
        self.btn_ultimo    = QPushButton(QIcon("imagenes/ultimo.png"), "")
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
        for b in [self.btn_primero, self.btn_anterior, self.btn_siguiente, self.btn_ultimo]:
            pie_layout.addWidget(b)
        self.btn_nuevo    = QPushButton(QIcon("imagenes/nuevo.png"), "Nuevo")
        self.btn_guardar  = QPushButton(QIcon("imagenes/guardar.png"), "Guardar")
        self.btn_anular   = QPushButton(QIcon("imagenes/eliminar.png"), "Anular")
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
        for b in [self.btn_nuevo, self.btn_guardar, self.btn_anular, self.btn_cancelar]:
            pie_layout.addWidget(b)
        right_layout.addLayout(pie_layout)

        splitter.addWidget(right_widget)
        splitter.setSizes([340, 800])   # <<< igual que Compras

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)


    def _on_item_changed(self, item):
        r, c = item.row(), item.column()
        if c in (3, 4):  # cantidad o precio
            if not self.grilla.item(r, 3) or not self.grilla.item(r, 4):
                return
            if (self.grilla.item(r, 3).text() or "").strip() == "" or \
            (self.grilla.item(r, 4).text() or "").strip() == "":
                return
            self.grilla.blockSignals(True)
            self.calcular_total_row(r)
            self.actualizar_total_pie()
            self.grilla.blockSignals(False)


    def agregar_item_a_grilla(self, it):
        tipo, _id, nombre, pv = it

        # Merge producto
        if tipo == "producto":
            for row in range(self.grilla.rowCount()):
                cod = self.grilla.item(row, 0)
                tip = self.grilla.item(row, 2)
                if cod and tip and cod.text() == str(_id) and tip.text().startswith("producto"):
                    self.grilla.blockSignals(True)
                    cant_item = self.grilla.item(row, 3)
                    cant_actual = int((cant_item.text() or "0").replace(".", "").replace(",", ""))
                    cant_item.setText(str(cant_actual + 1))
                    self.calcular_total_row(row)
                    self.grilla.blockSignals(False)
                    self.actualizar_total_pie()
                    self.grilla.setCurrentCell(row, 3)
                    return

        self.grilla.blockSignals(True)
        row = self.grilla.rowCount()
        self.grilla.insertRow(row)
        self.grilla.setItem(row, 0, QTableWidgetItem(str(_id)))
        self.grilla.setItem(row, 1, QTableWidgetItem(nombre))
        self.grilla.setItem(row, 2, QTableWidgetItem(tipo))
        self.grilla.setItem(row, 3, QTableWidgetItem("1"))
        self.grilla.setItem(row, 4, QTableWidgetItem(f"{pv:,.0f}".replace(",", ".")))
        total = int(round(float(pv)))
        iva = round(total / 11)
        self.grilla.setItem(row, 5, QTableWidgetItem(f"{total:,.0f}".replace(",", ".")))
        self.grilla.setItem(row, 6, QTableWidgetItem(f"{iva:,.0f}".replace(",", ".")))
        self.grilla.blockSignals(False)

        self.actualizar_total_pie()
        self.grilla.setCurrentCell(row, 3)
        self.grilla.editItem(self.grilla.item(row, 3))

    # ---------- Data maestros ----------
    def cargar_maestros(self):
        s = self.session
        # Pacientes
        self.cbo_paciente.clear()
        for p in s.execute(select(Paciente).order_by(Paciente.apellido)).scalars():
            self.cbo_paciente.addItem(f"{p.apellido}, {p.nombre}", p.idpaciente)
        self._enable_search_on_combobox(self.cbo_paciente)   # <--- AQUI

        # Profesionales
        self.cbo_profesional.clear()
        for pr in s.execute(select(Profesional).order_by(Profesional.apellido)).scalars():
            self.cbo_profesional.addItem(f"{pr.apellido}, {pr.nombre}", pr.idprofesional)

        # Clínicas
        self.cbo_clinica.clear()
        for c in s.execute(select(Clinica).order_by(Clinica.nombre)).scalars():
            self.cbo_clinica.addItem(c.nombre, c.idclinica)

    # ---------- Estado/limpieza ----------
    def set_campos_enabled(self, estado: bool):
        self.fecha.setEnabled(estado)
        self.txt_nro_factura.setEnabled(estado)
        self.cbo_paciente.setEnabled(estado)
        self.cbo_profesional.setEnabled(estado)
        self.cbo_clinica.setEnabled(estado)
        self.observaciones.setEnabled(estado)
        self.grilla.setEnabled(estado)
        self.cbo_tipo.setEnabled(estado)
        self.busca_item.setEnabled(estado)
        self.btn_buscar.setEnabled(estado)
        self.btn_agregar.setEnabled(estado)
        self.btn_eliminar.setEnabled(estado)

    def limpiar_formulario(self, editable=False):
        self.idventa.clear()
        self.fecha.setDate(QDate.currentDate())
        if self.cbo_paciente.count(): self.cbo_paciente.setCurrentIndex(0)
        if self.cbo_profesional.count(): self.cbo_profesional.setCurrentIndex(0)
        if self.cbo_clinica.count(): self.cbo_clinica.setCurrentIndex(0)
        self.txt_nro_factura.clear()
        self.observaciones.clear()
        self.grilla.setRowCount(0)
        self.lbl_total.setText("Total: 0    IVA10: 0")
        self.idventa_actual = None
        self.idx_actual = -1
        self.lbl_estado.setText("Activo"); self.lbl_estado.setStyleSheet("font-weight:bold; color: green;")
        self.set_campos_enabled(editable)
        self.btn_guardar.setEnabled(editable)
        self.btn_cancelar.setEnabled(True)
        self.btn_anular.setEnabled(False)
        self.btn_nuevo.setEnabled(not editable)
        
    def eliminar_fila_grilla(self):
        row = self.grilla.currentRow()
        if row < 0:
            QMessageBox.information(self, "Atención", "Debe seleccionar una fila.")
            return

        if QMessageBox.question(
            self, "Eliminar ítem", "¿Eliminar la fila seleccionada?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) == QMessageBox.No:
            return

        self.grilla.removeRow(row)
        # Recalcular totales del pie
        self.actualizar_total_pie()

        # Dejar alguna fila seleccionada si quedan filas
        if self.grilla.rowCount() > 0:
            self.grilla.setCurrentCell(min(row, self.grilla.rowCount() - 1), 0)

    def cancelar(self):
        """Vuelve el formulario a modo lectura y limpia la edición actual."""
        self.modo_nuevo = False
        self.limpiar_formulario(editable=False)
    # ---------- Carga / navegación ----------
    def cargar_ventas(self):
        ctrl = VentasController(self.session, usuario_id=self.usuario_id)
        self.ventas = ctrl.listar_ventas(solo_no_anuladas=False)
        self.idx_actual = -1
        self.limpiar_formulario(editable=False)

    def mostrar_venta(self, idx):
        if not self.ventas or idx < 0 or idx >= len(self.ventas): return
        v = self.ventas[idx]
        self.idventa_actual = v.idventa
        self.idventa.setText(str(v.idventa))
        self.fecha.setDate(QDate(v.fecha.year, v.fecha.month, v.fecha.day))
        if v.idpaciente: self.cbo_paciente.setCurrentIndex(self.cbo_paciente.findData(v.idpaciente))
        if v.idprofesional: self.cbo_profesional.setCurrentIndex(self.cbo_profesional.findData(v.idprofesional))
        if v.idclinica: self.cbo_clinica.setCurrentIndex(self.cbo_clinica.findData(v.idclinica))
        self.observaciones.setPlainText(v.observaciones or "")
        nf = getattr(v, "nro_factura", None)
        self.txt_nro_factura.setText(nf if nf else "")

        # Detalle
        self.grilla.blockSignals(True)
        self.grilla.setRowCount(0)
        dets = self.session.execute(select(VentaDetalle).where(VentaDetalle.idventa == v.idventa)).scalars().all()
        for det in dets:
            it = self.session.execute(select(Item).where(Item.iditem == det.iditem)).scalar_one_or_none()
            nombre = it.nombre if it else ""
            tipo   = it.tipo if it else "producto"

            row = self.grilla.rowCount()
            self.grilla.insertRow(row)
            self.grilla.setItem(row, 0, QTableWidgetItem(str(det.iditem)))
            self.grilla.setItem(row, 1, QTableWidgetItem(nombre))
            self.grilla.setItem(row, 2, QTableWidgetItem(tipo))
            self.grilla.setItem(row, 3, QTableWidgetItem(str(int(Decimal(det.cantidad)))))
            self.grilla.setItem(row, 4, QTableWidgetItem(f"{int(Decimal(det.preciounitario)):,.0f}".replace(",", ".")))

            subtotal = Decimal(det.cantidad) * Decimal(det.preciounitario) - Decimal(det.descuento or 0)
            self.grilla.setItem(row, 5, QTableWidgetItem(f"{int(subtotal):,.0f}".replace(",", ".")))
            iva = (subtotal / Decimal(11)).quantize(Decimal("1"))
            self.grilla.setItem(row, 6, QTableWidgetItem(f"{int(iva):,.0f}".replace(",", ".")))

        self.idx_actual = idx
        self.set_campos_enabled(False)
        self.btn_guardar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.btn_anular.setEnabled(True)  # si luego agregás flag anulada, podés condicionar
        self.btn_nuevo.setEnabled(True)
        # Calcular IVA total del detalle mostrado
        iva_total = 0
        for r in range(self.grilla.rowCount()):
            try:
                iva_total += float(self.grilla.item(r, 6).text().replace(".", "").replace(",", "."))
            except Exception:
                pass

        self.lbl_total.setText(
            f"Total: {Decimal(v.montototal or 0):,.0f}    IVA10: {int(iva_total):,}".replace(",", ".")
        )
        self.grilla.blockSignals(False)
        self.actualizar_total_pie()
        self._pintar_estado(v)

    def ir_primero(self):
        if self.ventas: self.mostrar_venta(0)

    def ir_anterior(self):
        if self.ventas and self.idx_actual > 0:
            self.mostrar_venta(self.idx_actual - 1)

    def ir_siguiente(self):
        if self.ventas and self.idx_actual < len(self.ventas) - 1:
            self.mostrar_venta(self.idx_actual + 1)

    def ir_ultimo(self):
        if self.ventas: self.mostrar_venta(len(self.ventas) - 1)

    # ---------- Búsqueda e ítems ----------
    def _agregar_fila_manual(self):
        row = self.grilla.rowCount()
        self.grilla.blockSignals(True)
        self.grilla.insertRow(row)

        # columnas vacías por defecto
        for c in range(self.grilla.columnCount()):
            self.grilla.setItem(row, c, QTableWidgetItem(""))

        # setear sólo lo que corresponde
        self.grilla.setItem(row, 3, QTableWidgetItem("1"))  # Cantidad (entera)
        self.grilla.setItem(row, 4, QTableWidgetItem("0"))  # Precio
        self.grilla.setItem(row, 5, QTableWidgetItem("0"))  # Total
        self.grilla.setItem(row, 6, QTableWidgetItem("0"))  # IVA

        self.calcular_total_row(row)
        self.grilla.blockSignals(False)

        self.actualizar_total_pie()
        self.grilla.setCurrentCell(row, 0)
        self.grilla.editItem(self.grilla.item(row, 0))

    def buscar_y_agregar_item(self):
        from decimal import Decimal
        from sqlalchemy import select, func
        from models.item import Item
        from models.item import ItemTipo  # <-- ojo: NO es from models.item import ItemTipo

        texto = (self.busca_item.text() or "").strip()
        if not texto:
            return

        s = self.session

        # Si una consulta previa falló, la sesión queda en estado abortado.
        try:
            s.rollback()
        except Exception:
            pass

        # Qué pide el combo (producto | paquete)
        want = (self.cbo_tipo.currentText() or "").strip().lower()

        # Filtro por tipo con JOIN explícito y case-insensitive
        tipo_ci = func.lower(func.trim(ItemTipo.nombre))
        if want == "producto":
            tipo_pred = tipo_ci.in_(["producto", "ambos"])
        else:
            tipo_pred = tipo_ci.in_(["paquete", "ambos"])

        # Traer Items que coincidan por nombre y tipo
        rows = s.execute(
            select(Item)
            .join(ItemTipo, ItemTipo.iditemtipo == Item.iditemtipo)
            .where(
                tipo_pred,
                Item.nombre.ilike(f"%{texto}%"),
            )
            .limit(50)
        ).scalars().all()

        resultados = []
        for r in rows:
            # precio_venta (o precio como fallback)
            pv = getattr(r, "precio_venta", None)
            if pv is None:
                pv = getattr(r, "precio", 0)

            # Normalizar etiqueta de tipo para la grilla
            t = want  # por defecto, si el item es "ambos" muestro según lo pedido
            tipo_attr = getattr(r, "tipo", None)  # puede ser relación a ItemTipo o string
            if isinstance(tipo_attr, str):
                t = (tipo_attr or "").strip().lower() or t
            elif tipo_attr is not None:
                tnom = (getattr(tipo_attr, "nombre", "") or "").strip().lower()
                if tnom in ("producto", "paquete"):
                    t = tnom
                # si es "ambos", dejamos t = want

            resultados.append((t, r.iditem, r.nombre, Decimal(pv or 0)))

        # Si no hubo resultados y se pidió "paquete", fallback opcional a tabla Paquete (legacy)
        if not resultados and want == "paquete":
            try:
                from models.paquete import Paquete
                packs = s.execute(
                    select(Paquete).where(Paquete.nombre.ilike(f"%{texto}%")).limit(50)
                ).scalars().all()
                for p in packs:
                    pv = getattr(p, "precio_venta", 0) or 0
                    resultados.append(("paquete", p.idpaquete, p.nombre, Decimal(pv)))
            except Exception:
                pass

        if not resultados:
            QMessageBox.information(self, "Sin resultados", "No se encontró ningún ítem.")
            return

        if len(resultados) == 1:
            self.agregar_item_a_grilla(resultados[0])
        else:
            dlg = ItemSelectDialog(resultados, self)
            if dlg.exec_() and dlg.selected is not None:
                self.agregar_item_a_grilla(resultados[dlg.selected])

        self.busca_item.clear()

    def guardar_venta(self):
        if not self.modo_nuevo:
            QMessageBox.warning(self, "Acción inválida", "Debe presionar 'Nuevo' para registrar una nueva venta.")
            return
        if self.grilla.rowCount() == 0:
            QMessageBox.warning(self, "Sin detalle", "Debe agregar al menos un ítem.")
            return
        
        nro = (self.txt_nro_factura.text() or "").strip()
        if self._mask_vacia(nro):
            nro = None
        else:
            if not self.txt_nro_factura.hasAcceptableInput():
                QMessageBox.warning(self, "N° Factura", "Formato inválido. Usá 001-001-0000001.")
                return

        ctrl = VentasController(self.session, usuario_id=self.usuario_id)
        datos = {
            "fecha": self.fecha.date().toPyDate(),
            "nro_factura": nro,
            "idpaciente": self.cbo_paciente.currentData(),
            "idprofesional": self.cbo_profesional.currentData(),
            "idclinica": self.cbo_clinica.currentData(),
            "observaciones": self.observaciones.toPlainText(),
            "items": self._collect_items()
        }
        try:
            idventa = ctrl.crear_venta(datos)
            QMessageBox.information(self, "Venta", f"Venta N° {idventa} guardada correctamente.")
            self.modo_nuevo = False
            self.cargar_ventas()
            self.limpiar_formulario(editable=False)
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", str(e))

    def anular_venta_actual(self):
        if not self.idventa_actual:
            QMessageBox.warning(self, "Atención", "No hay venta cargada para anular.")
            return
        if QMessageBox.question(self, "Confirmar anulación", "¿Está seguro que desea anular esta venta?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.No:
            return
        ctrl = VentasController(self.session, usuario_id=self.usuario_id)
        try:
            ctrl.anular_venta(self.idventa_actual)
            QMessageBox.information(self, "Éxito", "Venta anulada correctamente.")
            self.cargar_ventas()
            self.limpiar_formulario(editable=False)
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", str(e))

    # ---------- Focus / Enter flow ----------
    def setup_focus(self):
        for w in [self.cbo_paciente, self.cbo_profesional, self.cbo_clinica, self.observaciones, self.busca_item]:
            w.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if obj == self.cbo_paciente:
                self.cbo_profesional.setFocus(); return True
            elif obj == self.cbo_profesional:
                self.cbo_clinica.setFocus(); return True
            elif obj == self.cbo_clinica:
                self.observaciones.setFocus(); return True
            elif obj == self.observaciones:
                self.busca_item.setFocus(); return True
            elif obj == self.busca_item:
                self.buscar_y_agregar_item(); return True
        return super().eventFilter(obj, event)

    def closeEvent(self, ev):
        try:
            self.session.close()
        finally:
            super().closeEvent(ev)

    def nuevo(self):
        """Pone el formulario en modo nuevo y limpia todos los campos."""
        self.modo_nuevo = True
        self.limpiar_formulario(editable=True)

    def calcular_total_row(self, row: int):
        """Recalcula Total e IVA10 de la fila `row` usando Cantidad x Precio."""
        try:
            txt_cant = (self.grilla.item(row, 3).text() or "").strip()
            txt_prec = (self.grilla.item(row, 4).text() or "").strip()
            # quitar separadores de miles y comas
            cantidad = int((txt_cant.replace(".", "").replace(",", "")) or "0")
            precio   = int((txt_prec.replace(".", "").replace(",", "")) or "0")

            total = round(precio * cantidad)
            iva10 = round(total / 11)

            self.grilla.setItem(row, 3, QTableWidgetItem(str(cantidad)))
            self.grilla.setItem(row, 4, QTableWidgetItem(f"{precio:,.0f}".replace(",", ".")))
            self.grilla.setItem(row, 5, QTableWidgetItem(f"{total:,.0f}".replace(",", ".")))
            self.grilla.setItem(row, 6, QTableWidgetItem(f"{iva10:,.0f}".replace(",", ".")))
        except Exception:
            self.grilla.setItem(row, 5, QTableWidgetItem("0"))
            self.grilla.setItem(row, 6, QTableWidgetItem("0"))

    def actualizar_total_pie(self):
        """Suma las columnas Total (col=5) e IVA10 (col=6) y actualiza la etiqueta del pie."""
        total = 0
        total_iva = 0
        for r in range(self.grilla.rowCount()):
            try:
                v_total = (self.grilla.item(r, 5).text() if self.grilla.item(r, 5) else "0")
                v_iva   = (self.grilla.item(r, 6).text() if self.grilla.item(r, 6) else "0")
                total += float(v_total.replace(".", "").replace(",", "."))
                total_iva += float(v_iva.replace(".", "").replace(",", "."))
            except Exception:
                pass

        self.lbl_total.setText(
            f"Total: {total:,.0f}    IVA10: {int(round(total_iva)):,.0f}".replace(",", ".")
    )
