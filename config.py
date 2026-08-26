# config.py

import os
from sqlalchemy.engine.url import URL

# Host de la base:
#   - LAN (por defecto):        192.168.1.32   -> acceso directo por red local
#   - VPS / parte web:          100.95.236.31  -> IP Tailscale del servidor
# En el VPS definir la variable de entorno DB_HOST=100.95.236.31
# (dejando esta PC y las de la LAN con el valor por defecto).
DB_HOST = os.environ.get("DB_HOST", "192.168.1.32")

DATABASE_URI = URL.create(
    "postgresql+psycopg2",
    username="Cardus",
    password="S@nguines--23",  # sin encode manual
    host=DB_HOST,
    port=5432,
    database="consultorio",
)
