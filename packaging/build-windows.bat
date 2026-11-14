@echo off
cd /d "%~dp0\.."
py -3 -m pip install nuitka==4.3.5
py -3 packaging\build.py
if errorlevel 1 (
  echo Build failed. Python, Nuitka, a C compiler and NSIS are required only on this build machine.
  pause
  exit /b 1
)
echo Installer ready in dist.
pause
