import os
import shutil
import subprocess
import sys
from filecmp import cmp
import ctypes

from PyQt5.QtWidgets import QApplication, QMessageBox, QProgressDialog
from PyQt5.QtCore import Qt

RUTA_LOCAL = r'C:\consultorio'
RUTA_SERVIDOR = r'\\192.168.1.32\consultorio'

def version_mayor(v1, v2):
    def normalizar(v): return list(map(int, v.strip().split('.')))
    return normalizar(v1) > normalizar(v2)

def leer_version(ruta):
    try:
        with open(ruta, 'r') as f:
            return f.read().strip()
    except Exception as e:
        print(f"No se pudo leer el archivo de versión: {ruta} - {e}")
        return None

def sincronizar_imagenes(origen, destino):
    if not os.path.exists(origen):
        print(f"No se encontró la carpeta de imágenes en el servidor: {origen}")
        return
    if not os.path.exists(destino):
        os.makedirs(destino)
    for archivo in os.listdir(origen):
        ruta_origen = os.path.join(origen, archivo)
        ruta_destino = os.path.join(destino, archivo)
        if not os.path.exists(ruta_destino) or not cmp(ruta_origen, ruta_destino, shallow=False):
            shutil.copy2(ruta_origen, ruta_destino)
            print(f"Copiado: {archivo}")

def mensaje_error(msg):
    ctypes.windll.user32.MessageBoxW(0, msg, "Error de Actualización", 0)

def actualizar_con_progreso():
    app = QApplication(sys.argv)

    dialog = QProgressDialog("Actualizando aplicación...", None, 0, 0)
    dialog.setWindowTitle("Actualización en progreso")
    dialog.setCancelButton(None)
    dialog.setWindowModality(Qt.ApplicationModal)
    dialog.show()
    app.processEvents()

    try:
        shutil.copy2(os.path.join(RUTA_SERVIDOR, 'main.exe'), os.path.join(RUTA_LOCAL, 'main.exe'))
        print("main.exe actualizado.")
        shutil.copy2(os.path.join(RUTA_SERVIDOR, 'version.txt'), os.path.join(RUTA_LOCAL, 'version.txt'))
        print("version.txt actualizado.")
        sincronizar_imagenes(os.path.join(RUTA_SERVIDOR, 'imagenes'), os.path.join(RUTA_LOCAL, 'imagenes'))
        print("Carpeta imágenes sincronizada.")
    except Exception as e:
        print(f"Error durante la actualización: {e}")
        dialog.close()
        mensaje_error(f"Ocurrió un error durante la actualización:\n{e}")
        sys.exit(1)

    dialog.close()

def main():
    version_local = leer_version(os.path.join(RUTA_LOCAL, 'version.txt'))
    version_remota = leer_version(os.path.join(RUTA_SERVIDOR, 'version.txt'))
    exe_path = os.path.join(RUTA_LOCAL, 'main.exe')

    if not version_remota:
        mensaje_error("No se pudo obtener la versión del servidor. Cancelando.")
        sys.exit(1)

    if not version_local or version_mayor(version_remota, version_local):
        actualizar_con_progreso()
        subprocess.Popen([exe_path])
        sys.exit(0)
    else:
        # Si está actualizado, entra directo sin mostrar mensaje
        subprocess.Popen([exe_path])
        sys.exit(0)

if __name__ == "__main__":
    main()
