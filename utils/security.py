# utils/security.py
from passlib.context import CryptContext

# bcrypt por defecto
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, stored: str) -> bool:
    """
    Soporta dos escenarios:
    - Si stored ya es bcrypt ($2...), verifica con passlib.
    - Si stored es texto plano (sistemas legacy), compara igualdad simple.
    """
    if not isinstance(stored, str):
        return False
    if stored.startswith("$2a$") or stored.startswith("$2b$") or stored.startswith("$2y$"):
        return pwd_context.verify(plain, stored)
    return plain == stored  # soporte legacy

def needs_rehash(stored: str) -> bool:
    return stored.startswith("$2") and pwd_context.needs_update(stored)
