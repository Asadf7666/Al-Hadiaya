!include "MUI2.nsh"
!include "x64.nsh"
Unicode true
!ifndef PRODUCT_VERSION
!define PRODUCT_VERSION "1.0.0"
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
!define MUI_WELCOMEPAGE_TEXT "Offline billing, warehouse stock and takeaway cafe management.$\r$\n$\r$\nThis app installs for your Windows account. Python is included. Updates back up your database before replacing application files.$\r$\n$\r$\nPlease close shop billing before updating. Verify your tax configuration, opening stock and printer before live trading."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\AlHidayaTraders.exe"
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
  File "../outreach.py"
  File "../media_catalogue.py"
  File "../whatsapp_orders.py"
  File "../activity_alerts.py"
  File "../procurement.py"
  File "../stock_alerts.py"
  File "../cloud_sync.py"
  File "../staff_access.py"
  File "../operation_guard.py"
  File "../desktop_http.py"
  File "../backup_bundle.py"
  File "../backup_retention.py"
  File "../health.py"
  File "../whatsapp_policy.py"
  File "../dist/AlHidayaTraders.exe"
  File "../README.md"
  File "../RELEASE-NOTES.md"
  File "../VERSION"
  File "../catalog.json"
  SetOutPath "$INSTDIR\static"
  File "../static/index.html"
  File "../static/style.css"
  File "../static/app.js"
  File "../static/team.js"
  SetOutPath "$INSTDIR\packaging"
  File "maintenance.py"
  SetOutPath "$INSTDIR\tools"
  File "../tools/reset_owner.py"
  SetOutPath "$INSTDIR\docs"
  File "../docs/*.md"
  SetOutPath "$INSTDIR\runtime"
  File /r "../build/runtime/*.*"
  SetOutPath "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Al Hidaya Traders"
  CreateShortcut "$SMPROGRAMS\Al Hidaya Traders\Al Hadiya Traders.lnk" "$INSTDIR\AlHidayaTraders.exe"
  CreateShortcut "$DESKTOP\Al Hidaya Traders.lnk" "$INSTDIR\AlHidayaTraders.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders" "DisplayName" "Al Hadiya Traders"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders" "DisplayVersion" "${PRODUCT_VERSION}"
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
  Delete "$INSTDIR\outreach.py"
  Delete "$INSTDIR\media_catalogue.py"
  Delete "$INSTDIR\whatsapp_orders.py"
  Delete "$INSTDIR\activity_alerts.py"
  Delete "$INSTDIR\procurement.py"
  Delete "$INSTDIR\stock_alerts.py"
  Delete "$INSTDIR\cloud_sync.py"
  Delete "$INSTDIR\staff_access.py"
  Delete "$INSTDIR\operation_guard.py"
  Delete "$INSTDIR\desktop_http.py"
  Delete "$INSTDIR\backup_bundle.py"
  Delete "$INSTDIR\backup_retention.py"
  Delete "$INSTDIR\health.py"
  Delete "$INSTDIR\whatsapp_policy.py"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\RELEASE-NOTES.md"
  Delete "$INSTDIR\VERSION"
  Delete "$INSTDIR\catalog.json"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR\static"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\packaging"
  RMDir /r "$INSTDIR\tools"
  RMDir /r "$INSTDIR\docs"
  RMDir "$INSTDIR"
  Delete "$DESKTOP\Al Hidaya Traders.lnk"
  Delete "$SMPROGRAMS\Al Hidaya Traders\Al Hadiya Traders.lnk"
  RMDir "$SMPROGRAMS\Al Hidaya Traders"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AlHidayaTraders"
  MessageBox MB_ICONINFORMATION "Application removed. Your database and backups remain in %LOCALAPPDATA%\AlHidayaTraders."
SectionEnd
