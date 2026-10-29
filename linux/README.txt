MOONDECK FOR LINUX (Pop!_OS / COSMIC)
=====================================

Glass widgets that show in real time: CPU (usage, per-core usage, frequency,
temperature, power), memory, each GPU (usage, temperature, VRAM, power, clock,
fan), network, disks, the sensors you choose (temperatures, fans, voltages...),
a media widget to control music and the volume of each app, clock, calendar,
weather, your Discord voice channel, audio devices (speakers, headphones,
microphone) and an internet speed test. Themes, colors, backgrounds and neon
borders to your liking from the Settings window.
Languages: Spanish, English, German, Chinese and Russian (menu > "Settings..." >
General > Language; by default, the system's).
Two modes: loose widgets on the desktop, or a full-screen panel (ideal for a
second monitor) that you can arrange however you like.


REQUIREMENTS
------------
- Pop!_OS 24.04 with COSMIC (Ubuntu 24.04 or similar also work; the glass
  effect and placing the widgets need a Wayland desktop with "layer-shell":
  COSMIC, KDE Plasma, Hyprland, Sway...).
- No administrator rights to use it. The installer only asks for your password
  to install a few small system packages with apt.


INSTALLATION (1 minute)
-----------------------
1. Extract the zip wherever you like.
2. Open a terminal in that folder (right-click > "Open in terminal") and run:
        ./instalar.sh
   The installer:
   - asks for the language (for the installer and for MoonDeck),
   - installs whatever is missing with apt (GTK, gtk-layer-shell, tray icon...),
   - copies the app to ~/.local/share/MoonDeck,
   - adds it to the applications menu as "MoonDeck",
   - asks if you want it to start at login,
   - and if you want to open it now.
   Afterwards you can delete the zip and the folder.

Your settings (positions, sensors...) are kept in ~/.config/MoonDeck

UPDATING TO A NEW VERSION: menu > "Settings..." > General > "Check for
updates". If there is a new version, "Update to ..." downloads it from
github.com/blkshhh/MoonDeck and "Restart MoonDeck" opens it. Your settings are
kept, and "Back to the previous one" undoes the update.
(Extracting the new zip and running ./instalar.sh again also works.)


USAGE
-----
Open "MoonDeck" from the applications menu.

There are two modes (you switch from the menu and the last one is remembered):

  WIDGETS MODE   each widget is a glass card on the desktop, below the
                 windows (like the wallpaper). They arrange themselves in
                 columns, each with its own height and right below the
                 previous one. If you move one, they stay where you leave
                 them (also after restarting).
  PANEL MODE     a single full-screen layer on the monitor you choose, with
                 all the widgets in a grid filling the screen. It also stays
                 below the windows. Ideal for the second monitor while gaming.

  The widgets and the panel are shown on ALL virtual desktops: they are part
  of the desktop, like the wallpaper or the COSMIC panel.

  Menu ....................... right-click a widget (or the panel background,
                               or the tray icon)
  Switch to panel mode ....... menu > "Panel mode (full screen) on..." >
                               choose the screen
  Back to widgets ............ menu > "Back to widgets mode"
  Move the panel to a monitor  menu > "Move the panel to..."
  Take a widget out of the
  panel ...................... right-click it > "Take out of the panel": it
                               gets its own window, ALWAYS ON TOP of everything
                               (also of a full-screen game). Drag it wherever
                               you want.
  Put it back in the panel ... right-click it > "Back to the panel"
  Customize the panel ........ menu > "Edit layout" (see below)
  Choose sensors ............. menu > "Choose sensors..." (see below)
  Hide/show widgets .......... menu > "Visible widgets"
  Move a widget .............. drag it with the left button (widgets mode or
                               widgets taken out of the panel)
  Show / hide everything ..... menu > "Show / hide"
  Rearrange in a grid ........ menu > "Rearrange widgets on..." > choose the screen
  Exit ....................... menu > "Exit", or Ctrl+Q on a clicked widget
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

SENSORS
  Menu (or right-click the Sensors widget) > "Choose sensors...".
  ALL the sensors the computer reads are listed, grouped by device and type:
  temperatures, fans, voltages, power, clocks, loads... There is a search box
  ("cpu", "voltage", "fan", "nvme"...). Check the ones you want to see (up to
  40). "Default" goes back to the automatic selection (temperatures and fans).
  If the widget is wide, the sensors are split into several columns; if they
  don't all fit, it shows "... and N more": make it bigger or choose fewer.


CLOCK, CALENDAR, AUDIO AND SPEED
--------------------------------
  Clock ............ adapts to the size of the widget or the cell.
                     Right-click it: "Clock type" (Digital, Analog,
                     Minimalist, World clock, Rings, Binary, Nixie tubes, Flip
                     cards or 7-segment LED), "24-hour format",
                     "Show seconds" and "Cities" (up to 8).
  Calendar ......... the month with today highlighted; arrows to change the
                     month and click the month name to go back to today.
                     Right-click > "Week starts on": Monday or Sunday.
  Audio devices .... the output and the input (microphone) in use; "Change"
                     shows the others to pick another one. Button to mute the
                     default microphone.
  Speed test ....... a speedometer like a car's; "Start test" button: measures
                     ping, download and upload in about 15 s against
                     Cloudflare's servers. Right-click > "Speedometer style":
                     Sporty, Needle or Ring. It uses data like any speed test
                     (up to ~500 MB on very fast connections). The last result
                     is saved.


MEDIA
-----
At the top, what is playing in each app (Spotify, Firefox, Chrome, VLC...):
cover, song, artist, progress and previous / pause / next buttons. If several
are playing at once, they are all shown (up to 3). Click the progress bar (or
drag it) to jump to another point of the song or video.
At the bottom, the mixer: general volume and the volume of each app with
sound, with a mute button. It is the same volume as COSMIC's (PipeWire).


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
The voice channel you are in: server, channel and who is there (whoever talks
lights up in green; red icons if their mic is off or they are deafened). Next
to each person, a button opens their volume (0-200 %) and "Mute" just for you.
At the bottom: the volume of your mic and your output, and the Mute, Deafen
and Leave buttons. Right-click > "Join a recent channel" to go back to the
last 8 channels.

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
The data is only stored in ~/.config/MoonDeck/discord.json.
It works with the official Discord (also with Vencord) and with Vesktop.

When you're not in voice, the widget shows the voice channels of your server
(with who is in each one): click one to join. Choose your server in Settings >
Widget options > "Your Discord server". If Discord is closed, the "Open
Discord" button opens it minimized and, if you want, joins the last channel or
the one with most people (Settings > Widget options > Discord).


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
There is no FPS widget on Linux: there is no general way to measure the FPS of
any game from outside, like PresentMon does on Windows. To see them, use
MangoHud (sudo apt install mangohud; in Steam: game properties > launch
options: mangohud %command%).


SETTINGS (THEMES, COLORS, BACKGROUNDS...)
-----------------------------------------
Right-click any widget (or the tray icon) > "Settings...". Everything applies
instantly:

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
                         opacity, gradient (two colors and direction), blur
                         on/off, border color, opacity and width, rounded corners, "Neon
                         mode" (the border shines like a neon tube) and
                         "Flicker" (the neon fails now and then, like an old
                         tube).
                         In panel mode, also the background covering the
                         whole screen: color and opacity.
  Layout and size ...... save the current panel layout as the one "Reset"
                         goes back to (or back to the factory one), and save
                         the current widget positions as the ones "Rearrange
                         widgets" uses; the widget width and the columns
                         when arranging them.
  Store ................ each extra widget (Sensors, Speed test, Discord, Apps,
                         Games, Immich, Docker) on its own: delete the ones
                         you don't use and download them again whenever you
                         want.
  General .............. language, open at login, the mouse wheel, how often
                         sensors are read, and updates.


TROUBLESHOOTING
---------------
- No motherboard fan shows up: Linux doesn't always load the motherboard
  sensor driver. Try:
      sudo apt install lm-sensors && sudo sensors-detect
  (answer everything with Enter) and restart.

- The widgets show up as normal windows and can't be placed:
  gtk-layer-shell is missing or the desktop doesn't support it (e.g. GNOME).
  Run ./instalar.sh again.

- Nothing opens: look at ~/.config/MoonDeck/error.log, or open it from a
  terminal to see the error:
      python3 ~/.local/share/MoonDeck/monitor.py

- The tray icon doesn't show: in COSMIC, add the "Notification area" applet
  to the panel. Without the icon, the menu is still on the right-click.


UNINSTALLING
------------
Applications menu > "Uninstall MoonDeck" (or run
~/.local/share/MoonDeck/desinstalar.sh). It removes the app, its shortcuts,
the autostart and the settings.
