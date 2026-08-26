# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# ----------------------------------------------------------------------
#  Dependencias del dictado por voz.
#  Se importan de forma perezosa (dentro de funciones), así que PyInstaller
#  no las detecta solo. Además traen DLLs y archivos de datos que hay que
#  arrastrar a mano:
#    - sounddevice   -> DLL de PortAudio (libportaudio*.dll)
#    - faster_whisper-> assets del modelo VAD (silero) + tokenizer
#    - ctranslate2   -> runtime nativo (motor de whisper) + OpenMP
#    - av (PyAV)     -> librerías de ffmpeg para leer/decodificar audio
#    - onnxruntime   -> ejecuta el VAD de faster-whisper
# ----------------------------------------------------------------------
binaries = []
datas = []
hiddenimports = []

# numpy NO se incluye acá: ya lo maneja el hook interno de PyInstaller.
# Forzarlo con collect_all arrastra toda la suite de tests, numpy.distutils
# y jax (que crashea al importarse), inflando el .exe sin necesidad.
for _paquete in ("sounddevice", "faster_whisper", "ctranslate2",
                 "av", "onnxruntime"):
    try:
        _b, _d, _h = collect_all(_paquete)
        binaries += _b
        datas += _d
        hiddenimports += _h
    except Exception:
        # si el paquete no está instalado en el entorno de build, se ignora
        pass


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['imagenes\\logo2.ico'],
)
