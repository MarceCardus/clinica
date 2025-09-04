# utils/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from config import DATABASE_URI
from models.base import Base  # seguimos usando el mismo Base
# Motor de conexión robusto
engine = create_engine(
    DATABASE_URI,
    future=True,
    echo=False,
    pool_pre_ping=True,     # evita conexiones muertas
    pool_recycle=900,       # recicla cada 15 min
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_use_lifo=True,     # <-- toma la conexión más reciente del pool (LIFO)
    pool_reset_on_return="rollback",  # opcional, explícito
    connect_args={
        "application_name": "clinica_app",
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 60,
        "keepalives_interval": 30,
        "keepalives_count": 5,
        "options": "-c statement_timeout=30000",
        # "sslmode": "require",
    },
)


# Fábrica de sesiones (thread-safe con scoped_session, útil para varias ventanas)
SessionLocal = scoped_session(sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
))

def get_session():
    """Obtiene una Session nueva desde el registry (útil para inyectar donde sea)."""
    return SessionLocal()

def new_session():
    """
    Fuerza una sesión nueva (rompe el thread-local si existía) y devuelve una Session lista.
    Útil para acciones individuales en la UI (reportes, exportaciones).
    """
    SessionLocal.remove()
    return SessionLocal()