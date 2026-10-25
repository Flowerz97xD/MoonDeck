# Instalador de MoonDeck para Windows 10/11.
# Se ejecuta con instalar.bat (doble clic). Copia la app a
# %LOCALAPPDATA%\Programs\MoonDeck, así que da igual dónde se haya
# descomprimido el zip. Volver a ejecutarlo actualiza a la versión del zip.
# También quita la versión anterior ("Monitor de Hardware"); su configuración
# la recoge MoonDeck sola la primera vez que se abre.
# No necesita administrador, salvo PawnIO y el arranque automático, que lo piden.

$ErrorActionPreference = "Stop"
$Origen = Split-Path -Parent $MyInvocation.MyCommand.Path
$Destino = Join-Path $env:LOCALAPPDATA "Programs\MoonDeck"
$Viejo = Join-Path $env:LOCALAPPDATA "Programs\MonitorHardware"
$LhmVersion = "v0.9.6"
$LhmUrl = "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/$LhmVersion/LibreHardwareMonitor.zip"
$PmVersion = "2.6.0"
$PmUrl = "https://github.com/GameTechDev/PresentMon/releases/download/v$PmVersion/PresentMon-$PmVersion-x64.exe"

function Paso($texto) { Write-Host "`n== $texto" -ForegroundColor Cyan }
function Pregunta($texto, $porDefecto) {
    $r = Read-Host "$texto"
    if ([string]::IsNullOrWhiteSpace($r)) { return $porDefecto }
    return $r -match '^[sSyYjJдД是]'   # "sí" en los cinco idiomas
}
function Refrescar-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}
function Buscar-Python {
    # Versiones con todas las librerías disponibles (3.11 a 3.14). Se piden por
    # número al lanzador "py": el Python por defecto podría ser otro más nuevo.
    $candidatos = @(@("py", "-3.12"), @("py", "-3.13"), @("py", "-3.11"), @("py", "-3.14"), @("python"))
    foreach ($c in $candidatos) {
        try {
            $exe, $resto = $c
            $v = & $exe @resto -c "import sys; print('%d.%d' % sys.version_info[:2]); print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $v) {
                $ver = [version]$v[0]
                if ($ver -ge [version]"3.11" -and $ver -lt [version]"3.15") { return $v[1] }
            }
        } catch { }
    }
    return $null
}

# Idioma del instalador (y de MoonDeck) -------------------------------------
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$Textos = @{
    es = @{
        titulo = 'MoonDeck - instalación'
        destino = 'Se instalará en: {0}'
        abierto = 'MoonDeck (o el antiguo Monitor de Hardware) está abierto. Ciérralo: icono de la bandeja > Salir.'
        enter = 'Pulsa Enter cuando esté cerrado'
        p1 = '1/7 Copiando la aplicación'
        copiados = 'Copiados {0} archivos.'
        p2 = '2/7 Buscando Python (3.11 a 3.14)'
        sin_python = 'No se encontró una versión compatible. Se instalará Python 3.12 con winget.'
        python_falla = 'No se pudo encontrar Python tras instalarlo. Cierra esta ventana y vuelve a ejecutar instalar.bat.'
        p3 = '3/7 Instalando librerías (PySide6, psutil, pythonnet, pycaw...) - tarda unos minutos'
        pip_falla = 'Falló la instalación de librerías (pip). Haz una captura de esta ventana.'
        p4 = '4/7 Descargando LibreHardwareMonitor {0} (sensores)'
        p5 = '5/7 Descargando PresentMon {0} (medidor de FPS de Intel)'
        p6 = '6/7 Driver PawnIO'
        pawn = 'Hace falta para leer la temperatura de la CPU. Windows pedirá permiso de administrador.'
        pawn_preg = '¿Instalar o actualizar PawnIO ahora? [S/n]'
        p7 = '7/7 Accesos directos'
        accesos = 'Creados en el escritorio y en el menú Inicio.'
        arranque = '¿Arrancar automáticamente al iniciar sesión (sin aviso de UAC)? [s/N]'
        tarea = 'Tarea programada creada.'
        no_borrar = 'No se pudo borrar {0} (algún archivo en uso); puedes borrarla a mano.'
        listo = 'Listo. Ya puedes borrar el zip y la carpeta descomprimida.'
        abrir = '¿Abrir MoonDeck ahora? [S/n]'
    }
    en = @{
        titulo = 'MoonDeck - installation'
        destino = 'It will be installed in: {0}'
        abierto = 'MoonDeck (or the old Monitor de Hardware) is open. Close it: tray icon > Exit.'
        enter = 'Press Enter when it is closed'
        p1 = '1/7 Copying the application'
        copiados = 'Copied {0} files.'
        p2 = '2/7 Looking for Python (3.11 to 3.14)'
        sin_python = 'No compatible version found. Python 3.12 will be installed with winget.'
        python_falla = 'Python couldn''t be found after installing it. Close this window and run instalar.bat again.'
        p3 = '3/7 Installing libraries (PySide6, psutil, pythonnet, pycaw...) - takes a few minutes'
        pip_falla = 'Installing the libraries (pip) failed. Take a screenshot of this window.'
        p4 = '4/7 Downloading LibreHardwareMonitor {0} (sensors)'
        p5 = '5/7 Downloading PresentMon {0} (Intel''s FPS meter)'
        p6 = '6/7 PawnIO driver'
        pawn = 'It''s needed to read the CPU temperature. Windows will ask for administrator permission.'
        pawn_preg = 'Install or update PawnIO now? [Y/n]'
        p7 = '7/7 Shortcuts'
        accesos = 'Created on the desktop and in the Start menu.'
        arranque = 'Start automatically at login (without a UAC prompt)? [y/N]'
        tarea = 'Scheduled task created.'
        no_borrar = 'Couldn''t delete {0} (some file in use); you can delete it by hand.'
        listo = 'Done. You can now delete the zip and the extracted folder.'
        abrir = 'Open MoonDeck now? [Y/n]'
    }
    de = @{
        titulo = 'MoonDeck - Installation'
        destino = 'Wird installiert in: {0}'
        abierto = 'MoonDeck (oder der alte Monitor de Hardware) ist geöffnet. Schließe es: Infobereich-Symbol > Beenden.'
        enter = 'Drücke Enter, wenn es geschlossen ist'
        p1 = '1/7 App wird kopiert'
        copiados = '{0} Dateien kopiert.'
        p2 = '2/7 Python wird gesucht (3.11 bis 3.14)'
        sin_python = 'Keine passende Version gefunden. Python 3.12 wird mit winget installiert.'
        python_falla = 'Python wurde nach der Installation nicht gefunden. Schließe dieses Fenster und führe instalar.bat erneut aus.'
        p3 = '3/7 Bibliotheken werden installiert (PySide6, psutil, pythonnet, pycaw...) - dauert ein paar Minuten'
        pip_falla = 'Die Installation der Bibliotheken (pip) ist fehlgeschlagen. Mach einen Screenshot dieses Fensters.'
        p4 = '4/7 LibreHardwareMonitor {0} wird heruntergeladen (Sensoren)'
        p5 = '5/7 PresentMon {0} wird heruntergeladen (FPS-Messung von Intel)'
        p6 = '6/7 PawnIO-Treiber'
        pawn = 'Wird zum Lesen der CPU-Temperatur benötigt. Windows fragt nach Administratorrechten.'
        pawn_preg = 'PawnIO jetzt installieren oder aktualisieren? [J/n]'
        p7 = '7/7 Verknüpfungen'
        accesos = 'Auf dem Desktop und im Startmenü erstellt.'
        arranque = 'Bei der Anmeldung automatisch starten (ohne UAC-Abfrage)? [j/N]'
        tarea = 'Geplante Aufgabe erstellt.'
        no_borrar = '{0} konnte nicht gelöscht werden (eine Datei ist in Benutzung); du kannst den Ordner von Hand löschen.'
        listo = 'Fertig. Du kannst jetzt die ZIP-Datei und den entpackten Ordner löschen.'
        abrir = 'MoonDeck jetzt öffnen? [J/n]'
    }
    zh = @{
        titulo = 'MoonDeck - 安装'
        destino = '将安装到：{0}'
        abierto = 'MoonDeck（或旧的 Monitor de Hardware）正在运行。请关闭它：托盘图标 > 退出。'
        enter = '关闭后按回车'
        p1 = '1/7 正在复制应用'
        copiados = '已复制 {0} 个文件。'
        p2 = '2/7 正在查找 Python（3.11 到 3.14）'
        sin_python = '没有找到兼容的版本。将用 winget 安装 Python 3.12。'
        python_falla = '安装后仍找不到 Python。请关闭此窗口并重新运行 instalar.bat。'
        p3 = '3/7 正在安装库（PySide6、psutil、pythonnet、pycaw...）- 需要几分钟'
        pip_falla = '安装库（pip）失败。请截图这个窗口。'
        p4 = '4/7 正在下载 LibreHardwareMonitor {0}（传感器）'
        p5 = '5/7 正在下载 PresentMon {0}（Intel 的 FPS 测量工具）'
        p6 = '6/7 PawnIO 驱动'
        pawn = '读取 CPU 温度需要它。Windows 会请求管理员权限。'
        pawn_preg = '现在安装或更新 PawnIO 吗？[Y/n]'
        p7 = '7/7 快捷方式'
        accesos = '已在桌面和开始菜单中创建。'
        arranque = '登录时自动启动（不弹出 UAC 提示）？[y/N]'
        tarea = '已创建计划任务。'
        no_borrar = '无法删除 {0}（有文件正在使用）；你可以手动删除。'
        listo = '完成。现在可以删除压缩包和解压出来的文件夹。'
        abrir = '现在打开 MoonDeck 吗？[Y/n]'
    }
    ru = @{
        titulo = 'MoonDeck - установка'
        destino = 'Будет установлено в: {0}'
        abierto = 'MoonDeck (или старый Monitor de Hardware) открыт. Закройте его: значок в трее > Выход.'
        enter = 'Нажмите Enter, когда он закроется'
        p1 = '1/7 Копирование приложения'
        copiados = 'Скопировано файлов: {0}.'
        p2 = '2/7 Поиск Python (3.11–3.14)'
        sin_python = 'Подходящая версия не найдена. Python 3.12 будет установлен через winget.'
        python_falla = 'Не удалось найти Python после установки. Закройте это окно и снова запустите instalar.bat.'
        p3 = '3/7 Установка библиотек (PySide6, psutil, pythonnet, pycaw...) - займёт несколько минут'
        pip_falla = 'Не удалось установить библиотеки (pip). Сделайте снимок этого окна.'
        p4 = '4/7 Загрузка LibreHardwareMonitor {0} (датчики)'
        p5 = '5/7 Загрузка PresentMon {0} (измеритель FPS от Intel)'
        p6 = '6/7 Драйвер PawnIO'
        pawn = 'Он нужен, чтобы читать температуру CPU. Windows попросит права администратора.'
        pawn_preg = 'Установить или обновить PawnIO сейчас? [Д/n]'
        p7 = '7/7 Ярлыки'
        accesos = 'Созданы на рабочем столе и в меню «Пуск».'
        arranque = 'Запускать автоматически при входе в систему (без запроса UAC)? [д/N]'
        tarea = 'Запланированная задача создана.'
        no_borrar = 'Не удалось удалить {0} (какой-то файл занят); удалите папку вручную.'
        listo = 'Готово. Теперь можно удалить архив и распакованную папку.'
        abrir = 'Открыть MoonDeck сейчас? [Д/n]'
    }
}
$porSistema = @{ es = "1"; en = "2"; de = "3"; zh = "4"; ru = "5" }[(Get-UICulture).TwoLetterISOLanguageName]
if (-not $porSistema) { $porSistema = "2" }
Write-Host "MoonDeck" -ForegroundColor Green
Write-Host "  1) Español   2) English   3) Deutsch   4) 中文   5) Русский"
$r = Read-Host "> [$porSistema]"
if ([string]::IsNullOrWhiteSpace($r)) { $r = $porSistema }
$Idioma = @{ "1" = "es"; "2" = "en"; "3" = "de"; "4" = "zh"; "5" = "ru" }[$r.Trim()]
if (-not $Idioma) { $Idioma = "en" }
$T = $Textos[$Idioma]

Write-Host "`n$($T.titulo)" -ForegroundColor Green
Write-Host ($T.destino -f $Destino)

# 0. Monitor abierto ----------------------------------------------------------
function Abiertos {
    Get-Process pythonw, python -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -and ($_.Path.StartsWith($Destino, [StringComparison]::OrdinalIgnoreCase) -or
                      $_.Path.StartsWith($Viejo, [StringComparison]::OrdinalIgnoreCase)) }
}
while (Abiertos) {
    Write-Host "`n$($T.abierto)" -ForegroundColor Yellow
    Read-Host $T.enter
}

# 1. Archivos de la app -------------------------------------------------------
Paso $T.p1
New-Item -ItemType Directory $Destino -Force | Out-Null
$archivos = Get-ChildItem $Origen -File | Where-Object { $_.Extension -in ".py", ".bat", ".ps1", ".txt" }
foreach ($f in $archivos) { Copy-Item $f.FullName $Destino -Force }
# El LEEME y el README van en la raíz del zip, junto a instalar.bat.
foreach ($n in "LEEME.txt", "README.txt") {
    $leeme = Join-Path (Split-Path -Parent $Origen) $n
    if (Test-Path $leeme) { Copy-Item $leeme $Destino -Force }
}
# Quitar la marca de "descargado de internet" (si no, Windows avisa en cada .bat).
Get-ChildItem $Destino -File | Unblock-File
Set-Location $Destino
Write-Host ($T.copiados -f $archivos.Count)

# 2. Python ------------------------------------------------------------------
Paso $T.p2
$Python = Buscar-Python
if (-not $Python) {
    Write-Host $T.sin_python
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    Refrescar-Path
    $Python = Buscar-Python
    if (-not $Python) {
        Write-Host $T.python_falla -ForegroundColor Red
        exit 1
    }
}
Write-Host "Python: $Python"

# 3. Entorno y dependencias --------------------------------------------------
Paso $T.p3
$venvPython = ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    # Si el entorno es de un Python que ya no existe o no es compatible, se rehace.
    $ok = $false
    try { & $venvPython -c "import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] < (3, 15) else 1)" 2>$null; $ok = $LASTEXITCODE -eq 0 } catch { }
    if (-not $ok) { Remove-Item ".venv" -Recurse -Force }
}
if (-not (Test-Path $venvPython)) { & $Python -m venv .venv }
& $venvPython -m pip install --upgrade pip --quiet --disable-pip-version-check
& $venvPython -m pip install -r requirements.txt --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Write-Host $T.pip_falla -ForegroundColor Red; exit 1 }

# Configuración: la del antiguo "Monitor de Hardware" si es la primera vez, y el idioma elegido.
$Config = Join-Path $env:APPDATA "MoonDeck"
$ConfigVieja = Join-Path $env:APPDATA "MonitorHardware"
if (-not (Test-Path (Join-Path $Config "config.json")) -and (Test-Path $ConfigVieja)) {
    New-Item -ItemType Directory $Config -Force | Out-Null
    Get-ChildItem $ConfigVieja -Exclude "error.log" | Copy-Item -Destination $Config -Recurse -Force
}
New-Item -ItemType Directory $Config -Force | Out-Null
& $venvPython -c "import json, os, sys; r = sys.argv[1]; c = json.load(open(r, encoding='utf-8')) if os.path.exists(r) else {}; c['idioma'] = sys.argv[2]; json.dump(c, open(r, 'w', encoding='utf-8'), indent=1)" (Join-Path $Config "config.json") $Idioma

# 4. LibreHardwareMonitor ----------------------------------------------------
Paso ($T.p4 -f $LhmVersion)
$tmp = Join-Path $env:TEMP "lhm-monitor"
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory $tmp | Out-Null
Invoke-WebRequest $LhmUrl -OutFile "$tmp\lhm.zip" -UseBasicParsing
# Quitar la marca de "descargado de internet": .NET se niega a cargar DLLs marcadas.
Unblock-File "$tmp\lhm.zip"
Expand-Archive "$tmp\lhm.zip" "$tmp\x" -Force
New-Item -ItemType Directory "lib" -Force | Out-Null
Copy-Item "$tmp\x\*.dll" "lib\" -Force
Remove-Item $tmp -Recurse -Force

# 5. PresentMon --------------------------------------------------------------
Paso ($T.p5 -f $PmVersion)
Invoke-WebRequest $PmUrl -OutFile "lib\PresentMon.exe" -UseBasicParsing
Get-ChildItem "lib" | Unblock-File

# 6. Driver PawnIO -----------------------------------------------------------
Paso $T.p6
Write-Host $T.pawn
if (Pregunta $T.pawn_preg $true) {
    winget install -e --id namazso.PawnIO --accept-package-agreements --accept-source-agreements
}

# 7. Accesos directos --------------------------------------------------------
Paso $T.p7
$pythonw = Join-Path $Destino ".venv\Scripts\pythonw.exe"
$script = Join-Path $Destino "monitor.py"

function Crear-Acceso($ruta, $destino, $argumentos, $comoAdmin) {
    $sh = New-Object -ComObject WScript.Shell
    $lnk = $sh.CreateShortcut($ruta)
    $lnk.TargetPath = $destino
    $lnk.Arguments = $argumentos
    $lnk.WorkingDirectory = $Destino
    $lnk.IconLocation = "$env:SystemRoot\System32\shell32.dll,15"
    $lnk.Description = "MoonDeck"
    $lnk.Save()
    if ($comoAdmin) {
        # Marcar "Ejecutar como administrador" (byte 0x15, bit 0x20 del .lnk).
        $bytes = [IO.File]::ReadAllBytes($ruta)
        $bytes[0x15] = $bytes[0x15] -bor 0x20
        [IO.File]::WriteAllBytes($ruta, $bytes)
    }
}
$escritorio = [Environment]::GetFolderPath("Desktop")
$programas = [Environment]::GetFolderPath("Programs")
$menu = Join-Path $programas "MoonDeck"
New-Item -ItemType Directory $menu -Force | Out-Null
Crear-Acceso (Join-Path $escritorio "MoonDeck.lnk") $pythonw "`"$script`"" $true
Crear-Acceso (Join-Path $menu "MoonDeck.lnk") $pythonw "`"$script`"" $true
Crear-Acceso (Join-Path $menu "Desinstalar MoonDeck.lnk") (Join-Path $Destino "desinstalar.bat") "" $false
Write-Host $T.accesos
# Los de la version anterior ("Monitor de Hardware"), fuera.
Remove-Item (Join-Path $escritorio "Monitor de Hardware.lnk"), (Join-Path $programas "Monitor de Hardware") `
    -Recurse -Force -ErrorAction SilentlyContinue
$tareaVieja = [bool](Get-ScheduledTask -TaskName "Monitor de Hardware" -ErrorAction SilentlyContinue)

if (Pregunta $T.arranque $false) {
    # Una tarea con privilegios altos solo se puede registrar como administrador,
    # así que se genera un script pequeño y se ejecuta elevado.
    $usuario = "$env:USERDOMAIN\$env:USERNAME"
    $tareaPs1 = Join-Path $env:TEMP "monitor-hardware-tarea.ps1"
    @"
`$accion = New-ScheduledTaskAction -Execute '$pythonw' -Argument '"$script"' -WorkingDirectory '$Destino'
`$disparo = New-ScheduledTaskTrigger -AtLogOn -User '$usuario'
`$ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
`$quien = New-ScheduledTaskPrincipal -UserId '$usuario' -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName 'MoonDeck' -Action `$accion -Trigger `$disparo -Settings `$ajustes -Principal `$quien -Force
Unregister-ScheduledTask -TaskName 'Monitor de Hardware' -Confirm:`$false -ErrorAction SilentlyContinue
"@ | Out-File $tareaPs1 -Encoding UTF8
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$tareaPs1`"" -Verb RunAs -Wait
    Remove-Item $tareaPs1 -ErrorAction SilentlyContinue
    Write-Host $T.tarea
} elseif ($tareaVieja) {
    # La tarea de la version anterior apuntaria a una carpeta que ya no existe.
    Start-Process schtasks.exe -ArgumentList '/Delete /TN "Monitor de Hardware" /F' -Verb RunAs -Wait
}

# La carpeta de la version anterior ya no hace falta.
if (Test-Path $Viejo) {
    Remove-Item $Viejo -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path $Viejo) { Write-Host ($T.no_borrar -f $Viejo) -ForegroundColor Yellow }
}

Write-Host "`n$($T.listo)" -ForegroundColor Green
if (Pregunta $T.abrir $true) {
    Start-Process $pythonw -ArgumentList "`"$script`"" -WorkingDirectory $Destino -Verb RunAs
}
