@echo off
rem Abre el monitor con consola, como administrador, para ver los errores.
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
cd /d "%~dp0"
".venv\Scripts\python.exe" monitor.py
pause
