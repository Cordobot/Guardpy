<p align="center"><img src="assets/logo-readme.png" width="96" alt=""></p>

<h1 align="center">Guardpy</h1>
<p align="center">Guarda tus carpetas en Google Drive a la hora que elijas y libera espacio en tu PC.</p>

<p align="center"><a href="../../releases/latest"><b>⬇ Descargar Guardpy para Windows</b></a></p>

---

## Qué hace
- **Copia automática**: a la hora y los días que elijas, sube tus carpetas a Google Drive.
- **Libera espacio**: borra los archivos del PC **solo si la copia en Drive es idéntica** (se verifica cada archivo).
- **No se le escapa nada**: si el PC estaba apagado a esa hora, hace la copia al encenderlo.
- **No interrumpe**: no toca archivos que estés usando o que se estén grabando (por ejemplo, clips de Medal).
- **Siempre a mano**: se abre con Windows y queda junto al reloj. Doble clic en el ícono para abrirlo.
- Diseño de Windows 11, en modo claro u oscuro según tu sistema.

En Drive tus archivos quedan en `Productos/<nombre de la carpeta>/…` (puedes cambiar el nombre).

## Instalación
1. Descarga `Guardpy-Setup-x.y.z.exe` desde [la última versión](../../releases/latest) y ábrelo.
2. Si aparece **"Windows protegió su PC"**, pulsa **Más información → Ejecutar de todas formas**. Ocurre porque el instalador no tiene firma digital.
3. Abre Guardpy y conecta tu cuenta de Google.

Si tenías la versión anterior (DriveAutoUpload), Guardpy la reemplaza y conserva tu configuración.

## Conectar Google
Si Guardpy te pide un **archivo de Google**, créalo una sola vez:

1. Entra a <https://console.cloud.google.com> y crea un proyecto (cualquier nombre, por ejemplo "Guardpy").
2. Ve a **APIs y servicios → Biblioteca**, busca **Google Drive API** y pulsa **Habilitar**.
3. Ve a **APIs y servicios → Pantalla de consentimiento de OAuth**: tipo **Externo**, nombre "Guardpy", tu correo. Guarda.
   Luego pulsa **Publicar app** (así no te pedirá iniciar sesión de nuevo cada 7 días).
4. Ve a **Credenciales → Crear credenciales → ID de cliente de OAuth**, tipo **App de escritorio** → **Crear** → **Descargar JSON**.
5. En Guardpy pulsa **Elegir archivo de Google…**, selecciona ese archivo y luego inicia sesión en el navegador.
   Google mostrará "Google no verificó esta app": pulsa **Configuración avanzada → Ir a Guardpy**. Es normal, porque la app es tuya.

## Para desarrolladores
Al cambiar el número en `VERSION` y subirlo a `main`, GitHub Actions compila Guardpy, toma capturas de la interfaz y publica el instalador en Releases.

Opcional: si guardas el contenido del JSON del paso 4 en el secreto del repositorio `GOOGLE_CLIENT_JSON`, el instalador lo incluye y los usuarios solo tienen que pulsar **Conectar con Google**.

Compilar en Windows:
```
pip install -r requirements.txt pyinstaller
python assets/make_icon.py
pyinstaller --noconfirm --windowed --name Guardpy --icon assets/icon.ico --paths src --collect-data googleapiclient --collect-data sv_ttk --collect-all pywinstyles --add-data "VERSION;." src/main.py
iscc installer\Guardpy.iss
```
