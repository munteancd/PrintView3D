; PrintView3D - Windows installer (Inno Setup 6)
;
; Built automatically by GitHub Actions (see .github/workflows/build.yml), or locally:
;   pyinstaller --noconfirm --clean printview3d.spec
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=0.8.0 packaging\windows\PrintView3D.iss
; Output: dist\PrintView3D-Setup.exe
;
; PrintView3D updates itself by running this installer with
;   /SILENT /SUPPRESSMSGBOXES /NORESTART /UPDATE=1
; (progress window, no questions, previous choices kept, new version started afterwards).
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
; File Explorer thumbnail provider (packaging\windows\thumbnails). The version is part of the
; file name, so an update never has to overwrite a DLL that Windows still has loaded.
#define ThumbDll "PrintView3DThumbnails-" + AppVersion + ".dll"
#define ThumbClsid "{{64535B54-55A8-4412-919A-88F46D3E3B86}"

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
; Tell File Explorer that file types changed (new thumbnails show up without a restart).
ChangesAssociations=yes
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
en.Thumbnails=Show previews of 3MF, STL, G-code and FreeCAD files in File Explorer
nl.Thumbnails=Voorbeelden van 3MF-, STL-, G-code- en FreeCAD-bestanden tonen in Verkenner
de.Thumbnails=Vorschaubilder für 3MF-, STL-, G-Code- und FreeCAD-Dateien im Explorer anzeigen
fr.Thumbnails=Afficher les aperçus des fichiers 3MF, STL, G-code et FreeCAD dans l'Explorateur
es.Thumbnails=Mostrar vistas previas de archivos 3MF, STL, G-code y FreeCAD en el Explorador
en.DeleteSettings=Also delete your PrintView3D settings (recent files, slicer choice, theme)?
nl.DeleteSettings=Ook je PrintView3D-instellingen verwijderen (recente bestanden, slicer, thema)?
de.DeleteSettings=Auch deine PrintView3D-Einstellungen löschen (zuletzt geöffnet, Slicer, Design)?
fr.DeleteSettings=Supprimer aussi vos réglages PrintView3D (fichiers récents, slicer, thème) ?
es.DeleteSettings=¿Eliminar también tus ajustes de PrintView3D (archivos recientes, slicer, tema)?
#if FileExists(AddBackslash(CompilerPath) + "Languages\Arabic.isl")
ar.Thumbnails=عرض معاينات ملفات 3MF وSTL وG-code وFreeCAD في مستكشف الملفات
ar.FileAssoc=إضافة PrintView3D إلى "فتح باستخدام" لملفات ‎.stl و‎.3mf و‎.gcode
ar.DeleteSettings=هل تريد أيضًا حذف إعدادات PrintView3D (الملفات الأخيرة، برنامج التقطيع، السمة)؟
#endif

[Tasks]
Name: "thumbnails"; Description: "{cm:Thumbnails}"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "fileassoc"; Description: "{cm:FileAssoc}"

[Files]
Source: "{#Root}\dist\PrintView3D\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\examples\*"; DestDir: "{app}\examples"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "{#Root}\packaging\windows\thumbnails\out\{#ThumbDll}"; DestDir: "{app}"; Flags: ignoreversion; Tasks: thumbnails

[InstallDelete]
; Thumbnail DLLs of earlier versions (skipped if Windows still has one loaded; removed next time).
Type: files; Name: "{app}\PrintView3DThumbnails-*.dll"
; Remove files of the previous version that no longer exist (the app folder is replaced as a whole).
Type: filesandordirs; Name: "{app}\_internal"

[Registry]
; Thumbnail provider, for this user only (no administrator rights needed).
Root: HKCU; Subkey: "Software\Classes\CLSID\{#ThumbClsid}"; ValueType: string; ValueData: "PrintView3D thumbnails"; Flags: uninsdeletekey; Tasks: thumbnails
Root: HKCU; Subkey: "Software\Classes\CLSID\{#ThumbClsid}\InprocServer32"; ValueType: string; ValueData: "{app}\{#ThumbDll}"; Tasks: thumbnails
Root: HKCU; Subkey: "Software\Classes\CLSID\{#ThumbClsid}\InprocServer32"; ValueType: string; ValueName: "ThreadingModel"; ValueData: "Apartment"; Tasks: thumbnails
; Also on the extension itself: Windows looks there before the file type (ProgID) and before
; SystemFileAssociations, so another program's handler (Windows' 3MF handler, the "Certificate
; Trust List" type that .stl also has) cannot hide ours. Removed in [Code] only if it is still ours.
Root: HKCU; Subkey: "Software\Classes\.3mf\ShellEx\{{e357fccd-a995-4576-b01f-234630154e96}"; ValueType: string; ValueData: "{#ThumbClsid}"; Tasks: thumbnails
Root: HKCU; Subkey: "Software\Classes\.stl\ShellEx\{{e357fccd-a995-4576-b01f-234630154e96}"; ValueType: string; ValueData: "{#ThumbClsid}"; Tasks: thumbnails
Root: HKCU; Subkey: "Software\Classes\.gcode\ShellEx\{{e357fccd-a995-4576-b01f-234630154e96}"; ValueType: string; ValueData: "{#ThumbClsid}"; Tasks: thumbnails
Root: HKCU; Subkey: "Software\Classes\.gco\ShellEx\{{e357fccd-a995-4576-b01f-234630154e96}"; ValueType: string; ValueData: "{#ThumbClsid}"; Tasks: thumbnails
Root: HKCU; Subkey: "Software\Classes\.fcstd\ShellEx\{{e357fccd-a995-4576-b01f-234630154e96}"; ValueType: string; ValueData: "{#ThumbClsid}"; Tasks: thumbnails
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.3mf\ShellEx\{{e357fccd-a995-4576-b01f-234630154e96}"; ValueType: string; ValueData: "{#ThumbClsid}"; Flags: uninsdeletekey; Tasks: thumbnails
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.stl\ShellEx\{{e357fccd-a995-4576-b01f-234630154e96}"; ValueType: string; ValueData: "{#ThumbClsid}"; Flags: uninsdeletekey; Tasks: thumbnails
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.gcode\ShellEx\{{e357fccd-a995-4576-b01f-234630154e96}"; ValueType: string; ValueData: "{#ThumbClsid}"; Flags: uninsdeletekey; Tasks: thumbnails
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.gco\ShellEx\{{e357fccd-a995-4576-b01f-234630154e96}"; ValueType: string; ValueData: "{#ThumbClsid}"; Flags: uninsdeletekey; Tasks: thumbnails
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.fcstd\ShellEx\{{e357fccd-a995-4576-b01f-234630154e96}"; ValueType: string; ValueData: "{#ThumbClsid}"; Flags: uninsdeletekey; Tasks: thumbnails

[Icons]
; AppUserModelID must match the one PrintView3D gives itself (app.py, APP_USER_MODEL_ID): the taskbar
; takes the icon and name of a running or pinned PrintView3D from the shortcut with that ID.
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "STL, 3MF and G-code viewer"; AppUserModelID: "PrintView3D.Viewer"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon; AppUserModelID: "PrintView3D.Viewer"

[Run]
; "Open with" registration (the same as Settings -> Register in the program).
Filename: "{app}\{#AppExe}"; Parameters: "--register"; Tasks: fileassoc; Flags: runhidden waituntilterminated
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; Update started from inside PrintView3D (/UPDATE=1): start the new version again by itself.
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: IsUpdate

[UninstallRun]
; Undo every file association before the files are removed.
Filename: "{app}\{#AppExe}"; Parameters: "--unregister"; Flags: runhidden waituntilterminated; RunOnceId: "Unregister"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Code]
function IsUpdate: Boolean;
begin
  Result := ExpandConstant('{param:UPDATE|0}') = '1';
end;

// Remove our thumbnail handler from the extension keys, but only where it is still ours
// (another program may have registered its own handler there since).
procedure RemoveThumbnailHandlers;
var
  Exts: array of String;
  I: Integer;
  Key, Value: String;
begin
  SetArrayLength(Exts, 5);
  Exts[0] := '.3mf';
  Exts[1] := '.stl';
  Exts[2] := '.gcode';
  Exts[3] := '.gco';
  Exts[4] := '.fcstd';
  for I := 0 to GetArrayLength(Exts) - 1 do
  begin
    Key := 'Software\Classes\' + Exts[I] + '\ShellEx\{e357fccd-a995-4576-b01f-234630154e96}';
    if RegQueryStringValue(HKCU, Key, '', Value) and (CompareText(Value, '{64535B54-55A8-4412-919A-88F46D3E3B86}') = 0) then
      RegDeleteKeyIncludingSubkeys(HKCU, Key);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Dir: String;
begin
  if CurUninstallStep = usUninstall then
    RemoveThumbnailHandlers;
  if CurUninstallStep = usPostUninstall then
  begin
    Dir := ExpandConstant('{userappdata}\PrintView3D');
    if DirExists(Dir) and (not UninstallSilent) then
      if MsgBox(CustomMessage('DeleteSettings'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(Dir, True, True, True);
  end;
end;
