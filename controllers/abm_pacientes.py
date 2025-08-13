import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QMessageBox, QComboBox, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from utils.db import SessionLocal
from models.paciente import Paciente
from models.barrio import Barrio
from models.ciudad import Ciudad
from models.departamento import Departamento
from sqlalchemy.orm import joinedload

class PacienteForm(QMainWindow):
    def __init__(self, usuario_id):
        super().__init__()
        self.usuario_id = usuario_id
        self.setWindowTitle("Gestión de Pacientes")

        # Paginación
        self.page_size = 20
        self.current_page = 0

        # --- Layout principal ---
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 8, 12, 8)

        # --- Buscador arriba ---
        buscador_layout = QHBoxLayout()
        buscador_layout.addWidget(QLabel("Buscar:"))
        self.input_buscar = QLineEdit()
        self.input_buscar.setPlaceholderText("Escriba para filtrar...")
        self.input_buscar.textChanged.connect(self.filtrar_pacientes)
        buscador_layout.addWidget(self.input_buscar)
        buscador_layout.addStretch()

        self.combo_estado = QComboBox()
        self.combo_estado.addItems(["Activo", "Inactivo", "Todos"])
        self.combo_estado.setCurrentText("Activo")  # Por defecto solo Activos
        self.combo_estado.currentIndexChanged.connect(self.cargar_pacientes)
        buscador_layout.addWidget(QLabel("Estado:"))
        buscador_layout.addWidget(self.combo_estado)

        layout.addLayout(buscador_layout)

        # --- Grilla de pacientes (12 columnas fijas) ---
        self.table = QTableWidget(0, 12)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Apellido", "Sexo", "CI", "Teléfono",
            "Ciudad", "Estado", "Editar", "Eliminar", "Historial", "Fotos"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # OPCIONAL RECOMENDADO: ajuste de columnas
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Stretch)
        for col in (8, 9, 10, 11):  # columnas de acción
            hdr.setSectionResizeMode(col, QHeaderView.ResizeToContents)

        # --- Botón "Agregar" abajo a la derecha ---
        footer = QHBoxLayout()
        footer.addStretch()
        self.btn_agregar = QPushButton("Agregar Paciente")
        self.btn_agregar.setIcon(QIcon("imagenes/agregar.png"))
        self.btn_agregar.setFixedHeight(36)
        self.btn_agregar.clicked.connect(self.agregar_paciente)
        footer.addWidget(self.btn_agregar)
        layout.addLayout(footer)

        # --- Paginación ---
        self.footer_paginacion = QHBoxLayout()
        self.btn_prev = QPushButton("Anterior")
        self.btn_prev.clicked.connect(self.pag_anterior)
        self.btn_next = QPushButton("Siguiente")
        self.btn_next.clicked.connect(self.pag_siguiente)
        self.lbl_pagina = QLabel()

        self.footer_paginacion.addStretch()
        self.footer_paginacion.addWidget(self.btn_prev)
        self.footer_paginacion.addWidget(self.lbl_pagina)
        self.footer_paginacion.addWidget(self.btn_next)
        layout.addLayout(self.footer_paginacion)

        self.setCentralWidget(central)

        # --- Cargar pacientes ---
        self.pacientes = []
        self.cargar_pacientes()

    # ===================== Datos y UI de tabla =====================

    def poblar_tabla(self, pacientes):
        """Rellena la tabla respetando SIEMPRE los mismos índices de columna."""
        tbl = self.table
        tbl.setSortingEnabled(False)
        tbl.setUpdatesEnabled(False)

        # No borres headers (clear borra encabezados). Solo contenido:
        tbl.clearContents()
        tbl.setRowCount(len(pacientes))

        for i, pac in enumerate(pacientes):
            # 0..7: datos
            tbl.setItem(i, 0, QTableWidgetItem(str(pac.idpaciente)))
            tbl.setItem(i, 1, QTableWidgetItem(pac.nombre or ""))
            tbl.setItem(i, 2, QTableWidgetItem(pac.apellido or ""))
            tbl.setItem(i, 3, QTableWidgetItem(pac.sexo or ""))
            tbl.setItem(i, 4, QTableWidgetItem(pac.ci_pasaporte or ""))
            tbl.setItem(i, 5, QTableWidgetItem(pac.telefono or ""))

            ciudad = pac.barrio.ciudad.nombre if pac.barrio and pac.barrio.ciudad else ""
            tbl.setItem(i, 6, QTableWidgetItem(ciudad))
            tbl.setItem(i, 7, QTableWidgetItem("Activo" if pac.estado else "Inactivo"))

            # 8..11: botones (siempre en las mismas columnas)
            btn_editar = QPushButton()
            btn_editar.setIcon(QIcon("imagenes/editar.png"))
            btn_editar.setToolTip("Editar paciente")
            btn_editar.clicked.connect(lambda _, pid=pac.idpaciente: self.editar_paciente(pid))
            tbl.setCellWidget(i, 8, btn_editar)

            btn_eliminar = QPushButton()
            btn_eliminar.setIcon(QIcon("imagenes/eliminar.png"))
            btn_eliminar.setToolTip("Eliminar (desactivar)")
            btn_eliminar.clicked.connect(lambda _, pid=pac.idpaciente: self.eliminar_paciente(pid))
            tbl.setCellWidget(i, 9, btn_eliminar)

            btn_historial = QPushButton()
            btn_historial.setIcon(QIcon("imagenes/historial.png"))
            btn_historial.setToolTip("Ver ficha clínica")
            btn_historial.clicked.connect(lambda _, pid=pac.idpaciente: self.ver_historial(pid))
            tbl.setCellWidget(i, 10, btn_historial)

            btn_fotos = QPushButton()
            btn_fotos.setIcon(QIcon("imagenes/fotos.png"))
            btn_fotos.setToolTip("Ver fotos")
            btn_fotos.clicked.connect(lambda _, pid=pac.idpaciente: self.abrir_fotos(pid))
            tbl.setCellWidget(i, 11, btn_fotos)

        tbl.setUpdatesEnabled(True)
        tbl.setSortingEnabled(True)

    def cargar_pacientes(self):
        """Carga lista completa (según estado) y vuelve a la primera página."""
        session = SessionLocal()
        query = (
            session.query(Paciente)
            .options(joinedload(Paciente.barrio).joinedload(Barrio.ciudad))
        )

        # Filtrar por estado
        estado = self.combo_estado.currentText()
        if estado == "Activo":
            query = query.filter(Paciente.estado == True)
        elif estado == "Inactivo":
            query = query.filter(Paciente.estado == False)
        # "Todos" no filtra

        query = query.order_by(Paciente.apellido.asc(), Paciente.nombre.asc()).all()
        session.close()

        self.pacientes = query
        self.current_page = 0
        self.mostrar_pacientes_pagina()

    def mostrar_pacientes_pagina(self):
        """Muestra solo la página actual usando poblar_tabla."""
        total = len(self.pacientes)
        start = self.current_page * self.page_size
        end = min(start + self.page_size, total)

        self.poblar_tabla(self.pacientes[start:end])

        total_paginas = max(1, (total + self.page_size - 1) // self.page_size)
        self.lbl_pagina.setText(f"Página {self.current_page + 1} de {total_paginas}")
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(end < total)

    def filtrar_pacientes(self):
        """Filtra sobre self.pacientes (ya filtrado por estado) sin tocar columnas."""
        texto = (self.input_buscar.text() or "").strip().lower()
        if not texto:
            # Volver a vista paginada normal
            self.mostrar_pacientes_pagina()
            return

        filtrados = []
        for pac in self.pacientes:
            campos = [
                str(pac.idpaciente),
                (pac.nombre or "").lower(),
                (pac.apellido or "").lower(),
                (pac.ci_pasaporte or "").lower(),
                (pac.telefono or "").lower(),
                (pac.barrio.ciudad.nombre.lower() if pac.barrio and pac.barrio.ciudad else "")
            ]
            if any(texto in c for c in campos):
                filtrados.append(pac)

        # Mostrar filtrados usando exactamente las mismas columnas
        self.poblar_tabla(filtrados)

        # Desactivar paginación en modo filtro (opcional)
        self.lbl_pagina.setText(f"{len(filtrados)} resultado(s)")
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)

    # ===================== Navegación de páginas =====================

    def pag_anterior(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.mostrar_pacientes_pagina()

    def pag_siguiente(self):
        if (self.current_page + 1) * self.page_size < len(self.pacientes):
            self.current_page += 1
            self.mostrar_pacientes_pagina()

    # ===================== Acciones =====================

    def agregar_paciente(self):
        from controllers.fichaClinica import FichaClinicaForm
        dlg = FichaClinicaForm(idpaciente=None, parent=self)
        if dlg.exec_():
            self.cargar_pacientes()

    def editar_paciente(self, idpaciente):
        from controllers.fichaClinica import FichaClinicaForm
        dlg = FichaClinicaForm(idpaciente=idpaciente, parent=self, solo_control=False)
        if dlg.exec_():
            self.cargar_pacientes()

    def eliminar_paciente(self, idpaciente):
        reply = QMessageBox.question(self, "Confirmar", "¿Desea desactivar este paciente?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No:
            return
        session = SessionLocal()
        pac = session.query(Paciente).filter_by(idpaciente=idpaciente).first()
        if pac:
            pac.estado = False
            session.commit()
        session.close()
        self.cargar_pacientes()

    def ver_historial(self, idpaciente):
        from controllers.fichaClinica import FichaClinicaForm
        dlg = FichaClinicaForm(idpaciente=idpaciente, parent=self, solo_control=True)
        dlg.exec_()

    def ver_ficha_clinica(self, idpaciente):
        from controllers.fichaClinica import FichaClinicaForm
        dlg = FichaClinicaForm(idpaciente=idpaciente, parent=self)
        dlg.exec_()

    def abrir_fotos(self, idpaciente):
        from controllers.abm_fotoavance import FotosAvanceDialog
        dlg = FotosAvanceDialog(idpaciente, usuario_id=self.usuario_id)
        dlg.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = PacienteForm(usuario_id=1)
    ventana.showMaximized()
    sys.exit(app.exec_())
