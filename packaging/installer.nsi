!include "MUI2.nsh"
!include "x64.nsh"
Unicode true
Name "Al Hidaya Traders"
OutFile "../dist/AlHidayaTraders-Setup-0.2.1.exe"
InstallDir "$LOCALAPPDATA\Programs\AlHidayaTraders"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "0.2.1.0"
VIAddVersionKey "ProductName" "Al Hidaya Traders"
VIAddVersionKey "FileDescription" "Offline shop manager installer (pilot)"
VIAddVersionKey "FileVersion" "0.2.1"
VIAddVersionKey "ProductVersion" "0.2.1"
VIAddVersionKey "LegalCopyright" "Al Hidaya Traders"
!define MUI_WELCOMEPAGE_TITLE "Welcome to Al Hidaya Traders"
!define MUI_WELCOMEPAGE_TEXT "Offline billing, warehouse stock and takeaway cafe management.$\r$\n$\r$\nThis pilot installs for your Windows account. Python is included. Updates back up your database before replacing application files.$\r$\n$\r$\nPlease close shop billing before updating. Test the pilot before using it for live trading."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\AlHidayaTraders.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Open Al Hidaya Traders"
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

Section "Al Hidaya Traders"
  SetShellVarContext current
  IfFileExists "$INSTDIR\runtime\python.exe" 0 installfiles
  IfFileExists "$INSTDIR\packaging\maintenance.py" 0 installfiles
  ExecWait '"$INSTDIR\runtime\python.exe" "$INSTDIR\packaging\maintenance.py"' $0
  StrCmp $0 0 installfiles
  MessageBox MB_ICONSTOP "Could not close the app or create the pre-update backup. Close the app and check your data-folder permissions, then rerun this installer. No files were updated."
  Abort
installfiles:
  SetOutPath "$INSTDIR"
  File "../app.py"
  File "../notifications.py"
  File "../dist/AlHidayaTraders.exe"
  File "../README.md"
  File "../VERSION"
  File "../catalog.json"
  SetOutPath "$INSTDIR\static"
  File "../static/index.html"
  File "../static/style.css"
  File "../static/app.js"
  SetOutPath "$INSTDIR\packaging"
  File "maintenance.py"
  SetOutPath "$INSTDIR\runtime"
  File /r "../build/runtime/*.*"
  SetOutPath "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Al Hidaya Traders"
  CreateShortcut "$SMPROGRAMS\Al Hidaya Traders\Al Hidaya Traders.lnk" "$INSTDIR\AlHidayaTraders.exe"
  CreateShortcut "$DESKTOP\Al Hidaya Traders.lnk" "$INSTDIR\AlHidayaTraders.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders" "DisplayName" "Al Hidaya Traders"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders" "DisplayVersion" "0.2.1"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  ExecWait '"$INSTDIR\runtime\python.exe" "$INSTDIR\packaging\maintenance.py"' $0
  StrCmp $0 0 removefiles
  MessageBox MB_ICONSTOP "Close the app before uninstalling. Your shop data has not been removed."
  Abort
removefiles:
  Delete "$INSTDIR\AlHidayaTraders.exe"
  Delete "$INSTDIR\app.py"
  Delete "$INSTDIR\notifications.py"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\VERSION"
  Delete "$INSTDIR\catalog.json"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR\static"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\packaging"
  RMDir "$INSTDIR"
  Delete "$DESKTOP\Al Hidaya Traders.lnk"
  Delete "$SMPROGRAMS\Al Hidaya Traders\Al Hidaya Traders.lnk"
  RMDir "$SMPROGRAMS\Al Hidaya Traders"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders"
  MessageBox MB_ICONINFORMATION "Application removed. Your database and backups remain in %LOCALAPPDATA%\AlHidayaTraders."
SectionEnd
