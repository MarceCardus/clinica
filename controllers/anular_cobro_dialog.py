# controllers/anular_cobro_dialog.py
from decimal import Decimal
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog
)
from sqlalchemy import select, func
from utils.db import SessionLocal
from models.cobro import Cobro
from models.paciente import Paciente
from models.cobro_venta import CobroVenta
from services.cobros_service import anular_cobro

def _fmt0(x) -> str:
    try:
        n = int(Decimal(str(x)))
    except Exception:
        n = 0
    return f"{n:,}".replace(",", ".")

class AnularCobroDialog(QDialog):
    def __init__(self, parent=None, session=None, usuario_actual: int | str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Anular cobro")
        self.resize(980, 620)
        self.session = session or SessionLocal()
        self.usuario_actual = usuario_actual

        root = QVBoxLayout(self)

        # Fila de filtros (fecha + listar + anular)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Fecha:"))
        self.dtp = QDateEdit(QDate.currentDate())
        self.dtp.setCalendarPopup(True)
        self.btnListar = QPushButton("Listar")
        self.btnListar.setObjectName("primary")      # ← azul
        self.btnAnular = QPushButton("Anular (Supr)")
        self.btnAnular.setObjectName("danger")       # ← rojo
        self.btnAnular.setEnabled(False)
        fila.addWidget(self.dtp)
        fila.addWidget(self.btnListar)
        fila.addStretch()
        fila.addWidget(self.btnAnular)
        root.addLayout(fila)

        # Tabla de cobros
        self.tbl = QTableWidget(0, 8)
        self.tbl.setHorizontalHeaderLabels(
            ["ID", "Fecha", "Paciente", "Forma", "Monto", "Imputado", "Disponible", "Estado"]
        )
        hv = self.tbl.horizontalHeader()
        hv.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hv.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hv.setSectionResizeMode(2, QHeaderView.Stretch)          # Paciente ancho
        hv.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Forma
        hv.setSectionResizeMode(4, QHeaderView.ResizeToContents) # Monto
        hv.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Imputado
        hv.setSectionResizeMode(6, QHeaderView.ResizeToContents) # Disponible
        hv.setSectionResizeMode(7, QHeaderView.ResizeToContents) # Estado
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        self.tbl.setAlternatingRowColors(True)
        root.addWidget(self.tbl)

        # Conexiones
        self.btnListar.clicked.connect(self._load)
        self.dtp.dateChanged.connect(self._load)
        self.tbl.itemSelectionChanged.connect(self._update_buttons)
        self.btnAnular.clicked.connect(self._do_anular)

        # Atajo: Supr para anular
        self.tbl.keyPressEvent = self._tbl_keypress_wrapper(self.tbl.keyPressEvent)
        self._style()
        # Primera carga
        self._load()

    def _style(self):
        self.setStyleSheet("""
            QDialog { background: #f6f8fb; }
            QTableWidget { background: #ffffff; border: 1px solid #c6d4ea; border-radius: 6px; }
            QHeaderView::section { background: #e8f0fe; padding: 6px; border: none; color:#0d3a6a; }

            QPushButton#primary {
                background: #245b9e; color: #fff; border: none; border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton#primary:hover { background: #1f4f8a; }

            QPushButton#danger {
                background: #c62828; color: #fff; border: none; border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton#danger:disabled { background: #e0e0e0; color: #9e9e9e; }
            QPushButton#danger:enabled:hover { background: #b71c1c; }
        """)


    def _tbl_keypress_wrapper(self, orig):
        def _inner(event):
            if event.key() == Qt.Key_Delete and self.btnAnular.isEnabled():
                self._do_anular(); return
            return orig(event)
        return _inner

    def _update_buttons(self):
        row = self.tbl.currentRow()
        ok = row >= 0 and (self.tbl.item(row, 7).text().upper() != "ANULADO")
        self.btnAnular.setEnabled(ok)

    def _load(self):
        self.tbl.setRowCount(0)
        f = self.dtp.date().toPyDate()

        # cobros del día + sum(imputado)
        rows = self.session.execute(
            select(
                Cobro.idcobro,
                Cobro.fecha,
                Paciente.apellido,
                Paciente.nombre,
                Cobro.formapago,
                Cobro.monto,
                func.coalesce(func.sum(CobroVenta.montoimputado), 0),
                Cobro.estado
            )
            .join(Paciente, Paciente.idpaciente == Cobro.idpaciente)
            .outerjoin(CobroVenta, CobroVenta.idcobro == Cobro.idcobro)
            .where(Cobro.fecha == f)
            .group_by(Cobro.idcobro, Cobro.fecha, Paciente.apellido, Paciente.nombre,
                      Cobro.formapago, Cobro.monto, Cobro.estado)
            .order_by(Cobro.idcobro.desc())
        ).all()

        for idc, fecha, ape, nom, forma, monto, imputado, estado in rows:
            disp = f"{(ape or '').strip()}, {(nom or '').strip()}"
            disponible = max(Decimal(monto) - Decimal(imputado or 0), Decimal("0"))
            r = self.tbl.rowCount(); self.tbl.insertRow(r)
            data = [idc, fecha.strftime("%Y-%m-%d"), disp, (forma or ""), _fmt0(monto),
                    _fmt0(imputado or 0), _fmt0(disponible), (estado or "ACTIVO")]
            for c, val in enumerate(data):
                it = QTableWidgetItem(str(val))
                if c in (4,5,6):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                # ID/Fecha no editables
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.tbl.setItem(r, c, it)

        self._update_buttons()

    def _do_anular(self):
        row = self.tbl.currentRow()
        if row < 0:
            return
        idcobro = int(self.tbl.item(row, 0).text())
        estado = self.tbl.item(row, 7).text().upper()
        if estado == "ANULADO":
            QMessageBox.information(self, "Cobro", "Este cobro ya está anulado.")
            return

        motivo, ok = QInputDialog.getText(self, "Anular cobro",
                                          "Motivo de anulación (opcional):")
        if not ok:
            return

        try:
            anular_cobro(session=self.session, idcobro=idcobro, motivo=motivo,
             usuario=self.usuario_actual)
            # Si tu `registrar/anular` ya maneja la transacción con begin_nested,
            # igual conviene hacer commit “externo” para cerrar la sesión del UI.
            self.session.commit()
            QMessageBox.information(self, "Cobro", "Cobro anulado correctamente.")
            self._load()
        except Exception as e:
            try: self.session.rollback()
            except: pass
            QMessageBox.critical(self, "Error", f"No se pudo anular el cobro:\n{e}")
