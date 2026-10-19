; PrintView3D - Windows installer (Inno Setup 6)
;
; Built automatically by GitHub Actions (see .github/workflows/build.yml), or locally:
;   pyinstaller --noconfirm --clean printview3d.spec
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=0.8.0 packaging\windows\PrintView3D.iss
; Output: dist\PrintView3D-Setup.exe
;
; - Installs for the current user only: no administrator password needed.
; - Installing a newer version updates the old one; settings are kept.
; - Appears in Windows Settings -> Apps, where it can be uninstalled.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "PrintView3D"
#define AppExe "PrintView3D.exe"
#define Root "..\.."

[Setup]
; Never change AppId: Windows uses it to recognise updates of the same program.
AppId={{f46ac51f-055b-41dc-be29-5f0191feaf3d}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=PrintView3D contributors
AppPublisherURL=https://github.com/sevagjb/PrintView3D
AppSupportURL=https://github.com/sevagjb/PrintView3D/issues
AppUpdatesURL=https://github.com/sevagjb/PrintView3D/releases
AppComments=Viewer for STL, 3MF and G-code files with one-click hand-off to your slicer.
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup
; Per-user install into %LOCALAPPDATA%\Programs\PrintView3D (same folder as the old install script).
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
UsePreviousAppDir=yes
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
SetupIconFile={#Root}\src\printview3d\resources\icon.ico
WizardStyle=modern
ShowLanguageDialog=auto
; Close a running PrintView3D before updating it.
CloseApplications=yes
RestartApplications=no
OutputDir={#Root}\dist
OutputBaseFilename={#AppName}-Setup
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "nl"; MessagesFile: "compiler:Languages\Dutch.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
#if FileExists(AddBackslash(CompilerPath) + "Languages\Arabic.isl")
Name: "ar"; MessagesFile: "compiler:Languages\Arabic.isl"
#endif

[CustomMessages]
en.FileAssoc=Add PrintView3D to "Open with" for .stl, .3mf and .gcode files
nl.FileAssoc=PrintView3D toevoegen aan "Openen met" voor .stl-, .3mf- en .gcode-bestanden
de.FileAssoc=PrintView3D zu "Öffnen mit" für .stl-, .3mf- und .gcode-Dateien hinzufügen
fr.FileAssoc=Ajouter PrintView3D à « Ouvrir avec » pour les fichiers .stl, .3mf et .gcode
es.FileAssoc=Añadir PrintView3D a "Abrir con" para archivos .stl, .3mf y .gcode
en.DeleteSettings=Also delete your PrintView3D settings (recent files, slicer choice, theme)?
nl.DeleteSettings=Ook je PrintView3D-instellingen verwijderen (recente bestanden, slicer, thema)?
de.DeleteSettings=Auch deine PrintView3D-Einstellungen löschen (zuletzt geöffnet, Slicer, Design)?
fr.DeleteSettings=Supprimer aussi vos réglages PrintView3D (fichiers récents, slicer, thème) ?
es.DeleteSettings=¿Eliminar también tus ajustes de PrintView3D (archivos recientes, slicer, tema)?
#if FileExists(AddBackslash(CompilerPath) + "Languages\Arabic.isl")
ar.FileAssoc=إضافة PrintView3D إلى "فتح باستخدام" لملفات ‎.stl و‎.3mf و‎.gcode
ar.DeleteSettings=هل تريد أيضًا حذف إعدادات PrintView3D (الملفات الأخيرة، برنامج التقطيع، السمة)؟
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "fileassoc"; Description: "{cm:FileAssoc}"

[Files]
Source: "{#Root}\dist\PrintView3D\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\examples\*"; DestDir: "{app}\examples"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[InstallDelete]
; Remove files of the previous version that no longer exist (the app folder is replaced as a whole).
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "STL, 3MF and G-code viewer"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; "Open with" registration (the same as Settings -> Register in the program).
Filename: "{app}\{#AppExe}"; Parameters: "--register"; Tasks: fileassoc; Flags: runhidden waituntilterminated
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Undo every file association before the files are removed.
Filename: "{app}\{#AppExe}"; Parameters: "--unregister"; Flags: runhidden waituntilterminated; RunOnceId: "Unregister"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Dir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Dir := ExpandConstant('{userappdata}\PrintView3D');
    if DirExists(Dir) and (not UninstallSilent) then
      if MsgBox(CustomMessage('DeleteSettings'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(Dir, True, True, True);
  end;
end;
