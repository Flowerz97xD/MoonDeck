@echo off
rem Abre el monitor como administrador (necesario para las temperaturas).
net session >nul 2>&1 || (powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" monitor.py
