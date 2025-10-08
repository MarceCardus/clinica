import sys
import os
import models
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QMdiArea, QAction, QMdiSubWindow, QLabel, QStatusBar, QMessageBox, QDialog
)
from PyQt5.QtGui import QPalette, QColor, QIcon
from PyQt5.QtCore import Qt
from controllers.ui_theme  import apply_theme
from models.base import Base
from models.clinica import Clinica
from models.paciente import Paciente
from models.profesional import Profesional
from models.especialidad import Especialidad
from models.profesional_especialidad import ProfesionalEspecialidad
from models.usuario import Usuario
from models.producto import Producto
from models.paquete import Paquete
from models.paquete_producto import PaqueteProducto
from models.proveedor import Proveedor
from models.insumo import Insumo
from models.compra import Compra
from models.compra_detalle import CompraDetalle
from models.venta import Venta
from models.venta_detalle import VentaDetalle
from models.cobro import Cobro
from models.cobro_venta import CobroVenta
from models.venta_cuota import VentaCuota
from models.sesion import Sesion
from models.fotoavance import FotoAvance
from models.receta import Receta
from models.comisionprofesional import ComisionProfesional
from models.cajamovimiento import CajaMovimiento
from models.auditoria import Auditoria
from models.antecPatologico import AntecedentePatologicoPersonal
from models.antecEnfActual import AntecedenteEnfermedadActual
from models.antecFliar import AntecedenteFamiliar
from models.barrio import Barrio
from models.ciudad import Ciudad

# --- IMPORTA Y REGISTRA LA AUDITORÍA ---
from models.setup_auditoria import inicializar_auditoria
inicializar_auditoria()

from controllers.abm_pacientes import PacienteForm      # Cambia este import si tu archivo tiene otro nombre
from login import LoginDialog              # El archivo del formulario de login
from controllers.abm_especialidad import ABMEspecialidad
from controllers.abm_clinica import ABMClinica
from controllers.abm_proveedores import ABMProveedor
from controllers.abm_profesionales import ABMProfesionales
from controllers.abm_producto import ABMProducto
from controllers.abm_turnos import CitaForm
from models.usuario import Usuario
from controllers.abm_paquete import ABMPaquete
from controllers.ventas_form import ABMVenta
from controllers.ventas_controller import VentasController
from controllers.abm_insumos import ABMInsumos
from controllers.abm_compras_form import ABMCompra
from controllers.InformeStockForm import InformeStockForm
from controllers.informe_compras import ComprasReportForm
from controllers.informe_ventas_form import VentasReportForm
from controllers.abm_items import ABMItems
from controllers.cobro_dialog import CobroDialog
from controllers.informe_cobros_form import InformeCobrosForm
from controllers.cambiar_password_dialog import CambiarPasswordDialog
from controllers.informe_stock_mensual_form import InformeStockMensualForm
from controllers.informe_ventas_por_item_dialog import InformeVentasPorItemDialog
from models.paciente import Paciente
from models.profesional import Profesional
from models.clinica import Clinica
from models.producto import Producto
from models.paquete import Paquete
from utils.db import SessionLocal
from controllers.abm_plan_tipo import ABMPlanTipo
from controllers.abm_aparatos import ABMAparatos
from controllers.informe_saldo_cliente import InformeSaldoClienteDialog
from controllers.informe_cobros_paciente import InformeCobrosPorPacienteDlg
from controllers.informe_ranking import InformeRankingDlg
from controllers.informe_atencion_prof import InformeAtencionProfesionalDlg
from controllers.buscar_paciente_planes import BuscarPacientePlanesDlg

from controllers.visor_graficos import VisorGraficosDlg

class MainWindow(QMainWindow):
    def __init__(self, usuario: Usuario, rol: str, session):
        super().__init__()
        self.session = session
        self.usuario: Usuario = usuario
        self.rol: str = rol
        self.usuario_id: int = usuario.idusuario
        self.setWindowTitle(f"Sistema de Consultorio – Main ({self.usuario.usuario})")
        self.setWindowIcon(QIcon("imagenes/logo.ico"))
        self.setGeometry(0, 0, 1400, 800)
        self.mdi_area = QMdiArea()
        self.setCentralWidget(self.mdi_area)
        self.ventana_paciente = None
        self.ventana_profesional = None
        self.ventana_especialidad = None
        self.ventana_clinica = None
        self.ventana_proveedor = None
        self.usuario_logueado = usuario
        # --- Colores institucionales ---
        palette = self.mdi_area.palette()
        palette.setColor(QPalette.Window, QColor("#eaf1fb"))
        self.mdi_area.setPalette(palette)
        self.mdi_area.setBackground(Qt.white)

        self.init_menu()
        self.init_status_bar()

    def init_menu(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
            background-color: #175ca4;
            color: white;
            font-weight: bold;
            font-size: 20px;
            }
            QMenuBar::item {
            background: transparent;
            padding: 8px 24px;
            margin: 0 4px;
            }
            QMenuBar::item:selected {
                background: #4688ce;
                border-radius: 8px;
            }
            QMenu {
                background-color: #f8f9fa;
                font-size: 18px;
            }
            QMenu::item:selected {
                background: #eaf1fb;
                color: #175ca4;
            }
        """)
       

        # Menú Mantenimiento
        self.menu_mantenimiento = menubar.addMenu("Mantenimiento")

        # Pacientes
        action_pacientes = QAction("Pacientes", self)
        action_pacientes.triggered.connect(self.abrir_pacientes)
        self.menu_mantenimiento.addAction(action_pacientes)

        # Especialidades
        action_especialidad = QAction("Especialidades", self)
        action_especialidad.triggered.connect(self.abrir_especialidad)
        self.menu_mantenimiento.addAction(action_especialidad)

        # Clinicas
        action_clinica = QAction("Clinicas", self)
        action_clinica.triggered.connect(self.abrir_clinica)
        self.menu_mantenimiento.addAction(action_clinica)

        # Proveedores
        action_proveedor = QAction("Proveedores", self)
        action_proveedor.triggered.connect(self.abrir_proveedor)
        self.menu_mantenimiento.addAction(action_proveedor)

        # Profesionales
        action_profesional = QAction("Profesionales", self)
        action_profesional.triggered.connect(self.abrir_profesional)
        self.menu_mantenimiento.addAction(action_profesional)

        #action_abm_producto = QAction("Productos", self)
        #action_abm_producto.triggered.connect(self.abrir_producto)
        #self.menu_mantenimiento.addAction(action_abm_producto)

        action_abm_paquete = QAction("Paquetes", self)
        action_abm_paquete.triggered.connect(self.abrir_paquetes)
        self.menu_mantenimiento.addAction(action_abm_paquete)

        #action_abm_insumo = QAction("Insumos", self)
        #action_abm_insumo.triggered.connect(self.abrir_insumos)
        #self.menu_mantenimiento.addAction(action_abm_insumo)

        action_abm_item = QAction("Items", self)
        action_abm_item.triggered.connect(self.abrir_items)
        self.menu_mantenimiento.addAction(action_abm_item)

        action_abm_planTipo = QAction("Tipos de Plan", self)
        action_abm_planTipo.triggered.connect(self.abrir_plan_tipo)
        self.menu_mantenimiento.addAction(action_abm_planTipo)

        action_abm_aparato = QAction("Tipos de Aparatos", self)
        action_abm_aparato.triggered.connect(self.abrir_aparato)
        self.menu_mantenimiento.addAction(action_abm_aparato)

        action_cambiar = QAction("Cambiar contraseña", self)
        action_cambiar.triggered.connect(self.on_cambiar_password)
        self.menu_mantenimiento.addAction(action_cambiar) 

          # Menú Agendar
        self.menu_agendar = menubar.addMenu("Agendar")
        
        action_abm_agendar = QAction("Agendar Pacientes", self)
        action_abm_agendar.triggered.connect(self.abrir_agenda)
        self.menu_agendar.addAction(action_abm_agendar)

        act_planes = QAction("Planes y Sesiones", self)
        act_planes.triggered.connect(self.abrir_buscar_paciente_planes)
        self.menu_agendar.addAction(act_planes)     # o el menú que prefieras
        

        # Menú Compras
        self.action_compras = QAction("Compras", self)
        self.action_compras.triggered.connect(self.abrir_compra)
        menubar.addAction(self.action_compras)

           # Menú Ventas
        self.menu_ventas = menubar.addMenu("Ventas")
        self.action_nueva_venta = QAction("Nueva Venta", self)
        self.action_nueva_venta.triggered.connect(self.abrir_venta)
        self.menu_ventas.addAction(self.action_nueva_venta)
        self.action_plan_cuotas = QAction("Venta Cuotas", self)
        self.action_plan_cuotas.triggered.connect(self.abrir_venta_cuotas)  # stub abajo
        self.menu_ventas.addAction(self.action_plan_cuotas)

         # Menú Cobros
        self.menu_cobros = menubar.addMenu("Cobros")
        self.action_nuevo_cobro = QAction("Nuevo Cobro", self)
        self.action_nuevo_cobro.triggered.connect(self.abrir_cobro)
        self.menu_cobros.addAction(self.action_nuevo_cobro)
        self.action_anular_cobro = QAction("Anular Cobro", self)
        self.action_anular_cobro.triggered.connect(self.abrir_anular_cobro)
        self.menu_cobros.addAction(self.action_anular_cobro)

        # Menú Informes
        self.menu_informes = menubar.addMenu("Informes")
        action_abm_informe_stock = QAction("Stock", self)
        action_abm_informe_stock.triggered.connect(self.abrir_informe_stock)
        self.menu_informes.addAction(action_abm_informe_stock)
         # Informes → stock mes
        self.action_informe_stock_mensual = QAction("Stock Mensual", self)
        self.action_informe_stock_mensual.triggered.connect(self.abrir_informe_stock_mensual)
        self.menu_informes.addAction(self.action_informe_stock_mensual)
        # Informes → Compras
        self.action_informe_compras = QAction("Compras", self)
        self.action_informe_compras.triggered.connect(self.abrir_informe_compras)
        self.menu_informes.addAction(self.action_informe_compras)
        # Informes → Ventas
        self.action_informe_ventas = QAction("Ventas", self)
        self.action_informe_ventas.triggered.connect(self.abrir_informe_ventas)
        self.menu_informes.addAction(self.action_informe_ventas)
        # Informes → Ventas pot tipo ITem
        self.action_informe_ventas_item = QAction("Ventas por Ítem", self)
        self.action_informe_ventas_item.triggered.connect(self.abrir_informe_ventas_por_item)
        self.menu_informes.addAction(self.action_informe_ventas_item)
        # Informes → Saldo de Clientes
        self.action_informe_saldo_clientes = QAction("Saldo de Clientes", self)
        self.action_informe_saldo_clientes.triggered.connect(self.on_informe_saldo_cliente)
        self.menu_informes.addAction(self.action_informe_saldo_clientes)

        # Informes → Cobros
        self.action_informe_cobros = QAction("Cobros", self)
        self.action_informe_cobros.triggered.connect(self.abrir_informe_cobros)
        self.menu_informes.addAction(self.action_informe_cobros)

         # Informes → Cobros Pacientes
        self.action_informe_cobros_pac = QAction("Cobros por Paciente", self)
        self.action_informe_cobros_pac.triggered.connect(self.on_informe_cobros_por_paciente)
        self.menu_informes.addAction(self.action_informe_cobros_pac)

        # Informes → Ranking
        self.action_informe_ranking = QAction("Ranking", self)
        self.action_informe_ranking.triggered.connect(self.abrir_informe_ranking)
        self.menu_informes.addAction(self.action_informe_ranking)

         # Informes → ATP
        self.action_informe_atp = QAction("ATP", self)
        self.action_informe_atp.triggered.connect(self.abrir_informe_atencion_prof)
        self.menu_informes.addAction(self.action_informe_atp)

        # Informes → Gráficos
        actionInformeGeneral = QAction("Gráficos", self)
        actionInformeGeneral.triggered.connect(self.abrir_visor_graficos)
        self.menu_informes.addAction(actionInformeGeneral)


        # --- BLOQUEO DE MENÚ SEGÚN ROL ---
        if self.rol != "superusuario":
            self.action_compras.setEnabled(False)
            self.action_nueva_venta.setEnabled(False)
            self.action_plan_cuotas.setEnabled(False)

    def init_status_bar(self):
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        lbl_usuario = QLabel(f"Usuario: {self.usuario.usuario} | Rol: {self.rol.upper()}")
        lbl_usuario.setStyleSheet("font-weight: bold; color: #175ca4; margin-right:20px;")
        status_bar.addPermanentWidget(lbl_usuario)

    def abrir_buscar_paciente_planes(self):
        dlg = BuscarPacientePlanesDlg(self)
        dlg.exec_()

    def abrir_visor_graficos(self):
        dlg = VisorGraficosDlg(self)
        dlg.exec_()

    def abrir_informe_general(self):
        dlg = InformeGeneralDlg(self)
        dlg.exec_()

    def abrir_informe_atencion_prof(self):
        dlg = InformeAtencionProfesionalDlg(self)
        dlg.exec_()

    def abrir_informe_ranking(self):
        dlg = InformeRankingDlg(self)
        dlg.exec_()
    
    def abrir_plan_tipo(self):
        dlg = ABMPlanTipo(self)
        dlg.exec_()

    def abrir_informe_stock_mensual(self):
        dlg = InformeStockMensualForm(self) 
        dlg.exec_()

    def on_informe_cobros_por_paciente(self):
        dlg = InformeCobrosPorPacienteDlg(self)
        dlg.exec_()

    def on_informe_saldo_cliente(self):
        dlg = InformeSaldoClienteDialog(self.session, self)
        dlg.resize(1100, 640)
        dlg.exec_()

    def abrir_informe_ventas_por_item(self):
        try:
            dlg = InformeVentasPorItemDialog(self)
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Informes", f"Error al abrir el informe:\n{e}")

    def abrir_informe_cobros(self):
        dlg = InformeCobrosForm(self.session, self)
        dlg.exec_()

    def abrir_aparato(self):
        dlg = ABMAparatos(self)
        dlg.exec_()

    def on_cambiar_password(self):
        # si guardaste el id como self.usuario_logueado.idusuario:
        dlg = CambiarPasswordDialog(self.usuario_logueado.idusuario, self)
        dlg.exec_()

    def abrir_cobro(self):
        dlg = CobroDialog(parent=self, session=self.session, usuario_actual=self.usuario.idusuario)  # <-- ID numérico
        dlg.exec_()
        # si querés refrescar listas/tableros después, hacelo acá
        # self.refrescar_dashboard()

    def abrir_anular_cobro(self):
        from controllers.anular_cobro_dialog import AnularCobroDialog
        dlg = AnularCobroDialog(parent=self, session=self.session,
                                usuario_actual=self.usuario.idusuario)
        dlg.exec_()

    def abrir_pacientes(self):
        for subwin in self.mdi_area.subWindowList():
            widget = subwin.widget()
            if widget and isinstance(widget, PacienteForm):
                subwin.setFocus()
                subwin.showNormal()
                self.ajustar_subventana(subwin)
                return
        sub = QMdiSubWindow()
        sub.setWidget(PacienteForm(usuario_id=self.usuario_id))
        sub.setWindowTitle("Gestión de Pacientes")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        self.ajustar_subventana(sub)
        sub.show()

    def abrir_venta(self):
        for subwin in self.mdi_area.subWindowList():
            if isinstance(subwin.widget(), ABMVenta):
                subwin.setFocus()
                subwin.showNormal()
                self.ajustar_subventana(subwin)
                return
        sub = QMdiSubWindow()
        sub.setWidget(ABMVenta(usuario_id=self.usuario_id))
        sub.setWindowTitle("ABM de Ventas")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        self.ajustar_subventana(sub)
        sub.show()
    
    def abrir_venta_cuotas(self):
        self._abrir_plan_cuotas()

    def abrir_compra(self):
        for subwin in self.mdi_area.subWindowList():
            widget = subwin.widget()
            if widget is not None and isinstance(widget, ABMCompra):
                subwin.setFocus()
                subwin.showNormal()
                return
        sub = QMdiSubWindow()
        sub.setWidget(ABMCompra())
        sub.setWindowTitle("ABM de Compras")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        sub.show()

    def abrir_venta(self):
        for subwin in self.mdi_area.subWindowList():
            widget = subwin.widget()
            if widget is not None and isinstance(widget, ABMVenta):
                subwin.setFocus()
                subwin.showNormal()
                return
        sub = QMdiSubWindow()
        sub.setWidget(ABMVenta(usuario_id=self.usuario_id))
        sub.setWindowTitle("ABM de Ventas")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        sub.show()


    def abrir_informe_compras(self):
        # Si ya existe, traer al frente
        for subwin in self.mdi_area.subWindowList():
            widget = subwin.widget()
            if widget and isinstance(widget, ComprasReportForm):
                subwin.setFocus()
                subwin.showNormal()
                self.ajustar_subventana(subwin)
                return

        # Si no existe, crear nueva subventana
        sub = QMdiSubWindow()
        sub.setWidget(ComprasReportForm(self))   # el form crea su propia SessionLocal
        sub.setWindowTitle("Informe de Compras")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        self.ajustar_subventana(sub)
        sub.show()

    def abrir_informe_ventas(self):
        # Si ya existe, traer al frente
        for subwin in self.mdi_area.subWindowList():
            widget = subwin.widget()
            if widget and isinstance(widget, VentasReportForm):
                subwin.setFocus()
                subwin.showNormal()
                self.ajustar_subventana(subwin)
                return

        # Si no existe, crear nueva subventana
        sub = QMdiSubWindow()
        sub.setWidget(VentasReportForm(self))   # el form crea su propia SessionLocal
        sub.setWindowTitle("Informe de Ventas")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        self.ajustar_subventana(sub)
        sub.show()    

    def abrir_especialidad(self):
        for subwin in self.mdi_area.subWindowList():
            widget = subwin.widget()
            if widget is not None and isinstance(widget, ABMEspecialidad):
                subwin.setFocus()
                subwin.showNormal()
                return
        sub = QMdiSubWindow()
        sub.setWidget(ABMEspecialidad())
        sub.setWindowTitle("ABM de Especialidades")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        sub.show()

    def abrir_clinica(self):
        for subwin in self.mdi_area.subWindowList():
            widget = subwin.widget()
            if widget is not None and isinstance(widget, ABMClinica):
                subwin.setFocus()
                subwin.showNormal()
                return
        sub = QMdiSubWindow()
        sub.setWidget(ABMClinica())
        sub.setWindowTitle("ABM de Clinicas")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        sub.show()

    def abrir_proveedor(self):
        for subwin in self.mdi_area.subWindowList():
            widget = subwin.widget()
            if widget is not None and isinstance(widget, ABMProveedor):
                subwin.setFocus()
                subwin.showNormal()
                self.ajustar_subventana(subwin)  # <-- llamá esto
                return
        sub = QMdiSubWindow()
        sub.setWidget(ABMProveedor())
        sub.setWindowTitle("ABM de Proveedores")
        self.mdi_area.addSubWindow(sub)
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.ajustar_subventana(sub)
        sub.show()

    def abrir_profesional(self):
        for subwin in self.mdi_area.subWindowList():
            widget = subwin.widget()
            if widget is not None and isinstance(widget, ABMProfesionales):
                subwin.setFocus()
                subwin.showNormal()
                return
        sub = QMdiSubWindow()
        sub.setWidget(ABMProfesionales())
        sub.setWindowTitle("ABM de Profesionales")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        sub.show()

    def ajustar_subventana(self, subventana):
        area = self.mdi_area.viewport().geometry()
        # Margen de 5px para que no tape el borde ni la barra
        margen = 5
        ancho = area.width() - margen
        alto = area.height() - margen
        subventana.setGeometry(margen // 2, margen // 2, ancho, alto)
        subventana.setWindowState(Qt.WindowNoState)  # Importante: que NO esté en modo maximizado

    def abrir_producto(self):
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), ABMProducto):
                sub.setFocus(); return
        sub = QMdiSubWindow()
        sub.setWidget(ABMProducto())
        sub.setWindowTitle("ABM de Productos")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        self.ajustar_subventana(sub)
        sub.show()

    def abrir_paquetes(self):
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), ABMPaquete):
                sub.setFocus(); return
        sub = QMdiSubWindow()
        sub.setWidget(ABMPaquete())
        sub.setWindowTitle("ABM de Paquetes")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        self.ajustar_subventana(sub)
        sub.show()

    def abrir_insumos(self):
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), ABMInsumos):
                sub.setFocus(); return
        sub = QMdiSubWindow()
        sub.setWidget(ABMInsumos())
        sub.setWindowTitle("ABM de Insumos")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        self.ajustar_subventana(sub)
        sub.show()

    def abrir_items(self):
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), ABMItems):
                sub.setFocus(); return
        sub = QMdiSubWindow()
        sub.setWidget(ABMItems())
        sub.setWindowTitle("ABM de Insumos")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        self.ajustar_subventana(sub)
        sub.show()

    def abrir_agenda(self):
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), CitaForm):
                sub.setFocus()
                return

        sub = QMdiSubWindow()
        # Instancia únicamente con usuario_id
        turno_widget = CitaForm(usuario_id=self.usuario_id)
        sub.setWidget(turno_widget)

        sub.setWindowTitle("ABM de Citas")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        self.ajustar_subventana(sub)
        sub.show()

    

    def abrir_informe_stock(self):
        # Si ya existe la ventana, traerla al frente
        for subwin in self.mdi_area.subWindowList():
            widget = subwin.widget()
            if widget and isinstance(widget, InformeStockForm):
                subwin.setFocus()
                subwin.showNormal()
                self.ajustar_subventana(subwin)
                return

        # Si no existe, crear una nueva subventana
        from utils.db import SessionLocal
        session = SessionLocal()
        sub = QMdiSubWindow()
        sub.setWidget(InformeStockForm(session, self))
        sub.setWindowTitle("Informe de Stock de Insumos")
        sub.setAttribute(Qt.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub)
        self.ajustar_subventana(sub)
        sub.show()

if __name__ == "__main__":
    from login import LoginDialog
    app = QApplication(sys.argv)
    apply_theme(app)
    app.setWindowIcon(QIcon("imagenes/logo2.ico")) 
    login = LoginDialog()
    session = SessionLocal()
    if login.exec_() == LoginDialog.Accepted:
        usuario = login.usuario_actual    # Debe ser el OBJETO Usuario, no string
        rol = login.rol
        main_win = MainWindow(usuario, rol, session)
        main_win.showMaximized()
        sys.exit(app.exec_())
