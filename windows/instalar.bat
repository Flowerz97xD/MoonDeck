@echo off
title MoonDeck - instalacion / installation
if not exist "%~dp0app\instalar.ps1" (
    echo.
    echo  Primero descomprime el zip: clic derecho sobre el zip ^> "Extraer todo",
    echo  y luego abre instalar.bat desde la carpeta descomprimida.
    echo.
    echo  First extract the zip: right-click the zip ^> "Extract all",
    echo  then open instalar.bat from the extracted folder.
    echo.
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\instalar.ps1"
echo.
pause
