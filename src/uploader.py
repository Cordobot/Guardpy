"""Logica de subida a Google Drive: subir, verificar MD5 y borrar del PC."""
import hashlib
import shutil
import sys
import time
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from config import APP_DIR, log

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CREDENTIALS = APP_DIR / "credentials.json"
# Cliente OAuth incluido en el instalador (opcional, se agrega al compilar)
BUNDLED = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "google_client.json"
TOKEN = APP_DIR / "token.json"
IGNORAR = {"desktop.ini", "thumbs.db"}
IGNORAR_EXT = {".tmp", ".part", ".crdownload", ".lock"}
ESPERA_ESTABLE = 30  # segundos sin cambios


class SinCredenciales(Exception):
    pass


def importar_credenciales(ruta):
    shutil.copy(ruta, CREDENTIALS)
    if TOKEN.exists():
        TOKEN.unlink()


def cliente_oauth():
    if CREDENTIALS.exists():
        return CREDENTIALS
    if BUNDLED.exists():
        return BUNDLED
    return None


def conectado():
    return TOKEN.exists() and cliente_oauth() is not None


def desconectar():
    if TOKEN.exists():
        TOKEN.unlink()


def conectar(interactivo=True):
    cliente = cliente_oauth()
    if cliente is None:
        raise SinCredenciales("Conecta tu cuenta de Google en Guardpy.")
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # sesion vencida o revocada (en modo "Testing" Google la vence cada 7 dias)
                TOKEN.unlink(missing_ok=True)
                if not interactivo:
                    raise SinCredenciales("Tu sesión de Google venció. Abre Guardpy y pulsa "
                                          "\"Conectar con Google\".")
                creds = None
        if creds and creds.valid:
            pass
        elif interactivo:
            flow = InstalledAppFlow.from_client_secrets_file(str(cliente), SCOPES)
            creds = flow.run_local_server(
                port=0, open_browser=True,
                success_message="Listo. Guardpy ya está conectado a tu Google Drive. Puedes cerrar esta pestaña.")
        else:
            raise SinCredenciales("Conecta tu cuenta de Google en Guardpy.")
        TOKEN.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _carpeta(svc, nombre, padre=None):
    nombre_q = nombre.replace("\\", "\\\\").replace("'", "\\'")
    q = (f"name = '{nombre_q}' and mimeType = 'application/vnd.google-apps.folder' "
         "and trashed = false")
    if padre:
        q += f" and '{padre}' in parents"
    res = svc.files().list(q=q, fields="files(id)").execute().get("files", [])
    if res:
        return res[0]["id"]
    meta = {"name": nombre, "mimeType": "application/vnd.google-apps.folder"}
    if padre:
        meta["parents"] = [padre]
    return svc.files().create(body=meta, fields="id").execute()["id"]


def _md5(ruta):
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def _listo(ruta):
    if ruta.name.lower() in IGNORAR or ruta.suffix.lower() in IGNORAR_EXT:
        return False
    if time.time() - ruta.stat().st_mtime < ESPERA_ESTABLE:
        return False
    try:
        with open(ruta, "rb+"):
            pass
    except OSError:
        return False
    return True


def ejecutar(cfg, progreso=lambda msg: None):
    """Sube todo. Devuelve (subidos, errores)."""
    svc = conectar(interactivo=False)
    raiz = _carpeta(svc, cfg["carpeta_drive"])
    subidos = errores = 0
    for origen in cfg["carpetas"]:
        base = Path(origen)
        if not base.is_dir():
            log(f"Carpeta no existe, se omite: {base}")
            continue
        destino = _carpeta(svc, base.name, raiz)
        cache = {}
        archivos = [p for p in base.rglob("*") if p.is_file()]
        for ruta in archivos:
            try:
                if not _listo(ruta):
                    continue
                padre = destino
                acum = ""
                for parte in ruta.parent.relative_to(base).parts:
                    acum += "/" + parte
                    if acum not in cache:
                        cache[acum] = _carpeta(svc, parte, padre)
                    padre = cache[acum]
                progreso(f"Subiendo {ruta.name}")
                local = _md5(ruta)
                with open(ruta, "rb") as f:
                    media = MediaIoBaseUpload(f, mimetype="application/octet-stream",
                                              resumable=True, chunksize=10 * 1024 * 1024)
                    req = svc.files().create(body={"name": ruta.name, "parents": [padre]},
                                             media_body=media, fields="id, md5Checksum")
                    resp = None
                    while resp is None:
                        _, resp = req.next_chunk()
                if resp.get("md5Checksum") != local:
                    log(f"ERROR verificacion, NO se borra: {ruta}")
                    errores += 1
                    continue
                if cfg.get("borrar", True):
                    ruta.unlink()
                    log(f"OK subido y borrado: {ruta}")
                else:
                    log(f"OK subido: {ruta}")
                subidos += 1
            except Exception as e:  # noqa: BLE001
                log(f"ERROR con {ruta}: {e}")
                errores += 1
        if cfg.get("borrar", True):
            # limpia subcarpetas vacias (no la carpeta raiz)
            for d in sorted((p for p in base.rglob("*") if p.is_dir()), reverse=True):
                try:
                    d.rmdir()
                except OSError:
                    pass
    return subidos, errores
