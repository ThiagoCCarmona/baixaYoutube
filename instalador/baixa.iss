; Instalador do BaixaYoutube (Inno Setup 6).
; Gerado por build.ps1, que passa /DVersao=x.y.z e /DRepositorio=dono/repo.

#ifndef Versao
  #define Versao "0.0.0"
#endif
#ifndef Repositorio
  #define Repositorio ""
#endif

[Setup]
AppId={{1916524E-4A25-4665-ACBA-4FBFF60CC776}
AppName=BaixaYoutube
AppVersion={#Versao}
AppVerName=BaixaYoutube {#Versao}
AppPublisher=baixa
#if Repositorio != ""
AppPublisherURL=https://github.com/{#Repositorio}
AppSupportURL=https://github.com/{#Repositorio}/issues
AppUpdatesURL=https://github.com/{#Repositorio}/releases
#endif
VersionInfoVersion={#Versao}
DefaultDirName={localappdata}\Programs\BaixaYoutube
DefaultGroupName=BaixaYoutube
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=BaixaYoutube-Setup-{#Versao}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\BaixaYoutube.exe
SetupIconFile=..\build\baixa.ico
; Fecha o app aberto antes de substituir os arquivos (usado pela atualização automática).
CloseApplications=force
RestartApplications=no

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Remove bibliotecas da versão anterior para não misturar arquivos velhos e novos.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\BaixaYoutube\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\BaixaYoutube"; Filename: "{app}\BaixaYoutube.exe"
Name: "{group}\Desinstalar BaixaYoutube"; Filename: "{uninstallexe}"
Name: "{autodesktop}\BaixaYoutube"; Filename: "{app}\BaixaYoutube.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BaixaYoutube.exe"; Description: "{cm:LaunchProgram,BaixaYoutube}"; Flags: nowait postinstall skipifsilent
; Na atualização automática (modo silencioso) reabre o app sozinho.
Filename: "{app}\BaixaYoutube.exe"; Flags: nowait runasoriginaluser; Check: WizardSilent

[UninstallDelete]
; Motores yt-dlp baixados pelo atualizador (configurações do usuário são mantidas).
Type: filesandordirs; Name: "{userappdata}\baixa\motor"
Type: files; Name: "{userappdata}\baixa\atualizacoes.json"
