# MoonDeck

**English** · [Español](README.es.md)

![MoonDeck in panel mode](docs/capturas/panel.jpg)

Glass desktop widgets for **Linux (Pop!_OS / COSMIC)** and **Windows 10/11**.

They show in real time: CPU, memory, GPUs, network, disks, sensors (temperatures, fans, voltages…), FPS (Windows only), music and per-app volume, clock, calendar, weather, your Discord voice channel (and your server's channels, to join with a click), audio devices, an internet speed test, an app launcher, Immich and Docker server widgets and three mini-games (Minesweeper, 2048 and the Chrome dinosaur).

Two modes:
- **Widgets:** loose cards on the desktop.
- **Panel:** a full-screen grid (great for a second monitor) that you arrange by dragging.

Themes, colors, backgrounds and neon borders are changed from the Settings window.

Languages: English, Spanish, German, Chinese and Russian.

## Screenshots

Taken on Linux (COSMIC); the Windows version looks the same.

<table>
<tr>
<td><img src="docs/capturas/synthwave.jpg" alt="Synthwave"></td>
<td><img src="docs/capturas/pastel.jpg" alt="Pastel lavender"></td>
</tr>
<tr>
<td><img src="docs/capturas/tron.jpg" alt="Tron"></td>
<td><img src="docs/capturas/settings.jpg" alt="Settings window"></td>
</tr>
</table>

## Install

Download the zip for your system from [Releases](https://github.com/blkshhh/MoonDeck/releases/latest):
- **Linux:** extract it and run `./instalar.sh`.
- **Windows:** extract it and double-click `instalar.bat`.

The installer asks for the language. To update later: Settings > General > "Check for updates".

User instructions: `linux/README.txt` and `windows/README.txt` (Spanish: `LEEME.txt`).

Connecting the Discord widget: [docs/DISCORD.en.md](docs/DISCORD.en.md) (Spanish: [docs/DISCORD.md](docs/DISCORD.md)).

## Project layout

| Folder | Contents |
|---|---|
| `comun/` | Shared modules: themes (`tema.py`), weather (`tiempo.py`), Discord (`discord_voz.py`), speed test (`velocidad.py`), updater (`actualizar.py`) and translations (`idioma.py`, `lang_*.py`) |
| `linux/` | Linux version: GTK 3 + gtk-layer-shell, COSMIC blur (`glass.py`), sensors from `/sys/class/hwmon` and `nvidia-smi`, audio via PipeWire (`pactl`) and MPRIS |
| `windows/` | Windows version: PySide6 (Qt), acrylic glass, LibreHardwareMonitor, PresentMon (FPS) and pycaw/WinRT for audio |
| `secretos/` | **Not in Git.** `discord_client_secret.txt` with your Discord application's Client Secret |
| `dist/` | **Not in Git.** The zips built by `construir.sh` |

The code is written in Spanish; the UI strings are Spanish keys that `comun/idioma.py` translates with `comun/lang_*.py`.

## Building the zips

```bash
./construir.sh            # dist/: includes the Discord secret (for friends)
./construir.sh --publico  # dist/publico/: no secret (for Releases)
./publicar.sh 1.0.1 "Notes"  # bumps the version, tags and creates the Release
```

With `secretos/discord_client_secret.txt` present, the private zips carry the secret, so the Discord widget works with no setup for anyone added as a tester of your Discord application (discord.com/developers > App Testers). Only share those with people you trust.

## Running without installing

- **Linux:** `python3 linux/monitor.py`
- **Windows:** `python windows\monitor.py`, with `windows/requirements.txt` installed.

Settings are stored in `~/.config/MoonDeck` (Linux) or `%APPDATA%\MoonDeck` (Windows).

## License

MIT. Uses LibreHardwareMonitor (MPL 2.0), PawnIO and Intel's PresentMon (MIT).

The games are ported from [2048](https://github.com/gabrielecirulli/2048) by Gabriele Cirulli (MIT) and the Chromium offline dinosaur game (BSD 3-Clause, © The Chromium Authors; sprites in `comun/dino_sprite.py`, taken from [wayou/t-rex-runner](https://github.com/wayou/t-rex-runner)).
