# controllers/cobro_dialog.py
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from PyQt5.QtCore import Qt, QDate, QTimer
from PyQt5.QtGui import QKeySequence, QIcon
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QComboBox,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QMessageBox,
    QCheckBox, QShortcut, QDateEdit, QSplitter, QSizePolicy, QWidget, QCompleter
)

from sqlalchemy import select, func, literal

# ajusta este import a tu fábrica de sesiones si hace falta
from utils.db import SessionLocal

from models.paciente import Paciente
from models.venta import Venta
from services.cobros_service import (
    registrar_cobro,
    imputar_credito_a_venta,
    total_credito_disponible,
)


class CobroDialog(QDialog):
    def __init__(self, parent=None, session=None, usuario_actual: str | int | None = None):
        super().__init__(parent)
        self.setWindowTitle("Registrar cobro")
        self.resize(1440, 720)          # más ancho/alto de inicio
        self.setMinimumSize(1150, 620)  # evita que quede demasiado chico

        self.session = session or SessionLocal()
        self.usuario_actual = usuario_actual if usuario_actual is not None else "sistema"

        self._updating = False
        self._pacientes_cache = []      # [(id, doc, nombre, apellido, display)]
        self._map_display_to_id = {}    # display -> id
        self._selected_paciente_id = None
        self._ventas_del_dia = []       # [(idventa, idpaciente, paciente_disp, total, saldo, fecha)]

        self._build_ui()
        self._wire_shortcuts()
        self._style()
        self._load_pacientes()
        self._load_ventas_por_fecha()   # derecha (hoy)
        self._focus_inicio()

    # ===================== Helpers de dinero / formato ======================

    def _money(self, x) -> Decimal:
        return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _parse_money(self, s: str) -> Decimal:
        """
        Soporta: 400000 | 400.000 | 400,000 | 400.000,00 | 400,000.00
        Limpia NBSP y caracteres no numéricos salvo . , -
        """
        if not s:
            return Decimal("0.00")
        s = str(s).replace("\u00a0", " ").strip()
        s = "".join(ch for ch in s if ch.isdigit() or ch in ",.-")
        if not s or s in {",", ".", "-", "-.", "-,"}:
            return Decimal("0.00")

        has_comma = "," in s
        has_dot = "." in s

        if has_comma and has_dot:
            # europeo: . miles, , decimales
            s = s.replace(".", "").replace(",", ".")
        elif has_comma and not has_dot:
            s = s.replace(",", ".")
        elif has_dot and not has_comma:
            # decidir si el punto es miles o decimal
            parts = s.split(".")
            if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]) and 1 <= len(parts[0]) <= 3:
                s = "".join(parts)  # puntos como miles
            # si no, se deja como decimal
        # else: solo dígitos -> entero

        try:
            return self._money(Decimal(s))
        except Exception:
            return Decimal("0.00")

    def _leer_monto(self) -> Decimal:
        return self._parse_money(self.txtMonto.text())
    
    def _normalize_monto(self):
        """Normaliza el QLineEdit de monto al salir del control (sin disparar textChanged en cascada)."""
        monto = self._leer_monto()  # lee lo que haya (400000, 400.000, 400.000,00, etc.)
        self.txtMonto.blockSignals(True)
        try:
            # Mostramos sin decimales, con separador de miles (Gs)
            self.txtMonto.setText(self._fmt0(monto))
        finally:
            self.txtMonto.blockSignals(False)
        # Recalcular restante después de normalizar
        self._recalc_restante()

    def _fmt0(self, x: Decimal | int) -> str:
        """Formato sin decimales con separador de miles '.' (Gs)."""
        n = int(Decimal(x))
        return f"{n:,}".replace(",", ".")

    # ============================== UI =====================================

    def _build_ui(self):
        root = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # -------- IZQUIERDA --------
        left = QVBoxLayout()
        left_widget = QWidget(self)
        left_widget.setLayout(left)
        splitter.addWidget(left_widget)

        # Paciente
        header = QFormLayout()
        self.txtPaciente = QLineEdit()
        self.txtPaciente.setPlaceholderText("Buscar por CI / Nombre / Apellido…")
        header.addRow("Paciente:", self.txtPaciente)

        # Monto / Forma / FIFO
        fila_top = QHBoxLayout()
        self.txtMonto = QLineEdit()
        self.txtMonto.setPlaceholderText("0,00")
        self.cboForma = QComboBox()
        self.cboForma.addItems(["Efectivo", "T. Crédito", "T. Débito", "Transferencia", "Cheque"])
        self.chkFIFO = QCheckBox("Imputar automático (FIFO)")
        fila_top.addWidget(QLabel("Monto:"))
        fila_top.addWidget(self.txtMonto, 2)
        fila_top.addWidget(QLabel("Forma:"))
        fila_top.addWidget(self.cboForma, 2)
        fila_top.addWidget(self.chkFIFO, 2)

        left.addLayout(header)
        left.addLayout(fila_top)

        # Mostrar crédito a favor del paciente
        self.lblCredito = QLabel("Crédito a favor: 0")
        left.addWidget(self.lblCredito)
        # Normalizar monto al salir del control
        self.txtMonto.editingFinished.connect(self._normalize_monto)

        
        # Observaciones
        self.txtObs = QTextEdit()
        self.txtObs.setPlaceholderText("Observaciones…")
        self.txtObs.setFixedHeight(130)
        left.addWidget(self.txtObs)

        # Tabla de ventas del paciente
        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["ID Venta", "Fecha", "Total", "Saldo", "A imputar"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        left.addWidget(self.tbl)

        # Que SOLO la tabla crezca
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

        # -------- DERECHA --------
        right = QVBoxLayout()
        right_widget = QWidget(self)
        right_widget.setLayout(right)
        splitter.addWidget(right_widget)

        # Proporciones del splitter
        left_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        left_widget.setMinimumWidth(740)
        left_widget.setMaximumWidth(820)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        QTimer.singleShot(0, lambda: splitter.setSizes([720, 1100]))

        # Fecha + listar
        fila_fecha = QHBoxLayout()
        self.dtpFecha = QDateEdit(QDate.currentDate())
        self.dtpFecha.setCalendarPopup(True)
        btnListar = QPushButton("Listar")
        fila_fecha.addWidget(QLabel("Fecha:"))
        fila_fecha.addWidget(self.dtpFecha)
        fila_fecha.addWidget(btnListar)
        fila_fecha.addStretch()
        right.addLayout(fila_fecha)

        # Grilla derecha
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

        # -------- FOOTER (ancho completo) --------
        footer = QHBoxLayout()
        self.lblRestante = QLabel("Restante: 0,00")
        self.lblRestante.setObjectName("lblRestante")

        self.btnRepartir = QPushButton("Repartir (F7)")
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
        root.addWidget(footer_w)

        # Conexiones footer
        self.btnRepartir.clicked.connect(self._repartir_monto)
        self.btnAuto.clicked.connect(self._set_fifo_checked)
        self.btnGuardar.clicked.connect(self._on_guardar)
        self.btnCancelar.clicked.connect(self.reject)
        self.btnGuardar.setDefault(True)
        self.btnGuardar.setAutoDefault(True)

    # ============================== ESTILO/UX ===============================

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
            QPushButton { background: #2e7d32; color: white; padding: 6px 10px; border: none; border-radius: 6px; }
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

    def _refresh_credito_label(self):
        pid = getattr(self, "_selected_paciente_id", None)
        if not pid:
            self.lblCredito.setText("Crédito a favor: 0")
            self.lblCredito.setStyleSheet("color:#666")
            return
        try:
            credito = total_credito_disponible(self.session, int(pid))
        except Exception:
            credito = Decimal("0")
        self.lblCredito.setText(f"Crédito a favor: {self._fmt0(credito)}")
        self.lblCredito.setStyleSheet("color:#2e7d32" if credito > 0 else "color:#666")
    # ======================= Pacientes (completer) ==========================

    def _load_pacientes(self):
        # detectar columna de documento
        doc_col = None
        for name in ["ci_pasaporte", "ci_passaporte", "ci", "cedula", "documento", "dni", "ruc", "num_doc", "nro_documento", "numero_documento"]:
            doc_col = getattr(Paciente, name, None)
            if doc_col is not None:
                break
        if doc_col is None:
            doc_col = literal("").label("doc")

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
            disp = f"{doc_txt} - {ape}, {nom} ({pid})" if doc_txt else f"{ape}, {nom} ({pid})"
            self._pacientes_cache.append((pid, doc_txt, nom, ape, disp))
            self._map_display_to_id[disp] = pid

        completer = QCompleter([x[4] for x in self._pacientes_cache], self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.activated[str].connect(self._on_paciente_elegido)
        self.txtPaciente.setCompleter(completer)

    def _on_paciente_elegido(self, text):
        self._selected_paciente_id = self._map_display_to_id.get(text)
        self._load_ventas_pendientes()
        self._refresh_credito_label()

    def _guess_paciente_by_text(self):
        txt = self.txtPaciente.text().strip().lower()
        if not txt:
            self._selected_paciente_id = None
            return
        matches = [pid for (pid, _ci, _n, _a, disp) in self._pacientes_cache if txt in disp.lower()]
        self._selected_paciente_id = matches[0] if len(matches) == 1 else None

    # =================== Ventas panel derecho (por fecha) ===================

    def _load_ventas_por_fecha(self):
        self.tblDia.setRowCount(0)
        f = self.dtpFecha.date().toPyDate()
        rows = self.session.execute(
            select(Venta.idventa, Venta.idpaciente, Venta.montototal, Venta.saldo, Venta.fecha,
                   Paciente.apellido, Paciente.nombre)
            .join(Paciente, Paciente.idpaciente == Venta.idpaciente)
            .where(Venta.fecha == f, func.upper(func.coalesce(Venta.estadoventa, "")) != "ANULADA")
            .order_by(Paciente.apellido.asc(), Paciente.nombre.asc(), Venta.idventa.asc())
        ).all()

        self._ventas_del_dia = []
        for (idv, pid, tot, sal, fch, ape, nom) in rows:
            disp_pac = f"{(ape or '').strip()}, {(nom or '').strip()} ({pid})"
            self._ventas_del_dia.append((idv, pid, disp_pac, tot, sal, fch))
            r = self.tblDia.rowCount()
            self.tblDia.insertRow(r)
            datos = [idv, disp_pac, self._fmt0(tot), self._fmt0(sal)]
            for c, val in enumerate(datos):
                it = QTableWidgetItem(str(val))
                if c in (2, 3):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tblDia.setItem(r, c, it)

    def _usar_venta_de_la_derecha(self, item):
        row = item.row()
        idv, pid, disp_pac, _tot, sal, _fch = self._ventas_del_dia[row]
        # set paciente
        self.txtPaciente.setText(disp_pac)
        self._selected_paciente_id = pid
        # set monto = saldo de esa venta
        self.txtMonto.setText(self._fmt0(sal))
        self.chkFIFO.setChecked(False)
        # cargar ventas pendientes del paciente y marcar a_imputar para esa venta
        self._load_ventas_pendientes()
        monto = self._leer_monto()
        restante = monto
        for r in range(self.tbl.rowCount()):
            idventa_izq = int(self.tbl.item(r, 0).text())
            if idventa_izq == idv:
                saldo = self._parse_money(self.tbl.item(r, 3).text())
                aplicar = min(restante, saldo)
                self.tbl.item(r, 4).setText(self._fmt0(aplicar))
                break
        self._recalc_restante()
        self.btnGuardar.setFocus()

    # ================= Ventas pendientes (panel izquierdo) ==================

    def _load_ventas_pendientes(self):
        self._updating = True
        try:
            self.tbl.setRowCount(0)
            if not self._selected_paciente_id:
                self._guess_paciente_by_text()
                if not self._selected_paciente_id:
                    self._recalc_restante()
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
                r = self.tbl.rowCount()
                self.tbl.insertRow(r)
                it_id = QTableWidgetItem(str(idv)); it_id.setFlags(it_id.flags() & ~Qt.ItemIsEditable)
                it_f = QTableWidgetItem(fch.strftime("%Y-%m-%d")); it_f.setFlags(it_f.flags() & ~Qt.ItemIsEditable)
                it_t = QTableWidgetItem(self._fmt0(tot))
                it_s = QTableWidgetItem(self._fmt0(sal))
                it_a = QTableWidgetItem("0")
                self.tbl.setItem(r, 0, it_id); self.tbl.setItem(r, 1, it_f)
                self.tbl.setItem(r, 2, it_t);  self.tbl.setItem(r, 3, it_s)
                self.tbl.setItem(r, 4, it_a)

            self._toggle_fifo_mode()
            self._recalc_restante()
            self._refresh_credito_label()
        finally:
            self._updating = False

    # ============================ Helpers IZQ ===============================

    def _ventas_iter(self):
        """Genera (row_index, idventa:int, saldo:Decimal, a_imputar:Decimal)."""
        for r in range(self.tbl.rowCount()):
            it_id = self.tbl.item(r, 0)
            idventa = int((it_id.text() if it_id else "0") or "0")
            it_saldo = self.tbl.item(r, 3)
            it_imp = self.tbl.item(r, 4)
            saldo = self._parse_money(it_saldo.text() if it_saldo else "0")
            a_imp = self._parse_money(it_imp.text() if it_imp else "0")
            yield (r, idventa, saldo, a_imp)

    def _toggle_fifo_mode(self):
        fifo = self.chkFIFO.isChecked()
        for r in range(self.tbl.rowCount()):
            it = self.tbl.item(r, 4)
            if not it:
                continue
            flags = it.flags()
            it.setFlags((flags & ~Qt.ItemIsEditable) if fifo else (flags | Qt.ItemIsEditable))
        if fifo:
            self._updating = True
            try:
                for r in range(self.tbl.rowCount()):
                    self.tbl.item(r, 4).setText("0")
            finally:
                self._updating = False
                self._recalc_restante()

    def _recalc_restante(self):
        monto = self._leer_monto()
        suma = Decimal("0.00")
        for _, _, _, a in self._ventas_iter():
            suma += a
        restante = self._money(monto - suma)
        self.lblRestante.setText(f"Restante: {self._fmt0(restante)}")
        self.lblRestante.setStyleSheet(
            "#lblRestante { font-size:16px; font-weight:700; color:%s; }"
            % ("#2e7d32" if restante == Decimal("0.00") else "#b26a00")
        )

    def _on_item_changed(self, item):
        if self._updating or item.column() != 4:
            return
        self._updating = True
        try:
            row = item.row()
            saldo = self._parse_money(self.tbl.item(row, 3).text())
            val = self._parse_money(item.text())
            if val < Decimal("0"):
                val = Decimal("0")
            if val > saldo:
                val = saldo

            monto = self._leer_monto()
            suma_otros = Decimal("0.00")
            for r, _, _, a in self._ventas_iter():
                if r != row:
                    suma_otros += a
            restante = self._money(monto - suma_otros)
            if val > restante:
                val = max(Decimal("0.00"), restante)

            item.setText(self._fmt0(val))
            self._recalc_restante()
        finally:
            self._updating = False

    def _repartir_monto(self):
        if self.chkFIFO.isChecked():
            return
        self._updating = True
        try:
            restante = self._leer_monto()
            for r, _, saldo, _ in self._ventas_iter():
                aplicar = min(restante, saldo) if restante > 0 else Decimal("0.00")
                self.tbl.item(r, 4).setText(self._fmt0(aplicar))
                restante -= aplicar
        finally:
            self._updating = False
            self._recalc_restante()

    def _fill_full_on_doubleclick(self, item):
        if item.column() != 4 or self.chkFIFO.isChecked():
            return
        row = item.row()
        saldo = self._parse_money(self.tbl.item(row, 3).text())
        monto = self._leer_monto()
        suma_otros = sum(a for r, _, _, a in self._ventas_iter() if r != row)
        restante = self._money(monto - suma_otros)
        aplicar = min(restante, saldo) if restante > 0 else Decimal("0.00")
        self.tbl.item(row, 4).setText(self._fmt0(aplicar))
        self._recalc_restante()

    # ============================== Guardar ================================

    def _on_guardar(self):
        try:
            # Asegurar paciente (si solo tipeó y dio Enter)
            if not getattr(self, "_selected_paciente_id", None):
                self._guess_paciente_by_text()
            pid = getattr(self, "_selected_paciente_id", None)
            if not pid:
                QMessageBox.warning(self, "Cobro", "Seleccione un paciente.")
                return
            pid = int(pid)

            monto_ingresado = self._leer_monto()
            if monto_ingresado < 0:
                QMessageBox.warning(self, "Cobro", "Ingrese un monto válido.")
                return

            auto_fifo = self.chkFIFO.isChecked()

            # ------------------- Paso 1: CONSUMIR CRÉDITO PREVIO -------------------
            # Si hay ventas seleccionadas manualmente (imputaciones) consumimos crédito contra cada una.
            # Si es FIFO, consumimos crédito contra todas las ventas pendientes del paciente.
            # Esto reduce saldos antes de crear cualquier cobro nuevo.

            aplicado_credito_total = Decimal("0.00")
            imputaciones_finales = []   # lo que realmente quedará para el nuevo cobro (si hace falta)

            if not auto_fifo:
                # 1) Construir 'pedidas' (imputaciones que el usuario marcó en la grilla)
                pedidas = []
                for _, idv, saldo, a in self._ventas_iter():
                    if a > 0:
                        pedidas.append({"idventa": idv, "monto": a, "saldo": saldo})

                # 2) VALIDACIÓN: nada que hacer (sin imputaciones, sin monto y sin crédito)
                if not pedidas and monto_ingresado == 0:
                    if total_credito_disponible(self.session, pid) <= 0:
                        QMessageBox.information(
                            self, "Cobro",
                            "No hay nada que registrar: sin imputaciones, sin monto y sin crédito a favor."
                        )
                        return

                # 3) Consumir crédito previo contra cada venta pedida (FIFO interno del service)
                for ped in pedidas:
                    aplicado = imputar_credito_a_venta(self.session, idpaciente=pid, idventa=ped["idventa"])
                    aplicado_credito_total += aplicado
                    # monto aún a cubrir con el cobro nuevo para esa venta:
                    restante_esta = self._money(Decimal(ped["monto"]) - Decimal(aplicado))
                    if restante_esta > 0:
                        imputaciones_finales.append({"idventa": ped["idventa"], "monto": restante_esta})

                # 1.b) decidir cuánto del monto ingresado usar para imputar y si hay excedente
                total_a_cubrir = sum((i["monto"] for i in imputaciones_finales), Decimal("0"))
                if total_a_cubrir == 0:
                    # No queda nada por cubrir; si el usuario ingresó plata, queda como crédito nuevo
                    if monto_ingresado > 0:
                        registrar_cobro(
                            session=self.session,
                            fecha=date.today(),
                            idpaciente=pid,
                            monto=monto_ingresado,
                            formapago=self.cboForma.currentText(),
                            observaciones=(self.txtObs.toPlainText() or "") + " (anticipo a favor)",
                            usuarioregistro=self.usuario_actual,
                            imputaciones=None,
                            auto_fifo=False,
                        )
                    # commit + UI
                    self.session.commit()
                    self.session.expire_all()
                    self.msg_ok(f"Cobro registrado. Crédito aplicado: {self._fmt0(aplicado_credito_total)}.")
                    self._reset_after_save()
                    return

                # 🔧 NUEVO: si aún queda por cubrir pero no ingresó dinero, confirmamos crédito y salimos
                if monto_ingresado == 0:
                    self.session.commit()
                    self.session.expire_all()
                    self.msg_ok(f"Crédito aplicado: {self._fmt0(aplicado_credito_total)}. Aún quedan saldos pendientes.")
                    self._reset_after_save()
                    return

                # 1.c) Si el monto ingresado es menor al total requerido, imputamos parcialmente
                monto_restante = self._money(monto_ingresado)
                if monto_restante > 0 and total_a_cubrir > 0:
                    imputaciones_aplicar = []
                    for imp in imputaciones_finales:
                        if monto_restante <= 0:
                            break
                        aplicar = min(monto_restante, imp["monto"])
                        if aplicar > 0:
                            imputaciones_aplicar.append({"idventa": imp["idventa"], "monto": aplicar})
                            monto_restante -= aplicar

                    if imputaciones_aplicar:
                        monto_imputado_nuevo = sum((x["monto"] for x in imputaciones_aplicar), Decimal("0"))
                        # Cobro por lo que alcanzó para imputar
                        registrar_cobro(
                            session=self.session,
                            fecha=date.today(),
                            idpaciente=pid,
                            monto=monto_imputado_nuevo,
                            formapago=self.cboForma.currentText(),
                            observaciones=self.txtObs.toPlainText(),
                            usuarioregistro=self.usuario_actual,
                            imputaciones=imputaciones_aplicar,
                            auto_fifo=False,
                        )
                    else:
                        monto_imputado_nuevo = Decimal("0")

                    # Excedente (si quedó plata y ya no hay nada por cubrir → anticipo)
                    excedente = self._money(monto_ingresado - monto_imputado_nuevo)
                    if excedente > 0:
                        registrar_cobro(
                            session=self.session,
                            fecha=date.today(),
                            idpaciente=pid,
                            monto=excedente,
                            formapago=self.cboForma.currentText(),
                            observaciones=(self.txtObs.toPlainText() or "") + " (excedente a favor)",
                            usuarioregistro=self.usuario_actual,
                            imputaciones=None,
                            auto_fifo=False,
                        )

                    self.session.commit()
                    self.session.expire_all()
                    self.msg_ok(f"Cobro registrado. Crédito aplicado: {self._fmt0(aplicado_credito_total)}.")
                    self._reset_after_save()
                    return

            else:
                # VALIDACIÓN FIFO: si no hay monto y tampoco crédito a favor, no hay nada que aplicar
                if monto_ingresado == 0 and total_credito_disponible(self.session, pid) <= 0:
                    QMessageBox.information(
                        self, "Cobro",
                        "No hay nada que registrar: sin monto y sin crédito a favor."
                    )
                    return

                # AUTO FIFO: consumimos crédito contra TODAS las ventas pendientes del paciente
                # 1) Traer las ventas pendientes (como en _load_ventas_pendientes)
                ventas = self.session.execute(
                    select(Venta.idventa, Venta.saldo)
                    .where(
                        Venta.idpaciente == pid,
                        func.upper(func.coalesce(Venta.estadoventa, "")) != "ANULADA",
                        Venta.saldo > 0
                    )
                    .order_by(Venta.fecha.asc(), Venta.idventa.asc())
                ).all()

                for (idv, _sal) in ventas:
                    aplicado_credito_total += imputar_credito_a_venta(self.session, idpaciente=pid, idventa=idv)

                # 2) Si el usuario ingresó monto > 0, ahora sí creamos un cobro FIFO para lo que quede
                if monto_ingresado > 0:
                    registrar_cobro(
                        session=self.session,
                        fecha=date.today(),
                        idpaciente=pid,
                        monto=monto_ingresado,
                        formapago=self.cboForma.currentText(),
                        observaciones=self.txtObs.toPlainText(),
                        usuarioregistro=self.usuario_actual,
                        imputaciones=None,
                        auto_fifo=True,   # esto aplicará el NUEVO cobro a las ventas con saldo restante
                    )

                self.session.commit()
                self.session.expire_all()
                self.msg_ok(f"Cobro registrado. Crédito aplicado: {self._fmt0(aplicado_credito_total)}.")
                self._reset_after_save()
                return

        except Exception as e:
            try:
                self.session.rollback()
            except Exception:
                pass
            self.msg_error(f"Ocurrió un error al registrar el cobro:\n{e}")



    # ============================ Eventos varios ===========================
    def _reset_after_save(self):
        """Deja el formulario listo para cargar otro cobro sin cerrar el diálogo."""
        # Vaciar panel izquierdo
        self._selected_paciente_id = None
        self.txtPaciente.clear()
        self.txtMonto.setText(self._fmt0(0))
        self.cboForma.setCurrentIndex(0)
        self.chkFIFO.setChecked(False)
        self.txtObs.clear()
        self.tbl.setRowCount(0)
        self.lblRestante.setText(f"Restante: {self._fmt0(0)}")
        self._refresh_credito_label()

        # Refrescar panel derecho (ventas del día/fecha seleccionada)
        self._load_ventas_por_fecha()

        # Foco de nuevo al buscador de paciente
        self.txtPaciente.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.cboForma and event.type() == event.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.btnGuardar.setFocus()
            return True
        if obj is self.tblDia and event.type() == event.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            it = self.tblDia.currentItem()
            if it:
                self._usar_venta_de_la_derecha(it)
            return True
        return super().eventFilter(obj, event)

    def _set_fifo_checked(self):
        self.chkFIFO.setChecked(True)
        self._toggle_fifo_mode()

    # ============================ Mensajería ===============================

    def msg_error(self, msg: str):
        QMessageBox.critical(self, "Error", msg)

    def msg_ok(self, msg: str):
        QMessageBox.information(self, "Cobro", msg)
