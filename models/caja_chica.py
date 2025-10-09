# models/caja_chica.py
from sqlalchemy import Column, Integer, DateTime, Numeric, String, Enum, ForeignKey, func
from sqlalchemy.orm import relationship
from .base import Base

class CajaChicaSesion(Base):
    __tablename__ = 'caja_chica_sesion'

    idcajachica = Column(Integer, primary_key=True, autoincrement=True)
    
    # Fechas y usuario de apertura/cierre
    fecha_apertura = Column(DateTime, nullable=False, default=func.now())
    fecha_cierre = Column(DateTime)
    # Asumo que tienes un modelo de Usuario
    idusuario_apertura = Column(Integer, ForeignKey('usuario.idusuario'), nullable=False) 
    idusuario_cierre = Column(Integer, ForeignKey('usuario.idusuario'))
    
    # Montos
    monto_inicial = Column(Numeric(14, 2), nullable=False)
    monto_final_calculado = Column(Numeric(14, 2)) # Calculado por el sistema
    monto_final_real = Column(Numeric(14, 2))      # Contado físicamente por el usuario
    diferencia = Column(Numeric(14, 2), default=0) # Sobrante o faltante
    
    # Estado y observaciones
    estado = Column(Enum('ABIERTA', 'CERRADA', name='estado_caja_chica'), nullable=False, default='ABIERTA')
    observaciones = Column(String)
    
    # Relación con los movimientos
    movimientos = relationship("CajaChicaMovimiento", back_populates="caja_sesion", cascade="all, delete-orphan")

class CajaChicaMovimiento(Base):
    __tablename__ = 'caja_chica_movimiento'
    
    idmovimiento = Column(Integer, primary_key=True, autoincrement=True)
    # A qué sesión de caja pertenece
    idcajachica = Column(Integer, ForeignKey('caja_chica_sesion.idcajachica', ondelete="CASCADE"), nullable=False)
    
    # Datos del movimiento
    fecha_hora = Column(DateTime, nullable=False, default=func.now())
    # El tipo es clave para saber qué fue
    tipo_movimiento = Column(Enum('GASTO', 'PAGO_COMPRA', 'INGRESO', name='tipo_movimiento_caja'), nullable=False)
    descripcion = Column(String(255), nullable=False)
    monto = Column(Numeric(14, 2), nullable=False)
    
    # --- LA CONEXIÓN CLAVE ---
    # Si el gasto corresponde a una compra registrada, la vinculamos aquí.
    idcompra = Column(Integer, ForeignKey('compra.idcompra', ondelete="SET NULL"), nullable=True)
    
    # Asumo que tienes un modelo de Usuario que registra la operación
    idusuario_registro = Column(Integer, ForeignKey('usuario.idusuario'), nullable=False)
    
    # Relaciones
    caja_sesion = relationship("CajaChicaSesion", back_populates="movimientos")
    compra = relationship("Compra") # Relación simple para acceder a los datos de la compra