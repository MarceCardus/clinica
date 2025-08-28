# config.py

from sqlalchemy.engine.url import URL
#DATABASE_URI = 'postgresql+psycopg2://clinicauser:sanguines@192.168.1.32:5432/consultorio'
#DATABASE_URI = 'postgresql+psycopg2://Cardus:sanguines@localhost:5432/consultorio'
DATABASE_URI = URL.create(
    "postgresql+psycopg2",
    username="Cardus",
    password="S@nguines--23",  # sin encode manual
    host="181.1.152.126",
    port=5433,
    database="consultorio",
)

