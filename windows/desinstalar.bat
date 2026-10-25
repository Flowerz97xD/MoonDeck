@echo off
title MoonDeck - desinstalar / uninstall
echo Se borrara MoonDeck: la aplicacion, sus accesos directos,
echo el arranque automatico y tu configuracion.
echo MoonDeck will be removed: the app, its shortcuts, the autostart
echo and your settings.
echo.
echo Antes, cierra MoonDeck (icono de la bandeja ^> Salir).
echo First, close MoonDeck (tray icon ^> Exit).
pause
set "CARPETA=%~dp0"
powershell -NoProfile -Command "$p = [Environment]::GetFolderPath('Programs'); Remove-Item ([Environment]::GetFolderPath('Desktop') + '\MoonDeck.lnk'), ($p + '\MoonDeck.lnk'), ($p + '\MoonDeck') -Recurse -ErrorAction SilentlyContinue"
powershell -NoProfile -Command "if (Get-ScheduledTask -TaskName 'MoonDeck' -ErrorAction SilentlyContinue) { Start-Process schtasks.exe -ArgumentList '/Delete /TN \"MoonDeck\" /F' -Verb RunAs -Wait }"
rmdir /s /q "%APPDATA%\MoonDeck" >nul 2>&1
echo.
echo Desinstalado. (Python y PawnIO siguen instalados; quitalos desde
echo Configuracion ^> Aplicaciones si no los usas para nada mas.)
echo Uninstalled. (Python and PawnIO stay installed; remove them from
echo Settings ^> Apps if you don't use them for anything else.)
pause
rem La carpeta de la app se borra al final, desde fuera, porque este .bat esta dentro.
cd /d "%TEMP%"
start "" /b cmd /c "ping -n 2 127.0.0.1 >nul & rmdir /s /q "%CARPETA%""
exit
