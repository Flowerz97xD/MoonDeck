#!/bin/bash
# Publica una versión nueva de MoonDeck en GitHub:
#   ./publicar.sh 1.1.0 "Novedades: ..."
#   ./publicar.sh 1.1.0 notas.md          (las novedades en un archivo)
# Cambia el número en comun/version.py, hace el commit y la etiqueta v1.1.0, lo
# sube, genera los zips públicos (sin secreto) y crea el release con ellos. El
# botón "Buscar actualizaciones" de la app lo verá enseguida.
set -e
cd "$(dirname "$0")"
VERSION="$1"
NOTAS="$2"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || [ -z "$NOTAS" ]; then
    echo "Uso: ./publicar.sh 1.2.3 \"novedades\"   (o un archivo .md con las novedades)"
    exit 1
fi
command -v gh >/dev/null || { echo "Falta gh (sudo apt install gh && gh auth login)"; exit 1; }
if [ -n "$(git status --porcelain)" ]; then
    echo "Hay cambios sin guardar en git. Haz commit (o descártalos) antes de publicar:"
    git status --short
    exit 1
fi
if git rev-parse "v$VERSION" >/dev/null 2>&1; then
    echo "La versión v$VERSION ya existe."
    exit 1
fi

sed -i "s/^VERSION = \".*\"/VERSION = \"$VERSION\"/" comun/version.py
if [ -n "$(git status --porcelain comun/version.py)" ]; then  # la primera vez ya puede estar puesta
    git add comun/version.py
    git commit -q -m "Versión $VERSION"
fi
git tag -a "v$VERSION" -m "MoonDeck $VERSION"
git push -q
git push -q origin "v$VERSION"

./construir.sh --publico
if [ -f "$NOTAS" ]; then
    gh release create "v$VERSION" dist/publico/MoonDeck-*.zip --title "MoonDeck $VERSION" --notes-file "$NOTAS"
else
    gh release create "v$VERSION" dist/publico/MoonDeck-*.zip --title "MoonDeck $VERSION" --notes "$NOTAS"
fi
echo
echo "Publicada la v$VERSION. Para tus colegas (con el secreto de Discord): ./construir.sh"
