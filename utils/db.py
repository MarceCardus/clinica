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
    # WiFi/NAT cortan conexiones ociosas en silencio. Con recycle largo, SQLAlchemy
    # intenta reusar la conexión muerta y se cuelga ~10s en el timeout de TCP.
    # Con 60s, descarta las ociosas >1min y reconecta en ~0.1s sin intentar usarlas.
    pool_recycle=60,        # antes 900
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_use_lifo=True,     # <-- toma la conexión más reciente del pool (LIFO)
    pool_reset_on_return="rollback",  # opcional, explícito
    connect_args={
        "application_name": "clinica_app",
        "connect_timeout": 10,
        # keepalives agresivos: Windows sondea la conexión durante el ocio y la
        # marca muerta ANTES del próximo guardado (antes: 60/30/5 -> ~210s para detectar).
        "keepalives": 1,
        "keepalives_idle": 15,       # antes 60
        "keepalives_interval": 5,    # antes 30
        "keepalives_count": 3,       # antes 5
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