#!/bin/bash
# Genera los zips de MoonDeck:
#   ./construir.sh            -> dist/          con el secreto de Discord (para tus colegas)
#   ./construir.sh --publico  -> dist/publico/  sin secreto (para GitHub Releases)
# Cada uno trae:
#   MoonDeck-Linux.zip    -> descomprimir y ./instalar.sh
#   MoonDeck-Windows.zip  -> descomprimir y doble clic en instalar.bat
set -e
cd "$(dirname "$0")"
RAIZ=$(pwd)
SECRETO="$RAIZ/secretos/discord_client_secret.txt"
PUBLICO=false
[ "$1" = "--publico" ] && PUBLICO=true
DIST="$RAIZ/dist"
$PUBLICO && DIST="$RAIZ/dist/publico"
BUILD="$DIST/build"
rm -rf "$BUILD"
mkdir -p "$BUILD"

secreto() {  # escribe secreto_discord.py en la carpeta $1 (si hay secreto y no es público)
    if ! $PUBLICO && [ -s "$SECRETO" ]; then
        printf '# Generado por construir.sh (no subir a Git)\nCLIENT_SECRET = "%s"\n' "$(tr -d '\r\n' < "$SECRETO")" \
            > "$1/secreto_discord.py"
    fi
}

# --- Linux: todo junto en una carpeta ---
L="$BUILD/MoonDeck-Linux"
mkdir -p "$L"
find linux -maxdepth 1 -type f -exec cp {} "$L/" \;
cp comun/*.py "$L/"
secreto "$L"
chmod +x "$L/instalar.sh" "$L/desinstalar.sh" "$L/monitor.py"

# --- Windows: instalar.bat, LEEME y README arriba, el resto en app\ ---
W="$BUILD/MoonDeck"
mkdir -p "$W/app"
cp windows/instalar.bat windows/LEEME.txt windows/README.txt "$W/"
for f in $(find windows -maxdepth 1 -type f); do
    case "$(basename "$f")" in instalar.bat|LEEME.txt|README.txt) ;; *) cp "$f" "$W/app/" ;; esac
done
cp comun/*.py "$W/app/"
secreto "$W/app"

find "$BUILD" -name __pycache__ -prune -exec rm -rf {} +
rm -f "$DIST/MoonDeck-Linux.zip" "$DIST/MoonDeck-Windows.zip"
(cd "$BUILD" && zip -qr "$DIST/MoonDeck-Linux.zip" MoonDeck-Linux && zip -qr "$DIST/MoonDeck-Windows.zip" MoonDeck)
echo "Listo (versión $(python3 -c 'import sys; sys.path.insert(0, "comun"); import version; print(version.VERSION)')):"
ls -l "$DIST"/*.zip
if $PUBLICO; then
    echo "(sin secreto de Discord: para publicar)"
elif [ -s "$SECRETO" ]; then
    echo "(con el secreto de Discord incluido: solo para gente de confianza)"
else
    echo "(sin secreto de Discord)"
fi
