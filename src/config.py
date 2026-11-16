import json
import os
import time
from pathlib import Path

APP_NAME = "DriveAutoUpload"
VERSION = "1.0.0"
APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
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
