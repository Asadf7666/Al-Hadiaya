Unicode true
Name "Al Hadiya Traders"
OutFile "../dist/AlHidayaTraders.exe"
RequestExecutionLevel user
SilentInstall silent
AutoCloseWindow true
Section
  IfFileExists "$EXEDIR\runtime\pythonw.exe" 0 missing
  Exec '"$EXEDIR\runtime\pythonw.exe" "$EXEDIR\app.py"'
  IfErrors missing
  Quit
missing:
  MessageBox MB_ICONSTOP "Application files are missing. Reinstall Al Hadiya Traders. Your shop database will be preserved."
SectionEnd
