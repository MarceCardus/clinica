# controllers/cobro_dialog.py
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QComboBox,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QMessageBox,
    QCheckBox, QShortcut, QDateEdit, QSplitter, QSizePolicy
)
from PyQt5.QtCore import Qt, QDate, QTimer
from PyQt5.QtGui import QKeySequence, QIcon
from sqlalchemy import select, func, literal

# ajusta este import a tu fábrica de sesiones
from utils.db import SessionLocal

from models.paciente import Paciente
from models.venta import Venta
from services.cobros_service import registrar_cobro

# ---------- utils ----------
def _money(x) -> Decimal:
    return Decimal(str(x if x not in (None, "") else "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def parse_money(txt: str) -> Decimal:
    if txt is None:
        return Decimal("0.00")
    s = txt.strip().replace(".", "").replace(",", ".")
    if s == "":
        s = "0"
    return _money(s)

def fmt_money(d: Decimal) -> str:
    s = f"{_money(d):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_money0(d: Decimal) -> str:
    """Gs sin decimales, con miles."""
    try:
        n = int(_money(d).quantize(Decimal("1")))  # redondeo a entero
    except Exception:
        n = 0
    s = f"{n:,}"
    # 1,234,567 -> 1.234.567
    return s.replace(",", ".")

# ---------- dialog ----------
class CobroDialog(QDialog):
    def __init__(self, parent=None, session=None, usuario_actual: str = None):
        super().__init__(parent)
        self.setWindowTitle("Registrar cobro")
        self.resize(1280, 720)          # más ancho/alto de inicio
        self.setMinimumSize(1150, 620)  # evita que quede demasiado chico
        self.session = session or SessionLocal()
        self.usuario_actual = usuario_actual or "sistema"
        self._updating = False
        self._pacientes_cache = []   # [(id, ci, nombre, apellido, display)]
        self._map_display_to_id = {} # display -> id
        self._selected_paciente_id = None
        self._ventas_del_dia = []    # [(idventa, idpaciente, paciente_disp, total, saldo, fecha)]

        self._build_ui()
        self._wire_shortcuts()
        self._style()
        self._load_pacientes()
        self._load_ventas_por_fecha()  # derecha (hoy)
        self._focus_inicio()

    # ---------- UI ----------
    def _build_ui(self):
        from PyQt5.QtCore import Qt, QDate, QTimer
        from PyQt5.QtWidgets import (
            QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter, QDialog, QWidget,
            QLabel, QLineEdit, QComboBox, QCheckBox, QTextEdit, QTableWidget,
            QHeaderView, QPushButton, QDateEdit, QSizePolicy
        )

        root = QVBoxLayout(self)

        # ===== Splitter principal =====
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # ============ IZQUIERDA: FORM ============
        left = QVBoxLayout()
        left_widget = QDialog(self)
        left_widget.setLayout(left)
        splitter.addWidget(left_widget)

        # Paciente
        header = QFormLayout()
        self.txtPaciente = QLineEdit()
        self.txtPaciente.setPlaceholderText("Buscar por CI / Nombre / Apellido…")
        header.addRow("Paciente:", self.txtPaciente)

        # Monto / Forma / FIFO
        fila_top = QHBoxLayout()
        self.txtMonto = QLineEdit(); self.txtMonto.setPlaceholderText("0,00")
        self.cboForma = QComboBox(); self.cboForma.addItems(
            ["Efectivo", "T. Crédito", "T. Débito", "Transferencia", "Cheque"]
        )
        self.chkFIFO = QCheckBox("Imputar automático")
        fila_top.addWidget(QLabel("Monto:")); fila_top.addWidget(self.txtMonto, 2)
        fila_top.addWidget(QLabel("Forma:")); fila_top.addWidget(self.cboForma, 2)
        fila_top.addWidget(self.chkFIFO, 2)

        left.addLayout(header)
        left.addLayout(fila_top)

        # Observaciones
        self.txtObs = QTextEdit(); self.txtObs.setPlaceholderText("Observaciones…")
        self.txtObs.setFixedHeight(130)
        left.addWidget(self.txtObs)

        # Tabla de ventas del paciente
        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["ID Venta", "Fecha", "Total", "Saldo", "A imputar"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        left.addWidget(self.tbl)

        # Que SOLO la tabla crezca en el panel izquierdo
        # índices: 0=header, 1=fila_top, 2=txtObs, 3=tabla
        left.setStretch(0, 0)
        left.setStretch(1, 0)
        left.setStretch(2, 0)
        left.setStretch(3, 1)

        # Conexiones izquierda
        self.chkFIFO.stateChanged.connect(self._toggle_fifo_mode)
        self.txtMonto.textChanged.connect(self._recalc_restante)
        self.tbl.itemChanged.connect(self._on_item_changed)
        self.tbl.itemDoubleClicked.connect(self._fill_full_on_doubleclick)

        # Navegación con Enter
        self.txtPaciente.returnPressed.connect(lambda: self.txtMonto.setFocus())
        self.txtMonto.returnPressed.connect(lambda: self.cboForma.setFocus())
        self.cboForma.activated.connect(lambda _i: self.btnGuardar.setFocus())
        self.cboForma.installEventFilter(self)  # Enter -> Guardar

        # ============ DERECHA: LISTA VENTAS POR FECHA ============
        right = QVBoxLayout()
        right_widget = QDialog(self)
        right_widget.setLayout(right)
        splitter.addWidget(right_widget)

        # Proporciones del splitter (izq cómodo, der grande)
        left_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        left_widget.setMinimumWidth(600)          # ↑ un poco más ancho
        left_widget.setMaximumWidth(820)
        splitter.setStretchFactor(0, 2)           # izquierda
        splitter.setStretchFactor(1, 5)           # derecha
        QTimer.singleShot(0, lambda: splitter.setSizes([720, 1100]))

        # Fecha + listar
        fila_fecha = QHBoxLayout()
        self.dtpFecha = QDateEdit(QDate.currentDate()); self.dtpFecha.setCalendarPopup(True)
        btnListar = QPushButton("Listar")
        fila_fecha.addWidget(QLabel("Fecha:"))
        fila_fecha.addWidget(self.dtpFecha)
        fila_fecha.addWidget(btnListar)
        fila_fecha.addStretch()
        right.addLayout(fila_fecha)

        # Grilla derecha (ID chico, Paciente grande, montos finos)
        self.tblDia = QTableWidget(0, 4)
        self.tblDia.setHorizontalHeaderLabels(["ID", "Paciente", "Total", "Saldo"])
        hv = self.tblDia.horizontalHeader()
        hv.setSectionResizeMode(0, QHeaderView.Fixed);  hv.resizeSection(0, 56)
        hv.setSectionResizeMode(1, QHeaderView.Stretch)
        hv.setSectionResizeMode(2, QHeaderView.Fixed);  hv.resizeSection(2, 110)
        hv.setSectionResizeMode(3, QHeaderView.Fixed);  hv.resizeSection(3, 110)
        self.tblDia.verticalHeader().setVisible(False)
        self.tblDia.setAlternatingRowColors(True)
        right.addWidget(self.tblDia)

        # Conexiones derecha
        btnListar.clicked.connect(self._load_ventas_por_fecha)
        self.dtpFecha.dateChanged.connect(self._load_ventas_por_fecha)
        self.tblDia.itemDoubleClicked.connect(self._usar_venta_de_la_derecha)
        self.tblDia.installEventFilter(self)

        # ============ FOOTER GLOBAL (ocupa TODO el ancho) ============
        footer = QHBoxLayout()
        self.lblRestante = QLabel("Restante: 0,00")
        self.lblRestante.setObjectName("lblRestante")

        self.btnRepartir = QPushButton("Repartir (F7)")  # textos más cortos
        self.btnAuto     = QPushButton("Automático (F8)")
        self.btnGuardar  = QPushButton("Guardar (F9)")
        self.btnCancelar = QPushButton("Cancelar (Esc)")
        for b in (self.btnRepartir, self.btnAuto, self.btnGuardar, self.btnCancelar):
            b.setMinimumWidth(100)

        footer.addWidget(self.lblRestante)
        footer.addStretch()
        footer.addWidget(self.btnRepartir)
        footer.addWidget(self.btnAuto)
        footer.addWidget(self.btnGuardar)
        footer.addWidget(self.btnCancelar)

        footer_w = QWidget(); footer_w.setLayout(footer)
        footer_w.setFixedHeight(80)
        root.addWidget(footer_w)  # 👈 debajo del splitter, ancho completo

        # Conexiones footer
        self.btnRepartir.clicked.connect(self._repartir_monto)
        self.btnAuto.clicked.connect(self._set_fifo_checked)   # o tu toggle
        self.btnGuardar.clicked.connect(self._on_guardar)
        self.btnCancelar.clicked.connect(self.reject)
        self.btnGuardar.setDefault(True)
        self.btnGuardar.setAutoDefault(True)



    # estilos
    def _style(self):
        self.setStyleSheet("""
            QDialog { background: #f6f8fb; }
            QLabel { color: #0d3a6a; }
            QLineEdit, QComboBox, QTextEdit, QDateEdit {
                background:#fff; border:1px solid #c6d4ea; border-radius:6px; padding:4px 6px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QDateEdit:focus {
                border: 1px solid #4a90e2; box-shadow: 0 0 0 2px rgba(74,144,226,.15);
            }
            QTableWidget { background: #ffffff; border: 1px solid #c6d4ea; border-radius: 6px; }
            QHeaderView::section { background: #e8f0fe; padding: 6px; border: none; color:#0d3a6a; }
            QPushButton {
                background: #2e7d32; color: white; padding: 6px 10px; border: none; border-radius: 6px;
            }
            QPushButton:hover { background: #2a6e2d; }
            QPushButton#danger { background: #c62828; }
            QPushButton#secondary { background: #245b9e; }
            #lblRestante { font-size:16px; font-weight:700; color: #b26a00; }
        """)
        self.btnRepartir.setObjectName("secondary")
        self.btnAuto.setObjectName("secondary")
        self.btnCancelar.setObjectName("danger")

    def _wire_shortcuts(self):
        QShortcut(QKeySequence("F7"), self, activated=self._repartir_monto)
        QShortcut(QKeySequence("F8"), self, activated=self._set_fifo_checked)
        QShortcut(QKeySequence("F9"), self, activated=self._on_guardar)
        QShortcut(QKeySequence("Esc"), self, activated=self.reject)

    def _focus_inicio(self):
        self.txtPaciente.setFocus()
        self.txtPaciente.selectAll()

    # ---------- Pacientes (completer) ----------
    def _load_pacientes(self):
        """Carga cache de pacientes y configura el QCompleter (busca por CI/Nombre/Apellido)."""
        # detectar la columna de documento: ci_pasaporte / ci_passaporte u otros alias
        doc_col = None
        for name in [
            "ci_pasaporte", "ci_passaporte",  # <- tus nombres
            "ci", "cedula", "documento", "dni", "ruc", "num_doc", "nro_documento", "numero_documento"
        ]:
            doc_col = getattr(Paciente, name, None)
            if doc_col is not None:
                break
        if doc_col is None:
            # si no existe ninguna, usamos cadena vacía como placeholder para no romper el SELECT
            doc_col = literal("").label("doc")

        # traemos id, doc, nombre, apellido
        rows = self.session.execute(
            select(Paciente.idpaciente, doc_col, Paciente.nombre, Paciente.apellido)
            .order_by(Paciente.apellido.asc(), Paciente.nombre.asc())
        ).all()

        self._pacientes_cache.clear()
        self._map_display_to_id.clear()

        for pid, doc, nom, ape in rows:
            doc_txt = (str(doc) if doc is not None else "").strip()
            nom = (nom or "").strip()
            ape = (ape or "").strip()
            # Muestra: "CI - Apellido, Nombre (ID)" si hay CI; si no, "Apellido, Nombre (ID)"
            disp = f"{doc_txt} - {ape}, {nom} ({pid})" if doc_txt else f"{ape}, {nom} ({pid})"
            self._pacientes_cache.append((pid, doc_txt, nom, ape, disp))
            self._map_display_to_id[disp] = pid

        # Completer con filtro por "contiene"
        from PyQt5.QtWidgets import QCompleter
        completer = QCompleter([x[4] for x in self._pacientes_cache], self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.activated[str].connect(self._on_paciente_elegido)
        self.txtPaciente.setCompleter(completer)


    def _on_paciente_elegido(self, text):
        self._selected_paciente_id = self._map_display_to_id.get(text)
        self._load_ventas_pendientes()

    def _guess_paciente_by_text(self):
        """Si el usuario tipea y presiona Enter, intenta mapear por coincidencia única."""
        txt = self.txtPaciente.text().strip().lower()
        if not txt:
            self._selected_paciente_id = None
            return
        matches = [pid for (pid, ci, nom, ape, disp) in self._pacientes_cache
                   if txt in disp.lower()]
        self._selected_paciente_id = matches[0] if len(matches) == 1 else None

    # ---------- Ventas panel derecho ----------
    def _load_ventas_por_fecha(self):
        self.tblDia.setRowCount(0)
        f = self.dtpFecha.date().toPyDate()
        rows = self.session.execute(
            select(Venta.idventa, Venta.idpaciente, Venta.montototal, Venta.saldo, Venta.fecha,
                   Paciente.apellido, Paciente.nombre)
            .join(Paciente, Paciente.idpaciente == Venta.idpaciente)
            .where(
                Venta.fecha == f,
                func.upper(func.coalesce(Venta.estadoventa, "")) != "ANULADA"
            )
            .order_by(Paciente.apellido.asc(), Paciente.nombre.asc(), Venta.idventa.asc())
        ).all()
        self._ventas_del_dia = []
        for (idv, pid, tot, sal, fch, ape, nom) in rows:
            disp_pac = f"{(ape or '').strip()}, {(nom or '').strip()} ({pid})"
            self._ventas_del_dia.append((idv, pid, disp_pac, tot, sal, fch))
            r = self.tblDia.rowCount(); self.tblDia.insertRow(r)
            datos = [idv, disp_pac, fmt_money0(tot), fmt_money0(sal)]  # 👈 sin decimales
            for c, val in enumerate(datos):
                it = QTableWidgetItem(str(val))
                if c in (2, 3): it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tblDia.setItem(r, c, it)

    def _usar_venta_de_la_derecha(self, item):
        """Rellena el form con paciente + saldo de la venta elegida y marca la imputación."""
        row = item.row()
        idv, pid, disp_pac, tot, sal, _fch = self._ventas_del_dia[row]
        # set paciente
        self.txtPaciente.setText(disp_pac.replace(f" ({pid})", f" ({pid})"))
        self._selected_paciente_id = pid
        # set monto = saldo de esa venta
        self.txtMonto.setText(fmt_money(sal))
        self.chkFIFO.setChecked(False)
        # cargar ventas pendientes del paciente y marcar a_imputar para esa venta
        self._load_ventas_pendientes()
        # Buscar fila en la izquierda y setear "A imputar" = min(saldo, monto restante)
        monto = parse_money(self.txtMonto.text())
        restante = monto
        for r in range(self.tbl.rowCount()):
            idventa_izq = int(self.tbl.item(r, 0).text())
            if idventa_izq == idv:
                saldo = parse_money(self.tbl.item(r, 3).text())
                aplicar = min(restante, saldo)
                self.tbl.item(r, 4).setText(fmt_money(aplicar))
                break
        self._recalc_restante()
        self.btnGuardar.setFocus()

    # ---------- Ventas pendientes del paciente (izquierda) ----------
    def _load_ventas_pendientes(self):
        self._updating = True
        try:
            self.tbl.setRowCount(0)
            if not self._selected_paciente_id:
                # intenta adivinar por texto libre si hay una coincidencia única
                self._guess_paciente_by_text()
                if not self._selected_paciente_id:
                    self._recalc_restante(); 
                    return

            pid = int(self._selected_paciente_id)
            ventas = self.session.execute(
                select(Venta.idventa, Venta.fecha, Venta.montototal, Venta.saldo)
                .where(
                    Venta.idpaciente == pid,
                    func.upper(func.coalesce(Venta.estadoventa, "")) != "ANULADA",
                    Venta.saldo > 0
                )
                .order_by(Venta.fecha.asc(), Venta.idventa.asc())
            ).all()

            for (idv, fch, tot, sal) in ventas:
                r = self.tbl.rowCount(); self.tbl.insertRow(r)
                it_id = QTableWidgetItem(str(idv)); it_id.setFlags(it_id.flags() & ~Qt.ItemIsEditable)
                it_f = QTableWidgetItem(fch.strftime("%Y-%m-%d")); it_f.setFlags(it_f.flags() & ~Qt.ItemIsEditable)
                it_t = QTableWidgetItem(fmt_money0(tot))   # 👈
                it_s = QTableWidgetItem(fmt_money0(sal))   # 👈
                it_a = QTableWidgetItem("0")
                self.tbl.setItem(r, 0, it_id); self.tbl.setItem(r, 1, it_f)
                self.tbl.setItem(r, 2, it_t);  self.tbl.setItem(r, 3, it_s)
                self.tbl.setItem(r, 4, it_a)

            self._toggle_fifo_mode()
            self._recalc_restante()
        finally:
            self._updating = False

    # ---------- Helpers izq ----------
    def _ventas_iter(self):
        for r in range(self.tbl.rowCount()):
            idv = int(self.tbl.item(r, 0).text())
            saldo = parse_money(self.tbl.item(r, 3).text())
            a_imp = parse_money(self.tbl.item(r, 4).text())
            yield r, idv, saldo, a_imp

    def _toggle_fifo_mode(self):
        fifo = self.chkFIFO.isChecked()
        for r in range(self.tbl.rowCount()):
            it = self.tbl.item(r, 4)
            if not it: continue
            flags = it.flags()
            it.setFlags((flags & ~Qt.ItemIsEditable) if fifo else (flags | Qt.ItemIsEditable))
        if fifo:
            self._updating = True
            try:
                for r in range(self.tbl.rowCount()):
                    self.tbl.item(r, 4).setText("0,00")
            finally:
                self._updating = False
                self._recalc_restante()

    def _recalc_restante(self):
        monto = parse_money(self.txtMonto.text())
        suma = Decimal("0.00")
        for _, _, _, a in self._ventas_iter():
            suma += a
        restante = _money(monto - suma)
        self.lblRestante.setText(f"Restante: {fmt_money0(restante)}")
        self.lblRestante.setStyleSheet("#lblRestante { font-size:16px; font-weight:700; color:%s; }" %
                                       ("#2e7d32" if restante == Decimal("0.00") else "#b26a00"))

    def _on_item_changed(self, item):
        if self._updating or item.column() != 4: return
        self._updating = True
        try:
            row = item.row()
            saldo = parse_money(self.tbl.item(row, 3).text())
            val = parse_money(item.text())
            if val < Decimal("0"): val = Decimal("0")
            if val > saldo: val = saldo

            monto = parse_money(self.txtMonto.text())
            suma_otros = Decimal("0.00")
            for r, _, _, a in self._ventas_iter():
                if r != row: suma_otros += a
            restante = _money(monto - suma_otros)
            if val > restante: val = max(Decimal("0.00"), restante)

            item.setText(fmt_money(val))
            self._recalc_restante()
        finally:
            self._updating = False

    def _repartir_monto(self):
        if self.chkFIFO.isChecked(): return
        self._updating = True
        try:
            restante = parse_money(self.txtMonto.text())
            for r, _, saldo, _ in self._ventas_iter():
                aplicar = min(restante, saldo) if restante > 0 else Decimal("0.00")
                self.tbl.item(r, 4).setText(fmt_money(aplicar))
                restante -= aplicar
        finally:
            self._updating = False
            self._recalc_restante()

    def _fill_full_on_doubleclick(self, item):
        if item.column() != 4 or self.chkFIFO.isChecked(): return
        row = item.row()
        saldo = parse_money(self.tbl.item(row, 3).text())
        monto = parse_money(self.txtMonto.text())
        suma_otros = sum(a for r, _, _, a in self._ventas_iter() if r != row)
        restante = _money(monto - suma_otros)
        aplicar = min(restante, saldo) if restante > 0 else Decimal("0.00")
        self.tbl.item(row, 4).setText(fmt_money(aplicar))
        self._recalc_restante()

    # ---------- Guardar ----------
    def _on_guardar(self):
        try:
            # Asegurar paciente (autocompletar si solo escribió)
            if not getattr(self, "_selected_paciente_id", None):
                self._guess_paciente_by_text()
            pid = getattr(self, "_selected_paciente_id", None)
            if not pid:
                QMessageBox.warning(self, "Cobro", "Seleccione un paciente.")
                return

            # Monto
            monto = self._leer_monto()   # o: parse_money(self.txtMonto.text())
            if monto <= 0:
                QMessageBox.warning(self, "Cobro", "Ingrese un monto válido.")
                return

            auto_fifo = self.chkFIFO.isChecked()

            # Construir imputaciones solo si NO es FIFO
            imputaciones = None
            if not auto_fifo:
                imputaciones = []
                suma = Decimal("0.00")
                for _, idv, saldo, a in self._ventas_iter():   # (row, idventa, saldo, a_imputar)
                    if a > 0:
                        if a > saldo:
                            QMessageBox.warning(self, "Cobro",
                                f"La imputación a la venta {idv} excede su saldo.")
                            return
                        imputaciones.append({"idventa": idv, "monto": a})
                        suma += a
                if suma > monto:
                    QMessageBox.warning(self, "Cobro",
                        "La suma imputada supera el monto del cobro.")
                    return

            # Registrar (usa lo calculado arriba)
            registrar_cobro(
                session=self.session,
                # Si preferís fecha de hoy, reemplazá por: fecha=date.today(),
                fecha=self.dtpFecha.date().toPyDate(),
                idpaciente=int(pid),
                monto=monto,
                formapago=self.cboForma.currentText(),
                observaciones=self.txtObs.toPlainText(),
                usuarioregistro=self.usuario_actual,
                imputaciones=imputaciones,
                auto_fifo=auto_fifo,
            )

            self.msg_ok("Cobro registrado.")
            self.accept()

        except Exception as e:
            try:
                self.session.rollback()
            except Exception:
                pass
            self.msg_error(f"Ocurrió un error al registrar el cobro:\n{e}")


    # ---------- Event filters ----------
    def eventFilter(self, obj, event):
        # Enter en combo de Forma => Guardar
        if obj is self.cboForma and event.type() == event.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.btnGuardar.setFocus(); return True
        # Enter en tabla derecha => usar venta
        if obj is self.tblDia and event.type() == event.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            it = self.tblDia.currentItem()
            if it: self._usar_venta_de_la_derecha(it)
            return True
        return super().eventFilter(obj, event)

    def _set_fifo_checked(self):
        """Activa FIFO desde el botón/atajo y aplica el modo."""
        self.chkFIFO.setChecked(True)
        self._toggle_fifo_mode()