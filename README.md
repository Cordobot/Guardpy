# DriveAutoUpload

Programa de Windows que, a la hora que elijas, sube a Google Drive los archivos de tus carpetas y **los borra del PC solo después de verificar** (MD5) que la copia en Drive es idéntica.

- Se abre al iniciar Windows y vive en la bandeja del sistema (junto al reloj).
- Hora y días configurables. Si el PC estaba apagado a esa hora, sube al encenderlo.
- Botón **Subir ahora** en el menú del ícono.
- No toca archivos que se estén usando o que hayan cambiado hace menos de 30 s (por ejemplo, un clip que Medal aún graba).
- Respeta subcarpetas: `Drive/Productos/<nombre carpeta>/...`
- Registro en `%APPDATA%\DriveAutoUpload\registro.log`.

Carpetas por defecto: `C:\Users\<tú>\Desarrollo` y `C:\Users\<tú>\Videos\Medal`.

## Instalación
1. Descarga `DriveAutoUpload-Setup-x.y.z.exe` desde [Releases](../../releases/latest) y ejecútalo.
   Si Windows muestra "Windows protegió su PC", pulsa **Más información → Ejecutar de todas formas** (el instalador no está firmado).
2. Al abrirse por primera vez aparece la ventana de configuración.

## Conectar Google (una sola vez)
1. Entra a https://console.cloud.google.com y crea un proyecto.
2. **APIs y servicios → Biblioteca** → activa **Google Drive API**.
3. **Pantalla de consentimiento OAuth** → tipo *Externo* → agrega tu correo como *usuario de prueba*.
4. **Credenciales → Crear credenciales → ID de cliente OAuth** → tipo **App de escritorio** → descarga el JSON.
5. En DriveAutoUpload: **Cargar credentials.json** → **Iniciar sesión en Google**.

> Mientras la app esté "en pruebas" en Google Cloud, Google puede pedir volver a iniciar sesión cada 7 días. Para evitarlo, en la pantalla de consentimiento pulsa **Publicar app** (no requiere verificación para uso personal; solo verás un aviso de "app no verificada" al iniciar sesión).

## Compilar desde el código
Los instaladores se generan solos con GitHub Actions al crear un tag `vX.Y.Z`.
Localmente (Windows):
```
pip install -r requirements.txt pyinstaller
python assets/make_icon.py
pyinstaller --noconfirm --windowed --name DriveAutoUpload --icon assets/icon.ico --paths src --collect-data googleapiclient src/main.py
iscc installer\DriveAutoUpload.iss
```
