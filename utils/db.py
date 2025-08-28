# utils/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from config import DATABASE_URI
from models.base import Base  # seguimos usando el mismo Base

# Motor de conexión robusto
engine = create_engine(
    DATABASE_URI,
    echo=False,               # poné True si necesitás ver SQL en consola
    pool_pre_ping=True,       # evita usar conexiones muertas del pool
    pool_recycle=900,         # recicla sockets cada 15 min (evita timeouts/NAT)
    pool_size=5,              # ajuste para app de escritorio
    max_overflow=10,
    pool_timeout=30,
    connect_args={
        "application_name": "clinica_app",
        "connect_timeout": 10,
        # TCP keepalives (lado cliente)
        "keepalives": 1,
        "keepalives_idle": 60,
        "keepalives_interval": 30,
        "keepalives_count": 5,
        # Límite por sentencia (30s) para que no queden colgadas
        "options": "-c statement_timeout=30000",
        # Si tu servidor acepta SSL, podés activar:
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
