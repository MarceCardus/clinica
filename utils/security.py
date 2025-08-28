# utils/security.py
from passlib.context import CryptContext
from passlib.handlers import bcrypt  # fuerza inclusión en PyInstaller  (# noqa: F401)

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__ident="2b",     # homogeneiza a $2b
    bcrypt__rounds=12       # coste razonable
)

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, stored: str) -> bool:
    if not isinstance(stored, str) or not stored:
        return False
    # hashes bcrypt conocidos
    if stored.startswith(("$2a$", "$2b$", "$2y$")):
        return pwd_context.verify(plain, stored)
    # legacy texto plano
    return plain == stored

def needs_rehash(stored: str) -> bool:
    # si no es bcrypt -> conviene rehash al validar OK
    if not isinstance(stored, str) or not stored.startswith("$2"):
        return True
    return pwd_context.needs_update(stored)

# helper útil en el login
def verify_and_upgrade(plain: str, stored: str):
    ok = verify_password(plain, stored)
    new_hash = hash_password(plain) if ok and needs_rehash(stored) else None
    return ok, new_hash
