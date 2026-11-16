#define AppName "Guardpy"
#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif

[Setup]
AppId={{6E2B7C1A-4F3D-4C59-9A1E-DA7E5B0C2F11}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Cordobot
AppPublisherURL=https://github.com/Cordobot/Guardpy
DefaultDirName={localappdata}\Programs\{#AppName}
UsePreviousAppDir=no
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Guardpy-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\Guardpy.exe
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=force

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "startup"; Description: "Abrir Guardpy al iniciar Windows (recomendado)"; GroupDescription: "Opciones:"
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Opciones:"

[InstallDelete]
Type: filesandordirs; Name: "{localappdata}\Programs\DriveAutoUpload"
Type: files; Name: "{userprograms}\DriveAutoUpload\*.lnk"
Type: dirifempty; Name: "{userprograms}\DriveAutoUpload"
Type: files; Name: "{userdesktop}\DriveAutoUpload.lnk"

[Files]
Source: "..\dist\Guardpy\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Guardpy.exe"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\Guardpy.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "DriveAutoUpload"; Flags: deletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\Guardpy.exe"" --oculto"; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "taskkill"; Parameters: "/f /im DriveAutoUpload.exe"; Flags: runhidden
Filename: "{app}\Guardpy.exe"; Description: "Abrir Guardpy ahora"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill"; Parameters: "/f /im Guardpy.exe"; Flags: runhidden; RunOnceId: "KillApp"
