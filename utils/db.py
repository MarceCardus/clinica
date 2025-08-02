# utils/db.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from config import DATABASE_URI

# Motor de conexión
engine = create_engine(DATABASE_URI, echo=True)

# Fábrica de sesiones
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Declarative base: todos los modelos deben heredar de aquí
Base = declarative_base()
