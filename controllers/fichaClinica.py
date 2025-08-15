import sys
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QTabWidget, QWidget, QHBoxLayout,
    QFormLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QCheckBox,
    QDateEdit, QTableWidget, QTableWidgetItem, QComboBox, QGridLayout, QMessageBox,
    QSpinBox, QTimeEdit
)
from PyQt5.QtGui import QIcon,QColor
from PyQt5.QtCore import QDate, Qt, QSize,QTime
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from utils.db import SessionLocal
from models.paciente import Paciente
from models.antecPatologico import AntecedentePatologicoPersonal
from models.antecFliar import AntecedenteFamiliar
from models.antecEnfActual import AntecedenteEnfermedadActual
from models.encargado import Encargado
from models.pacienteEncargado import PacienteEncargado
from controllers.abm_encargados import DialogoEncargado
from functools import partial
from models.indicacion import Indicacion
from models.insumo import Insumo
from models.producto import Producto
from models.barrio import Barrio
from models.ciudad import Ciudad
from models.departamento import Departamento
from controllers.generador_recordatorios import (
    generar_recordatorios_medicamento,
    validar_indicacion_medicamento,
    eliminar_recordatorios_de_indicacion
)

def convertir_vacio_a_none(valor):
    valor = valor.strip()
    try:
        return float(valor) if valor else None
    except ValueError:
        return None

class FichaClinicaForm(QDialog):
    def __init__(self, idpaciente, parent=None, solo_control=False):
        super().__init__(parent)
        self.setWindowTitle("Ficha Clínica del Paciente")
        self.setMinimumWidth(1100)
        self.idpaciente = idpaciente
        self.solo_control = solo_control
        self.session = SessionLocal()
        self.control_editando_id = None
        self.init_ui()
        self.cargar_todo()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # Creamos los widgets de cada tab
        self.tab_basicos = QWidget()
        self.ui_tab_basicos()
        self.tab_encargados = QWidget()
        self.ui_tab_encargados()
        self.tab_fliares = QWidget()
        self.ui_tab_fliares()
        self.tab_patologicos = QWidget()
        self.ui_tab_patologicos()
        self.tab_enfactual = QWidget()
        self.ui_tab_enfactual()
        self.tab_procedimientos = QWidget()
        self.ui_tab_procedimientos()
        self.tab_recetas = QWidget()
        self.ui_tab_recetas()
        self.tab_recordatorios = QWidget()
        self.ui_tab_recordatorios()
        
        if hasattr(self, "cbo_departamento"):
            self._cargar_departamentos()
        # SOLO agregamos los tabs acá, según el modo:
        if getattr(self, 'solo_control', False):
            self.tabs.addTab(self.tab_enfactual, "📈 Control de Estado")
            self.tabs.addTab(self.tab_procedimientos, "💉 Procedimientos")
            self.tabs.addTab(self.tab_recetas, "📋 Indicaciones")
            self.tabs.addTab(self.tab_recordatorios, "🔔 Recordatorios")
        else:
            self.tabs.addTab(self.tab_basicos, "🧑 Datos Personales")
            self.tabs.addTab(self.tab_encargados, "👤 Encargados")
            self.tabs.addTab(self.tab_fliares, "👪 Antecedentes Familiares")
            self.tabs.addTab(self.tab_patologicos, "🩺 Antecedentes Patológicos")
            self.tabs.addTab(self.tab_enfactual, "📈 Control de Estado")
            self.tabs.addTab(self.tab_procedimientos, "💉 Procedimientos")
            self.tabs.addTab(self.tab_recetas, "📋 Indicaciones/Recetas")
            self.tabs.addTab(self.tab_recordatorios, "🔔 Recordatorios")

        main_layout.addWidget(self.tabs)

        # El botón siempre se crea (lo ocultás si hace falta)
        self.btn_guardar = QPushButton("Guardar Cambios")
        self.btn_guardar.clicked.connect(self.guardar_todo)
        main_layout.addWidget(self.btn_guardar)

        if getattr(self, 'solo_control', False):
            self.btn_guardar.setVisible(False)
        else:
            self.btn_guardar.setVisible(True)


            main_layout.addWidget(self.tabs)
            if self.solo_control:
                while self.tabs.count() > 1:
                    self.tabs.removeTab(0)
                self.btn_guardar.setVisible(False)

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
                # --- Ubicación: Departamento / Ciudad / Barrio ---
        fila_ubi = QHBoxLayout()
        self.cbo_departamento = QComboBox(); self.cbo_departamento.setPlaceholderText("Departamento…")
        self.cbo_ciudad = QComboBox();       self.cbo_ciudad.setPlaceholderText("Ciudad…")
        self.cbo_barrio = QComboBox();       self.cbo_barrio.setPlaceholderText("Barrio…")

        fila_ubi.addWidget(self.cbo_departamento, 2)
        fila_ubi.addWidget(self.cbo_ciudad, 2)
        fila_ubi.addWidget(self.cbo_barrio, 2)
        layout.addRow(QLabel("Ubicación:"), QWidget())  # etiqueta alineada
        layout.addRow(fila_ubi)

        # Cascada
        self.cbo_departamento.currentIndexChanged.connect(self._on_departamento_changed)
        self.cbo_ciudad.currentIndexChanged.connect(self._on_ciudad_changed)

        self.txt_observaciones = QTextEdit(); layout.addRow("Observaciones:", self.txt_observaciones)

    def _validar_ubicacion(self) -> bool:
        """Barrio obligatorio."""
        if not hasattr(self, "cbo_barrio"):
            return True  # por si la pestaña no existe en este modo

        idbarrio = self.cbo_barrio.currentData()
        if not idbarrio:
            self.tabs.setCurrentWidget(self.tab_basicos)
            QMessageBox.warning(
                self, "Falta barrio",
                "Seleccioná Departamento, Ciudad y Barrio antes de guardar."
            )
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
                if idx >= 0: self.cbo_departamento.setCurrentIndex(idx)
            else:
                self.cbo_departamento.setCurrentIndex(-1)
        finally:
            self.cbo_departamento.blockSignals(False); session.close()

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
                if idx >= 0: self.cbo_ciudad.setCurrentIndex(idx)
            else:
                self.cbo_ciudad.setCurrentIndex(-1)
        finally:
            self.cbo_ciudad.blockSignals(False); session.close()

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
                if idx >= 0: self.cbo_barrio.setCurrentIndex(idx)
            else:
                self.cbo_barrio.setCurrentIndex(-1)
        finally:
            self.cbo_barrio.blockSignals(False); session.close()

    def _on_departamento_changed(self):
        dep_id = self.cbo_departamento.currentData()
        self._cargar_ciudades(dep_id)
        self.cbo_barrio.clear()

    def _on_ciudad_changed(self):
        ciu_id = self.cbo_ciudad.currentData()
        self._cargar_barrios(ciu_id)


    def ui_tab_encargados(self):
        layout = QVBoxLayout(self.tab_encargados)
        self.table_encargados = QTableWidget(0, 5)
        self.table_encargados.setHorizontalHeaderLabels(["Nombre", "CI", "Edad", "Ocupación", "Teléfono"])
        layout.addWidget(self.table_encargados)
        btn_agregar = QPushButton("Agregar Encargado")
        btn_agregar.clicked.connect(self.abrir_dialogo_encargado)
        layout.addWidget(btn_agregar)

    def abrir_dialogo_encargado(self):
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

    def toggle_campos_familiares(self, state):
        enabled = self.chk_aplica.isChecked()
        self.txt_patologia_padre.setEnabled(enabled)
        self.txt_patologia_madre.setEnabled(enabled)
        self.txt_patologia_hermanos.setEnabled(enabled)
        self.txt_patologia_hijos.setEnabled(enabled)
        self.txt_fliares_obs.setEnabled(enabled)

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

    def ui_tab_enfactual(self):
        layout = QVBoxLayout(self.tab_enfactual)
        self.table_controles = QTableWidget(0, 14)
        self.table_controles.setHorizontalHeaderLabels([
            "Fecha", "Peso", "Altura", "Cintura", "OMB", "Bajo OMB", "P. Ideal",
            "Brazo Izq.", "Brazo Der.", "Pierna Izq.", "Pierna Der.", "Espalda",
            "Editar", "Eliminar"
        ])
        layout.addWidget(self.table_controles)
        # Compactar en 3 columnas:
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
            form_grid.addWidget(widget, row, col+1)
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
 
        

    def cargar_todo(self):
        paciente = (self.session.query(Paciente)
            .options(
                joinedload(Paciente.antecedentes_patologicos_personales),
                joinedload(Paciente.antecedentes_enfermedad_actual),
                joinedload(Paciente.antecedentes_familiares),
                joinedload(Paciente.encargados),
                # opcional si existen relaciones:
                joinedload(Paciente.indicaciones),
                joinedload(Paciente.procedimientos),
                joinedload(Paciente.barrio).joinedload(Barrio.ciudad).joinedload(Ciudad.departamento),
            )
            .filter_by(idpaciente=self.idpaciente).first()
        )
        # Procedimientos
        if hasattr(self, "table_procedimientos"):
            self.table_procedimientos.setRowCount(0)
            for proc in getattr(paciente, "procedimientos", []):
                row = self.table_procedimientos.rowCount()
                self.table_procedimientos.insertRow(row)
                self.table_procedimientos.setItem(row, 0, QTableWidgetItem(str(proc.fecha)))

                # Mostrar nombre del procedimiento (producto)
                producto = self.session.query(Producto).filter_by(idproducto=proc.idproducto).first()
                nombre_proc = producto.nombre if producto else "-"
                self.table_procedimientos.setItem(row, 1, QTableWidgetItem(nombre_proc))

                self.table_procedimientos.setItem(row, 2, QTableWidgetItem(proc.comentario or ""))

                # Botón editar
                btn_e = QPushButton()
                btn_e.setIcon(QIcon("imagenes/editar.png"))
                btn_e.setIconSize(QSize(24, 24))
                btn_e.setFlat(True)
                btn_e.clicked.connect(partial(self.cargar_procedimiento_en_form, proc))
                self.table_procedimientos.setCellWidget(row, 3, btn_e)

                # Botón eliminar
                btn_d = QPushButton()
                btn_d.setIcon(QIcon("imagenes/eliminar.png"))
                btn_d.setIconSize(QSize(24, 24))
                btn_d.setFlat(True)
                btn_d.clicked.connect(partial(self.eliminar_procedimiento, proc.id))
                self.table_procedimientos.setCellWidget(row, 4, btn_d)
        if paciente:
            self.txt_nombre.setText(paciente.nombre)
            self.txt_apellido.setText(paciente.apellido)
            self.txt_ci.setText(paciente.ci_pasaporte)
            self.txt_tipo_doc.setCurrentText(paciente.tipo_documento or "CI")
            if paciente.fechanacimiento:
                self.date_nac.setDate(QDate(paciente.fechanacimiento.year, paciente.fechanacimiento.month, paciente.fechanacimiento.day))
            self.txt_sexo.setCurrentText(paciente.sexo or "Masculino")
            self.txt_telefono.setText(paciente.telefono or "")
            self.txt_email.setText(paciente.email or "")
            self.txt_direccion.setText(paciente.direccion or "")
            self.txt_observaciones.setText(paciente.observaciones or "")
            if hasattr(self, "cbo_departamento"):
                dep_id = ciu_id = bar_id = None
                if paciente and paciente.barrio and paciente.barrio.ciudad:
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
            self.table_encargados.setRowCount(0)
            for enc_rel in paciente.encargados:
                encargado = enc_rel.encargado
                row = self.table_encargados.rowCount()
                self.table_encargados.insertRow(row)
                self.table_encargados.setItem(row, 0, QTableWidgetItem(encargado.nombre))
                self.table_encargados.setItem(row, 1, QTableWidgetItem(encargado.ci))
                self.table_encargados.setItem(row, 2, QTableWidgetItem(str(encargado.edad or "")))
                self.table_encargados.setItem(row, 3, QTableWidgetItem(encargado.ocupacion or ""))
                self.table_encargados.setItem(row, 4, QTableWidgetItem(encargado.telefono or ""))
            if paciente.antecedentes_familiares:
                af = paciente.antecedentes_familiares[0]
                self.chk_aplica.setChecked(af.aplica)
                self.txt_patologia_padre.setText(af.patologia_padre or "")
                self.txt_patologia_madre.setText(af.patologia_madre or "")
                self.txt_patologia_hermanos.setText(af.patologia_hermanos or "")
                self.txt_patologia_hijos.setText(af.patologia_hijos or "")
                self.txt_fliares_obs.setText(af.observaciones or "")
            if paciente.antecedentes_patologicos_personales:
                ap = paciente.antecedentes_patologicos_personales[0]
                self.chk_cardiovasculares.setChecked(ap.cardiovasculares)
                self.chk_respiratorios.setChecked(ap.respiratorios)
                self.chk_alergicos.setChecked(ap.alergicos)
                self.chk_neoplasicos.setChecked(ap.neoplasicos)
                self.chk_digestivos.setChecked(ap.digestivos)
                self.chk_genitourinarios.setChecked(ap.genitourinarios)
                self.chk_asmatico.setChecked(ap.asmatico)
                self.chk_metabolicos.setChecked(ap.metabolicos)
                self.chk_osteoarticulares.setChecked(ap.osteoarticulares)
                self.chk_neuropsiquiatricos.setChecked(ap.neuropsiquiatricos)
                self.chk_internaciones.setChecked(ap.internaciones)
                self.chk_cirugias.setChecked(ap.cirugias)
                self.chk_psicologicos.setChecked(ap.psicologicos)
                self.chk_audiovisuales.setChecked(ap.audiovisuales)
                self.chk_transfusiones.setChecked(ap.transfusiones)
                self.txt_otros_patologicos.setText(ap.otros or "")
            self.table_controles.setRowCount(0)
            for ctrl in paciente.antecedentes_enfermedad_actual:
                row = self.table_controles.rowCount()
                self.table_controles.insertRow(row)
                self.table_controles.setItem(row, 0, QTableWidgetItem(str(ctrl.fecha)))
                self.table_controles.setItem(row, 1, QTableWidgetItem(str(ctrl.peso or "")))
                self.table_controles.setItem(row, 2, QTableWidgetItem(str(ctrl.altura or "")))
                self.table_controles.setItem(row, 3, QTableWidgetItem(str(ctrl.cint or "")))
                self.table_controles.setItem(row, 4, QTableWidgetItem(str(ctrl.omb or "")))
                self.table_controles.setItem(row, 5, QTableWidgetItem(str(ctrl.bajo_omb or "")))
                self.table_controles.setItem(row, 6, QTableWidgetItem(str(ctrl.p_ideal or "")))
                self.table_controles.setItem(row, 7, QTableWidgetItem(str(ctrl.brazo_izquierdo or "")))
                self.table_controles.setItem(row, 8, QTableWidgetItem(str(ctrl.brazo_derecho or "")))
                self.table_controles.setItem(row, 9, QTableWidgetItem(str(ctrl.pierna_izquierda or "")))
                self.table_controles.setItem(row,10, QTableWidgetItem(str(ctrl.pierna_derecha or "")))
                self.table_controles.setItem(row,11, QTableWidgetItem(str(ctrl.espalda or "")))
                btn_editar = QPushButton()
                btn_editar.setIcon(QIcon("imagenes/editar.png"))
                btn_editar.setIconSize(QSize(24, 24))
                btn_editar.setFlat(True)
                btn_editar.clicked.connect(partial(self.cargar_control_en_form, ctrl))
                self.table_controles.setCellWidget(row, 12, btn_editar)

                btn_eliminar = QPushButton()
                btn_eliminar.setIcon(QIcon("imagenes/eliminar.png"))
                btn_eliminar.setIconSize(QSize(24, 24))
                btn_eliminar.setFlat(True)
                btn_eliminar.clicked.connect(partial(self.eliminar_control, ctrl.id))
                self.table_controles.setCellWidget(row, 13, btn_eliminar)
        self.paciente_db = paciente
        self.cargar_recordatorios()
        self.cargar_indicaciones()
    
    def ui_tab_procedimientos(self):
        from models.producto import Producto
        from models.tipoproducto import TipoProducto

        layout = QVBoxLayout(self.tab_procedimientos)

        self.table_procedimientos = QTableWidget(0, 5)
        self.table_procedimientos.setHorizontalHeaderLabels(
            ["Fecha", "Procedimiento", "Comentario", "", ""]
        )
        layout.addWidget(self.table_procedimientos)

        form = QFormLayout()
        self.proc_fecha = QDateEdit(calendarPopup=True)
        self.proc_fecha.setDate(QDate.currentDate())

        # Combo de procedimientos (productos de tipo 'PROCEDIMIENTO')
        self.proc_combo = QComboBox()
        self.proc_combo.addItem("Seleccionar...", None)

        procedimientos = (
            self.session.query(Producto)
            .join(Producto.tipoproducto)
            .filter(func.lower(TipoProducto.nombre) == 'procedimientos')
            .order_by(Producto.nombre)
            .all()
        )
        for prod in procedimientos:
            self.proc_combo.addItem(prod.nombre, prod.idproducto)

        self.proc_comentario = QLineEdit()
        form.addRow("Fecha:", self.proc_fecha)
        form.addRow("Procedimiento:", self.proc_combo)
        form.addRow("Comentario:", self.proc_comentario)
        layout.addLayout(form)

        # Botones agregar/editar/cancelar
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
        self.procedimiento_editando_id = None


    def ui_tab_recetas(self):
        from models.profesional import Profesional
        from models.insumo import Insumo

        layout = QVBoxLayout(self.tab_recetas)

        # Grilla de indicaciones
        self.table_recetas = QTableWidget(0, 8)
        self.table_recetas.setHorizontalHeaderLabels([
            "Fecha", "Profesional", "Medicamento", "Dosis", "Frecuencia (h)", "Duración (d)", "Editar", "Eliminar"
        ])
        layout.addWidget(self.table_recetas)

        # Formulario para agregar/editar indicación
        form = QFormLayout()
        self.receta_fecha = QDateEdit(calendarPopup=True)
        self.receta_fecha.setDate(QDate.currentDate())

        # PROFESIONAL
        self.receta_profesional = QComboBox()
        self.receta_profesional.clear()
        self.receta_profesional.addItem("Seleccionar...", None)
        profesionales = self.session.query(Profesional).order_by(Profesional.apellido, Profesional.nombre).all()
        for prof in profesionales:
            nombre = f"{prof.apellido}, {prof.nombre}"
            self.receta_profesional.addItem(nombre, prof.idprofesional)

        # MEDICAMENTO (desde Insumo)
        self.receta_medicamento = QComboBox()
        self.receta_medicamento.clear()
        self.receta_medicamento.addItem("Seleccionar...", None)
        insumos = self.session.query(Insumo).filter(
            Insumo.categoria == 'USO_PROCEDIMIENTO'  # Cambia el filtro si corresponde a "MEDICAMENTO" según tu modelo
        ).order_by(Insumo.nombre).all()
        for insumo in insumos:
            self.receta_medicamento.addItem(insumo.nombre, insumo.idinsumo)

        self.receta_dosis = QLineEdit()
        self.receta_frecuencia = QSpinBox()
        self.receta_frecuencia.setMinimum(1)
        self.receta_frecuencia.setMaximum(24)
        self.receta_frecuencia.setValue(8)
        self.receta_duracion = QSpinBox()
        self.receta_duracion.setMinimum(1)
        self.receta_duracion.setMaximum(30)
        self.receta_duracion.setValue(7)
        self.receta_hora_inicio = QTimeEdit()
        self.receta_hora_inicio.setTime(QTime.currentTime())
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

        # Botones agregar/editar/cancelar
        hl = QHBoxLayout()
        self.btn_agregar_receta = QPushButton("Agregar")
        self.btn_agregar_receta.setIcon(QIcon("imagenes/agregar.png"))
        self.btn_agregar_receta.clicked.connect(self.agregar_o_editar_indicacion) # Función nueva
        hl.addWidget(self.btn_agregar_receta)

        self.btn_cancelar_receta = QPushButton("Cancelar")
        self.btn_cancelar_receta.setVisible(False)
        self.btn_cancelar_receta.clicked.connect(self.cancelar_edicion_receta)
        hl.addWidget(self.btn_cancelar_receta)
        hl.addStretch()
        layout.addLayout(hl)
        self.receta_editando_id = None

    def ui_tab_recordatorios(self):
        from PyQt5.QtWidgets import QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton
        from PyQt5.QtCore import QSize

        layout = QVBoxLayout(self.tab_recordatorios)
        self.table_recordatorios = QTableWidget(0, 6)
        self.table_recordatorios.setHorizontalHeaderLabels([
            "Fecha", "Mensaje", "Estado", "Editar", "Realizado", "Eliminar"
        ])
        layout.addWidget(self.table_recordatorios)
        

    def cargar_recordatorios(self):
        from models.recordatorio_paciente import RecordatorioPaciente
        self.table_recordatorios.setRowCount(0)
        recordatorios = (
            self.session.query(RecordatorioPaciente)
            .filter(
                RecordatorioPaciente.idpaciente == self.idpaciente,
                RecordatorioPaciente.estado == "pendiente"
            )
            .order_by(RecordatorioPaciente.fecha_recordatorio.desc())
            .all()
        )
        for i, r in enumerate(recordatorios):
            self.table_recordatorios.insertRow(i)

            # --- Fecha con hora (si hay) ---
            try:
                dt = r.fecha_recordatorio  # puede ser datetime o date
                txt_fecha = dt.strftime("%d/%m/%Y %H:%M") if hasattr(dt, "hour") else dt.strftime("%d/%m/%Y")
            except Exception:
                txt_fecha = str(r.fecha_recordatorio)
            self.table_recordatorios.setItem(i, 0, QTableWidgetItem(txt_fecha))
            # --------------------------------

            self.table_recordatorios.setItem(i, 1, QTableWidgetItem(r.mensaje or ""))

            item_estado = QTableWidgetItem(r.estado or "")
            if r.estado == "realizado":
                item_estado.setBackground(QColor("#b6fcb6"))
            self.table_recordatorios.setItem(i, 2, item_estado)

            # Botón editar (si querés)
            btn_editar = QPushButton("Editar")
            btn_editar.setIconSize(QSize(16, 16))
            btn_editar.setFlat(True)
            # btn_editar.clicked.connect(lambda _, rid=r.id: self.editar_recordatorio(rid))
            self.table_recordatorios.setCellWidget(i, 3, btn_editar)

            # Botón marcar realizado
            btn_realizado = QPushButton("Realizado")
            btn_realizado.setStyleSheet("color: green; font-weight: bold")
            btn_realizado.setEnabled(r.estado != "realizado")
            btn_realizado.clicked.connect(lambda _, rid=r.id: self.marcar_recordatorio_realizado(rid))
            self.table_recordatorios.setCellWidget(i, 4, btn_realizado)

            # Botón eliminar
            btn_eliminar = QPushButton("Eliminar")
            btn_eliminar.setStyleSheet("color: red")
            btn_eliminar.clicked.connect(lambda _, rid=r.id: self.eliminar_recordatorio(rid))
            self.table_recordatorios.setCellWidget(i, 5, btn_eliminar)


    def marcar_recordatorio_realizado(self, rid):
        from models.recordatorio_paciente import RecordatorioPaciente
        rec = self.session.query(RecordatorioPaciente).filter_by(id=rid).first()
        if rec:
            rec.estado = "realizado"
            self.session.commit()
            QMessageBox.information(self, "Recordatorio", "Marcado como realizado.")
            self.cargar_recordatorios()

    def eliminar_recordatorio(self, rid):
        from models.recordatorio_paciente import RecordatorioPaciente
        rec = self.session.query(RecordatorioPaciente).filter_by(id=rid).first()
        if rec:
            self.session.delete(rec)
            self.session.commit()
            self.cargar_recordatorios()

    def agregar_o_editar_procedimiento(self):
        from models.procedimiento import Procedimiento

        idproducto = self.proc_combo.currentData()
        if not idproducto:
            QMessageBox.warning(self, "Falta procedimiento", "Seleccioná un procedimiento.")
            return

        if self.procedimiento_editando_id:
            # Editar
            proc = self.session.query(Procedimiento).filter_by(id=self.procedimiento_editando_id).first()
            if proc:
                proc.fecha = self.proc_fecha.date().toPyDate()
                proc.idproducto = idproducto
                proc.comentario = self.proc_comentario.text().strip()
                self.session.commit()
        else:
            # Agregar nuevo
            proc = Procedimiento(
                idpaciente=self.idpaciente,
                fecha=self.proc_fecha.date().toPyDate(),
                idproducto=idproducto,
                comentario=self.proc_comentario.text().strip()
            )
            self.session.add(proc)
            self.session.commit()

            # --- Generar recordatorio automático si el producto lo requiere ---
            producto = self.session.query(Producto).get(idproducto)
            if producto and producto.requiere_recordatorio and producto.dias_recordatorio:
                from datetime import timedelta
                from models.recordatorio_paciente import RecordatorioPaciente
                fecha_recordatorio = proc.fecha + timedelta(days=producto.dias_recordatorio)
                mensaje = producto.mensaje_recordatorio or f"Control de {producto.nombre}"
                recordatorio = RecordatorioPaciente(
                    idpaciente=self.idpaciente,
                    idprocedimiento=proc.id,
                    fecha_recordatorio=fecha_recordatorio,
                    mensaje=mensaje
                )
                self.session.add(recordatorio)
                self.session.commit()

        self.cancelar_edicion_procedimiento()
        self.cargar_todo()
        self.cargar_recordatorios()
        QMessageBox.information(self, "Procedimiento", "Guardado correctamente.")


    def cargar_procedimiento_en_form(self, proc):
        self.procedimiento_editando_id = proc.id
        self.proc_fecha.setDate(QDate(proc.fecha.year, proc.fecha.month, proc.fecha.day))

        idx = self.proc_combo.findData(proc.idproducto)
        self.proc_combo.setCurrentIndex(idx if idx != -1 else 0)

        self.proc_comentario.setText(proc.comentario or "")
        self.btn_agregar_procedimiento.setText("Guardar cambios")
        self.btn_cancelar_procedimiento.setVisible(True)

    def cancelar_edicion_procedimiento(self):
        self.procedimiento_editando_id = None
        self.proc_fecha.setDate(QDate.currentDate())
        self.proc_combo.setCurrentIndex(0)
        self.proc_comentario.clear()
        self.btn_agregar_procedimiento.setText("Agregar")
        self.btn_cancelar_procedimiento.setVisible(False)
        
   
    def eliminar_procedimiento(self, idproc):
        from sqlalchemy.exc import IntegrityError
        reply = QMessageBox.question(self, "Confirmar", "¿Eliminar procedimiento?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No:
            return

        from models.procedimiento import Procedimiento
        proc = self.session.query(Procedimiento).filter_by(id=idproc).first()
        if proc:
            try:
                self.session.delete(proc)
                self.session.commit()
                self.cargar_todo()
            except IntegrityError:
                self.session.rollback()
                QMessageBox.warning(
                    self,
                    "No se puede eliminar",
                    "No se puede eliminar el procedimiento porque tiene recordatorios asociados.\n"
                    "Elimine primero los recordatorios."
                )
            except Exception as e:
                self.session.rollback()
                QMessageBox.critical(
                    self,
                    "Error inesperado",
                    f"Ocurrió un error inesperado:\n{str(e)}"
                )


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
        self.input_peso.clear()
        self.input_altura.clear()
        self.input_cint.clear()
        self.input_omb.clear()
        self.input_bajo_omb.clear()
        self.input_pideal.clear()
        self.input_brazo_izq.clear()
        self.input_brazo_der.clear()
        self.input_pierna_izq.clear()
        self.input_pierna_der.clear()
        self.input_espalda.clear()
        self.btn_guardar_control.setText("Agregar Control")
        self.btn_cancelar_edicion.setVisible(False)

    def eliminar_control(self, cid):
        reply = QMessageBox.question(self, "Confirmar", "¿Eliminar control?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No:
            return
        ctrl = self.session.query(AntecedenteEnfermedadActual).filter_by(id=cid).first()
        if ctrl:
            self.session.delete(ctrl)
            self.session.commit()
            self.cargar_todo()
   
    def cargar_receta_en_form(self, receta):
        self.receta_editando_id = receta.idreceta
        self.receta_fecha.setDate(QDate(receta.fecha.year, receta.fecha.month, receta.fecha.day))
        # Seleccionar el profesional correcto en el combo
        idx = self.receta_profesional.findData(receta.idprofesional)
        if idx != -1:
            self.receta_profesional.setCurrentIndex(idx)
        else:
            self.receta_profesional.setCurrentIndex(0)
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

    def cargar_indicacion_en_form(self, ind):
        self.receta_editando_id = ind.idindicacion
        self.receta_fecha.setDate(QDate(ind.fecha.year, ind.fecha.month, ind.fecha.day))

        idx_prof = self.receta_profesional.findData(ind.idprofesional)
        self.receta_profesional.setCurrentIndex(idx_prof if idx_prof != -1 else 0)

        idx_insumo = self.receta_medicamento.findData(ind.idinsumo)
        self.receta_medicamento.setCurrentIndex(idx_insumo if idx_insumo != -1 else 0)

        self.receta_dosis.setText(ind.dosis or "")
        self.receta_frecuencia.setValue(ind.frecuencia_horas or 8)
        self.receta_duracion.setValue(ind.duracion_dias or 7)

        # --- Conversión segura a QTime ---
        if ind.hora_inicio:
            try:
                # si es datetime.time
                h = getattr(ind.hora_inicio, 'hour', None)
                m = getattr(ind.hora_inicio, 'minute', None)
                s = getattr(ind.hora_inicio, 'second', 0)
                if h is not None and m is not None:
                    self.receta_hora_inicio.setTime(QTime(h, m, s))
                else:
                    # si viene como string "HH:MM[:SS]"
                    parts = str(ind.hora_inicio).split(':')
                    hh = int(parts[0]); mm = int(parts[1]); ss = int(parts[2]) if len(parts) > 2 else 0
                    self.receta_hora_inicio.setTime(QTime(hh, mm, ss))
            except Exception:
                self.receta_hora_inicio.setTime(QTime.currentTime())
        else:
            self.receta_hora_inicio.setTime(QTime.currentTime())
        # ----------------------------------

        self.receta_recordatorio.setChecked(ind.recordatorio_activo)
        self.receta_obs.setPlainText(ind.observaciones or "")
        self.btn_agregar_receta.setText("Guardar Cambios")
        self.btn_cancelar_receta.setVisible(True)

     

    def eliminar_indicacion(self, idindicacion):
        from models.indicacion import Indicacion
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
        from models.indicacion import Indicacion

        idprof = self.receta_profesional.currentData()
        idinsumo = self.receta_medicamento.currentData()

        if not idprof:
            QMessageBox.warning(self, "Falta profesional", "Seleccioná un profesional.")
            return
        if not idinsumo:
            QMessageBox.warning(self, "Falta medicamento", "Seleccioná un medicamento.")
            return

        # EDITAR
        if self.receta_editando_id:
            indicacion = self.session.query(Indicacion).filter_by(idindicacion=self.receta_editando_id).first()
            if indicacion:
                indicacion.fecha = self.receta_fecha.date().toPyDate()
                indicacion.idprofesional = idprof
                indicacion.idinsumo = idinsumo
                indicacion.dosis = self.receta_dosis.text().strip()
                indicacion.frecuencia_horas = self.receta_frecuencia.value()
                indicacion.duracion_dias = self.receta_duracion.value()
                indicacion.hora_inicio = self.receta_hora_inicio.time().toPyTime()
                indicacion.recordatorio_activo = self.receta_recordatorio.isChecked()
                indicacion.observaciones = self.receta_obs.toPlainText().strip()
        else:
            # NUEVA
            indicacion = Indicacion(
                fecha=self.receta_fecha.date().toPyDate(),
                idpaciente=self.idpaciente,
                idprofesional=idprof,
                tipo='MEDICAMENTO',
                idinsumo=idinsumo,
                dosis=self.receta_dosis.text().strip(),
                frecuencia_horas=self.receta_frecuencia.value(),
                duracion_dias=self.receta_duracion.value(),
                hora_inicio=self.receta_hora_inicio.time().toPyTime(),
                recordatorio_activo=self.receta_recordatorio.isChecked(),
                observaciones=self.receta_obs.toPlainText().strip()
            )
            self.session.add(indicacion)
        self.session.commit()

        # Validación de campos personalizados (si usás)
        errores = validar_indicacion_medicamento(indicacion)
        if errores:
            QMessageBox.warning(self, "Faltan datos", "\n".join(errores))
            return

        eliminar_recordatorios_de_indicacion(self.session, indicacion.idindicacion)
        if indicacion.recordatorio_activo:
            generar_recordatorios_medicamento(self.session, indicacion)

        self.cargar_indicaciones()
        self.cancelar_edicion_receta()
        self.cargar_recordatorios()
        QMessageBox.information(self, "Indicacion", "Guardado correctamente.")
    
    def cargar_indicaciones(self):
        from models.indicacion import Indicacion
        from models.profesional import Profesional
        from models.insumo import Insumo

        self.table_recetas.setRowCount(0)
        indicaciones = (
            self.session.query(Indicacion)
            .filter_by(idpaciente=self.idpaciente, tipo='MEDICAMENTO')
            .order_by(Indicacion.fecha.desc())
            .all()
        )
        for ind in indicaciones:
            row = self.table_recetas.rowCount()
            self.table_recetas.insertRow(row)
            # Fecha
            self.table_recetas.setItem(row, 0, QTableWidgetItem(str(ind.fecha)))
            # Profesional (buscamos el nombre)
            profesional = self.session.query(Profesional).filter_by(idprofesional=ind.idprofesional).first()
            nombre_prof = f"{profesional.nombre} {profesional.apellido}" if profesional else "-"
            self.table_recetas.setItem(row, 1, QTableWidgetItem(nombre_prof))
            # Medicamento (nombre de insumo)
            insumo = self.session.query(Insumo).filter_by(idinsumo=ind.idinsumo).first()
            nombre_insumo = insumo.nombre if insumo else "-"
            self.table_recetas.setItem(row, 2, QTableWidgetItem(nombre_insumo))
            # Dosis
            self.table_recetas.setItem(row, 3, QTableWidgetItem(ind.dosis or ""))
            # Frecuencia
            self.table_recetas.setItem(row, 4, QTableWidgetItem(str(ind.frecuencia_horas or "")))
            # Duración
            self.table_recetas.setItem(row, 5, QTableWidgetItem(str(ind.duracion_dias or "")))

            # Botón Editar
            btn_editar = QPushButton()
            btn_editar.setIcon(QIcon("imagenes/editar.png"))
            btn_editar.setIconSize(QSize(24, 24))
            btn_editar.setFlat(True)
            btn_editar.clicked.connect(partial(self.cargar_indicacion_en_form, ind))
            self.table_recetas.setCellWidget(row, 6, btn_editar)

            # Botón Eliminar
            btn_eliminar = QPushButton()
            btn_eliminar.setIcon(QIcon("imagenes/eliminar.png"))
            btn_eliminar.setIconSize(QSize(24, 24))
            btn_eliminar.setFlat(True)
            btn_eliminar.clicked.connect(partial(self.eliminar_indicacion, ind.idindicacion))
            self.table_recetas.setCellWidget(row, 7, btn_eliminar)


    def guardar_todo(self):
        ci_ingresado = self.txt_ci.text().strip()
        if ci_ingresado:
            # Buscar si ya existe ese CI en otro paciente (excepto este)
            paciente_existente = (
                self.session.query(Paciente)
                .filter(Paciente.ci_pasaporte == ci_ingresado)
                .filter(Paciente.idpaciente != self.idpaciente)
                .first()
            )
            if paciente_existente:
                QMessageBox.warning(self, "Error", "Ya existe un paciente con ese número de CI/Pasaporte.")
                return
        # Barrio obligatorio
        if not self._validar_ubicacion():
            return
        # ALTA O EDICIÓN
        if self.paciente_db is None:
            # ALTA
            p = Paciente()
            self.session.add(p)
            self.paciente_db = p  # por si necesitás después
            # Si tu modelo requiere idclinica, idusuario, u otros, ponelos aquí
        else:
            # EDICIÓN
            p = self.paciente_db

        # Ubicación: guardamos sólo el barrio (de ahí se deducen ciudad y departamento)
        if hasattr(self, "cbo_barrio"):
            idbarrio_sel = self.cbo_barrio.currentData()
            p.idbarrio = idbarrio_sel

        # Cargar los datos
        p.nombre = self.txt_nombre.text().strip()
        p.apellido = self.txt_apellido.text().strip()
        p.ci_pasaporte = self.txt_ci.text().strip()
        p.tipo_documento = self.txt_tipo_doc.currentText()
        p.fechanacimiento = self.date_nac.date().toPyDate()
        p.sexo = self.txt_sexo.currentText()
        p.telefono = self.txt_telefono.text().strip()
        p.email = self.txt_email.text().strip()
        p.direccion = self.txt_direccion.text().strip()
        p.observaciones = self.txt_observaciones.toPlainText().strip()

        # Familiares
        if p.antecedentes_familiares:
            af = p.antecedentes_familiares[0]
        else:
            af = AntecedenteFamiliar()
            self.session.add(af)
            p.antecedentes_familiares.append(af)  # Relación correcta
        af.aplica = self.chk_aplica.isChecked()
        af.patologia_padre = self.txt_patologia_padre.text().strip()
        af.patologia_madre = self.txt_patologia_madre.text().strip()
        af.patologia_hermanos = self.txt_patologia_hermanos.text().strip()
        af.patologia_hijos = self.txt_patologia_hijos.text().strip()
        af.observaciones = self.txt_fliares_obs.toPlainText().strip()

        # Patológicos personales
        if p.antecedentes_patologicos_personales:
            ap = p.antecedentes_patologicos_personales[0]
        else:
            ap = AntecedentePatologicoPersonal()
            self.session.add(ap)
            p.antecedentes_patologicos_personales.append(ap)  # Relación correcta
        ap.cardiovasculares = self.chk_cardiovasculares.isChecked()
        ap.respiratorios = self.chk_respiratorios.isChecked()
        ap.alergicos = self.chk_alergicos.isChecked()
        ap.neoplasicos = self.chk_neoplasicos.isChecked()
        ap.digestivos = self.chk_digestivos.isChecked()
        ap.genitourinarios = self.chk_genitourinarios.isChecked()
        ap.asmatico = self.chk_asmatico.isChecked()
        ap.metabolicos = self.chk_metabolicos.isChecked()
        ap.osteoarticulares = self.chk_osteoarticulares.isChecked()
        ap.neuropsiquiatricos = self.chk_neuropsiquiatricos.isChecked()
        ap.internaciones = self.chk_internaciones.isChecked()
        ap.cirugias = self.chk_cirugias.isChecked()
        ap.psicologicos = self.chk_psicologicos.isChecked()
        ap.audiovisuales = self.chk_audiovisuales.isChecked()
        ap.transfusiones = self.chk_transfusiones.isChecked()
        ap.otros = self.txt_otros_patologicos.toPlainText().strip()

        self.session.commit()
        QMessageBox.information(self, "Guardado", "Datos actualizados correctamente.")
        self.accept()


    def cargar_encargados(self):
        self.table_encargados.setRowCount(0)
        paciente = self.session.query(Paciente).options(
            joinedload(Paciente.encargados).joinedload(PacienteEncargado.encargado)
        ).filter_by(idpaciente=self.idpaciente).first()
        if paciente:
            for rel in paciente.encargados:
                encargado = rel.encargado
                row = self.table_encargados.rowCount()
                self.table_encargados.insertRow(row)
                self.table_encargados.setItem(row, 0, QTableWidgetItem(encargado.nombre or ""))
                self.table_encargados.setItem(row, 1, QTableWidgetItem(encargado.ci or ""))
                self.table_encargados.setItem(row, 2, QTableWidgetItem(str(encargado.edad or "")))
                self.table_encargados.setItem(row, 3, QTableWidgetItem(encargado.ocupacion or ""))
                self.table_encargados.setItem(row, 4, QTableWidgetItem(encargado.telefono or ""))

    def closeEvent(self, event):
        self.session.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = FichaClinicaForm(idpaciente=1)
    dialog.show()
    sys.exit(app.exec_())
