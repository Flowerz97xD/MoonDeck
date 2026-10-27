# MoonDeck

[English](README.md) · **Español**

![MoonDeck en modo panel](docs/capturas/panel.jpg)

Widgets de cristal para el escritorio, para **Linux (Pop!_OS / COSMIC)** y **Windows 10/11**.

Muestran en tiempo real CPU, memoria, GPUs, red, discos, sensores (temperaturas, ventiladores, voltajes…), FPS (solo en Windows), música y volumen por app, reloj, calendario, el tiempo, el canal de voz de Discord (y los canales de tu servidor, para entrar con un clic), los dispositivos de audio, un test de velocidad, un lanzador de aplicaciones, widgets para administrar Immich y Docker y tres minijuegos (Buscaminas, 2048 y el dinosaurio de Chrome).

Hay dos modos:
- **Widgets:** tarjetas sueltas por el escritorio.
- **Panel:** una cuadrícula a pantalla completa que se edita arrastrando.

Los temas, colores, fondos y bordes de neón se cambian desde la ventana de Configuración.

Idiomas: español, inglés, alemán, chino y ruso (`comun/lang_*.py`; los textos del código están en español y `comun/idioma.py` los traduce).

Guía para conectar el widget de Discord: [docs/DISCORD.md](docs/DISCORD.md) (en inglés: [docs/DISCORD.en.md](docs/DISCORD.en.md)).

Las instrucciones para el usuario están en `linux/LEEME.txt` y `windows/LEEME.txt` (en inglés: `README.txt`).

## Capturas

Hechas en Linux (COSMIC); la versión de Windows se ve igual.

<table>
<tr>
<td><img src="docs/capturas/synthwave.jpg" alt="Synthwave"></td>
<td><img src="docs/capturas/pastel.jpg" alt="Pastel lavanda"></td>
</tr>
<tr>
<td><img src="docs/capturas/tron.jpg" alt="Tron"></td>
<td><img src="docs/capturas/settings.jpg" alt="Ventana de configuración"></td>
</tr>
</table>

## Instalar

Descarga el zip de tu sistema en [Releases](https://github.com/blkshhh/MoonDeck/releases/latest):
- **Linux:** descomprime y ejecuta `./instalar.sh`.
- **Windows:** descomprime y haz doble clic en `instalar.bat`.

Para actualizar: Configuración > General > "Buscar actualizaciones".

## Estructura

| Carpeta | Qué hay |
|---|---|
| `comun/` | Módulos compartidos: temas (`tema.py`), el tiempo (`tiempo.py`), Discord (`discord_voz.py`) y el test de velocidad (`velocidad.py`) |
| `linux/` | Versión de Linux: GTK 3 + gtk-layer-shell, desenfoque de COSMIC (`glass.py`), sensores de `/sys/class/hwmon` y `nvidia-smi`, audio con PipeWire (`pactl`) y MPRIS |
| `windows/` | Versión de Windows: PySide6 (Qt), cristal acrílico, LibreHardwareMonitor, PresentMon (FPS) y pycaw/WinRT para el audio |
| `secretos/` | **No se sube a Git.** `discord_client_secret.txt` con el Client Secret de la aplicación de Discord |
| `dist/` | **No se sube a Git.** Los zips que genera `construir.sh` |

## Generar los zips para repartir

```bash
./construir.sh            # dist/: con el secreto de Discord (para amigos)
./construir.sh --publico  # dist/publico/: sin secreto (para Releases)
./publicar.sh 1.0.1 "Notas"  # sube la versión, etiqueta y crea la Release
```

Crea:
- `dist/MoonDeck-Linux.zip`: se descomprime y se ejecuta `./instalar.sh`.
- `dist/MoonDeck-Windows.zip` (Windows): se descomprime y se ejecuta `instalar.bat`.

Si existe `secretos/discord_client_secret.txt`, el secreto va dentro de los zips. Así el widget de Discord funciona sin configurar nada para quien esté añadido como tester de la aplicación (discord.com/developers > App Testers). Esos zips solo se pasan a gente de confianza.

## Probar sin instalar

- **Linux:** `python3 linux/monitor.py`. Los módulos de `comun/` se encuentran solos.
- **Windows:** `python windows\monitor.py`, con las librerías de `windows/requirements.txt` instaladas.

En los dos casos, la configuración se guarda en `~/.config/MoonDeck` (Linux) o en `%APPDATA%\MoonDeck` (Windows).

## Licencia

MIT. Usa LibreHardwareMonitor (MPL 2.0), PawnIO y PresentMon de Intel (MIT).

Los juegos son una adaptación de [2048](https://github.com/gabrielecirulli/2048) de Gabriele Cirulli (MIT) y del juego del dinosaurio de Chromium (BSD de 3 cláusulas, © The Chromium Authors; los dibujos están en `comun/dino_sprite.py`, sacados de [wayou/t-rex-runner](https://github.com/wayou/t-rex-runner)).
