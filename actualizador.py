import os
import shutil
import subprocess
import sys
import ctypes

from PyQt5.QtWidgets import QApplication, QProgressDialog
from PyQt5.QtCore import Qt

RUTA_LOCAL = r'C:\consultorio'
RUTA_SERVIDOR = r'\\192.168.1.32\consultorio'

# ===================== Util =====================

def _parse_version(v: str) -> list[int]:
    try:
        parts = [int(p) for p in v.strip().split('.')]
        return parts
    except Exception:
        return []

def version_mayor(v1: str, v2: str) -> bool:
    """True si v1 > v2 (soporta longitudes distintas)."""
    a, b = _parse_version(v1), _parse_version(v2)
    n = max(len(a), len(b))
    a += [0] * (n - len(a))
    b += [0] * (n - len(b))
    return a > b

def leer_version(ruta):
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"[WARN] No se pudo leer versión en {ruta}: {e}")
        return None

def message_box(title: str, msg: str):
    try:
        ctypes.windll.user32.MessageBoxW(0, msg, title, 0)
    except Exception:
        print(f"{title}: {msg}")

def lanzar_local(exe_path: str):
    if not os.path.isfile(exe_path):
        message_box("Error", f"No se encontró el ejecutable local:\n{exe_path}")
        sys.exit(1)
    try:
        subprocess.Popen([exe_path])
    except Exception as e:
        message_box("Error", f"No se pudo iniciar la aplicación local:\n{e}")
        sys.exit(1)
    sys.exit(0)

# ===================== Update =====================

def actualizar_con_progreso():
    """Devuelve True si la actualización terminó bien, False si hubo error."""
    app = QApplication.instance() or QApplication(sys.argv)

    dialog = QProgressDialog("Actualizando aplicación...", None, 0, 0)
    dialog.setWindowTitle("Actualización en progreso")
    dialog.setCancelButton(None)
    dialog.setWindowModality(Qt.ApplicationModal)
    dialog.show()
    app.processEvents()

    try:
        os.makedirs(RUTA_LOCAL, exist_ok=True)

        # --- SOLO ejecutable principal y version.txt ---
        src_main = os.path.join(RUTA_SERVIDOR, 'main.exe')
        dst_main = os.path.join(RUTA_LOCAL, 'main.exe')
        shutil.copy2(src_main, dst_main)
        print("[INFO] main.exe actualizado.")

        src_ver = os.path.join(RUTA_SERVIDOR, 'version.txt')
        dst_ver = os.path.join(RUTA_LOCAL, 'version.txt')
        shutil.copy2(src_ver, dst_ver)
        print("[INFO] version.txt actualizado.")

        # IMPORTANTE: ya NO copiamos nada de la carpeta 'imagenes'
        # (se eliminó la función sincronizar_imagenes y su uso)

    except Exception as e:
        print(f"[WARN] Error durante la actualización: {e}")
        dialog.close()
        return False
    finally:
        dialog.close()

    return True

# ===================== Main =====================

def main():
    exe_path = os.path.join(RUTA_LOCAL, 'main.exe')
    os.makedirs(RUTA_LOCAL, exist_ok=True)

    version_local = leer_version(os.path.join(RUTA_LOCAL, 'version.txt'))
    version_remota = leer_version(os.path.join(RUTA_SERVIDOR, 'version.txt'))

    # Si NO hay versión remota (share caído o falta version.txt): abrir local
    if not version_remota:
        print("[INFO] No hay versión remota disponible; iniciando versión local.")
        lanzar_local(exe_path)

    # Si no hay versión local o la remota es mayor: intentar actualizar
    if (not version_local) or version_mayor(version_remota, version_local):
        print(f"[INFO] Actualizando de {version_local or 'N/A'} a {version_remota}...")
        ok = actualizar_con_progreso()
        if not ok:
            print("[WARN] Falló la actualización; iniciando versión local.")
            lanzar_local(exe_path)
        lanzar_local(exe_path)
    else:
        print("[INFO] Versión local al día; iniciando aplicación.")
        lanzar_local(exe_path)

if __name__ == "__main__":
    main()
