#!/bin/bash
# Instalador de MoonDeck para Linux (pensado para Pop!_OS / COSMIC, vale en Ubuntu 24.04+).
# Volver a ejecutarlo actualiza a la versión de esta carpeta; la configuración se conserva.
# Pregunta el idioma (el del instalador y el de MoonDeck).
set -e
cd "$(dirname "$0")"
DESTINO="$HOME/.local/share/MoonDeck"
APPS="$HOME/.local/share/applications"
AUTO="$HOME/.config/autostart"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/MoonDeck"
VIEJA="${XDG_CONFIG_HOME:-$HOME/.config}/MonitorHardware"

# --- Idioma -------------------------------------------------------------------
case "${LANGUAGE:-${LC_ALL:-${LANG:-en}}}" in
    es*) PROPUESTO=1 ;; de*) PROPUESTO=3 ;; zh*) PROPUESTO=4 ;; ru*) PROPUESTO=5 ;; *) PROPUESTO=2 ;;
esac
echo "MoonDeck"
echo "  1) Español   2) English   3) Deutsch   4) 中文   5) Русский"
read -r -p "> [$PROPUESTO] " r
case "${r:-$PROPUESTO}" in 1) IDIOMA=es ;; 3) IDIOMA=de ;; 4) IDIOMA=zh ;; 5) IDIOMA=ru ;; *) IDIOMA=en ;; esac

case "$IDIOMA" in
es)
    T_TITULO="=== MoonDeck: instalación ==="
    T_FALTAN="Hacen falta estos paquetes del sistema:"
    T_APT="Se instalan con apt (te pedirá tu contraseña)."
    T_PAQ_OK="Paquetes del sistema: ya están todos."
    T_COPIANDO="Copiando la app a"
    T_ARRANQUE="¿Arrancar MoonDeck al iniciar sesión? [S/n] "
    T_ARRANQUE_OK="Arranque automático: activado."
    T_VIEJO="(El arranque de la versión anterior se ha quitado.)"
    T_LISTO="Instalado. Lo tienes en el menú de aplicaciones como \"MoonDeck\"."
    T_ABRIR="¿Abrirlo ahora? [S/n] " ;;
de)
    T_TITULO="=== MoonDeck: Installation ==="
    T_FALTAN="Diese Systempakete werden benötigt:"
    T_APT="Sie werden mit apt installiert (fragt nach deinem Passwort)."
    T_PAQ_OK="Systempakete: alle vorhanden."
    T_COPIANDO="App wird kopiert nach"
    T_ARRANQUE="MoonDeck bei der Anmeldung starten? [J/n] "
    T_ARRANQUE_OK="Autostart: aktiviert."
    T_VIEJO="(Der Autostart der vorherigen Version wurde entfernt.)"
    T_LISTO="Installiert. Du findest es im Anwendungsmenü als \"MoonDeck\"."
    T_ABRIR="Jetzt öffnen? [J/n] " ;;
zh)
    T_TITULO="=== MoonDeck：安装 ==="
    T_FALTAN="需要以下系统软件包："
    T_APT="将用 apt 安装（会要求输入你的密码）。"
    T_PAQ_OK="系统软件包：都已安装。"
    T_COPIANDO="正在把应用复制到"
    T_ARRANQUE="登录时启动 MoonDeck？[Y/n] "
    T_ARRANQUE_OK="开机自启：已开启。"
    T_VIEJO="（已移除旧版本的开机自启。）"
    T_LISTO="安装完成。在应用菜单中名为 \"MoonDeck\"。"
    T_ABRIR="现在打开吗？[Y/n] " ;;
ru)
    T_TITULO="=== MoonDeck: установка ==="
    T_FALTAN="Нужны эти системные пакеты:"
    T_APT="Они ставятся через apt (будет запрошен ваш пароль)."
    T_PAQ_OK="Системные пакеты: все уже есть."
    T_COPIANDO="Копирование приложения в"
    T_ARRANQUE="Запускать MoonDeck при входе в систему? [Д/n] "
    T_ARRANQUE_OK="Автозапуск: включён."
    T_VIEJO="(Автозапуск предыдущей версии удалён.)"
    T_LISTO="Установлено. Ищите \"MoonDeck\" в меню приложений."
    T_ABRIR="Открыть сейчас? [Д/n] " ;;
*)
    T_TITULO="=== MoonDeck: installation ==="
    T_FALTAN="These system packages are needed:"
    T_APT="They are installed with apt (it will ask for your password)."
    T_PAQ_OK="System packages: all present."
    T_COPIANDO="Copying the app to"
    T_ARRANQUE="Start MoonDeck at login? [Y/n] "
    T_ARRANQUE_OK="Autostart: enabled."
    T_VIEJO="(The autostart of the previous version was removed.)"
    T_LISTO="Installed. You'll find it in the applications menu as \"MoonDeck\"."
    T_ABRIR="Open it now? [Y/n] " ;;
esac
no() { [[ "$1" =~ ^[nNнН否] ]]; }  # "no" en cualquiera de los idiomas

echo
echo "$T_TITULO"
echo

PAQUETES="python3 python3-gi python3-gi-cairo python3-psutil gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 gir1.2-ayatanaappindicator3-0.1 pulseaudio-utils pciutils"
FALTAN=""
for p in $PAQUETES; do
    dpkg -s "$p" >/dev/null 2>&1 || FALTAN="$FALTAN $p"
done
if [ -n "$FALTAN" ]; then
    echo "$T_FALTAN$FALTAN"
    echo "$T_APT"
    sudo apt-get update -q
    sudo apt-get install -y $FALTAN
else
    echo "$T_PAQ_OK"
fi

# Cerrar la versión que esté abierta (la de ahora o la antigua "Monitor de Hardware").
pkill -f "^python3 $DESTINO/monitor.py" 2>/dev/null || true
pkill -f "^python3 $HOME/.local/share/MonitorHardware/monitor.py" 2>/dev/null || true

echo "$T_COPIANDO $DESTINO ..."
mkdir -p "$DESTINO" "$APPS"
cp ./*.py desinstalar.sh LEEME.txt README.txt "$DESTINO/"
chmod +x "$DESTINO/monitor.py" "$DESTINO/desinstalar.sh"

# Configuración: la del antiguo "Monitor de Hardware" si es la primera vez, y el idioma elegido.
if [ ! -e "$CONFIG/config.json" ] && [ -d "$VIEJA" ]; then
    mkdir -p "$CONFIG"
    cp -rn "$VIEJA"/. "$CONFIG"/
fi
mkdir -p "$CONFIG"
python3 - "$CONFIG/config.json" "$IDIOMA" <<'PY'
import json, sys
ruta, idioma = sys.argv[1], sys.argv[2]
try:
    with open(ruta) as f:
        config = json.load(f)
except (OSError, ValueError):
    config = {}
config["idioma"] = idioma
with open(ruta, "w") as f:
    json.dump(config, f, indent=1)
PY

cat > "$APPS/moondeck.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=MoonDeck
Comment=Widgets: CPU, GPU, RAM, network, disks, sensors, music, clock, weather, Discord...
Exec=python3 $DESTINO/monitor.py
Icon=utilities-system-monitor
Terminal=false
Categories=System;Monitor;
StartupNotify=false
DESK
cat > "$APPS/moondeck-desinstalar.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Uninstall MoonDeck
Name[es]=Desinstalar MoonDeck
Name[de]=MoonDeck deinstallieren
Name[zh]=卸载 MoonDeck
Name[ru]=Удалить MoonDeck
Exec=$DESTINO/desinstalar.sh
Icon=edit-delete
Terminal=true
Categories=System;
DESK

# Versiones anteriores ("Monitor de Hardware" y el prototipo ~/hwmonitor): que no
# queden dos en el menú ni en el arranque.
VIEJO_AUTO=false
[ -f "$AUTO/monitor-hardware.desktop" ] && VIEJO_AUTO=true
rm -f "$APPS/monitor-hardware.desktop" "$APPS/monitor-hardware-desinstalar.desktop" "$AUTO/monitor-hardware.desktop"
rm -rf "$HOME/.local/share/MonitorHardware"
if grep -qs "hwmonitor/hwmonitor.py" "$APPS/hwmonitor.desktop"; then
    rm -f "$APPS/hwmonitor.desktop"
fi
update-desktop-database "$APPS" >/dev/null 2>&1 || true

echo
read -r -p "$T_ARRANQUE" r
if ! no "$r"; then
    mkdir -p "$AUTO"
    cp "$APPS/moondeck.desktop" "$AUTO/moondeck.desktop"
    echo "X-GNOME-Autostart-Delay=3" >> "$AUTO/moondeck.desktop"
    echo "$T_ARRANQUE_OK"
else
    rm -f "$AUTO/moondeck.desktop"
fi
$VIEJO_AUTO && echo "$T_VIEJO"

echo
echo "$T_LISTO"
read -r -p "$T_ABRIR" r
if ! no "$r"; then
    setsid python3 "$DESTINO/monitor.py" >/dev/null 2>&1 < /dev/null &
fi
