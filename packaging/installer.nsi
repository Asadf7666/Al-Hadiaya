!include "MUI2.nsh"
!include "x64.nsh"
Unicode true
!ifndef PRODUCT_VERSION
!define PRODUCT_VERSION "1.4.0"
!endif
Name "Al Hadiya Traders"
OutFile "../dist/AlHidayaTraders-Setup-${PRODUCT_VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\AlHidayaTraders"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "${PRODUCT_VERSION}.0"
VIAddVersionKey "ProductName" "Al Hadiya Traders"
VIAddVersionKey "FileDescription" "Offline business manager installer"
VIAddVersionKey "FileVersion" "${PRODUCT_VERSION}"
VIAddVersionKey "ProductVersion" "${PRODUCT_VERSION}"
VIAddVersionKey "LegalCopyright" "Al Hadiya Traders"
!define MUI_WELCOMEPAGE_TITLE "Welcome to Al Hadiya Traders"
!define MUI_WELCOMEPAGE_TEXT "Offline billing, warehouse stock and takeaway cafe management.$\r$\n$\r$\nThis app installs for your Windows account. Nothing else needs installing. Updates back up your database before replacing application files.$\r$\n$\r$\nA 60-day trial is included. Install your licence file under Settings, Licence; no internet is needed.$\r$\n$\r$\nPlease close shop billing before updating. Verify your tax configuration, opening stock and printer before live trading."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\app\AlHidayaTraders.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Open Al Hadiya Traders"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "This installer requires 64-bit Windows 10 or Windows 11."
    Abort
  ${EndIf}
FunctionEnd

Section "Al Hadiya Traders"
  SetShellVarContext current
  ; Close the running app and back up before any file changes. Releases up to 1.3.0
  ; carried a Python runtime; later ones are a native program in the app folder.
  IfFileExists "$INSTDIR\app\AlHidayaTraders.exe" 0 legacy
  ExecWait '"$INSTDIR\app\AlHidayaTraders.exe" --maintenance' $0
  Goto checked
legacy:
  IfFileExists "$INSTDIR\runtime\python.exe" 0 installfiles
  IfFileExists "$INSTDIR\packaging\maintenance.py" 0 installfiles
  ExecWait '"$INSTDIR\runtime\python.exe" "$INSTDIR\packaging\maintenance.py"' $0
checked:
  StrCmp $0 0 installfiles
  MessageBox MB_ICONSTOP "Could not close the app or create the pre-update backup. Close the app and check your data-folder permissions, then rerun this installer. No files were updated."
  Abort
installfiles:
  ; Remove the Python runtime, source and bytecode that earlier releases installed.
  Delete "$INSTDIR\AlHidayaTraders.exe"
  Delete "$INSTDIR\*.py"
  Delete "$INSTDIR\*.pyc"
  Delete "$INSTDIR\VERSION"
  Delete "$INSTDIR\catalog.json"
  RMDir /r "$INSTDIR\__pycache__"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\static"
  RMDir /r "$INSTDIR\packaging"
  RMDir /r "$INSTDIR\tools"
  RMDir /r "$INSTDIR\app"
  SetOutPath "$INSTDIR\app"
  File /r "..\build\native\app.dist\*.*"
  SetOutPath "$INSTDIR"
  File "..\README.md"
  File "..\RELEASE-NOTES.md"
  SetOutPath "$INSTDIR\docs"
  File "..\docs\*.md"
  SetOutPath "$INSTDIR\app"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Al Hidaya Traders"
  CreateShortcut "$SMPROGRAMS\Al Hidaya Traders\Al Hadiya Traders.lnk" "$INSTDIR\app\AlHidayaTraders.exe"
  CreateShortcut "$DESKTOP\Al Hidaya Traders.lnk" "$INSTDIR\app\AlHidayaTraders.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders" "DisplayName" "Al Hadiya Traders"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  ExecWait '"$INSTDIR\app\AlHidayaTraders.exe" --maintenance' $0
  StrCmp $0 0 removefiles
  MessageBox MB_ICONSTOP "Close the app before uninstalling. Your shop data has not been removed."
  Abort
removefiles:
  SetOutPath "$TEMP"
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\docs"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\RELEASE-NOTES.md"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$DESKTOP\Al Hidaya Traders.lnk"
  Delete "$SMPROGRAMS\Al Hidaya Traders\Al Hadiya Traders.lnk"
  RMDir "$SMPROGRAMS\Al Hidaya Traders"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders"
  MessageBox MB_ICONINFORMATION "Application removed. Your database, backups and licence remain in %LOCALAPPDATA%\AlHidayaTraders."
SectionEnd
