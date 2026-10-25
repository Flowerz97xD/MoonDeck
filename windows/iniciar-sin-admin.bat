@echo off
rem Abre el monitor sin permisos de administrador: sin temperaturas de CPU ni datos de GPUs AMD/Intel.
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0monitor.py"
