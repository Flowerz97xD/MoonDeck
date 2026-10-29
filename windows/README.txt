MOONDECK FOR WINDOWS 10/11
==========================

Glass widgets that show in real time: CPU (usage, per-core usage, frequency,
temperature, power), memory, each GPU (usage, temperature, VRAM, power, clock,
fan), game FPS, network, disks, the sensors you choose (temperatures, fans,
voltages...), a media widget to control music and the volume of each app,
clock, calendar, weather, your Discord voice channel, audio devices (speakers,
headphones, microphone) and an internet speed test. Themes, colors,
backgrounds and neon borders to your liking from the Settings window.
Languages: Spanish, English, German, Chinese and Russian (menu > "Settings..." >
General > Language; by default, the system's).
Two modes: loose widgets on the desktop, or a full-screen panel (ideal for a
second monitor) that you can arrange however you like.


REQUIREMENTS
------------
- 64-bit Windows 10 or 11 (the glass effect looks best on Windows 11).
- Internet connection during the installation.
- Nothing else: the installer sets up Python and everything needed.


INSTALLATION (about 3-5 minutes)
--------------------------------
1. Extract the zip wherever you like (right-click > "Extract all"). For
   example in Downloads: the installer copies the app to its place, so you
   can delete the zip and the folder afterwards.
2. Double-click  instalar.bat
   - If Windows warns you ("Windows protected your PC" or "Security
     warning"): "More info" > "Run anyway", or "Run". It shows up because the
     script is not signed.
3. Follow the window. The installer:
   - asks for the language (for the installer and for MoonDeck),
   - installs Python 3.12 if you don't have a compatible version,
   - installs the libraries in their own folder, without touching the rest of
     the system,
   - downloads LibreHardwareMonitor (reads the sensors) and PresentMon
     (measures FPS),
   - asks whether to install the PawnIO driver: say YES (CPU temperatures),
   - creates shortcuts on the desktop and in the Start menu,
   - asks if you want it to start at login,
   - and if you want to open it now.

The app goes to  %LOCALAPPDATA%\Programs\MoonDeck
Your settings (positions, sensors...) to  %APPDATA%\MoonDeck

UPDATING TO A NEW VERSION: menu > "Settings..." > General > "Check for
updates". If there is a new version, "Update to ..." downloads it from
github.com/blkshhh/MoonDeck and "Restart MoonDeck" opens it. Your settings are
kept, and "Back to the previous one" undoes the update.
(Extracting the new zip and running instalar.bat again also works.)


USAGE
-----
Open "MoonDeck" from the desktop or the Start menu.
Windows will ask for administrator permission (UAC): accept.

There are two modes (you switch from the menu and the last one is remembered):

  WIDGETS MODE   each widget is a small glass window on the desktop. They
                 arrange themselves in columns, each with its own height and
                 right below the previous one. If you move one, they stay
                 where you leave them (also after restarting).
  PANEL MODE     a single full-screen window on the monitor you choose, with
                 all the widgets in a grid filling the screen. It adapts to
                 the resolution (1080p, 1440p, ultrawide...). Ideal for the
                 second monitor while gaming.

  Menu ....................... right-click a widget (or the panel background,
                               or the tray icon)
  Switch to panel mode ....... menu > "Panel mode (full screen) on..." >
                               choose the screen
  Back to widgets ............ menu > "Back to widgets mode"
  Move the panel to a monitor  menu > "Move the panel to..."
  Take a widget out of the
  panel ...................... right-click it > "Take out of the panel": it
                               gets its own window, ALWAYS ON TOP of the rest
                               (e.g. the FPS over the game on the other
                               monitor). Drag it wherever you want.
  Put it back in the panel ... right-click it > "Back to the panel"
  Customize the panel ........ menu > "Edit layout" (see below)
  Choose sensors ............. menu > "Choose sensors..." (see below)
  Hide/show widgets .......... menu > "Visible widgets"
  Move a widget .............. drag it with the left button (widgets mode or
                               widgets taken out of the panel)
  Show / hide everything ..... click the tray icon
  Rearrange in a grid ........ menu > "Rearrange widgets on..." > choose the screen
  Exit ....................... menu > "Exit", or Ctrl+Q
  Remove the title ........... right-click the widget > "Show title"
  Opacity of a widget ........ right-click it > "Opacity of this widget"
                               ("Apply to all widgets" copies that one)

In widgets mode, as long as you don't move any, they rearrange themselves when
one grows (e.g. when music starts playing). As soon as you drag one, they all
stay where they are, also after restarting. To go back to automatic placement:
menu > "Rearrange widgets on...".
Widgets taken out of the panel remember their position.

CUSTOMIZING THE PANEL
  Right-click > "Edit layout (move and resize)". The grid shows up and a bar
  appears at the top:
    - Drag a widget to ANY cell, even if it leaves gaps. If it lands on
      another one, that one moves to the place you left free.
    - Drag the bottom-right corner of a widget (the diagonal mark) to make it
      take more or fewer cells: e.g. Media at 2x2.
    - Columns - / + : how many columns the grid has.
    - Rows - / +    : "auto" uses just the needed ones; with a fixed number,
                      rows are shorter and there are free cells left.
    - Reset         : back to the default layout.
    - Done (or Esc) : finish editing.
  Also: right-click a widget > "Size in the grid" > Width/Height.
  Everything is saved automatically.

VISIBLE WIDGETS
  Menu > "Visible widgets": check or uncheck each widget (CPU, Memory, GPU,
  FPS, Network, Storage, Sensors, Media...). Also: right-click a widget >
  "Hide this widget".

SENSORS
  Menu (or right-click the Sensors widget) > "Choose sensors...".
  ALL the sensors the computer reads are listed, grouped by device and type:
  temperatures, fans, voltages, power, clocks, loads... There is a search box
  ("cpu", "voltage", "fan", "nvme"...). Check the ones you want to see (up to
  40). "Default" goes back to the automatic selection (temperatures and
  spinning fans).
  If the widget is wide, the sensors are split into several columns; if they
  don't all fit, it shows "... and N more": make it bigger or choose fewer.


SETTINGS (THEMES, COLORS, BACKGROUNDS...)
-----------------------------------------
Menu > "Settings...". Everything applies instantly:

  Theme ................ 19 built-in themes: Dark glass, Light glass, Solid
                         black, Purple neon, Ocean, Sunset, Cyberpunk,
                         Synthwave, Cybersecurity, Red alert, Tron, Vaporwave,
                         three pastels (lavender, peach and mint), Nord,
                         Dracula, Forest and Minimal. Also: accent color, text
                         colors, font and text size. "Export" / "Import" save
                         or load the theme in a .json file to share it.
  Widget options ....... the weather city, which day the calendar week starts
                         on (Monday or Sunday), the clock type and each
                         widget's options (Discord, speed test, apps...).
  Titles and backgrounds  remove the title or background of each widget.
  Style (widgets mode and panel mode, separately): background color and
                         opacity, gradient (two colors and direction), acrylic
                         glass on/off, border color, opacity and width, rounded corners,
                         "Neon mode" (the border shines like a neon tube) and
                         "Flicker" (the neon fails now and then, like an old
                         tube).
                         In panel mode, also the background covering the
                         whole screen: color and opacity.
  Layout and size ...... save the current panel layout as the one "Reset"
                         goes back to (or back to the factory one), and save
                         the current widget positions as the ones "Rearrange
                         widgets" uses; the widget width and the columns
                         when arranging them.
  Store ................ each extra widget (Sensors, FPS, Speed test, Discord,
                         Apps, Games, Immich, Docker) on its own: delete the
                         ones you don't use and download them again whenever
                         you want.
  General .............. language, open at login, the mouse wheel, how often
                         sensors are read, and updates.


WEATHER
-------
The weather of your city: now (temperature, feels like, humidity, wind,
sunrise and sunset), the next hours and the next 6 days with the chance of
rain. Data from Open-Meteo (free, no account); updated every 15 minutes. By
default, Barbate (Cádiz, Spain), the creator's hometown.
Right-click > "Change city..." (or Settings > Widget options) to search for
yours.


DISCORD
-------
The voice channel you are in: server, channel and who is there (a green ring
around whoever talks; red icons if their mic is off or they are deafened).
Next to each person, a button opens their volume (0-200 %) and "Mute" just for
you. At the bottom: the volume of your mic and your output, and Mute, Deafen
and Leave. Right-click > "Join a recent channel" (the last 8).

Discord only lets registered applications control voice: you need to create
one (free, only once, about 3 minutes). The "Connect to Discord..." window of
the widget explains the steps, and there is a full guide at:
  https://github.com/blkshhh/MoonDeck/blob/main/docs/DISCORD.en.md
Summary:
  1. discord.com/developers > "New Application" (any name works).
  2. OAuth2: copy the Client ID and the Client Secret ("Reset Secret"), and
     under Redirects add  http://localhost  and save.
  3. On the Discord widget: "Connect to Discord..." and paste both.
  4. Discord will ask you to "Authorize": accept. Only the first time.
If a friend invited you as a tester of their application and gave you their
MoonDeck, accept the invitation and leave the Client Secret empty.
The data is only stored in %APPDATA%\MoonDeck\discord.json.
It works with the Discord desktop app (not with the website).

When you're not in voice, the widget shows the voice channels of your server
(with who is in each one): click one to join. Choose your server in Settings >
Widget options > "Your Discord server". If Discord is closed, the "Open
Discord" button opens it minimized and, if you want, joins the last channel or
the one with most people (Settings > Widget options > Discord).


CLOCK, CALENDAR, AUDIO AND SPEED
--------------------------------
  Clock ............ adapts to the size of the widget or the cell.
                     Right-click it:
                       - "Clock type": Digital, Analog, Minimalist (just the
                         time, huge), World clock, Rings, Binary, Nixie
                         tubes, Flip cards or 7-segment LED.
                       - "24-hour format" and "Show seconds".
                       - "Cities": the world clock ones (up to 8).
  Calendar ......... the month with today highlighted; arrows to change the
                     month and click the month name to go back to today.
                     Right-click > "Week starts on": Monday or Sunday.
  Audio devices .... the output and the input (microphone) in use; "Change"
                     shows the others: click one to make it the Windows
                     default. Button to mute the microphone: it mutes all
                     the Windows default microphones (the multimedia one and
                     the communications one, used by Discord, Teams or games,
                     can be different).
  Speed test ....... a speedometer like a car's; "Start test" button: measures
                     ping, download and upload in about 15 s against
                     Cloudflare's servers (the ones of speed.cloudflare.com).
                     Right-click > "Speedometer style": Sporty, Needle or Ring.
                     It uses data like any speed test (up to ~500 MB on very
                     fast connections). The last result is saved.
  If you have too many widgets, hide them in menu > "Visible widgets".


MEDIA
-----
At the top, what is playing in each app (Spotify, Chrome, Edge, Firefox,
Media Player...): cover, song, artist, progress and previous / pause / next
buttons. If several are playing at once, they are all shown (up to 3), and
each one is controlled separately. Click the progress bar (or drag it) to
jump to another point of the song or video.
At the bottom, the mixer: general volume and the volume of each app with
sound (game, Discord, browser...), with a mute button. It is the same volume
as the Windows mixer.
Note: in the browser, control works with YouTube, Spotify Web, SoundCloud and
most music websites; some websites may not report the progress.


VIRTUAL DESKTOPS
----------------
Scroll the mouse wheel over a widget (except on volume bars and the like) to go
to the next or previous desktop. Ctrl + scroll down shows all desktops. Turn it
off in Settings > General.


IMMICH AND DOCKER
-----------------
Two widgets to manage your server (they start hidden: turn them on in menu >
"Visible widgets").
  Immich ........... disk space, how much photos and videos take (and each
                     user) and the queued jobs. Right-click > "Connect to
                     Immich..." and paste an admin API key (in Immich: Account
                     Settings > API Keys).
  Docker ........... the containers with their state (green, yellow or red
                     dot), uptime, CPU and RAM. Right-click one to stop, start
                     or restart it.


APPS
----
A launcher with the icons of the apps you choose (it starts hidden: turn it on
in menu > "Visible widgets" > Apps). Right-click > "Add app..." to choose them;
click an icon to open it; right-click an icon to remove or move it. "Icon
color": the original ones or tinted with the theme's accent or text color
(they follow the theme).


GAMES
-----
A widget with three mini-games (it starts hidden: turn it on in menu > "Visible
widgets" > Games). Right-click > "Game" to choose and "New game".
  Minesweeper ...... click to open a cell, right-click to place or remove a
                     flag, and click a number with all its flags to open the
                     cells around it. The first click is never a mine. The board
                     adapts to the size of the widget; the best time of each
                     size is saved.
  2048 ............. arrow keys (or W A S D), or drag with the mouse. The game
                     and the record are kept even if you close the app.
  Dinosaur ......... Chrome's: space, up arrow or click to jump (hold = higher)
                     and down arrow to duck.
To use the keyboard, click the game first. For the widget menu, right-click
outside the board (for example on the title).


FPS
---
The FPS widget measures the app in the foreground (the game you are playing)
with PresentMon, the Intel tool used by benchmark programs. It shows:
  - FPS ........ average of the last second
  - 1% low ..... FPS of the slowest 1% of frames in the last 10 s
                 (if it is much lower than the FPS, the game stutters)
  - frametime .. milliseconds per frame
Below the number you see the name of the program being measured.
With 2 monitors: even if you click the browser, Discord, Spotify, Steam or OBS
on the other monitor, it keeps measuring the game while it is open.
If no game is open it says "No games or 3D apps running".
It works with DirectX 9-12, Vulkan and OpenGL. It needs administrator rights.


WHY IT ASKS FOR ADMINISTRATOR RIGHTS
------------------------------------
Windows doesn't let programs read CPU temperatures and some sensors without
low-level access. LibreHardwareMonitor gets it with the PawnIO driver (open
source, signed), and that requires running as administrator.

If you'd rather not give it permissions: open  iniciar-sin-admin.bat  in the
app folder (%LOCALAPPDATA%\Programs\MoonDeck).
CPU usage, memory, network, disks and NVIDIA GPUs (via nvidia-smi) work, but
not the CPU, motherboard and disk temperatures, AMD/Intel GPUs or FPS.

If you choose to start at login, a scheduled task is created that opens it as
administrator without asking every time.


ADVANCED SETTINGS
-----------------
Open monitor.py (in %LOCALAPPDATA%\Programs\MoonDeck) with Notepad; the
settings are at the beginning:

  EFECTO = "acrilico"   set "ninguno" if the glass looks wrong or is slow
  (colors, backgrounds and opacity are changed in menu > "Settings...")
  INTERVALO = 1.0       seconds between updates
  COLUMNAS = 4          widgets per row when rearranging
  RECOLOCAR_AL_ABRIR = False  True = always arrange them automatically on open
  MAX_REPRODUCTORES = 3       apps with music shown at the same time
  MAX_APPS_VOLUMEN = 8        apps shown in the mixer


TROUBLESHOOTING
---------------
- No CPU temperature shows up:
  PawnIO is missing or it wasn't opened as administrator. Run instalar.bat
  again and say YES to PawnIO, and open MoonDeck with the shortcut.
  Note: some anti-cheats (e.g. FACEIT) block PawnIO.

- Some widget says something is missing ("lib\... is missing", "Media control
  not available", "Mixer not available"...): run instalar.bat again.

- No fan shows up: by default only the spinning ones and the graphics card
  ones (which say "stopped" when idle) are shown. Look in "Choose sensors...".
  If the motherboard doesn't report its fans, they won't show up.

- The FPS widget shows nothing with a game open:
  click the game window (it measures the app in the foreground). Some
  anti-cheats prevent measuring; it also happens with other FPS meters.

- Nothing opens / it closes immediately:
  press Win+R, type  %APPDATA%\MoonDeck\error.log  and Enter: the error is
  there. Send it to whoever gave you the app. You can also open depurar.bat
  (in the app folder) to see it in a console.

- The glass effect looks black or strange:
  check that Settings > Personalization > Colors > "Transparency effects" is
  on. If it still looks wrong, set EFECTO = "ninguno" in monitor.py.

- The installation fails at "Installing libraries": take a screenshot of the
  window and send it to whoever gave you the app.


UNINSTALLING
------------
Start menu > "MoonDeck" > "Desinstalar MoonDeck".
It removes the app, its shortcuts, the autostart and the settings.
Python and PawnIO stay installed; remove them from Settings > Apps if you
don't use them for anything else.


Credits: LibreHardwareMonitor (MPL 2.0), PawnIO and Intel's PresentMon (MIT).
Games: 2048 by Gabriele Cirulli (MIT) and the Chromium dinosaur (BSD,
(c) The Chromium Authors).
