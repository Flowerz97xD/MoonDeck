#!/bin/bash
# Quita MoonDeck: la app, sus accesos, el arranque automático y la configuración.
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/MoonDeck"
IDIOMA=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('idioma','en'))" "$CONFIG/config.json" 2>/dev/null || echo en)
case "$IDIOMA" in
es) T1="=== Desinstalar MoonDeck ==="; T2="¿Seguro? Se borra también tu configuración. [s/N] "; T3="Desinstalado. Los paquetes del sistema (GTK, layer-shell...) se quedan."; T4="Pulsa Enter para cerrar." ;;
de) T1="=== MoonDeck deinstallieren ==="; T2="Sicher? Auch deine Einstellungen werden gelöscht. [j/N] "; T3="Deinstalliert. Die Systempakete (GTK, layer-shell...) bleiben."; T4="Enter zum Schließen." ;;
zh) T1="=== 卸载 MoonDeck ==="; T2="确定吗？你的设置也会被删除。[y/N] "; T3="已卸载。系统软件包（GTK、layer-shell…）会保留。"; T4="按回车关闭。" ;;
ru) T1="=== Удаление MoonDeck ==="; T2="Точно? Ваши настройки тоже удалятся. [д/N] "; T3="Удалено. Системные пакеты (GTK, layer-shell...) остаются."; T4="Нажмите Enter, чтобы закрыть." ;;
*)  T1="=== Uninstall MoonDeck ==="; T2="Sure? Your settings are deleted too. [y/N] "; T3="Uninstalled. The system packages (GTK, layer-shell...) stay."; T4="Press Enter to close." ;;
esac
echo "$T1"
read -r -p "$T2" r
[[ "$r" =~ ^[sSyYjJдД是] ]] || exit 0
pkill -f "MoonDeck/monitor.py" 2>/dev/null
rm -f "$HOME/.local/share/applications/moondeck.desktop" \
      "$HOME/.local/share/applications/moondeck-desinstalar.desktop" \
      "$HOME/.config/autostart/moondeck.desktop"
rm -rf "$CONFIG" "$HOME/.local/share/MoonDeck"
echo "$T3"
read -r -p "$T4"
