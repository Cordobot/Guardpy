"""DriveAutoUpload - sube carpetas a Google Drive a una hora programada
y borra los archivos del PC despues de verificar la subida."""
import datetime as dt
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pystray
from PIL import Image, ImageDraw

import config
import uploader
from config import APP_NAME, VERSION, log

DIAS = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


# ---------------- inicio con Windows ----------------
def _exe_cmd():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{os.path.abspath(__file__)}"'


def inicio_activo():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except Exception:
        return False


def set_inicio(activo):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if activo:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _exe_cmd())
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except FileNotFoundError:
                    pass
    except Exception as e:
        log(f"No se pudo cambiar inicio con Windows: {e}")


# ---------------- icono ----------------
def icono(color):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=color)
    d.polygon([(32, 14), (48, 34), (38, 34), (38, 50), (26, 50), (26, 34), (16, 34)],
              fill="white")
    return img


ICONOS = {"ok": icono("#1a73e8"), "subiendo": icono("#f9ab00"), "error": icono("#d93025")}


class App:
    def __init__(self):
        self.cfg = config.cargar()
        self.ocupado = threading.Lock()
        self.cola = queue.Queue()
        self.estado = "Esperando"
        self.root = tk.Tk()
        self.root.withdraw()
        self.ventana = None
        self.tray = pystray.Icon(APP_NAME, ICONOS["ok"], f"{APP_NAME} {VERSION}", self._menu())
        self.tray.run_detached()
        self.root.after(500, self._procesar_cola)
        self.root.after(1000, self._tick)
        if not uploader.CREDENTIALS.exists() or not uploader.TOKEN.exists():
            self.root.after(800, self.abrir_config)
        log(f"Iniciado v{VERSION}")

    # ----- menu bandeja -----
    def _menu(self):
        return pystray.Menu(
            pystray.MenuItem(lambda _: f"Estado: {self.estado}", None, enabled=False),
            pystray.MenuItem(lambda _: f"Proxima: {self._proxima_txt()}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Subir ahora", lambda: self.cola.put("subir"), default=False),
            pystray.MenuItem("Configuracion...", lambda: self.cola.put("config"), default=True),
            pystray.MenuItem("Ver registro", lambda: os.startfile(config.LOG_FILE)
                             if config.LOG_FILE.exists() else None),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", lambda: self.cola.put("salir")),
        )

    def _procesar_cola(self):
        try:
            while True:
                cmd = self.cola.get_nowait()
                if cmd == "subir":
                    self.lanzar_subida()
                elif cmd == "config":
                    self.abrir_config()
                elif cmd == "salir":
                    self.tray.stop()
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(300, self._procesar_cola)

    # ----- programacion -----
    def _hora(self):
        h, m = (int(x) for x in self.cfg["hora"].split(":"))
        return h, m

    def _proxima(self):
        h, m = self._hora()
        ahora = dt.datetime.now()
        for i in range(8):
            d = (ahora + dt.timedelta(days=i)).replace(hour=h, minute=m, second=0, microsecond=0)
            if d.weekday() in self.cfg["dias"] and d > ahora:
                return d
        return None

    def _proxima_txt(self):
        p = self._proxima()
        return p.strftime("%a %d/%m %H:%M") if p else "sin dias elegidos"

    def _tick(self):
        """Cada 30 s: si ya paso la hora de hoy y no se ha ejecutado hoy, ejecuta.
        Asi, si el PC estaba apagado a esa hora, sube al encenderlo."""
        try:
            h, m = self._hora()
            ahora = dt.datetime.now()
            hoy = ahora.date().isoformat()
            if (ahora.weekday() in self.cfg["dias"]
                    and (ahora.hour, ahora.minute) >= (h, m)
                    and self.cfg.get("ultima_ejecucion") != hoy):
                self.lanzar_subida(programada=True)
        except Exception as e:
            log(f"Error en programador: {e}")
        self.root.after(30_000, self._tick)

    # ----- subida -----
    def lanzar_subida(self, programada=False):
        if not self.ocupado.acquire(blocking=False):
            return
        if programada:
            self.cfg["ultima_ejecucion"] = dt.date.today().isoformat()
            config.guardar(self.cfg)
        threading.Thread(target=self._subir, daemon=True).start()

    def _set_estado(self, txt, ico):
        self.estado = txt
        self.tray.icon = ICONOS[ico]
        self.tray.title = f"{APP_NAME}: {txt}"
        self.tray.update_menu()

    def _subir(self):
        try:
            self._set_estado("Subiendo...", "subiendo")
            log("Subida iniciada")
            n, err = uploader.ejecutar(dict(self.cfg),
                                       lambda msg: self._set_estado(msg[:60], "subiendo"))
            fin = dt.datetime.now().strftime("%H:%M")
            if err:
                self._set_estado(f"{n} subidos, {err} errores ({fin})", "error")
                self.tray.notify(f"{n} archivos subidos, {err} con error. Revisa el registro.",
                                 APP_NAME)
            else:
                self._set_estado(f"{n} subidos ({fin})", "ok")
                if n:
                    self.tray.notify(f"{n} archivos subidos a Drive y borrados del PC.", APP_NAME)
            log(f"Subida terminada: {n} ok, {err} errores")
        except uploader.SinCredenciales as e:
            self._set_estado("Falta iniciar sesion", "error")
            self.tray.notify(str(e), APP_NAME)
            log(str(e))
        except Exception as e:
            self._set_estado("Error", "error")
            log(f"Error en subida: {e}")
        finally:
            self.ocupado.release()

    # ----- ventana configuracion -----
    def abrir_config(self):
        if self.ventana and self.ventana.winfo_exists():
            self.ventana.lift()
            return
        w = self.ventana = tk.Toplevel(self.root)
        w.title(f"{APP_NAME} {VERSION} - Configuracion")
        w.resizable(False, False)
        f = ttk.Frame(w, padding=14)
        f.pack(fill="both")

        ttk.Label(f, text="Carpetas del PC a subir:").grid(row=0, column=0, sticky="w")
        lista = tk.Listbox(f, width=60, height=5)
        for c in self.cfg["carpetas"]:
            lista.insert("end", c)
        lista.grid(row=1, column=0, columnspan=3, pady=4)

        def agregar():
            d = filedialog.askdirectory(parent=w)
            if d:
                lista.insert("end", os.path.normpath(d))

        ttk.Button(f, text="Agregar carpeta", command=agregar).grid(row=2, column=0, sticky="w")
        ttk.Button(f, text="Quitar seleccionada",
                   command=lambda: [lista.delete(i) for i in reversed(lista.curselection())]
                   ).grid(row=2, column=1, sticky="w")

        ttk.Label(f, text="Carpeta destino en Drive:").grid(row=3, column=0, sticky="w", pady=(12, 0))
        destino = tk.StringVar(value=self.cfg["carpeta_drive"])
        ttk.Entry(f, textvariable=destino, width=30).grid(row=3, column=1, columnspan=2,
                                                         sticky="w", pady=(12, 0))

        ttk.Label(f, text="Hora de subida (HH:MM):").grid(row=4, column=0, sticky="w", pady=(8, 0))
        hh, mm = self.cfg["hora"].split(":")
        hf = ttk.Frame(f)
        hf.grid(row=4, column=1, columnspan=2, sticky="w", pady=(8, 0))
        hv = tk.StringVar(value=hh)
        mv = tk.StringVar(value=mm)
        ttk.Spinbox(hf, from_=0, to=23, width=4, textvariable=hv, format="%02.0f",
                    wrap=True).pack(side="left")
        ttk.Label(hf, text=":").pack(side="left")
        ttk.Spinbox(hf, from_=0, to=59, width=4, textvariable=mv, format="%02.0f",
                    wrap=True).pack(side="left")

        ttk.Label(f, text="Dias:").grid(row=5, column=0, sticky="w", pady=(8, 0))
        df = ttk.Frame(f)
        df.grid(row=5, column=1, columnspan=2, sticky="w", pady=(8, 0))
        dvars = []
        for i, nom in enumerate(DIAS):
            v = tk.BooleanVar(value=i in self.cfg["dias"])
            ttk.Checkbutton(df, text=nom, variable=v).pack(side="left")
            dvars.append(v)

        borrar = tk.BooleanVar(value=self.cfg.get("borrar", True))
        ttk.Checkbutton(f, text="Borrar del PC despues de subir (solo si la copia se verifica)",
                        variable=borrar).grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))
        inicio = tk.BooleanVar(value=inicio_activo())
        ttk.Checkbutton(f, text="Abrir al iniciar Windows", variable=inicio
                        ).grid(row=7, column=0, columnspan=3, sticky="w")

        # credenciales
        ttk.Separator(f).grid(row=8, column=0, columnspan=3, sticky="ew", pady=10)
        cred_txt = tk.StringVar()

        def refrescar_cred():
            if not uploader.CREDENTIALS.exists():
                cred_txt.set("Google: falta credentials.json")
            elif not uploader.TOKEN.exists():
                cred_txt.set("Google: credenciales cargadas, falta iniciar sesion")
            else:
                cred_txt.set("Google: conectado")

        refrescar_cred()
        ttk.Label(f, textvariable=cred_txt).grid(row=9, column=0, columnspan=3, sticky="w")

        def cargar_cred():
            p = filedialog.askopenfilename(parent=w, filetypes=[("JSON", "*.json")])
            if p:
                uploader.importar_credenciales(p)
                refrescar_cred()

        def login():
            def t():
                try:
                    uploader.conectar(interactivo=True)
                    log("Sesion de Google iniciada")
                except Exception as e:
                    log(f"Error al iniciar sesion: {e}")
                    self.root.after(0, lambda: messagebox.showerror(APP_NAME, str(e), parent=w))
                self.root.after(0, refrescar_cred)
            threading.Thread(target=t, daemon=True).start()

        bf = ttk.Frame(f)
        bf.grid(row=10, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Button(bf, text="Cargar credentials.json", command=cargar_cred).pack(side="left")
        ttk.Button(bf, text="Iniciar sesion en Google", command=login).pack(side="left", padx=6)

        def guardar():
            try:
                h, m = int(hv.get()), int(mv.get())
                assert 0 <= h < 24 and 0 <= m < 60
            except Exception:
                messagebox.showerror(APP_NAME, "Hora invalida.", parent=w)
                return
            nueva = f"{h:02d}:{m:02d}"
            if nueva != self.cfg["hora"]:
                # si se cambia la hora, permitir que corra hoy a la nueva hora
                self.cfg["ultima_ejecucion"] = ""
                if (dt.datetime.now().hour, dt.datetime.now().minute) >= (h, m):
                    self.cfg["ultima_ejecucion"] = dt.date.today().isoformat()
            self.cfg.update({
                "carpetas": list(lista.get(0, "end")),
                "carpeta_drive": destino.get().strip() or "Productos",
                "hora": nueva,
                "dias": [i for i, v in enumerate(dvars) if v.get()],
                "borrar": borrar.get(),
            })
            config.guardar(self.cfg)
            set_inicio(inicio.get())
            self.tray.update_menu()
            w.destroy()

        af = ttk.Frame(f)
        af.grid(row=11, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(af, text="Guardar", command=guardar).pack(side="right")
        ttk.Button(af, text="Cancelar", command=w.destroy).pack(side="right", padx=6)

    def run(self):
        self.root.mainloop()


def _instancia_unica():
    try:
        import ctypes
        ctypes.windll.kernel32.CreateMutexW(None, False, f"Global\\{APP_NAME}_mutex")
        return ctypes.windll.kernel32.GetLastError() != 183
    except Exception:
        return True


if __name__ == "__main__":
    if not _instancia_unica():
        sys.exit(0)
    App().run()
