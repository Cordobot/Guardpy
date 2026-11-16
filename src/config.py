import json
import os
import shutil
import sys
import time
from pathlib import Path

APP_NAME = "Guardpy"


def _version():
    for base in (getattr(sys, "_MEIPASS", ""), Path(__file__).resolve().parent.parent):
        p = Path(base) / "VERSION"
        if p.exists():
            return p.read_text().strip()
    return "dev"


VERSION = _version()
_APPDATA = Path(os.environ.get("APPDATA", Path.home()))
APP_DIR = _APPDATA / APP_NAME
_OLD_DIR = _APPDATA / "DriveAutoUpload"
if _OLD_DIR.exists() and not APP_DIR.exists():  # migrar configuracion de v1.0
    shutil.copytree(_OLD_DIR, APP_DIR)
APP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = APP_DIR / "config.json"
LOG_FILE = APP_DIR / "registro.log"

DEFAULT = {
    "carpetas": [
        str(Path.home() / "Desarrollo"),
        str(Path.home() / "Videos" / "Medal"),
    ],
    "carpeta_drive": "Productos",
    "hora": "02:00",
    "dias": [0, 1, 2, 3, 4, 5, 6],  # 0 = lunes
    "borrar": True,
    "ultima_ejecucion": "",
    "ultimo_resultado": "",
}


def cargar():
    cfg = dict(DEFAULT)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


def guardar(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def log(msg):
    linea = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > 5_000_000:
            LOG_FILE.replace(LOG_FILE.with_suffix(".old.log"))
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except Exception:
        pass
