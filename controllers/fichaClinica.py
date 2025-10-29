# controllers/fichaClinica.py
import sys

from functools import partial

from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QTabWidget, QWidget, QHBoxLayout,
    QFormLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QCheckBox,
    QDateEdit, QTableWidget, QTableWidgetItem, QComboBox, QGridLayout, QMessageBox,
    QSpinBox, QTimeEdit, QCompleter, QDoubleSpinBox, QAbstractItemView, QHeaderView
)
from PyQt5.QtGui import QIcon, QColor, QDoubleValidator
from PyQt5.QtCore import QDate, Qt, QSize, QTime

from sqlalchemy.orm import joinedload
from sqlalchemy import func, or_
from contextlib import contextmanager
from sqlalchemy import case
from models.item_composicion import ItemComposicion
from models.procedimiento_item import procedimiento_item
import math
from utils.db import SessionLocal

# Modelos
from models.paciente import Paciente
from models.antecPatologico import AntecedentePatologicoPersonal
from models.antecFliar import AntecedenteFamiliar
from models.antecEnfActual import AntecedenteEnfermedadActual
from models.encargado import Encargado
from models.pacienteEncargado import PacienteEncargado
from models.indicacion import Indicacion
from models.profesional import Profesional
from models.barrio import Barrio
from models.ciudad import Ciudad
from models.departamento import Departamento
from models.StockMovimiento import StockMovimiento
from models.recordatorio_paciente import RecordatorioPaciente
from models.item import Item          # ← único catálogo que usamos
from models.procedimiento import Procedimiento
from controllers.historial import get_historial_paciente,get_resumen_financiero_paciente
from controllers.generador_recordatorios import (
    generar_recordatorios_medicamento,
    validar_indicacion_medicamento,
    eliminar_recordatorios_de_indicacion
)


def convertir_vacio_a_none(valor: str):
    valor = (valor or "").strip()
    try:
        return float(valor) if valor else None
    except ValueError:
        return None


@contextmanager
def _painting_suspended(tbl):
    try:
        tbl.setUpdatesEnabled(False)
        sort_was = tbl.isSortingEnabled()
        tbl.setSortingEnabled(False)
        yield
    finally:
        tbl.setSortingEnabled(sort_was)
        tbl.setUpdatesEnabled(True)
        tbl.viewport().update()


class NumericItem(QTableWidgetItem):
    """Item numérico que ordena por valor y alinea a la derecha."""
    def __init__(self, val, fmt="{:.2f}"):
        f = None
        if val not in (None, ""):
            try:
                f = float(val)
            except Exception:
                try:
                    f = float(str(val).replace(",", ".").split()[0])
                except Exception:
                    f = None
        super().__init__("" if f is None else fmt.format(f))
        self._val = f if f is not None else float("-inf")
        self.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    

    def __lt__(self, other):
        if isinstance(other, NumericItem):
            return self._val < other._val
        try:
            return self._val < float(other.text().replace(",", "."))
        except Exception:
            return super().__lt__(other)

def gs(n):
        try:
            return f"Gs {float(n):,.0f}".replace(",", ".")
        except Exception:
            return ""
class MoneyItem(QTableWidgetItem):
    def __init__(self, val):
        try:
            f = float(val) if val is not None else None
        except Exception:
            f = None
        self._val = f if f is not None else float("-inf")
        super().__init__("" if f is None else gs(f))
        self.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def __lt__(self, other):
        if isinstance(other, MoneyItem):
            return self._val < other._val
        try:
            txt = other.text().replace("Gs", "").replace(".", "").strip()
            return self._val < float(txt or "0")
        except Exception:
            return super().__lt__(other)        
class DateItem(QTableWidgetItem):
    def __init__(self, val):
        from datetime import datetime, date
        key = float("-inf"); txt = ""
        try:
            if isinstance(val, (datetime, date)):
                d = val.date() if isinstance(val, datetime) else val
                key = d.toordinal(); txt = d.strftime("%d/%m/%y")
            else:
                s = str(val or "").strip()
                parsed = None
                for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        parsed = datetime.strptime(s, fmt); break
                    except Exception:
                        pass
                if not parsed:
                    try:
                        parsed = datetime.fromisoformat(s.replace("Z", ""))
                    except Exception:
                        parsed = None
                if parsed:
                    key = parsed.date().toordinal(); txt = parsed.strftime("%d/%m/%y")
                else:
                    txt = s
        except Exception:
            txt = str(val or "")
        super().__init__(txt)
        self._key = key
        self.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)

    def __lt__(self, other):
        if isinstance(other, DateItem):
            return self._key < other._key
        return super().__lt__(other)
            
class FichaClinicaForm(QDialog):
    def __init__(self, idpaciente, parent=None, solo_control=False,acciones_proc_en_solo=False):
        super().__init__(parent)
        self.setWindowTitle("Ficha Clínica del Paciente")
        self.setMinimumWidth(1100)

        self.idpaciente = idpaciente
        self.solo_control = solo_control
        self.acciones_proc_en_solo = acciones_proc_en_solo  # ← NUEVO
        self.session = SessionLocal()

        self.control_editando_id = None
        self.procedimiento_editando_id = None
        self.receta_editando_id = None

        self.init_ui()
        self.cargar_todo()
        self.tabs.currentChanged.connect(self._on_tab_changed)
    # ---------- util (autocompletar de combos) ----------
    def _setup_contains_completer(self, combo: QComboBox):
        combo.setEditable(True)
        compl = QCompleter(combo.model(), combo)
        compl.setCompletionColumn(0)
        compl.setCaseSensitivity(Qt.CaseInsensitive)
        compl.setFilterMode(Qt.MatchContains)
        combo.setCompleter(compl)
        combo.setInsertPolicy(QComboBox.NoInsert)
    # ----------------------------------------------------
    def _on_tab_changed(self, idx):
        try:
            if self.tabs.widget(idx) is self.tab_historial:
                self.cargar_historial_tab()
        except Exception as e:
            print("Error al refrescar historial:", e)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # Tabs
        self.tab_basicos = QWidget();        self.ui_tab_basicos()
        self.tab_encargados = QWidget();     self.ui_tab_encargados()
        self.tab_fliares = QWidget();        self.ui_tab_fliares()
        self.tab_patologicos = QWidget();    self.ui_tab_patologicos()
        self.tab_enfactual = QWidget();      self.ui_tab_enfactual()
        self.tab_procedimientos = QWidget(); self.ui_tab_procedimientos()
        self.tab_recetas = QWidget();        self.ui_tab_recetas()
        self.tab_recordatorios = QWidget();  self.ui_tab_recordatorios()
        self.tab_historial = QWidget();      self.ui_tab_historial()

        if hasattr(self, "cbo_departamento"):
            self._cargar_departamentos()

        if self.solo_control:
            self.tabs.addTab(self.tab_enfactual, "📈 Control de Estado")
            self.tabs.addTab(self.tab_historial, "📜 Historial")
            self.tabs.addTab(self.tab_procedimientos, "💉 Procedimientos")
            self.tabs.addTab(self.tab_recetas, "📋 Indicaciones")
            self.tabs.addTab(self.tab_recordatorios, "🔔 Recordatorios")
        else:
            self.tabs.addTab(self.tab_basicos, "🧑 Datos Personales")
            self.tabs.addTab(self.tab_encargados, "👤 Encargados")
            self.tabs.addTab(self.tab_fliares, "👪 Antecedentes Familiares")
            self.tabs.addTab(self.tab_patologicos, "🩺 Antecedentes Patológicos")
            self.tabs.addTab(self.tab_enfactual, "📈 Control de Estado")
            self.tabs.addTab(self.tab_historial, "📜 Historial")
            self.tabs.addTab(self.tab_procedimientos, "💉 Procedimientos")
            self.tabs.addTab(self.tab_recetas, "📋 Indicaciones/Recetas")
            self.tabs.addTab(self.tab_recordatorios, "🔔 Recordatorios")

        main_layout.addWidget(self.tabs)

        for tbl in (
            self.table_controles,
            self.table_procedimientos,
            self.table_recetas,
            self.table_recordatorios,
            self.table_encargados,
        ):
            tbl.clearSelection()
            tbl.verticalHeader().setVisible(False)
            tbl.setSortingEnabled(True)
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
            tbl.setSelectionMode(QAbstractItemView.SingleSelection)

        self.btn_guardar = QPushButton("Guardar Cambios")
        self.btn_guardar.clicked.connect(self.guardar_todo)
        main_layout.addWidget(self.btn_guardar)
        self.btn_guardar.setVisible(not self.solo_control)

    def _unidad_es_discreta(self, unidad: str) -> bool:
        """
        Heurística simple para decidir redondeo:
        - Líquidos y fraccionables (ml/cc/l/g/mg/kg/oz) => NO discreta (permite decimales).
        - Ampollas, jeringas, bisturí, frasco, vial, tableta, comprimido => DISCRETA (CEIL).
        - Si no reconoce, por defecto la tratamos como discreta para evitar fracciones raras.
        """
        u = (unidad or "").strip().lower()
        tokens_liquidos = ["ml", "cc", "l", "litro", "g", "mg", "kg", "oz"]
        if any(tok in u for tok in tokens_liquidos):
            return False
        tokens_discretos = ["amp", "unidad", "u", "ud", "jering", "bistur", "kit", "vial", "frasco", "table", "compri", "pz", "pieza"]
        if any(tok in u for tok in tokens_discretos):
            return True
        return True  # por defecto, discreta
    
    def _ml_a_unidad(self, value_ml: float, unidad: str) -> float:
        u = (unidad or "").strip().lower()
        if "ml" in u or "cc" in u:
            return value_ml
        if u.startswith("l"):              # l, litro, litros
            return value_ml / 1000.0
        if u.startswith("kg"):
            return value_ml / 1_000_000.0  # solo si asumís densidad≈1
        if u.startswith("g"):
            return value_ml / 1000.0       # idem nota densidad
        return value_ml                    # fallback
    
    def _unidad_a_ml(self, value: float, unidad: str) -> float:
        u = (unidad or "").strip().lower()
        if "ml" in u or "cc" in u:
            return value
        if u.startswith("l"):
            return value * 1000.0
        # lo demás solo si asumís densidad≈1
        if u.startswith("kg"):
            return value * 1_000_000.0
        if u.startswith("g"):
            return value * 1000.0
        return value
    # ================== DATOS BÁSICOS ==================
    def ui_tab_basicos(self):
        layout = QFormLayout(self.tab_basicos)
        self.txt_nombre = QLineEdit(); layout.addRow("Nombre:", self.txt_nombre)
        self.txt_apellido = QLineEdit(); layout.addRow("Apellido:", self.txt_apellido)
        self.txt_ci = QLineEdit(); layout.addRow("CI / Pasaporte:", self.txt_ci)
        self.txt_tipo_doc = QComboBox(); self.txt_tipo_doc.addItems(["CI", "Pasaporte", "Otro"])
        layout.addRow("Tipo Documento:", self.txt_tipo_doc)
        self.date_nac = QDateEdit(calendarPopup=True); layout.addRow("Fecha de Nacimiento:", self.date_nac)
        self.txt_sexo = QComboBox(); self.txt_sexo.addItems(["Masculino", "Femenino", "Otro"])
        layout.addRow("Sexo:", self.txt_sexo)
        self.txt_telefono = QLineEdit(); layout.addRow("Teléfono:", self.txt_telefono)
        self.txt_email = QLineEdit(); layout.addRow("Email:", self.txt_email)
        self.txt_direccion = QLineEdit(); layout.addRow("Dirección:", self.txt_direccion)
        self.txt_ruc = QLineEdit(); layout.addRow("RUC (para facturación):", self.txt_ruc)
        self.txt_razon_social = QLineEdit(); layout.addRow("Razón Social (para facturación):", self.txt_razon_social)

        # Completar razón social con nombre+apellido al salir de apellido
        old_event_ap = self.txt_apellido.focusOutEvent
        def on_apellido_focus_out(ev):
            if not self.txt_razon_social.text().strip():
                nom = self.txt_nombre.text().strip()
                ape = self.txt_apellido.text().strip()
                if nom and ape:
                    self.txt_razon_social.setText(f"{nom} {ape}")
            old_event_ap(ev)
        self.txt_apellido.focusOutEvent = on_apellido_focus_out

        # Sugerencia rápida de RUC a partir del CI si es numérico
        old_event_ci = self.txt_ci.focusOutEvent
        def on_ci_focus_out(ev):
            if not self.txt_ruc.text().strip():
                ci = self.txt_ci.text().strip()
                if ci.isdigit():
                    self.txt_ruc.setText(f"{ci}-")
            old_event_ci(ev)
        self.txt_ci.focusOutEvent = on_ci_focus_out

        # Ubicación
        fila_ubi = QHBoxLayout()
        self.cbo_departamento = QComboBox(); self.cbo_departamento.setPlaceholderText("Departamento…")
        self.cbo_ciudad = QComboBox();       self.cbo_ciudad.setPlaceholderText("Ciudad…")
        self.cbo_barrio = QComboBox();       self.cbo_barrio.setPlaceholderText("Barrio…")
        fila_ubi.addWidget(self.cbo_departamento, 2)
        fila_ubi.addWidget(self.cbo_ciudad, 2)
        fila_ubi.addWidget(self.cbo_barrio, 2)
        layout.addRow(QLabel("Ubicación:"), QWidget())
        layout.addRow(fila_ubi)
        self.cbo_departamento.currentIndexChanged.connect(self._on_departamento_changed)
        self.cbo_ciudad.currentIndexChanged.connect(self._on_ciudad_changed)

        self.txt_observaciones = QTextEdit()
        layout.addRow("Observaciones:", self.txt_observaciones)
        if self.solo_control:
            self.txt_observaciones.setReadOnly(True)
            self.txt_observaciones.setVisible(False)

    def _validar_ubicacion(self) -> bool:
        if not hasattr(self, "cbo_barrio"):
            return True
        idbarrio = self.cbo_barrio.currentData()
        if not idbarrio:
            self.tabs.setCurrentWidget(self.tab_basicos)
            QMessageBox.warning(self, "Falta barrio", "Seleccioná Departamento, Ciudad y Barrio antes de guardar.")
            self.cbo_barrio.setFocus()
            return False
        return True

    def _cargar_departamentos(self, preselect_id=None):
        session = SessionLocal()
        try:
            self.cbo_departamento.blockSignals(True)
            self.cbo_departamento.clear()
            for d in session.query(Departamento).order_by(Departamento.nombre.asc()).all():
                self.cbo_departamento.addItem(d.nombre or "", d.iddepartamento)
            if preselect_id is not None:
                idx = self.cbo_departamento.findData(preselect_id)
                if idx >= 0:
                    self.cbo_departamento.setCurrentIndex(idx)
            else:
                self.cbo_departamento.setCurrentIndex(-1)
        finally:
            self.cbo_departamento.blockSignals(False)
            session.close()

    def _cargar_ciudades(self, iddepartamento, preselect_id=None):
        session = SessionLocal()
        try:
            self.cbo_ciudad.blockSignals(True)
            self.cbo_ciudad.clear()
            if iddepartamento:
                qs = (session.query(Ciudad)
                      .filter(Ciudad.iddepartamento == iddepartamento)
                      .order_by(Ciudad.nombre.asc()).all())
                for c in qs:
                    self.cbo_ciudad.addItem(c.nombre or "", c.idciudad)
            if preselect_id is not None:
                idx = self.cbo_ciudad.findData(preselect_id)
                if idx >= 0:
                    self.cbo_ciudad.setCurrentIndex(idx)
            else:
                self.cbo_ciudad.setCurrentIndex(-1)
        finally:
            self.cbo_ciudad.blockSignals(False)
            session.close()

    def _cargar_barrios(self, idciudad, preselect_id=None):
        session = SessionLocal()
        try:
            self.cbo_barrio.blockSignals(True)
            self.cbo_barrio.clear()
            if idciudad:
                qs = (session.query(Barrio)
                      .filter(Barrio.idciudad == idciudad)
                      .order_by(Barrio.nombre.asc()).all())
                for b in qs:
                    self.cbo_barrio.addItem(b.nombre or "", b.idbarrio)
            if preselect_id is not None:
                idx = self.cbo_barrio.findData(preselect_id)
                if idx >= 0:
                    self.cbo_barrio.setCurrentIndex(idx)
            else:
                self.cbo_barrio.setCurrentIndex(-1)
        finally:
            self.cbo_barrio.blockSignals(False)
            session.close()

    def _on_departamento_changed(self):
        dep_id = self.cbo_departamento.currentData()
        self._cargar_ciudades(dep_id)
        self.cbo_barrio.clear()

    def _on_ciudad_changed(self):
        ciu_id = self.cbo_ciudad.currentData()
        self._cargar_barrios(ciu_id)

    # ================== ENCARGADOS ==================
    def ui_tab_encargados(self):
        layout = QVBoxLayout(self.tab_encargados)
        self.table_encargados = QTableWidget(0, 5)
        self.table_encargados.setHorizontalHeaderLabels(["Nombre", "CI", "Edad", "Ocupación", "Teléfono"])
        self.table_encargados.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_encargados.setAlternatingRowColors(True)
        layout.addWidget(self.table_encargados)
        btn_agregar = QPushButton("Agregar Encargado")
        btn_agregar.clicked.connect(self.abrir_dialogo_encargado)
        layout.addWidget(btn_agregar)

    def abrir_dialogo_encargado(self):
        from controllers.abm_encargados import DialogoEncargado
        dlg = DialogoEncargado(self)
        if dlg.exec_():
            data = dlg.get_datos()
            encargado = Encargado(
                nombre=data["nombre"],
                ci=data["ci"],
                edad=data["edad"],
                ocupacion=data["ocupacion"],
                telefono=data["telefono"],
                observaciones=data["observaciones"]
            )
            self.session.add(encargado)
            self.session.commit()
            vinculo = PacienteEncargado(
                idpaciente=self.idpaciente,
                idencargado=encargado.idencargado,
                tipo=data.get("tipo", "Encargado")
            )
            self.session.add(vinculo)
            self.session.commit()
            self.cargar_encargados()
            QMessageBox.information(self, "Encargado agregado", "Encargado vinculado correctamente.")

    # ================== FAMILIARES ==================
    def ui_tab_fliares(self):
        layout = QFormLayout(self.tab_fliares)
        self.chk_aplica = QCheckBox("Aplica antecedentes familiares")
        self.chk_aplica.stateChanged.connect(self.toggle_campos_familiares)
        layout.addRow(self.chk_aplica)
        self.txt_patologia_padre = QLineEdit(); layout.addRow("Patologías Padre:", self.txt_patologia_padre)
        self.txt_patologia_madre = QLineEdit(); layout.addRow("Patologías Madre:", self.txt_patologia_madre)
        self.txt_patologia_hermanos = QLineEdit(); layout.addRow("Patologías Hermanos:", self.txt_patologia_hermanos)
        self.txt_patologia_hijos = QLineEdit(); layout.addRow("Patologías Hijos:", self.txt_patologia_hijos)
        self.txt_fliares_obs = QTextEdit(); layout.addRow("Observaciones:", self.txt_fliares_obs)

    def toggle_campos_familiares(self, _):
        enabled = self.chk_aplica.isChecked()
        for w in (self.txt_patologia_padre, self.txt_patologia_madre,
                  self.txt_patologia_hermanos, self.txt_patologia_hijos,
                  self.txt_fliares_obs):
            w.setEnabled(enabled)

    # ================== PATOLÓGICOS ==================
    def ui_tab_patologicos(self):
        layout = QVBoxLayout(self.tab_patologicos)
        grid = QGridLayout()
        items = [
            ("chk_cardiovasculares", "Cardiovasculares"),
            ("chk_respiratorios", "Respiratorios"),
            ("chk_alergicos", "Alérgicos"),
            ("chk_neoplasicos", "Neoplásicos"),
            ("chk_digestivos", "Digestivos"),
            ("chk_genitourinarios", "Genitourinarios"),
            ("chk_asmatico", "Asmático"),
            ("chk_metabolicos", "Metabólicos"),
            ("chk_osteoarticulares", "Osteoarticulares"),
            ("chk_neuropsiquiatricos", "Neuropsiquiátricos"),
            ("chk_internaciones", "Internaciones"),
            ("chk_cirugias", "Cirugías"),
            ("chk_psicologicos", "Psicológicos"),
            ("chk_audiovisuales", "Audiovisuales"),
            ("chk_transfusiones", "Transfusiones")
        ]
        for idx, (attr, label) in enumerate(items):
            chk = QCheckBox(label)
            setattr(self, attr, chk)
            fila = idx // 2
            col = idx % 2
            grid.addWidget(chk, fila, col)
        layout.addLayout(grid)
        self.txt_otros_patologicos = QTextEdit()
        layout.addWidget(QLabel("Otros:"))
        layout.addWidget(self.txt_otros_patologicos)

    # ================== CONTROLES ==================
    def ui_tab_enfactual(self):
        layout = QVBoxLayout(self.tab_enfactual)

        self.table_controles = QTableWidget(0, 14)
        self.table_controles.setHorizontalHeaderLabels([
            "Fecha", "Peso", "Altura", "Cintura", "OMB", "Bajo OMB", "P. Ideal",
            "Brazo Izq.", "Brazo Der.", "Pierna Izq.", "Pierna Der.", "Espalda",
            "Editar", "Eliminar"
        ])
        layout.addWidget(self.table_controles)
        self.table_controles.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_controles.setAlternatingRowColors(True)

        form_grid = QGridLayout()

        self.input_fecha = QDateEdit(calendarPopup=True); self.input_fecha.setDate(QDate.currentDate())
        self.input_peso = QLineEdit()
        self.input_altura = QLineEdit()
        self.input_cint = QLineEdit()
        self.input_omb = QLineEdit()
        self.input_bajo_omb = QLineEdit()
        self.input_pideal = QLineEdit()
        self.input_brazo_izq = QLineEdit()
        self.input_brazo_der = QLineEdit()
        self.input_pierna_izq = QLineEdit()
        self.input_pierna_der = QLineEdit()
        self.input_espalda = QLineEdit()

        for w in (
            self.input_peso, self.input_altura, self.input_cint, self.input_omb,
            self.input_bajo_omb, self.input_pideal, self.input_brazo_izq, self.input_brazo_der,
            self.input_pierna_izq, self.input_pierna_der, self.input_espalda
        ):
            w.setAlignment(Qt.AlignRight)

        dv = QDoubleValidator(0.0, 1000.0, 2, self)
        for w in (
            self.input_peso, self.input_altura, self.input_cint, self.input_omb,
            self.input_bajo_omb, self.input_pideal, self.input_brazo_izq, self.input_brazo_der,
            self.input_pierna_izq, self.input_pierna_der, self.input_espalda
        ):
            w.setValidator(dv)

        campos = [
            ("Fecha:", self.input_fecha),
            ("Peso:", self.input_peso),
            ("Altura:", self.input_altura),
            ("Cintura:", self.input_cint),
            ("OMB:", self.input_omb),
            ("Bajo OMB:", self.input_bajo_omb),
            ("P. Ideal:", self.input_pideal),
            ("Brazo Izq.:", self.input_brazo_izq),
            ("Brazo Der.:", self.input_brazo_der),
            ("Pierna Izq.:", self.input_pierna_izq),
            ("Pierna Der.:", self.input_pierna_der),
            ("Espalda:", self.input_espalda),
        ]
        for idx, (label, widget) in enumerate(campos):
            row = idx // 3
            col = (idx % 3) * 2
            form_grid.addWidget(QLabel(label), row, col)
            form_grid.addWidget(widget, row, col + 1)

        layout.addLayout(form_grid)

        self.btn_guardar_control = QPushButton("Agregar Control")
        self.btn_guardar_control.clicked.connect(self.agregar_o_editar_control)
        self.btn_cancelar_edicion = QPushButton("Cancelar")
        self.btn_cancelar_edicion.clicked.connect(self.cancelar_edicion_control)
        self.btn_cancelar_edicion.setVisible(False)

        hl = QHBoxLayout()
        hl.addWidget(self.btn_guardar_control)
        hl.addWidget(self.btn_cancelar_edicion)
        hl.addStretch()
        layout.addLayout(hl)
    
    def _on_proc_combo_changed(self, _idx):
        if not hasattr(self, "lbl_cantidad"):
            return
        iditem = self.proc_combo.currentData()
        if not iditem:
            self.lbl_cantidad.setText("Cantidad:")
            self.proc_cantidad.setSuffix("")
            self.proc_cantidad.setDecimals(0)
            self.proc_cantidad.setMinimum(1)
            self.proc_cantidad.setSingleStep(1)
            return

        # ¿tiene composición?
        tiene_comp = self.session.query(ItemComposicion).filter(
            ItemComposicion.iditem_padre == iditem
        ).first() is not None

        it = self.session.get(Item, iditem)
        unidad = (getattr(it, "unidad", "") or "").strip()
        es_discreta = self._unidad_es_discreta(unidad)

        if tiene_comp:
            # El volumen se interpreta en ml
            self.lbl_cantidad.setText("Volumen (ml):")
            self.proc_cantidad.setSuffix(" ml")
            self.proc_cantidad.setDecimals(2)
            self.proc_cantidad.setMinimum(0.01)
            self.proc_cantidad.setSingleStep(10)  # cómodo para volúmenes
        else:
            self.lbl_cantidad.setText("Cantidad:")
            # mostrar la unidad real del ítem cuando sea útil
            self.proc_cantidad.setSuffix(f" {unidad}" if unidad else "")
            self.proc_cantidad.setDecimals(0 if es_discreta else 2)
            self.proc_cantidad.setMinimum(1 if es_discreta else 0.01)
            self.proc_cantidad.setSingleStep(1 if es_discreta else 0.5)
        
    # ================== PROCEDIMIENTOS ==================
    def ui_tab_procedimientos(self):
        layout = QVBoxLayout(self.tab_procedimientos)

        self.table_procedimientos = QTableWidget(0, 5)
        self.table_procedimientos.setHorizontalHeaderLabels(
             ["Fecha", "Item", "Comentario", "Editar", "Eliminar"]
        )
        self.table_procedimientos.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_procedimientos.setAlternatingRowColors(True)
        layout.addWidget(self.table_procedimientos)

        form = QFormLayout()
        self.proc_fecha = QDateEdit(calendarPopup=True)
        self.proc_fecha.setDate(QDate.currentDate())

        self.proc_combo = QComboBox()
        self.proc_combo.clear()
        self.proc_combo.addItem("Seleccionar...", None)

        # Ítems de procedimiento/servicio + Ítems compuestos (tienen composición)
        subq_comp = (self.session.query(ItemComposicion.iditem_padre)
                    .distinct()
                    .subquery())

        q = (self.session.query(Item)
            .filter(
                Item.activo.is_(True),
                or_(
                    Item.uso_procedimiento.is_(True),
                    Item.categoria == 'USO_PROCEDIMIENTO',
                    func.lower(Item.tipo_producto).in_(['procedimiento', 'procedimientos', 'servicio']),
                    Item.iditem.in_(self.session.query(subq_comp.c.iditem_padre))  # <= compuestos
                )
            )
            .order_by(Item.nombre.asc()))

        for it in q.all():
            self.proc_combo.addItem(it.nombre, it.iditem)

        self._setup_contains_completer(self.proc_combo)
        
        self.proc_cantidad = QDoubleSpinBox()
        self.proc_cantidad.setDecimals(2)
        self.proc_cantidad.setMinimum(0.01)
        self.proc_cantidad.setMaximum(999999)
        self.proc_cantidad.setValue(1.00)

        self.proc_comentario = QLineEdit()
        form.addRow("Fecha:", self.proc_fecha)
        form.addRow("Item:", self.proc_combo)
        self.lbl_cantidad = QLabel("Cantidad:")
        form.addRow(self.lbl_cantidad, self.proc_cantidad)
        self.proc_combo.currentIndexChanged.connect(self._on_proc_combo_changed)
        self._on_proc_combo_changed(self.proc_combo.currentIndex())
        form.addRow("Comentario:", self.proc_comentario)
        layout.addLayout(form)

        hl = QHBoxLayout()
        self.btn_agregar_procedimiento = QPushButton("Agregar")
        self.btn_agregar_procedimiento.setIcon(QIcon("imagenes/agregar.png"))
        self.btn_agregar_procedimiento.clicked.connect(self.agregar_o_editar_procedimiento)
        hl.addWidget(self.btn_agregar_procedimiento)

        self.btn_cancelar_procedimiento = QPushButton("Cancelar")
        self.btn_cancelar_procedimiento.setVisible(False)
        self.btn_cancelar_procedimiento.clicked.connect(self.cancelar_edicion_procedimiento)
        hl.addWidget(self.btn_cancelar_procedimiento)
        hl.addStretch()
        layout.addLayout(hl)

    def ui_tab_historial(self):
        layout = QVBoxLayout(self.tab_historial)

        # ----- Filtros -----
        filtros = QHBoxLayout()
        self.his_desde = QDateEdit(calendarPopup=True); self.his_desde.setDisplayFormat("dd/MM/yy")
        self.his_hasta = QDateEdit(calendarPopup=True); self.his_hasta.setDisplayFormat("dd/MM/yy")
        self.his_desde.setDate(QDate.currentDate().addMonths(-3))
        self.his_hasta.setDate(QDate.currentDate())
        self.his_chk_anuladas = QCheckBox("Ver anuladas"); self.his_chk_anuladas.setChecked(True)
        self.btn_his_refrescar = QPushButton("Actualizar")

        filtros.addWidget(QLabel("Desde:")); filtros.addWidget(self.his_desde)
        filtros.addWidget(QLabel("Hasta:")); filtros.addWidget(self.his_hasta)
        filtros.addWidget(self.his_chk_anuladas)
        filtros.addStretch()
        filtros.addWidget(self.btn_his_refrescar)
        layout.addLayout(filtros)

        # ----- Tabla -----
        self.tblHistorial = QTableWidget(0, 8)
        self.tblHistorial.setHorizontalHeaderLabels(
        ["Fecha", "Tipo", "Ítem / Medio", "Cantidad", "Precio", "Subtotal", "Saldo", "Obs."]
        )
        self.tblHistorial.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tblHistorial.setAlternatingRowColors(True)
        self.tblHistorial.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tblHistorial.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tblHistorial.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tblHistorial.setSortingEnabled(True)
        layout.addWidget(self.tblHistorial)

        # ----- Totales -----
        self.lblHisTotales = QLabel("—")
        layout.addWidget(self.lblHisTotales)

        # eventos
        self.btn_his_refrescar.clicked.connect(self.cargar_historial_tab)

    def _set_hist_cell(self, row, col, text):
        self.tblHistorial.setItem(row, col, QTableWidgetItem("" if text is None else str(text)))

    def cargar_historial_tab(self):
        if not hasattr(self, "idpaciente") or not self.idpaciente:
            return

        # Filtros opcionales
        fecha_desde = self.his_desde.date().toPyDate() if self.his_desde.date() else None
        fecha_hasta = self.his_hasta.date().toPyDate() if self.his_hasta.date() else None
        incluir_anuladas = self.his_chk_anuladas.isChecked()

        # === Opción A: vista básica (procedimientos + ventas)
        # data = get_historial_paciente(self.session, self.idpaciente, fecha_desde, fecha_hasta, incluir_anuladas)

        # === Opción B: si creaste la vista que incluye COBROS ===
        # duplicamos el DAO aquí sin tocar tu archivo dao, solo cambiando el nombre de la vista:
        from sqlalchemy import text
        where_filtros = ["h.idpaciente = :idpaciente"]
        params = {"idpaciente": self.idpaciente}
        if fecha_desde:
            where_filtros.append("h.fecha >= :desde"); params["desde"] = fecha_desde
        if fecha_hasta:
            where_filtros.append("h.fecha <= :hasta"); params["hasta"] = fecha_hasta
        if not incluir_anuladas:
            where_filtros.append("(h.estado IS NULL OR UPPER(h.estado) <> 'ANULADO')")

        # 👉 Cambiá el nombre de la vista a la que “tiene cobros”.
        # Si la llamaste 'vw_historial_paciente' y YA incluye cobros, dejá igual.
        NOMBRE_VISTA = "vw_historial_paciente"

        sql = text(f"""
            SELECT h.fecha, h.tipo_evento, h.item_nombre, h.cantidad,
                h.precio_unitario, h.subtotal, h.saldo, h.observacion
            FROM {NOMBRE_VISTA} h
            WHERE {" AND ".join(where_filtros)}
            ORDER BY h.fecha ASC, h.tipo_evento ASC
        """)
        rows = self.session.execute(sql, params).mappings().all()
        data = [dict(r) for r in rows]

        # Poblado de la tabla
        with _painting_suspended(self.tblHistorial):
            self.tblHistorial.setRowCount(len(data))
            for r, row in enumerate(data):
                # Fecha (usa DateItem para ordenar por valor real)
                self.tblHistorial.setItem(r, 0, DateItem(row.get("fecha")))
                # Tipo / Ítem
                self._set_hist_cell(r, 1, row.get("tipo_evento") or "")
                self._set_hist_cell(r, 2, row.get("item_nombre") or "")
                # Cantidad
                self.tblHistorial.setItem(r, 3, NumericItem(row.get("cantidad")))
                # Monetarios
                self.tblHistorial.setItem(r, 4, MoneyItem(row.get("precio_unitario")))
                self.tblHistorial.setItem(r, 5, MoneyItem(row.get("subtotal")))
                self.tblHistorial.setItem(r, 6, MoneyItem(0 if row.get("saldo") is None else row.get("saldo")))
                # Obs
                self._set_hist_cell(r, 7, row.get("observacion") or "")
            self.tblHistorial.resizeColumnsToContents()
        
        # 👉 Orden inicial por fecha (columna 0), descendente
        self.tblHistorial.sortItems(0, Qt.DescendingOrder)

        # Totales (ventas/cobros/saldo) desde tabla venta
        resumen = get_resumen_financiero_paciente(self.session, self.idpaciente)
        self.lblHisTotales.setText(
            f"Ventas: {gs(resumen['total_ventas'])}    "
            f"Cobrado: {gs(resumen['total_cobrado'])}    "
            f"Saldo: {gs(resumen['saldo_pendiente'])}"
        )


    def agregar_o_editar_procedimiento(self):
        iditem = self.proc_combo.currentData()
        if not iditem:
            QMessageBox.warning(self, "Falta procedimiento", "Seleccioná un procedimiento.")
            return

        cantidad = float(self.proc_cantidad.value() or 0)
        if cantidad <= 0:
            QMessageBox.warning(self, "Cantidad inválida", "La cantidad debe ser mayor que cero.")
            return

        # 👉 si hay una transacción abierta por consultas previas, la cerramos
        if self.session.in_transaction():
            try:
                self.session.rollback()
            except Exception:
                pass

        try:
            if self.procedimiento_editando_id:
                # EDITAR
                proc = (self.session.query(Procedimiento)
                        .filter_by(id=self.procedimiento_editando_id).first())
                if not proc:
                    QMessageBox.warning(self, "Procedimiento", "No se encontró el procedimiento a editar.")
                    return

                proc.fecha = self.proc_fecha.date().toPyDate()
                proc.iditem = iditem
                proc.comentario = self.proc_comentario.text().strip()
                self.session.flush()

                # Actualizar movimiento de stock
                self.session.query(StockMovimiento).filter_by(
                    motivo='PROCEDIMIENTO', idorigen=proc.id
                ).delete(synchronize_session=False)

                self._crear_movimiento_procedimiento(proc, cantidad)

            else:
                # AGREGAR
                proc = Procedimiento(
                    idpaciente=self.idpaciente,
                    fecha=self.proc_fecha.date().toPyDate(),
                    iditem=iditem,
                    comentario=self.proc_comentario.text().strip()
                )
                self.session.add(proc)
                self.session.flush()  # para tener proc.id

                self._crear_movimiento_procedimiento(proc, cantidad)

                # Recordatorio automático opcional
                item = self.session.get(Item, iditem)
                if item and getattr(item, "requiere_recordatorio", None) and getattr(item, "dias_recordatorio", None):
                    from datetime import timedelta
                    fecha_recordatorio = proc.fecha + timedelta(days=item.dias_recordatorio)
                    mensaje = (getattr(item, "mensaje_recordatorio", None) or f"Control de {item.nombre}")
                    rec = RecordatorioPaciente(
                        idpaciente=self.idpaciente,
                        idprocedimiento=proc.id,
                        fecha_recordatorio=fecha_recordatorio,
                        mensaje=mensaje
                    )
                    self.session.add(rec)

            self.session.commit()

            self.cancelar_edicion_procedimiento()
            self.cargar_todo()
            self.cargar_recordatorios()
            QMessageBox.information(self, "Procedimiento", "Guardado correctamente.")

        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"Ocurrió un error guardando el procedimiento:\n{e}")


    def _crear_movimiento_procedimiento(self, proc, cantidad) -> bool:
            """
            Si el ítem del procedimiento es 'compuesto' (tiene composición en ItemComposicion),
            explota la mezcla y descuenta stock de sus componentes en proporción a 'cantidad' (ml).
            Si no es compuesto, mantiene el comportamiento anterior (un movimiento por el ítem).
            Además, registra el detalle en la tabla intermedia 'procedimiento_item' para trazabilidad.
            """
            # 1) Ítem principal del procedimiento
            it_padre = self.session.get(Item, proc.iditem)
            if not it_padre:
                QMessageBox.warning(self, "Stock", "No se encontró el ítem del procedimiento.")
                return False

            # 2) Traer la composición (si existe)
            compos = (self.session.query(ItemComposicion)
                    .filter(ItemComposicion.iditem_padre == proc.iditem)
                    .all())

            # === CASO NO COMPUESTO: comportamiento original ===
            if not compos:
                cant_mov = cantidad
                if self._unidad_es_discreta(it_padre.unidad or ""):
                    cant_mov = math.ceil(cantidad - 1e-9)
                mov = StockMovimiento(
                    fecha=proc.fecha, iditem=proc.iditem, cantidad=cant_mov,
                    tipo='EGRESO', motivo='PROCEDIMIENTO', idorigen=proc.id,
                    observacion=f"Proc #{proc.id} - {it_padre.nombre}"
                )
                self.session.add(mov)
                return True

            # === CASO COMPUESTO ===
            # Interpretamos 'cantidad' como VOLUMEN (ml) del ítem compuesto (p. ej., KLEIN 1700 ml)
            try:
                volumen_ml = float(cantidad or 0)
            except Exception:
                volumen_ml = 0.0
            if volumen_ml <= 0:
                QMessageBox.warning(self, "Cantidad inválida", "El volumen (ml) debe ser mayor que cero.")
                return False

            # Antes de insertar nada, borro el detalle anterior del procedimiento (si lo hubiera)
            # Esto es especialmente útil al EDITAR un procedimiento existente
            self.session.execute(
                procedimiento_item.delete().where(
                    procedimiento_item.c.idprocedimiento == proc.id
                )
            )

            # 3) Pre-calcular consumos por componente y validar stock
            consumo_componentes = []  # [(insumo_item, consumo_final, consumo_calc, ratio_por_ml), ...]
            faltantes = []

            for comp in compos:
                # Compat: el id del componente puede llamarse iditem_insumo, iditem o iditem_hijo según tu modelo
                comp_id = getattr(comp, "iditem_insumo", None)
                if comp_id is None:
                    comp_id = getattr(comp, "iditem", None)
                if comp_id is None:
                    comp_id = getattr(comp, "iditem_hijo", None)
                if comp_id is None:
                    continue

                insumo = self.session.get(Item, comp_id)
                if not insumo:
                    continue

                # 'cantidad' en ItemComposicion es "por 1 litro" del padre (Opción B)
                ratio_por_litro = float(getattr(comp, "cantidad", 0.0) or 0.0)

                # Convertir ratio por litro → por ml y multiplicar por volumen (ml)
                consumo_calc = (ratio_por_litro / 1000.0) * volumen_ml   # consumo teórico en ml

                # Convertir ese consumo (ml) a la UNIDAD del insumo antes de validar/descontar
                unidad = (insumo.unidad or "").strip().lower()
                consumo_en_unidad = self._ml_a_unidad(consumo_calc, unidad)

                # Redondeo según unidad (discreta vs fraccionable)
                consumo_final = float(consumo_en_unidad)  # sin redondeo

                if consumo_final <= 0:
                    continue

                # Stock disponible del insumo (INGRESO - EGRESO)
                disp = (self.session.query(
                            func.coalesce(func.sum(
                                case(
                                    (StockMovimiento.tipo == 'INGRESO', StockMovimiento.cantidad),
                                    else_=-StockMovimiento.cantidad
                                )
                            ), 0)
                        )
                        .filter(StockMovimiento.iditem == insumo.iditem)
                        .scalar() or 0)

                stock_actual = float(disp)
                faltante = max(0.0, float(consumo_final) - stock_actual)  # sin redondeo
                if faltante > 0:
                    faltantes.append(
                        f"• {insumo.nombre}: falta {faltante:.3f} {insumo.unidad or ''} "
                        f"(necesita {consumo_final}, hay {stock_actual})"
                )

                consumo_componentes.append((insumo, consumo_final, consumo_calc, ratio_por_litro))

            if faltantes:
                QMessageBox.warning(
                    self,
                    "Stock insuficiente",
                    "No hay stock suficiente para:\n" + "\n".join(faltantes)
                )
                return False

            # 4) Insertar movimientos (EGRESO por componente) y detalle procedimiento_item
            for insumo, consumo_final, consumo_calc, ratio_por_litro in consumo_componentes:
                mov = StockMovimiento(
                    fecha=proc.fecha,
                    iditem=insumo.iditem,
                    cantidad=consumo_final,
                    tipo='EGRESO',
                    motivo='PROCEDIMIENTO',
                    idorigen=proc.id,
                    observacion=f"Proc #{proc.id} - {it_padre.nombre} -> {insumo.nombre}"
                )
                self.session.add(mov)

                # Detalle en la tabla intermedia para trazabilidad
                self.session.execute(
                    procedimiento_item.insert().values(
                        idprocedimiento=proc.id,
                        iditem=insumo.iditem,
                        cantidad=consumo_final
                    )
                )

            # (Opcional) Dejar snapshot en el comentario
            # proc.comentario = (proc.comentario or "") + f" | Expl: {volumen_ml} ml"

            return True

    def cargar_procedimiento_en_form(self, proc):
        self.procedimiento_editando_id = proc.id
        self.proc_fecha.setDate(QDate(proc.fecha.year, proc.fecha.month, proc.fecha.day))
        idx = self.proc_combo.findData(proc.iditem)
        self.proc_combo.blockSignals(True)
        self.proc_combo.setCurrentIndex(idx if idx != -1 else 0)
        self.proc_combo.blockSignals(False)
        self._on_proc_combo_changed(self.proc_combo.currentIndex())
        self.proc_comentario.setText(proc.comentario or "")

        # ¿Es compuesto? (tiene ItemComposicion)
        compos = (self.session.query(ItemComposicion)
                .filter(ItemComposicion.iditem_padre == proc.iditem)
                .all())

        if not compos:
            # === comportamiento original: tomar el último movimiento de stock del proc ===
            try:
                mov = (self.session.query(StockMovimiento)
                    .filter_by(motivo='PROCEDIMIENTO', idorigen=proc.id)
                    .order_by(StockMovimiento.idmovimiento.desc())
                    .first())
                if mov and mov.cantidad is not None:
                    self.proc_cantidad.setValue(float(mov.cantidad))
                else:
                    self.proc_cantidad.setValue(1.00)
            except Exception:
                self.proc_cantidad.setValue(1.00)
            self.btn_agregar_procedimiento.setText("Guardar cambios")
            self.btn_cancelar_procedimiento.setVisible(True)
            return

        # === Reconstruir VOL (ml) para compuestos ===
        # Buscamos un componente "ancla" con unidad líquida (ml/cc/l) y ratio significativo
        def _is_liquida(unidad: str) -> bool:
            u = (unidad or "").lower()
            return any(tok in u for tok in ["ml", "cc", "l", "litro"])

        # Elegir el mejor ancla
        ancla = None
        for comp in compos:
            comp_id = getattr(comp, "iditem_insumo", None)
            if comp_id is None:
                comp_id = getattr(comp, "iditem", None)
            if comp_id is None:
                comp_id = getattr(comp, "iditem_hijo", None)
            if comp_id is None:
                continue

            insumo = self.session.get(Item, comp_id)
            if insumo and _is_liquida(insumo.unidad or "") and float(getattr(comp, "cantidad", 0) or 0) > 0:
                ratio_actual = float(getattr(comp, "cantidad", 0) or 0)
                # preferí el que tenga ratio más cercano a 1.0
                if not ancla:
                    ancla = (insumo, ratio_actual)
                else:
                    if abs(ratio_actual - 1.0) < abs(ancla[1] - 1.0):
                        ancla = (insumo, ratio_actual)

        volumen_rec = None
        if ancla:
            insumo_ancla, ratio_ancla = ancla
            mov = (self.session.query(StockMovimiento)
                .filter_by(motivo='PROCEDIMIENTO', idorigen=proc.id, iditem=insumo_ancla.iditem)
                .order_by(StockMovimiento.idmovimiento.desc())
                .first())
            if mov and mov.cantidad is not None and ratio_ancla > 0:
                try:
                    cons_ml = self._unidad_a_ml(float(mov.cantidad), insumo_ancla.unidad or "")
                    volumen_rec = (cons_ml * 1000.0) / float(ratio_ancla)  # por litro → por ml
                except Exception:
                    volumen_rec = None

        # Si no hubo suerte con el ancla, probá con cualquier componente
        if volumen_rec is None:
            mov_any = (self.session.query(StockMovimiento)
                    .filter_by(motivo='PROCEDIMIENTO', idorigen=proc.id)
                    .order_by(StockMovimiento.idmovimiento.desc())
                    .first())
            if mov_any:
                # buscar su ratio en la composición (compat: iditem_insumo / iditem / iditem_hijo)
                ratio = None
                for comp in compos:
                    comp_id = getattr(comp, "iditem_insumo", None)
                    if comp_id is None:
                        comp_id = getattr(comp, "iditem", None)
                    if comp_id is None:
                        comp_id = getattr(comp, "iditem_hijo", None)
                    if comp_id == mov_any.iditem:
                        ratio = float(getattr(comp, "cantidad", 0) or 0)
                        break
                if ratio and ratio > 0:
                    try:
                        volumen_rec = float(mov_any.cantidad) / float(ratio)
                    except Exception:
                        volumen_rec = None

        # Setear el spin
        try:
            self.proc_cantidad.setValue(float(volumen_rec) if volumen_rec else 1.00)
        except Exception:
            self.proc_cantidad.setValue(1.00)

        self.btn_agregar_procedimiento.setText("Guardar cambios")
        self.btn_cancelar_procedimiento.setVisible(True)

    def cancelar_edicion_procedimiento(self):
        self.procedimiento_editando_id = None
        self.proc_fecha.setDate(QDate.currentDate())
        self.proc_combo.setCurrentIndex(0)
        self.proc_cantidad.setValue(1.00)
        self.proc_comentario.clear()
        self.btn_agregar_procedimiento.setText("Agregar")
        self.btn_cancelar_procedimiento.setVisible(False)

    def eliminar_procedimiento(self, idproc):
        from sqlalchemy.exc import IntegrityError

        if self.solo_control and not self.acciones_proc_en_solo:
            return

        reply = QMessageBox.question(self, "Confirmar", "¿Eliminar procedimiento?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No:
            return

        proc = self.session.query(Procedimiento).filter_by(id=idproc).first()
        if proc:
            try:
                # borrar movimientos asociados
                self.session.query(StockMovimiento).filter_by(
                    motivo='PROCEDIMIENTO', idorigen=proc.id
                ).delete(synchronize_session=False)
                self.session.execute(
                    procedimiento_item.delete().where(procedimiento_item.c.idprocedimiento == proc.id)
                )
                self.session.delete(proc)
                self.session.commit()
                self.cargar_todo()
            except IntegrityError:
                self.session.rollback()
                QMessageBox.warning(
                    self, "No se puede eliminar",
                    "No se puede eliminar el procedimiento porque tiene recordatorios asociados.\n"
                    "Elimine primero los recordatorios."
                )
            except Exception as e:
                self.session.rollback()
                QMessageBox.critical(self, "Error inesperado", f"Ocurrió un error inesperado:\n{str(e)}")
   
    # ================== CONTROLES (CRUD) ==================
    def agregar_o_editar_control(self):
        if self.control_editando_id:
            ctrl = self.session.query(AntecedenteEnfermedadActual).filter_by(id=self.control_editando_id).first()
            if ctrl:
                ctrl.fecha = self.input_fecha.date().toPyDate()
                ctrl.peso = convertir_vacio_a_none(self.input_peso.text())
                ctrl.altura = convertir_vacio_a_none(self.input_altura.text())
                ctrl.cint = self.input_cint.text().strip() or None
                ctrl.omb = self.input_omb.text().strip() or None
                ctrl.bajo_omb = self.input_bajo_omb.text().strip() or None
                ctrl.p_ideal = self.input_pideal.text().strip() or None
                ctrl.brazo_izquierdo = convertir_vacio_a_none(self.input_brazo_izq.text())
                ctrl.brazo_derecho = convertir_vacio_a_none(self.input_brazo_der.text())
                ctrl.pierna_izquierda = convertir_vacio_a_none(self.input_pierna_izq.text())
                ctrl.pierna_derecha = convertir_vacio_a_none(self.input_pierna_der.text())
                ctrl.espalda = convertir_vacio_a_none(self.input_espalda.text())
                self.session.commit()
        else:
            ctrl = AntecedenteEnfermedadActual(
                idpaciente=self.idpaciente,
                fecha=self.input_fecha.date().toPyDate(),
                peso=convertir_vacio_a_none(self.input_peso.text()),
                altura=convertir_vacio_a_none(self.input_altura.text()),
                cint=self.input_cint.text().strip() or None,
                omb=self.input_omb.text().strip() or None,
                bajo_omb=self.input_bajo_omb.text().strip() or None,
                p_ideal=self.input_pideal.text().strip() or None,
                brazo_izquierdo=convertir_vacio_a_none(self.input_brazo_izq.text()),
                brazo_derecho=convertir_vacio_a_none(self.input_brazo_der.text()),
                pierna_izquierda=convertir_vacio_a_none(self.input_pierna_izq.text()),
                pierna_derecha=convertir_vacio_a_none(self.input_pierna_der.text()),
                espalda=convertir_vacio_a_none(self.input_espalda.text()),
            )
            self.session.add(ctrl)
            self.session.commit()
        self.cancelar_edicion_control()
        self.cargar_todo()
        QMessageBox.information(self, "Listo", "Control guardado correctamente.")

    def cargar_control_en_form(self, ctrl):
        self.control_editando_id = ctrl.id
        self.input_fecha.setDate(QDate(ctrl.fecha.year, ctrl.fecha.month, ctrl.fecha.day))
        self.input_peso.setText(str(ctrl.peso or ""))
        self.input_altura.setText(str(ctrl.altura or ""))
        self.input_cint.setText(str(ctrl.cint or ""))
        self.input_omb.setText(str(ctrl.omb or ""))
        self.input_bajo_omb.setText(str(ctrl.bajo_omb or ""))
        self.input_pideal.setText(str(ctrl.p_ideal or ""))
        self.input_brazo_izq.setText(str(ctrl.brazo_izquierdo or ""))
        self.input_brazo_der.setText(str(ctrl.brazo_derecho or ""))
        self.input_pierna_izq.setText(str(ctrl.pierna_izquierda or ""))
        self.input_pierna_der.setText(str(ctrl.pierna_derecha or ""))
        self.input_espalda.setText(str(ctrl.espalda or ""))
        self.btn_guardar_control.setText("Guardar Cambios")
        self.btn_cancelar_edicion.setVisible(True)

    def cancelar_edicion_control(self):
        self.control_editando_id = None
        self.input_fecha.setDate(QDate.currentDate())
        for w in (self.input_peso, self.input_altura, self.input_cint, self.input_omb,
                  self.input_bajo_omb, self.input_pideal, self.input_brazo_izq, self.input_brazo_der,
                  self.input_pierna_izq, self.input_pierna_der, self.input_espalda):
            w.clear()
        self.btn_guardar_control.setText("Agregar Control")
        self.btn_cancelar_edicion.setVisible(False)

    # ================== INDICACIONES ==================
    def ui_tab_recetas(self):
        layout = QVBoxLayout(self.tab_recetas)

        self.table_recetas = QTableWidget(0, 8)
        self.table_recetas.setHorizontalHeaderLabels(
            ["Fecha", "Profesional", "Medicamento", "Dosis", "Frecuencia (h)", "Duración (d)", "Editar", "Eliminar"]
        )
        self.table_recetas.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_recetas.setAlternatingRowColors(True)
        layout.addWidget(self.table_recetas)

        form = QFormLayout()
        self.receta_fecha = QDateEdit(calendarPopup=True)
        self.receta_fecha.setDate(QDate.currentDate())

        # PROFESIONAL
        self.receta_profesional = QComboBox()
        self.receta_profesional.clear()
        self.receta_profesional.addItem("Seleccionar...", None)
        profesionales = (self.session.query(Profesional)
                         .filter_by(estado=True)
                         .order_by(Profesional.apellido, Profesional.nombre)
                         .all())
        for prof in profesionales:
            nombre = f"{prof.apellido}, {prof.nombre}"
            self.receta_profesional.addItem(nombre, prof.idprofesional)

        # MEDICAMENTO -> Item (tipo_insumo == 'medicamento')
        self.receta_medicamento = QComboBox()
        self.receta_medicamento.clear()
        self.receta_medicamento.addItem("Seleccionar...", None)

        items_meds = (self.session.query(Item)
                      .filter(
                          Item.activo.is_(True),
                          func.lower(Item.tipo_insumo) == 'medicamento'
                      )
                      .order_by(Item.nombre.asc())
                      .all())
        for it in items_meds:
            self.receta_medicamento.addItem(it.nombre, it.iditem)
        self._setup_contains_completer(self.receta_medicamento)

        self.receta_dosis = QLineEdit()
        self.receta_frecuencia = QSpinBox(); self.receta_frecuencia.setRange(1, 24); self.receta_frecuencia.setValue(8)
        self.receta_duracion = QSpinBox();   self.receta_duracion.setRange(1, 60);  self.receta_duracion.setValue(7)
        self.receta_hora_inicio = QTimeEdit(); self.receta_hora_inicio.setTime(QTime.currentTime())
        self.receta_recordatorio = QCheckBox("Recordatorio activo")
        self.receta_obs = QTextEdit()

        form.addRow("Fecha:", self.receta_fecha)
        form.addRow("Profesional:", self.receta_profesional)
        form.addRow("Medicamento:", self.receta_medicamento)
        form.addRow("Dosis:", self.receta_dosis)
        form.addRow("Frecuencia (horas):", self.receta_frecuencia)
        form.addRow("Duración (días):", self.receta_duracion)
        form.addRow("Hora de inicio:", self.receta_hora_inicio)
        form.addRow(self.receta_recordatorio)
        form.addRow("Observaciones:", self.receta_obs)
        layout.addLayout(form)

        hl = QHBoxLayout()
        self.btn_agregar_receta = QPushButton("Agregar")
        self.btn_agregar_receta.setIcon(QIcon("imagenes/agregar.png"))
        self.btn_agregar_receta.clicked.connect(self.agregar_o_editar_indicacion)
        hl.addWidget(self.btn_agregar_receta)

        self.btn_cancelar_receta = QPushButton("Cancelar")
        self.btn_cancelar_receta.setVisible(False)
        self.btn_cancelar_receta.clicked.connect(self.cancelar_edicion_receta)
        hl.addWidget(self.btn_cancelar_receta)
        hl.addStretch()
        layout.addLayout(hl)

    def ui_tab_recordatorios(self):
        layout = QVBoxLayout(self.tab_recordatorios)
        self.table_recordatorios = QTableWidget(0, 6)
        self.table_recordatorios.setHorizontalHeaderLabels(["Fecha", "Mensaje", "Estado", "Editar", "Realizado", "Eliminar"])
        self.table_recordatorios.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_recordatorios.setAlternatingRowColors(True)
        layout.addWidget(self.table_recordatorios)

    def cargar_recordatorios(self):
        with _painting_suspended(self.table_recordatorios):
            recs = (
                self.session.query(RecordatorioPaciente)
                .filter(
                    RecordatorioPaciente.idpaciente == self.idpaciente,
                    RecordatorioPaciente.estado.in_(["pendiente", "realizado"])
                )
                .order_by(RecordatorioPaciente.fecha_recordatorio.desc())
                .all()
            )

            tbl = self.table_recordatorios
            tbl.setRowCount(len(recs))

            for i, r in enumerate(recs):
                try:
                    dt = r.fecha_recordatorio
                    txt_fecha = dt.strftime("%d/%m/%Y %H:%M") if hasattr(dt, "hour") else dt.strftime("%d/%m/%Y")
                except Exception:
                    txt_fecha = str(r.fecha_recordatorio)

                tbl.setItem(i, 0, QTableWidgetItem(txt_fecha))
                tbl.setItem(i, 1, QTableWidgetItem(r.mensaje or ""))

                item_estado = QTableWidgetItem(r.estado or "")
                if r.estado == "realizado":
                    item_estado.setBackground(QColor("#b6fcb6"))
                tbl.setItem(i, 2, item_estado)

                btn_editar = QPushButton("Editar")
                btn_editar.setIconSize(QSize(16, 16))
                btn_editar.setFlat(True)
                btn_editar.clicked.connect(lambda _, rid=r.id: self.editar_recordatorio(rid))
                tbl.setCellWidget(i, 3, btn_editar)

                btn_realizado = QPushButton("Realizado")
                btn_realizado.setStyleSheet("color: green; font-weight: bold")
                btn_realizado.setEnabled(r.estado != "realizado")
                btn_realizado.clicked.connect(lambda _, rid=r.id: self.marcar_recordatorio_realizado(rid))
                tbl.setCellWidget(i, 4, btn_realizado)

                btn_eliminar = QPushButton("Eliminar")
                btn_eliminar.setStyleSheet("color: red")
                btn_eliminar.clicked.connect(lambda _, rid=r.id: self.eliminar_recordatorio(rid))
                tbl.setCellWidget(i, 5, btn_eliminar)

            tbl.resizeColumnsToContents()

    def editar_recordatorio(self, rid):
        from PyQt5.QtWidgets import QInputDialog
        rec = self.session.query(RecordatorioPaciente).filter_by(id=rid).first()
        if not rec:
            return
        nuevo_msg, ok = QInputDialog.getText(self, "Editar recordatorio", "Mensaje:", text=rec.mensaje or "")
        if ok:
            rec.mensaje = (nuevo_msg or "").strip()
            self.session.commit()
            self.cargar_recordatorios()

    def marcar_recordatorio_realizado(self, rid):
        rec = self.session.query(RecordatorioPaciente).filter_by(id=rid).first()
        if rec:
            rec.estado = "realizado"
            self.session.commit()
            QMessageBox.information(self, "Recordatorio", "Marcado como realizado.")
            self.cargar_recordatorios()

    def eliminar_recordatorio(self, rid):
        rec = self.session.query(RecordatorioPaciente).filter_by(id=rid).first()
        if rec:
            self.session.delete(rec)
            self.session.commit()
            self.cargar_recordatorios()

    # ================== INDICACIONES (CRUD) ==================
    def cargar_indicaciones(self):
        with _painting_suspended(self.table_recetas):
            indicaciones = (
                self.session.query(Indicacion)
                .filter_by(idpaciente=self.idpaciente, tipo='MEDICAMENTO')
                .order_by(Indicacion.fecha.desc())
                .all()
            )

            tbl = self.table_recetas
            rows = len(indicaciones)
            tbl.setRowCount(rows)

            prof_cache = {}
            item_cache = {}

            for i, ind in enumerate(indicaciones):
                tbl.setItem(i, 0, DateItem(ind.fecha))
                # Profesional
                pid = ind.idprofesional
                if pid not in prof_cache:
                    prof = self.session.query(Profesional).filter_by(idprofesional=pid).first() if pid else None
                    prof_cache[pid] = (f"{getattr(prof,'nombre','')} {getattr(prof,'apellido','')}".strip() or "-") if prof else "-"
                tbl.setItem(i, 1, QTableWidgetItem(prof_cache.get(pid, "-")))

                # Medicamento (Item)
                iid = ind.iditem
                if iid not in item_cache:
                    it = self.session.get(Item, iid) if iid else None
                    item_cache[iid] = it.nombre if it else "-"
                tbl.setItem(i, 2, QTableWidgetItem(item_cache.get(iid, "-")))

                tbl.setItem(i, 3, QTableWidgetItem(ind.dosis or ""))
                tbl.setItem(i, 4, QTableWidgetItem(str(ind.frecuencia_horas or "")))
                tbl.setItem(i, 5, QTableWidgetItem(str(ind.duracion_dias or "")))

                # Acciones (ocultas en solo_control)
                if not self.solo_control:
                    btn_editar = QPushButton()
                    btn_editar.setIcon(QIcon("imagenes/editar.png"))
                    btn_editar.setIconSize(QSize(24, 24))
                    btn_editar.setFlat(True)
                    btn_editar.clicked.connect(partial(self.cargar_indicacion_en_form, ind))
                    tbl.setCellWidget(i, 6, btn_editar)

                    btn_eliminar = QPushButton()
                    btn_eliminar.setIcon(QIcon("imagenes/eliminar.png"))
                    btn_eliminar.setIconSize(QSize(24, 24))
                    btn_eliminar.setFlat(True)
                    btn_eliminar.clicked.connect(partial(self.eliminar_indicacion, ind.idindicacion))
                    tbl.setCellWidget(i, 7, btn_eliminar)
                else:
                    tbl.setCellWidget(i, 6, QWidget())
                    tbl.setCellWidget(i, 7, QWidget())

            tbl.resizeColumnsToContents()

    def cargar_indicacion_en_form(self, ind):
        if self.solo_control:
            return
        self.receta_editando_id = ind.idindicacion

        # Fecha
        self.receta_fecha.setDate(QDate(ind.fecha.year, ind.fecha.month, ind.fecha.day))

        # Profesional
        idx_prof = self.receta_profesional.findData(ind.idprofesional)
        self.receta_profesional.setCurrentIndex(idx_prof if idx_prof != -1 else 0)

        # Medicamento (Item)
        idx_item = self.receta_medicamento.findData(ind.iditem)
        self.receta_medicamento.setCurrentIndex(idx_item if idx_item != -1 else 0)

        self.receta_dosis.setText(ind.dosis or "")
        self.receta_frecuencia.setValue(ind.frecuencia_horas or 8)
        self.receta_duracion.setValue(ind.duracion_dias or 7)

        try:
            if ind.hora_inicio:
                if hasattr(ind.hora_inicio, "hour"):
                    h, m, s = ind.hora_inicio.hour, ind.hora_inicio.minute, getattr(ind.hora_inicio, "second", 0)
                else:
                    parts = str(ind.hora_inicio).split(":")
                    h, m = int(parts[0]), int(parts[1]); s = int(parts[2]) if len(parts) > 2 else 0
                self.receta_hora_inicio.setTime(QTime(h, m, s))
            else:
                self.receta_hora_inicio.setTime(QTime.currentTime())
        except Exception:
            self.receta_hora_inicio.setTime(QTime.currentTime())

        self.receta_recordatorio.setChecked(bool(ind.recordatorio_activo))
        self.receta_obs.setPlainText(ind.observaciones or "")

        self.btn_agregar_receta.setText("Guardar Cambios")
        self.btn_cancelar_receta.setVisible(True)

    def cancelar_edicion_receta(self):
        self.receta_editando_id = None
        self.receta_fecha.setDate(QDate.currentDate())
        self.receta_profesional.setCurrentIndex(0)
        self.receta_medicamento.setCurrentIndex(0)
        self.receta_dosis.clear()
        self.receta_frecuencia.setValue(8)
        self.receta_duracion.setValue(7)
        self.receta_hora_inicio.setTime(QTime.currentTime())
        self.receta_recordatorio.setChecked(False)
        self.receta_obs.clear()
        self.btn_agregar_receta.setText("Agregar")
        self.btn_cancelar_receta.setVisible(False)

    def eliminar_indicacion(self, idindicacion):
        if self.solo_control:
            return
        reply = QMessageBox.question(self, "Confirmar", "¿Eliminar indicación y sus recordatorios?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No:
            return
        indicacion = self.session.query(Indicacion).filter_by(idindicacion=idindicacion).first()
        if indicacion:
            eliminar_recordatorios_de_indicacion(self.session, indicacion.idindicacion)
            self.session.delete(indicacion)
            self.session.commit()
            self.cargar_indicaciones()
            self.cargar_recordatorios()

    def agregar_o_editar_indicacion(self):
      

        idprof = self.receta_profesional.currentData()
        iditem = self.receta_medicamento.currentData()

        if not idprof:
            QMessageBox.warning(self, "Falta profesional", "Seleccioná un profesional.")
            return
        if not iditem:
            QMessageBox.warning(self, "Falta medicamento", "Seleccioná un medicamento.")
            return

        try:
            if self.receta_editando_id:
                indicacion = self.session.query(Indicacion).filter_by(idindicacion=self.receta_editando_id).first()
                if not indicacion:
                    QMessageBox.warning(self, "Indicacion", "No se encontró la indicación a editar.")
                    return
            else:
                indicacion = Indicacion(idpaciente=self.idpaciente, tipo='MEDICAMENTO')
                self.session.add(indicacion)

            # Asignar campos
            indicacion.fecha = self.receta_fecha.date().toPyDate()
            indicacion.idprofesional = idprof
            indicacion.iditem = iditem                  # ← clave del cambio
            indicacion.dosis = self.receta_dosis.text().strip()
            indicacion.frecuencia_horas = self.receta_frecuencia.value()
            indicacion.duracion_dias = self.receta_duracion.value()
            indicacion.hora_inicio = self.receta_hora_inicio.time().toPyTime()
            indicacion.recordatorio_activo = self.receta_recordatorio.isChecked()
            indicacion.observaciones = self.receta_obs.toPlainText().strip()

            # Validación de tu módulo
            errores = validar_indicacion_medicamento(indicacion)
            if errores:
                self.session.rollback()
                QMessageBox.warning(self, "Faltan datos", "\n".join(errores))
                return

            self.session.flush()

            eliminar_recordatorios_de_indicacion(self.session, indicacion.idindicacion)
            if indicacion.recordatorio_activo:
                generar_recordatorios_medicamento(self.session, indicacion)

            self.session.commit()

            self.cargar_indicaciones()
            self.cancelar_edicion_receta()
            self.cargar_recordatorios()
            QMessageBox.information(self, "Indicacion", "Guardado correctamente.")

        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"Ocurrió un error guardando la indicación:\n{e}")

    # ================== CARGAS GENERALES ==================
    def cargar_todo(self):
        paciente = (
            self.session.query(Paciente)
            .options(
                joinedload(Paciente.antecedentes_patologicos_personales),
                joinedload(Paciente.antecedentes_enfermedad_actual),
                joinedload(Paciente.antecedentes_familiares),
                joinedload(Paciente.encargados),
                joinedload(Paciente.indicaciones),
                joinedload(Paciente.procedimientos),
                joinedload(Paciente.barrio).joinedload(Barrio.ciudad).joinedload(Ciudad.departamento),
            )
            .filter_by(idpaciente=self.idpaciente).first()
        )
        self.paciente_db = paciente
        
        # ---------- Procedimientos ----------
        if hasattr(self, "table_procedimientos"):
            with _painting_suspended(self.table_procedimientos):
                self.table_procedimientos.setRowCount(0)  # ← volver a limpiar
                can_edit_proc = (not self.solo_control) or self.acciones_proc_en_solo
                self.table_procedimientos.setColumnHidden(3, not can_edit_proc)
                self.table_procedimientos.setColumnHidden(4, not can_edit_proc)
                for proc in (getattr(paciente, "procedimientos", []) or []):
                    row = self.table_procedimientos.rowCount()
                    self.table_procedimientos.insertRow(row)

                    # usar DateItem aquí
                    self.table_procedimientos.setItem(row, 0, DateItem(proc.fecha))

                    it = self.session.get(Item, proc.iditem)
                    nombre_proc = it.nombre if it else "-"
                    self.table_procedimientos.setItem(row, 1, QTableWidgetItem(nombre_proc))
                    self.table_procedimientos.setItem(row, 2, QTableWidgetItem(proc.comentario or ""))

                    if can_edit_proc:
                        # Editar
                        btn_e = QPushButton(); btn_e.setIcon(QIcon("imagenes/editar.png"))
                        btn_e.setIconSize(QSize(24, 24)); btn_e.setFlat(True)
                        btn_e.clicked.connect(partial(self.cargar_procedimiento_en_form, proc))
                        self.table_procedimientos.setCellWidget(row, 3, btn_e)

                        # Eliminar
                        btn_d = QPushButton(); btn_d.setIcon(QIcon("imagenes/eliminar.png"))
                        btn_d.setIconSize(QSize(24, 24)); btn_d.setFlat(True)
                        btn_d.clicked.connect(partial(self.eliminar_procedimiento, proc.id))
                        self.table_procedimientos.setCellWidget(row, 4, btn_d)

                self.table_procedimientos.resizeColumnsToContents()

        # Si no hay paciente, limpiar y salir
        if not paciente:
            for tname in ("table_controles", "table_encargados"):
                if hasattr(self, tname):
                    getattr(self, tname).setRowCount(0)
            if hasattr(self, "cargar_recordatorios"):
                self.cargar_recordatorios()
            if hasattr(self, "cargar_indicaciones"):
                self.cargar_indicaciones()
            return

        # ---------- Datos básicos ----------
        self.txt_nombre.setText(paciente.nombre or "")
        self.txt_apellido.setText(paciente.apellido or "")
        self.txt_ci.setText(paciente.ci_pasaporte or "")
        self.txt_tipo_doc.setCurrentText(paciente.tipo_documento or "CI")
        if getattr(paciente, "fechanacimiento", None):
            self.date_nac.setDate(QDate(paciente.fechanacimiento.year, paciente.fechanacimiento.month, paciente.fechanacimiento.day))
        self.txt_sexo.setCurrentText(paciente.sexo or "Masculino")
        self.txt_telefono.setText(paciente.telefono or "")
        self.txt_email.setText(paciente.email or "")
        self.txt_direccion.setText(paciente.direccion or "")
        self.txt_ruc.setText(paciente.ruc or "")
        self.txt_razon_social.setText(paciente.razon_social or "")
        self.txt_observaciones.setPlainText(paciente.observaciones or "")

        if hasattr(self, "cbo_departamento"):
            dep_id = ciu_id = bar_id = None
            if paciente.barrio and paciente.barrio.ciudad:
                bar_id = paciente.barrio.idbarrio
                ciu_id = paciente.barrio.ciudad.idciudad
                if paciente.barrio.ciudad.departamento:
                    dep_id = paciente.barrio.ciudad.departamento.iddepartamento
            self._cargar_departamentos(preselect_id=dep_id)
            if dep_id:
                self._cargar_ciudades(dep_id, preselect_id=ciu_id)
            else:
                self.cbo_ciudad.clear(); self.cbo_barrio.clear()
            if ciu_id:
                self._cargar_barrios(ciu_id, preselect_id=bar_id)

        # ---------- Encargados ----------
        if hasattr(self, "table_encargados"):
            with _painting_suspended(self.table_encargados):
                self.table_encargados.setRowCount(0)
                for enc_rel in (paciente.encargados or []):
                    encargado = enc_rel.encargado
                    row = self.table_encargados.rowCount()
                    self.table_encargados.insertRow(row)
                    self.table_encargados.setItem(row, 0, QTableWidgetItem(getattr(encargado, "nombre", "") or ""))
                    self.table_encargados.setItem(row, 1, QTableWidgetItem(getattr(encargado, "ci", "") or ""))
                    self.table_encargados.setItem(row, 2, QTableWidgetItem(str(getattr(encargado, "edad", "") or "")))
                    self.table_encargados.setItem(row, 3, QTableWidgetItem(getattr(encargado, "ocupacion", "") or ""))
                    self.table_encargados.setItem(row, 4, QTableWidgetItem(getattr(encargado, "telefono", "") or ""))
                self.table_encargados.resizeColumnsToContents()

        # ---------- Antecedentes familiares ----------
        if paciente.antecedentes_familiares:
            af = paciente.antecedentes_familiares[0]
            self.chk_aplica.setChecked(bool(af.aplica))
            self.txt_patologia_padre.setText(af.patologia_padre or "")
            self.txt_patologia_madre.setText(af.patologia_madre or "")
            self.txt_patologia_hermanos.setText(af.patologia_hermanos or "")
            self.txt_patologia_hijos.setText(af.patologia_hijos or "")
            self.txt_fliares_obs.setPlainText(af.observaciones or "")

        # ---------- Patológicos personales ----------
        if paciente.antecedentes_patologicos_personales:
            ap = paciente.antecedentes_patologicos_personales[0]
            self.chk_cardiovasculares.setChecked(bool(ap.cardiovasculares))
            self.chk_respiratorios.setChecked(bool(ap.respiratorios))
            self.chk_alergicos.setChecked(bool(ap.alergicos))
            self.chk_neoplasicos.setChecked(bool(ap.neoplasicos))
            self.chk_digestivos.setChecked(bool(ap.digestivos))
            self.chk_genitourinarios.setChecked(bool(ap.genitourinarios))
            self.chk_asmatico.setChecked(bool(ap.asmatico))
            self.chk_metabolicos.setChecked(bool(ap.metabolicos))
            self.chk_osteoarticulares.setChecked(bool(ap.osteoarticulares))
            self.chk_neuropsiquiatricos.setChecked(bool(ap.neuropsiquiatricos))
            self.chk_internaciones.setChecked(bool(ap.internaciones))
            self.chk_cirugias.setChecked(bool(ap.cirugias))
            self.chk_psicologicos.setChecked(bool(ap.psicologicos))
            self.chk_audiovisuales.setChecked(bool(ap.audiovisuales))
            self.chk_transfusiones.setChecked(bool(ap.transfusiones))
            self.txt_otros_patologicos.setPlainText(ap.otros or "")

        # ---------- Controles ----------
        if hasattr(self, "table_controles"):
            with _painting_suspended(self.table_controles):
                self.table_controles.setRowCount(0)  # ← volver a limpiar

                can_edit_ctrl = not self.solo_control
                self.table_controles.setColumnHidden(12, not can_edit_ctrl)
                self.table_controles.setColumnHidden(13, not can_edit_ctrl)

                for ctrl in (paciente.antecedentes_enfermedad_actual or []):
                    row = self.table_controles.rowCount()
                    self.table_controles.insertRow(row)

                    # usar DateItem aquí
                    self.table_controles.setItem(row, 0, DateItem(ctrl.fecha))
                    self.table_controles.setItem(row, 1,  NumericItem(ctrl.peso))
                    self.table_controles.setItem(row, 2,  NumericItem(ctrl.altura))
                    self.table_controles.setItem(row, 3,  NumericItem(ctrl.cint))
                    self.table_controles.setItem(row, 4,  NumericItem(ctrl.omb))
                    self.table_controles.setItem(row, 5,  NumericItem(ctrl.bajo_omb))
                    self.table_controles.setItem(row, 6,  NumericItem(ctrl.p_ideal))
                    self.table_controles.setItem(row, 7,  NumericItem(ctrl.brazo_izquierdo))
                    self.table_controles.setItem(row, 8,  NumericItem(ctrl.brazo_derecho))
                    self.table_controles.setItem(row, 9,  NumericItem(ctrl.pierna_izquierda))
                    self.table_controles.setItem(row, 10, NumericItem(ctrl.pierna_derecha))
                    self.table_controles.setItem(row, 11, NumericItem(ctrl.espalda))

                    if can_edit_ctrl:
                        btn_editar = QPushButton(); btn_editar.setIcon(QIcon("imagenes/editar.png"))
                        btn_editar.setIconSize(QSize(24, 24)); btn_editar.setFlat(True)
                        btn_editar.clicked.connect(partial(self.cargar_control_en_form, ctrl))
                        self.table_controles.setCellWidget(row, 12, btn_editar)

                        btn_eliminar = QPushButton(); btn_eliminar.setIcon(QIcon("imagenes/eliminar.png"))
                        btn_eliminar.setIconSize(QSize(24, 24)); btn_eliminar.setFlat(True)
                        btn_eliminar.clicked.connect(partial(self.eliminar_control, ctrl.id))
                        self.table_controles.setCellWidget(row, 13, btn_eliminar)

                self.table_controles.resizeColumnsToContents()
        if hasattr(self, "cargar_historial_tab"):
            self.cargar_historial_tab()
        # ---------- Pestañas dependientes ----------
        self.cargar_recordatorios()
        self.cargar_indicaciones()

    # ================== VARIOS ==================
    def cargar_encargados(self):
        with _painting_suspended(self.table_encargados):
            self.table_encargados.setRowCount(0)
            paciente = (self.session.query(Paciente)
                        .options(joinedload(Paciente.encargados)
                                 .joinedload(PacienteEncargado.encargado))
                        ).filter_by(idpaciente=self.idpaciente).first()
            if paciente:
                for rel in paciente.encargados:
                    enc = rel.encargado
                    r = self.table_encargados.rowCount()
                    self.table_encargados.insertRow(r)
                    self.table_encargados.setItem(r, 0, QTableWidgetItem(enc.nombre or ""))
                    self.table_encargados.setItem(r, 1, QTableWidgetItem(enc.ci or ""))
                    self.table_encargados.setItem(r, 2, QTableWidgetItem(str(enc.edad or "")))
                    self.table_encargados.setItem(r, 3, QTableWidgetItem(enc.ocupacion or ""))
                    self.table_encargados.setItem(r, 4, QTableWidgetItem(enc.telefono or ""))
            self.table_encargados.resizeColumnsToContents()

    def guardar_todo(self):
        # --- validaciones básicas ---
        nombre   = self.txt_nombre.text().strip()
        apellido = self.txt_apellido.text().strip()
        ci       = self.txt_ci.text().strip()

        if not nombre or not apellido or not ci:
            QMessageBox.warning(self, "Campos requeridos", "Nombre, Apellido y CI son obligatorios.")
            self.tabs.setCurrentWidget(self.tab_basicos)
            return

        # CI duplicado (excluyendo el propio id si es edición)
        existe = (self.session.query(Paciente)
                .filter(Paciente.ci_pasaporte == ci,
                        Paciente.idpaciente != (self.idpaciente or 0))
                .first())
        if existe:
            QMessageBox.warning(self, "Error", "Ya existe un paciente con ese número de CI/Pasaporte.")
            self.tabs.setCurrentWidget(self.tab_basicos)
            return

        # Ubicación obligatoria (idbarrio desde currentData)
        idbarrio = None
        if hasattr(self, "cbo_barrio"):
            idbarrio = self.cbo_barrio.currentData()
        if not idbarrio:
            self.tabs.setCurrentWidget(self.tab_basicos)
            QMessageBox.warning(self, "Falta barrio", "Seleccioná Departamento, Ciudad y Barrio antes de guardar.")
            return

        # Armar valores comunes
        fecha_nac = self.date_nac.date().toPyDate() if self.date_nac.date() else None
        valores_dict = dict(
            nombre=nombre,
            apellido=apellido,
            ci_pasaporte=ci,
            tipo_documento=self.txt_tipo_doc.currentText(),
            fechanacimiento=fecha_nac,
            sexo=self.txt_sexo.currentText(),
            telefono=self.txt_telefono.text().strip(),
            email=self.txt_email.text().strip(),
            direccion=self.txt_direccion.text().strip(),
            ruc=self.txt_ruc.text().strip(),
            razon_social=self.txt_razon_social.text().strip(),
            observaciones=self.txt_observaciones.toPlainText().strip(),
            idbarrio=idbarrio,
        )

        try:
            if not self.idpaciente:
                # ============== INSERT (nuevo paciente) ==============
                nuevo = Paciente(estado=True, **valores_dict)
                self.session.add(nuevo)
                self.session.flush()          # obtener nuevo.idpaciente
                self.idpaciente = nuevo.idpaciente

                # Crear contenedores mínimos si los usás luego
                af = AntecedenteFamiliar(idpaciente=self.idpaciente)
                ap = AntecedentePatologicoPersonal(idpaciente=self.idpaciente)
                self.session.add_all([af, ap])

            else:
                # ============== UPDATE (paciente existente) ==============
                pac = self.session.get(Paciente, self.idpaciente)
                if not pac:
                    QMessageBox.critical(self, "Error", "Paciente no encontrado para actualizar.")
                    return
                for k, v in valores_dict.items():
                    setattr(pac, k, v)

                # Familiares
                if not pac.antecedentes_familiares:
                    af = AntecedenteFamiliar(idpaciente=self.idpaciente)
                    self.session.add(af)
                else:
                    af = pac.antecedentes_familiares[0]
                af.aplica               = self.chk_aplica.isChecked()
                af.patologia_padre      = self.txt_patologia_padre.text().strip()
                af.patologia_madre      = self.txt_patologia_madre.text().strip()
                af.patologia_hermanos   = self.txt_patologia_hermanos.text().strip()
                af.patologia_hijos      = self.txt_patologia_hijos.text().strip()
                af.observaciones        = self.txt_fliares_obs.toPlainText().strip()

                # Patológicos personales
                if not pac.antecedentes_patologicos_personales:
                    ap = AntecedentePatologicoPersonal(idpaciente=self.idpaciente)
                    self.session.add(ap)
                else:
                    ap = pac.antecedentes_patologicos_personales[0]
                ap.cardiovasculares   = self.chk_cardiovasculares.isChecked()
                ap.respiratorios      = self.chk_respiratorios.isChecked()
                ap.alergicos          = self.chk_alergicos.isChecked()
                ap.neoplasicos        = self.chk_neoplasicos.isChecked()
                ap.digestivos         = self.chk_digestivos.isChecked()
                ap.genitourinarios    = self.chk_genitourinarios.isChecked()
                ap.asmatico           = self.chk_asmatico.isChecked()
                ap.metabolicos        = self.chk_metabolicos.isChecked()
                ap.osteoarticulares   = self.chk_osteoarticulares.isChecked()
                ap.neuropsiquiatricos = self.chk_neuropsiquiatricos.isChecked()
                ap.internaciones      = self.chk_internaciones.isChecked()
                ap.cirugias           = self.chk_cirugias.isChecked()
                ap.psicologicos       = self.chk_psicologicos.isChecked()
                ap.audiovisuales      = self.chk_audiovisuales.isChecked()
                ap.transfusiones      = self.chk_transfusiones.isChecked()
                ap.otros              = self.txt_otros_patologicos.toPlainText().strip()

            self.session.commit()
            QMessageBox.information(self, "Guardado", "Datos guardados correctamente.")
            self.accept()  # hace que el ABM refresque

        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"Ocurrió un error guardando el paciente:\n{e}")


    def closeEvent(self, event):
        self.session.close()
        event.accept()

    def eliminar_control(self, cid):
        if self.solo_control:
            return

        reply = QMessageBox.question(
            self, "Confirmar", "¿Eliminar control?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        ctrl = self.session.query(AntecedenteEnfermedadActual).filter_by(id=cid).first()
        if ctrl:
            self.session.delete(ctrl)
            self.session.commit()
            self.cargar_todo()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = FichaClinicaForm(idpaciente=1)
    dialog.show()
    sys.exit(app.exec_())
