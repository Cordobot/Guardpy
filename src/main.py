"""Guardpy - guarda tus carpetas en Google Drive a la hora que elijas
y libera espacio en el PC despues de verificar cada copia."""
import datetime as dt
import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pystray
import sv_ttk
from PIL import Image, ImageDraw, ImageTk

import config
import uploader
from config import APP_NAME, VERSION, log

try:
    import darkdetect
except Exception:  # pragma: no cover
    darkdetect = None

DIAS = ["L", "M", "X", "J", "V", "S", "D"]
DIAS_LARGO = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AYUDA_URL = "https://github.com/Cordobot/Guardpy#conectar-google"
FUENTE = "Segoe UI Variable Text"
FUENTE_T = "Segoe UI Variable Display"


# ---------------- inicio con Windows ----------------
def _exe_cmd():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --oculto'
    return f'"{sys.executable}" "{os.path.abspath(__file__)}" --oculto'


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
            try:  # limpiar entrada de la version anterior
                winreg.DeleteValue(k, "DriveAutoUpload")
            except FileNotFoundError:
                pass
    except Exception as e:
        log(f"No se pudo cambiar inicio con Windows: {e}")


# ---------------- iconos ----------------
def logo(size, color="#2563eb", badge=None):
    """Escudo con flecha hacia arriba."""
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = s
    escudo = [(w * .5, w * .04), (w * .9, w * .18), (w * .88, w * .52), (w * .5, w * .96),
              (w * .12, w * .52), (w * .1, w * .18)]
    d.polygon(escudo, fill=color)
    d.polygon([(w * .5, w * .24), (w * .72, w * .5), (w * .58, w * .5), (w * .58, w * .74),
               (w * .42, w * .74), (w * .42, w * .5), (w * .28, w * .5)], fill="white")
    if badge:
        d.ellipse((w * .6, w * .6, w * .98, w * .98), fill=badge, outline="white", width=s // 20)
    return img.resize((size, size), Image.LANCZOS)


TRAY = {
    "ok": logo(64),
    "subiendo": logo(64, badge="#f59e0b"),
    "error": logo(64, badge="#dc2626"),
}


def es_oscuro():
    forzado = os.environ.get("GUARDPY_THEME")
    if forzado:
        return forzado == "dark"
    try:
        return darkdetect is not None and darkdetect.isDark()
    except Exception:
        return False


def fmt_fecha(d):
    hoy = dt.date.today()
    if d.date() == hoy:
        dia = "hoy"
    elif d.date() == hoy + dt.timedelta(days=1):
        dia = "mañana"
    else:
        dia = DIAS_LARGO[d.weekday()]
    return f"{dia} a las {d.strftime('%I:%M %p').lstrip('0').lower()}"


class App:
    def __init__(self, oculto=False, selftest=None):
        self.cfg = config.cargar()
        self.ocupado = threading.Lock()
        self.cola = queue.Queue()
        self.subiendo = False
        self.selftest = selftest

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.minsize(560, 600)
        self._icono_ventana()
        sv_ttk.set_theme("dark" if es_oscuro() else "light")
        self._estilos()
        self._construir()
        self.root.protocol("WM_DELETE_WINDOW", self.ocultar)
        self.root.update_idletasks()
        self._barra_titulo()

        self.tray = pystray.Icon(APP_NAME, TRAY["ok"], APP_NAME, self._menu())
        if not selftest:
            self.tray.run_detached()

        self.root.after(300, self._procesar_cola)
        self.root.after(1000, self._tick)
        self.root.after(20_000, self._refrescar_estado_periodico)

        primera = not uploader.conectado()
        if oculto and not primera:
            self.root.withdraw()
        log(f"Iniciado v{VERSION}")
        if selftest:
            self.root.after(2500, self._captura)

    # ---------------- apariencia ----------------
    def _icono_ventana(self):
        self._ico_imgs = [ImageTk.PhotoImage(logo(s)) for s in (16, 32, 48, 64)]
        self.root.iconphoto(True, *self._ico_imgs)
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Cordobot.Guardpy")
        except Exception:
            pass

    def _barra_titulo(self):
        """Barra de titulo oscura/clara como Windows 11."""
        try:
            import pywinstyles
            if es_oscuro():
                pywinstyles.apply_style(self.root, "dark")
            else:
                pywinstyles.apply_style(self.root, "light")
        except Exception:
            pass

    def _estilos(self):
        st = ttk.Style()
        oscuro = es_oscuro()
        self.c_sub = "#a1a1aa" if oscuro else "#5f6368"
        self.c_ok = "#4ade80" if oscuro else "#15803d"
        self.c_err = "#f87171" if oscuro else "#b91c1c"
        self.c_link = "#60a5fa" if oscuro else "#2563eb"
        st.configure("Titulo.TLabel", font=(FUENTE_T, 22, "bold"))
        st.configure("Seccion.TLabel", font=(FUENTE_T, 13, "bold"))
        st.configure("Texto.TLabel", font=(FUENTE, 10))
        st.configure("Sub.TLabel", font=(FUENTE, 9), foreground=self.c_sub)
        st.map("Sub.TLabel", foreground=[("!disabled", self.c_sub)])
        st.configure("Estado.TLabel", font=(FUENTE, 11))
        st.configure("Ok.TLabel", font=(FUENTE, 10, "bold"), foreground=self.c_ok)
        st.configure("Err.TLabel", font=(FUENTE, 10, "bold"), foreground=self.c_err)
        st.configure("Carpeta.TLabel", font=(FUENTE, 10, "bold"))
        st.configure("Link.TLabel", font=(FUENTE, 9, "underline"),
                     foreground="#60a5fa" if oscuro else "#2563eb")
        st.configure("Grande.Accent.TButton", font=(FUENTE, 11, "bold"), padding=(18, 8))
        st.configure("TButton", font=(FUENTE, 10))
        st.configure("TCheckbutton", font=(FUENTE, 10))

    # ---------------- construccion ----------------
    def _construir(self):
        r = self.root
        alto = min(800, r.winfo_screenheight() - 90)
        r.geometry(f"600x{alto}")
        cont = ttk.Frame(r)
        cont.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(cont, highlightthickness=0, bd=0,
                                bg=ttk.Style().lookup("TFrame", "background"))
        sb = ttk.Scrollbar(cont, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        outer = ttk.Frame(self.canvas, padding=(24, 20, 20, 16))
        win = self.canvas.create_window((0, 0), window=outer, anchor="nw")
        outer.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(win, width=e.width))
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(
            int(-e.delta / 120), "units") if self.canvas.winfo_height() < outer.winfo_height() else None)

        # Cabecera
        cab = ttk.Frame(outer)
        cab.pack(fill="x")
        self._logo_img = ImageTk.PhotoImage(logo(52))
        ttk.Label(cab, image=self._logo_img).pack(side="left", padx=(0, 14))
        tf = ttk.Frame(cab)
        tf.pack(side="left", fill="x", expand=True)
        ttk.Label(tf, text=APP_NAME, style="Titulo.TLabel").pack(anchor="w")
        self.lbl_estado = ttk.Label(tf, text="", style="Estado.TLabel")
        self.lbl_estado.pack(anchor="w")
        self.btn_subir = ttk.Button(cab, text="Guardar ahora", style="Grande.Accent.TButton",
                                    command=self.lanzar_subida)
        self.btn_subir.pack(side="right")

        self.prog = ttk.Progressbar(outer, mode="indeterminate")
        self.lbl_prog = ttk.Label(outer, text="", style="Sub.TLabel")
        self.prog_anchor = ttk.Frame(outer, height=12)
        self.prog_anchor.pack(fill="x")

        # 1. Cuenta
        c1 = self._tarjeta(outer, "Cuenta de Google")
        fila = ttk.Frame(c1)
        fila.pack(fill="x")
        self.lbl_cuenta = ttk.Label(fila, text="", style="Texto.TLabel")
        self.lbl_cuenta.pack(side="left")
        self.btn_cuenta = ttk.Button(fila, text="", command=self._accion_cuenta)
        self.btn_cuenta.pack(side="right")
        self.lbl_cuenta_ayuda = ttk.Label(c1, text="", style="Sub.TLabel", wraplength=480,
                                          justify="left")
        self.lbl_cuenta_ayuda.pack(anchor="w", pady=(6, 0))
        self.lnk_ayuda = ttk.Label(c1, text="Cómo obtener el archivo de Google (paso a paso)",
                                   style="Link.TLabel", cursor="hand2", foreground=self.c_link)
        self.lnk_ayuda.bind("<Button-1>", lambda e: webbrowser.open(AYUDA_URL))

        # 2. Carpetas
        c2 = self._tarjeta(outer, "Carpetas que se guardan")
        self.frm_carpetas = ttk.Frame(c2)
        self.frm_carpetas.pack(fill="x")
        pie = ttk.Frame(c2)
        pie.pack(fill="x", pady=(8, 0))
        ttk.Button(pie, text="+  Agregar carpeta", command=self._agregar_carpeta).pack(side="left")
        dd = ttk.Frame(pie)
        dd.pack(side="right")
        ttk.Label(dd, text="En Drive:", style="Sub.TLabel").pack(side="left", padx=(0, 6))
        self.var_destino = tk.StringVar(value=self.cfg["carpeta_drive"])
        e = ttk.Entry(dd, textvariable=self.var_destino, width=16)
        e.pack(side="left")
        e.bind("<FocusOut>", lambda ev: self._guardar())
        e.bind("<Return>", lambda ev: self._guardar())

        # 3. Horario
        c3 = self._tarjeta(outer, "Cuándo guardar")
        hf = ttk.Frame(c3)
        hf.pack(fill="x")
        ttk.Label(hf, text="Hora", style="Texto.TLabel").pack(side="left")
        h, m = self.cfg["hora"].split(":")
        h = int(h)
        self.var_h = tk.StringVar(value=str(h % 12 or 12))
        self.var_m = tk.StringVar(value=m)
        self.var_ampm = tk.StringVar(value="a. m." if h < 12 else "p. m.")
        for var, vals, wdt in ((self.var_h, [str(i) for i in range(1, 13)], 4),
                               (self.var_m, [f"{i:02d}" for i in range(0, 60, 5)], 4),
                               (self.var_ampm, ["a. m.", "p. m."], 6)):
            cb = ttk.Combobox(hf, textvariable=var, values=vals, width=wdt, state="readonly")
            cb.pack(side="left", padx=(10 if var is self.var_h else 4, 0))
            cb.bind("<<ComboboxSelected>>", lambda ev: self._guardar(cambio_hora=True))
        df = ttk.Frame(c3)
        df.pack(fill="x", pady=(12, 0))
        ttk.Label(df, text="Días", style="Texto.TLabel").pack(side="left", padx=(0, 10))
        self.var_dias = []
        for i, nom in enumerate(DIAS):
            v = tk.BooleanVar(value=i in self.cfg["dias"])
            ttk.Checkbutton(df, text=nom, variable=v, style="Toggle.TButton", width=2,
                            command=self._guardar).pack(side="left", padx=2)
            self.var_dias.append(v)
        ttk.Label(c3, text="Si el PC está apagado a esa hora, Guardpy lo hará al encenderlo.",
                  style="Sub.TLabel").pack(anchor="w", pady=(10, 0))

        # 4. Opciones
        c4 = self._tarjeta(outer, "Opciones")
        self.var_borrar = tk.BooleanVar(value=self.cfg.get("borrar", True))
        ttk.Checkbutton(c4, text="Liberar espacio: borrar del PC después de guardar en Drive",
                        variable=self.var_borrar, style="Switch.TCheckbutton",
                        command=self._guardar).pack(anchor="w")
        ttk.Label(c4, text="Solo se borra si la copia en Drive es idéntica.",
                  style="Sub.TLabel").pack(anchor="w", padx=(46, 0))
        self.var_inicio = tk.BooleanVar(value=inicio_activo())
        ttk.Checkbutton(c4, text="Abrir Guardpy al iniciar Windows", variable=self.var_inicio,
                        style="Switch.TCheckbutton",
                        command=lambda: (set_inicio(self.var_inicio.get()))
                        ).pack(anchor="w", pady=(8, 0))

        # Pie
        pie = ttk.Frame(outer)
        pie.pack(fill="x", pady=(16, 0))
        lr = ttk.Label(pie, text="Ver historial", style="Link.TLabel", cursor="hand2",
                       foreground=self.c_link)
        lr.pack(side="left")
        lr.bind("<Button-1>", lambda e: self._abrir_registro())
        ttk.Label(pie, text=f"Versión {VERSION}", style="Sub.TLabel").pack(side="right")

        self._pintar_carpetas()
        self._refrescar_cuenta()
        self._refrescar_estado()

    def _tarjeta(self, padre, titulo):
        ttk.Label(padre, text=titulo, style="Seccion.TLabel").pack(anchor="w", pady=(12, 5))
        card = ttk.Frame(padre, style="Card.TFrame", padding=(16, 12))
        card.pack(fill="x")
        return card

    # ---------------- carpetas ----------------
    def _pintar_carpetas(self):
        for w in self.frm_carpetas.winfo_children():
            w.destroy()
        if not self.cfg["carpetas"]:
            ttk.Label(self.frm_carpetas, text="Aún no has elegido carpetas.",
                      style="Sub.TLabel").pack(anchor="w")
        for i, ruta in enumerate(self.cfg["carpetas"]):
            fila = ttk.Frame(self.frm_carpetas)
            fila.pack(fill="x", pady=3)
            txt = ttk.Frame(fila)
            txt.pack(side="left", fill="x", expand=True)
            p = Path(ruta)
            existe = p.is_dir()
            ttk.Label(txt, text=("🗀  " if existe else "⚠  ") + p.name,
                      style="Carpeta.TLabel").pack(anchor="w")
            ttk.Label(txt, text=str(p) if existe else f"{p}  (no existe, se creará)",
                      style="Sub.TLabel").pack(anchor="w")
            ttk.Button(fila, text="Quitar", command=lambda i=i: self._quitar_carpeta(i)
                       ).pack(side="right")

    def _agregar_carpeta(self):
        d = filedialog.askdirectory(parent=self.root, title="Elige una carpeta para guardar en Drive")
        if d:
            d = os.path.normpath(d)
            if "onedrive" in d.lower():
                if not messagebox.askyesno(
                        APP_NAME, "Esta carpeta está en OneDrive. Si Guardpy borra los archivos, "
                        "también se borrarán de OneDrive.\n\n¿Agregarla de todas formas?",
                        parent=self.root):
                    return
            if d not in self.cfg["carpetas"]:
                self.cfg["carpetas"].append(d)
                self._guardar()
                self._pintar_carpetas()

    def _quitar_carpeta(self, i):
        del self.cfg["carpetas"][i]
        self._guardar()
        self._pintar_carpetas()

    # ---------------- cuenta ----------------
    def _refrescar_cuenta(self):
        self.lnk_ayuda.pack_forget()
        if uploader.conectado():
            self.lbl_cuenta.config(text="●  Conectado a Google Drive", style="Ok.TLabel",
                                   foreground=self.c_ok)
            self.btn_cuenta.config(text="Desconectar", style="TButton")
            self.lbl_cuenta_ayuda.config(text="")
        elif uploader.cliente_oauth():
            self.lbl_cuenta.config(text="●  Sin conectar", style="Err.TLabel",
                                   foreground=self.c_err)
            self.btn_cuenta.config(text="Conectar con Google", style="Accent.TButton")
            self.lbl_cuenta_ayuda.config(
                text="Se abrirá tu navegador para que inicies sesión y des permiso a Guardpy.")
        else:
            self.lbl_cuenta.config(text="●  Sin conectar", style="Err.TLabel",
                                   foreground=self.c_err)
            self.btn_cuenta.config(text="Elegir archivo de Google...", style="Accent.TButton")
            self.lbl_cuenta_ayuda.config(
                text="Para conectar, Guardpy necesita el archivo de credenciales que "
                     "descargas una sola vez desde Google Cloud.")
            self.lnk_ayuda.pack(anchor="w", pady=(4, 0))

    def _accion_cuenta(self):
        if uploader.conectado():
            if messagebox.askyesno(APP_NAME, "¿Desconectar tu cuenta de Google?", parent=self.root):
                uploader.desconectar()
                self._refrescar_cuenta()
                self._refrescar_estado()
            return
        if not uploader.cliente_oauth():
            p = filedialog.askopenfilename(parent=self.root, title="Elige el archivo de Google",
                                           filetypes=[("Archivo de credenciales", "*.json")])
            if not p:
                return
            uploader.importar_credenciales(p)
        self.btn_cuenta.config(text="Esperando al navegador...", state="disabled")

        def t():
            try:
                uploader.conectar(interactivo=True)
                log("Cuenta de Google conectada")
                self.cola.put(("ui", lambda: self._notificar("Cuenta de Google conectada.")))
            except Exception as e:
                log(f"Error al conectar: {e}")
                self.cola.put(("ui", lambda: messagebox.showerror(
                    APP_NAME, f"No se pudo conectar:\n{e}", parent=self.root)))
            self.cola.put(("ui", lambda: (self.btn_cuenta.config(state="normal"),
                                          self._refrescar_cuenta(), self._refrescar_estado())))
        threading.Thread(target=t, daemon=True).start()

    # ---------------- guardar config ----------------
    def _hora_24(self):
        h = int(self.var_h.get()) % 12
        if self.var_ampm.get().startswith("p"):
            h += 12
        return h, int(self.var_m.get())

    def _guardar(self, cambio_hora=False):
        h, m = self._hora_24()
        nueva = f"{h:02d}:{m:02d}"
        if cambio_hora and nueva != self.cfg["hora"]:
            ahora = dt.datetime.now()
            self.cfg["ultima_ejecucion"] = (dt.date.today().isoformat()
                                            if (ahora.hour, ahora.minute) >= (h, m) else "")
        self.cfg.update({
            "carpeta_drive": self.var_destino.get().strip() or "Productos",
            "hora": nueva,
            "dias": [i for i, v in enumerate(self.var_dias) if v.get()],
            "borrar": self.var_borrar.get(),
        })
        config.guardar(self.cfg)
        self._refrescar_estado()

    # ---------------- estado ----------------
    def _proxima(self):
        h, m = (int(x) for x in self.cfg["hora"].split(":"))
        ahora = dt.datetime.now()
        hecho_hoy = self.cfg.get("ultima_ejecucion") == ahora.date().isoformat()
        for i in range(8):
            d = (ahora + dt.timedelta(days=i)).replace(hour=h, minute=m, second=0, microsecond=0)
            if d.weekday() not in self.cfg["dias"]:
                continue
            if i == 0 and (hecho_hoy or d <= ahora):
                if not hecho_hoy:
                    return ahora
                continue
            return d
        return None

    def _texto_estado(self):
        if self.subiendo:
            return "Guardando en Drive..."
        if not uploader.conectado():
            return "Conecta tu cuenta de Google para empezar"
        if not self.cfg["carpetas"]:
            return "Agrega una carpeta para empezar"
        p = self._proxima()
        if not p:
            return "Elige al menos un día"
        return f"Próxima copia: {fmt_fecha(p)}"

    def _refrescar_estado(self):
        txt = self._texto_estado()
        self.lbl_estado.config(text=txt)
        try:
            self.tray.title = f"{APP_NAME} - {txt}"
            self.tray.update_menu()
        except Exception:
            pass
        ultimo = self.cfg.get("ultimo_resultado")
        if ultimo and not self.subiendo:
            self.lbl_prog.config(text=ultimo)
            self.lbl_prog.pack(after=self.prog_anchor, anchor="w")
        self.btn_subir.config(state="disabled" if self.subiendo else "normal")

    def _refrescar_estado_periodico(self):
        self._refrescar_estado()
        self.root.after(20_000, self._refrescar_estado_periodico)

    # ---------------- bandeja ----------------
    def _menu(self):
        return pystray.Menu(
            pystray.MenuItem("Abrir Guardpy", lambda: self.cola.put(("mostrar",)), default=True),
            pystray.MenuItem(lambda _: self._texto_estado(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Guardar ahora", lambda: self.cola.put(("subir",))),
            pystray.MenuItem("Ver historial", lambda: self.cola.put(("registro",))),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir de Guardpy", lambda: self.cola.put(("salir",))),
        )

    def mostrar(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def ocultar(self):
        self._guardar()
        self.root.withdraw()
        if not self.cfg.get("aviso_bandeja"):
            self._notificar("Guardpy sigue funcionando junto al reloj. "
                            "Haz doble clic en el ícono para abrirlo.")
            self.cfg["aviso_bandeja"] = True
            config.guardar(self.cfg)

    def _abrir_registro(self):
        if config.LOG_FILE.exists():
            os.startfile(config.LOG_FILE)
        else:
            messagebox.showinfo(APP_NAME, "Todavía no hay historial.", parent=self.root)

    def _notificar(self, msg):
        try:
            self.tray.notify(msg, APP_NAME)
        except Exception:
            pass

    def _procesar_cola(self):
        try:
            while True:
                cmd = self.cola.get_nowait()
                if cmd[0] == "subir":
                    self.lanzar_subida()
                elif cmd[0] == "mostrar":
                    self.mostrar()
                elif cmd[0] == "registro":
                    self._abrir_registro()
                elif cmd[0] == "ui":
                    cmd[1]()
                elif cmd[0] == "salir":
                    self.tray.stop()
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(200, self._procesar_cola)

    # ---------------- programacion y subida ----------------
    def _tick(self):
        try:
            h, m = (int(x) for x in self.cfg["hora"].split(":"))
            ahora = dt.datetime.now()
            if (ahora.weekday() in self.cfg["dias"]
                    and (ahora.hour, ahora.minute) >= (h, m)
                    and self.cfg.get("ultima_ejecucion") != ahora.date().isoformat()
                    and uploader.conectado()):
                self.lanzar_subida(programada=True)
        except Exception as e:
            log(f"Error en programador: {e}")
        self.root.after(30_000, self._tick)

    def lanzar_subida(self, programada=False):
        if not uploader.conectado():
            self.mostrar()
            messagebox.showinfo(APP_NAME, "Primero conecta tu cuenta de Google.", parent=self.root)
            return
        if not self.ocupado.acquire(blocking=False):
            return
        if programada:
            self.cfg["ultima_ejecucion"] = dt.date.today().isoformat()
            config.guardar(self.cfg)
        self.subiendo = True
        self.tray.icon = TRAY["subiendo"]
        self.prog.pack(after=self.prog_anchor, fill="x", pady=(0, 4))
        self.lbl_prog.config(text="Preparando...")
        self.lbl_prog.pack(after=self.prog, anchor="w")
        self.prog.start(12)
        self._refrescar_estado()
        threading.Thread(target=self._subir, daemon=True).start()

    def _subir(self):
        ico, msg, resultado = "ok", None, ""
        try:
            log("Copia iniciada")
            n, err = uploader.ejecutar(
                dict(self.cfg),
                lambda t: self.cola.put(("ui", lambda t=t: self.lbl_prog.config(text=t))))
            hora = dt.datetime.now().strftime("%I:%M %p").lstrip("0").lower()
            if err:
                ico = "error"
                resultado = f"Última copia ({hora}): {n} guardados, {err} con error"
                msg = f"{n} archivos guardados, {err} con error. Abre el historial para ver detalles."
            else:
                resultado = (f"Última copia ({hora}): {n} archivos guardados en Drive"
                             if n else f"Última copia ({hora}): no había archivos nuevos")
                if n:
                    msg = f"{n} archivos guardados en Google Drive."
            log(f"Copia terminada: {n} ok, {err} errores")
        except uploader.SinCredenciales as e:
            ico, msg, resultado = "error", str(e), "No se pudo copiar: falta conectar Google"
            log(str(e))
        except Exception as e:
            ico, msg, resultado = "error", "Hubo un error al guardar. Revisa tu conexión a internet.", \
                f"Error en la última copia: {e}"
            log(f"Error en copia: {e}")
        finally:
            self.cfg["ultimo_resultado"] = resultado
            config.guardar(self.cfg)
            self.subiendo = False
            self.tray.icon = TRAY[ico]
            self.ocupado.release()

            def fin():
                self.prog.stop()
                self.prog.pack_forget()
                self._refrescar_estado()
            self.cola.put(("ui", fin))
            if msg:
                self._notificar(msg)

    # ---------------- prueba automatica (CI) ----------------
    def _captura(self):
        try:
            from PIL import ImageGrab
            self.root.update()
            x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
            w, h = self.root.winfo_width(), self.root.winfo_height()
            ImageGrab.grab(bbox=(x - 8, y - 32, x + w + 8, y + h + 8)).save(self.selftest)
            print("captura ok", self.selftest)
        except Exception as e:
            print("captura error", e)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def _instancia_unica():
    try:
        import ctypes
        ctypes.windll.kernel32.CreateMutexW(None, False, f"Local\\{APP_NAME}_mutex")
        return ctypes.windll.kernel32.GetLastError() != 183
    except Exception:
        return True


if __name__ == "__main__":
    selftest = None
    if "--selftest" in sys.argv:
        selftest = sys.argv[sys.argv.index("--selftest") + 1]
    elif not _instancia_unica():
        sys.exit(0)
    try:  # nitidez en pantallas con escalado
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    App(oculto="--oculto" in sys.argv, selftest=selftest).run()
