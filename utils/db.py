# utils/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URI
from models.base import Base  # <-- usamos el MISMO Base de models/base.py

# Motor de conexión
engine = create_engine(DATABASE_URI, echo=True)

# Fábrica de sesiones
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)
