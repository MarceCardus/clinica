# test_perf.py - CORRER EN LA PC DEL CONSULTORIO (la lenta, por WiFi)
# Reproduce el cuelgue de ~10s: usa una conexion, la deja ociosa, y la reusa.
import time, sys
from sqlalchemy import text
from utils.db import engine, SessionLocal
from models.agenda import Cita

print("DB host:", engine.url.host)

# 1) Guardado "en frio" (primera conexion)
t = time.perf_counter()
s = SessionLocal()
s.query(Cita).count()
s.close()
print(f"1) Primer acceso (conexion nueva):     {time.perf_counter()-t:.3f} s")

# 2) Guardado inmediato (conexion caliente del pool)
t = time.perf_counter()
s = SessionLocal()
s.query(Cita).count()
s.close()
print(f"2) Acceso inmediato (pool caliente):   {time.perf_counter()-t:.3f} s")

# 3) LA PRUEBA CLAVE: dejar la conexion ociosa y volver a usarla.
#    Si el WiFi/NAT corto la conexion, este acceso se cuelga ~10s.
idle = int(sys.argv[1]) if len(sys.argv) > 1 else 180  # segundos ocioso (default 3 min)
print(f"\n... esperando {idle}s ocioso (simula el tiempo entre turnos) ...\n")
time.sleep(idle)

t = time.perf_counter()
s = SessionLocal()
s.query(Cita).count()
s.close()
dt = time.perf_counter() - t
print(f"3) Acceso tras {idle}s ocioso:          {dt:.3f} s")

if dt > 3:
    print("\n>>> CONFIRMADO: la conexion ociosa se colgo. Es el problema de red/WiFi.")
    print(">>> El arreglo va en utils/db.py (pool_recycle + keepalives).")
else:
    print("\n>>> No se colgo esta vez. Proba con mas tiempo ocioso, p.ej.:  python test_perf.py 300")
