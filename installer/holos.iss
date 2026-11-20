; Установщик «Голос» (Holos) — 12.11.2026
; Собирается из tools\build_installer.py: ISCC /DStage=<папка сборки> /DOut=<куда exe> holos.iss
; Ставится в %LOCALAPPDATA%\Programs\Holos — без прав администратора.
; [18.11.2026] Модели отдельно от программы; папка установки — на виду:
;   полный (Holos-Setup) — программа + модели; /DUpdate (Holos-Update) — без моделей, только поверх установленной.
;   Папка — на виду при каждой установке; полный установщик в новую папку переносит data и предлагает убрать старую.

#ifdef Test
#define AppName "Голос-тест"
#else
#define AppName "Голос"
#endif
#define AppVer "3.2.3"
#define ModelCheck "app\models\sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16"

[Setup]
#ifdef Test
; проверка установщика, не трогая установленный «Голос»
AppId=Holos-Test
#else
AppId=Holos-BuckNeverBarks
#endif
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher=Бак + Claude — канал «Бак зря не гавкает»
AppPublisherURL=https://www.youtube.com/@BuckNeverBarks
DefaultDirName={localappdata}\Programs\Holos
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#Out}
#ifdef Update
OutputBaseFilename=Holos-Update-{#AppVer}
#else
OutputBaseFilename=Holos-Setup-{#AppVer}
#endif
DisableDirPage=no
UsePreviousAppDir=yes
CloseApplications=yes
SetupIconFile=holos.ico
UninstallDisplayIcon={app}\holos.ico
Compression=lzma2/fast
SolidCompression=no
WizardStyle=modern
LicenseFile={#Stage}\app\LICENSE
; [3.2.2, 19.11.2026] Окно языка всегда первым,
; по умолчанию — язык Windows; выбор запоминается в реестре, и программа при первом запуске открывается на нём
ShowLanguageDialog=yes
LanguageDetectionMethod=uilanguage

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "uk"; MessagesFile: "compiler:Languages\Ukrainian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
ru.Autostart=Запускать вместе с Windows
uk.Autostart=Запускати разом з Windows
en.Autostart=Start with Windows
ru.RunNow=Запустить «Голос»
uk.RunNow=Запустити «Голос»
en.RunNow=Launch Holos
ru.NoModels=В папке «%1» нет «Голоса» с моделями речи.%n%nЭтот файл — обновление: он ставится только поверх установленной программы. Выберите папку, где стоит «Голос», или скачайте полный установщик Holos-Setup.
uk.NoModels=У теці «%1» немає «Голосу» з моделями мовлення.%n%nЦей файл — оновлення: він ставиться лише поверх встановленої програми. Виберіть теку, де стоїть «Голос», або завантажте повний інсталятор Holos-Setup.
en.NoModels=Folder "%1" has no Holos with speech models.%n%nThis file is an update: it installs only on top of an installed Holos. Choose the folder where Holos is installed, or download the full Holos-Setup installer.
ru.MoveAsk=«Голос» переедет из «%1» в «%2».%n%nИстория, настройки и журнал перенесутся сами. Перед продолжением закройте «Голос»: значок в трее → «Выход».
uk.MoveAsk=«Голос» переїде з «%1» до «%2».%n%nІсторія, налаштування та журнал перенесуться самі. Перед продовженням закрийте «Голос»: значок у треї → «Вихід».
en.MoveAsk=Holos will move from "%1" to "%2".%n%nHistory, settings and log move automatically. Before you continue, close Holos: tray icon → "Exit".
ru.DeleteAsk=Данные перенесены в «%2».%n%nУдалить старую папку «%1»? Это освободит около 1,8 ГБ.
uk.DeleteAsk=Дані перенесено до «%2».%n%nВидалити стару теку «%1»? Це звільнить близько 1,8 ГБ.
en.DeleteAsk=Data moved to "%2".%n%nDelete the old folder "%1"? This frees about 1.8 GB.
ru.DeleteFailed=Старую папку «%1» удалить до конца не удалось — вероятно, «Голос» ещё открыт. Закройте его и удалите папку вручную.
uk.DeleteFailed=Стару теку «%1» видалити до кінця не вдалося — мабуть, «Голос» ще відкритий. Закрийте його та видаліть теку вручну.
en.DeleteFailed=Could not fully delete the old folder "%1" — Holos is probably still open. Close it and delete the folder manually.

[Messages]
#ifdef Update
ru.SelectDirBrowseLabel=Это обновление: оно ставится в папку, где уже стоит «Голос». Папку не меняйте. История и настройки сохранятся.
uk.SelectDirBrowseLabel=Це оновлення: воно ставиться в теку, де вже стоїть «Голос». Теку не змінюйте. Історія та налаштування збережуться.
en.SelectDirBrowseLabel=This is an update: it goes into the folder where Holos is already installed. Do not change the folder. History and settings are kept.
#else
ru.SelectDirBrowseLabel=Программа с моделями речи занимает около 1,8 ГБ. Чтобы не занимать диск C:, нажмите «Обзор…» и выберите другой диск, например D:\Holos (латиницей, без пробелов). При смене папки история и настройки перенесутся сами.
uk.SelectDirBrowseLabel=Програма з моделями мовлення займає близько 1,8 ГБ. Щоб не займати диск C:, натисніть «Огляд…» і виберіть інший диск, наприклад D:\Holos (латиницею, без пробілів). Під час зміни теки історія та налаштування перенесуться самі.
en.SelectDirBrowseLabel=Holos with speech models takes about 1.8 GB. To keep drive C: free, click "Browse..." and choose another drive, for example D:\Holos (Latin letters, no spaces). If you change the folder, history and settings move automatically.
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "{cm:Autostart}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#Stage}\runtime\*"; DestDir: "{app}\runtime"; Flags: recursesubdirs createallsubdirs ignoreversion
#ifdef Update
Source: "{#Stage}\app\*"; DestDir: "{app}\app"; Excludes: "\models,\models\*"; Flags: recursesubdirs createallsubdirs ignoreversion
#else
Source: "{#Stage}\app\*"; DestDir: "{app}\app"; Flags: recursesubdirs createallsubdirs ignoreversion
#endif
Source: "holos.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\main.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\holos.ico"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\main.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\holos.ico"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\main.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\holos.ico"; Tasks: autostart

[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\main.py"""; WorkingDir: "{app}\app"; Description: "{cm:RunNow}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\app\__pycache__"
Type: filesandordirs; Name: "{app}\runtime\Lib\__pycache__"

[Code]
function SameDir(A, B: String): Boolean;
begin
  Result := CompareText(RemoveBackslashUnlessRoot(A), RemoveBackslashUnlessRoot(B)) = 0;
end;

function PrevDir(): String;
begin
  Result := WizardForm.PrevAppDir;
end;

function DirChanged(): Boolean;
begin
  Result := (PrevDir() <> '') and not SameDir(PrevDir(), WizardDirValue());
end;

#ifdef Update
// Обновление без моделей — только поверх установленного «Голоса»
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not DirExists(AddBackslash(WizardDirValue()) + '{#ModelCheck}') then
    Result := FmtMessage(CustomMessage('NoModels'), [WizardDirValue()]);
end;
#else
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpSelectDir) and DirChanged() then
    Result := SuppressibleMsgBox(FmtMessage(CustomMessage('MoveAsk'), [PrevDir(), WizardDirValue()]),
                                 mbConfirmation, MB_OKCANCEL, IDOK) = IDOK;
end;

// Копия папки целиком: файлы перезаписываются, подпапки создаются
procedure CopyTree(Src, Dst: String);
var
  F: TFindRec;
begin
  ForceDirectories(Dst);
  if FindFirst(AddBackslash(Src) + '*', F) then
  try
    repeat
      if (F.Name <> '.') and (F.Name <> '..') then
      begin
        if F.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0 then
          CopyTree(AddBackslash(Src) + F.Name, AddBackslash(Dst) + F.Name)
        else
          FileCopy(AddBackslash(Src) + F.Name, AddBackslash(Dst) + F.Name, False);
      end;
    until not FindNext(F);
  finally
    FindClose(F);
  end;
end;

// Новая папка: перенести data, затем по согласию убрать старую (только если это и правда папка «Голоса»)
procedure CurStepChanged(CurStep: TSetupStep);
var
  OldDir, NewDir: String;
begin
  if (CurStep <> ssPostInstall) or not DirChanged() then
    Exit;
  OldDir := RemoveBackslashUnlessRoot(PrevDir());
  NewDir := ExpandConstant('{app}');
  if DirExists(OldDir + '\app\data') then
    CopyTree(OldDir + '\app\data', NewDir + '\app\data');
  // Новая папка внутри старой — старую не удалять, иначе пропадёт и новая
  if Pos(Lowercase(AddBackslash(OldDir)), Lowercase(AddBackslash(NewDir))) = 1 then
    Exit;
  if FileExists(OldDir + '\runtime\pythonw.exe') and FileExists(OldDir + '\app\main.py') then
    if SuppressibleMsgBox(FmtMessage(CustomMessage('DeleteAsk'), [OldDir, NewDir]),
                          mbConfirmation, MB_YESNO, IDYES) = IDYES then
    begin
      DelTree(OldDir, True, True, True);
      if DirExists(OldDir) then
        SuppressibleMsgBox(FmtMessage(CustomMessage('DeleteFailed'), [OldDir]), mbError, MB_OK, IDOK);
    end;
end;
#endif
