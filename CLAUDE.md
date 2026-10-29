# MoonDeck — guía para Claude

MoonDeck son widgets de cristal para el escritorio: Linux (GTK3) y Windows (PySide6).
El repo es de **blkshhh**. Si trabajas desde un fork, los cambios entran por pull request.
blkshhh los revisa y publica la versión: tú no publicas nada.

## Cómo trabajar (hazlo tú, sin preguntar cada paso)

Cuando el usuario pida un cambio:

1. **Ponte al día:** `gh repo sync` (fork ← blkshhh/MoonDeck) y después `git checkout main && git pull`.
2. **Rama nueva** para el cambio: `git checkout -b <nombre-corto>`.
3. **Hazlo** siguiendo las reglas de abajo.
4. **Pruébalo** (ver "Probar") y mira el `error.log`.
5. **Commit, push y PR:** `git push -u origin <rama>` y `gh pr create --repo blkshhh/MoonDeck --base main`.
   En el PR explica qué hace el cambio y cómo se ha probado.
6. Si el PR ya está abierto y hay que corregir algo, sube más commits a la misma rama: el PR se actualiza solo.

Al usuario solo le preguntas lo que de verdad tenga que decidir él (cómo quiere algo, qué se ve...),
no los pasos de git.

## Probar sin romper el MoonDeck instalado

- El MoonDeck instalado y el del código no se pisan si el de prueba usa otra carpeta de configuración.
  En Windows (cmd), desde la raíz del repo:
  ```
  python -m venv .venv
  .venv\Scripts\pip install -r windows\requirements.txt
  set APPDATA=%TEMP%\moondeck-prueba
  .venv\Scripts\python windows\monitor.py
  ```
  Su `error.log` queda en `%TEMP%\moondeck-prueba\MoonDeck\error.log`.
  Sin el `set APPDATA=...`, solo puede haber un MoonDeck a la vez: el segundo trae al que ya está
  abierto al frente y se cierra.
- Las temperaturas necesitan administrador. Para probar el resto no hace falta.
- **Nunca instales la copia del código encima de la oficial.** Desde el código, el botón
  "Buscar actualizaciones" no hace nada. La versión oficial se instala con el zip de
  github.com/blkshhh/MoonDeck/releases (`instalar.bat`) y se actualiza con ese botón.

## Reglas del código

- **Todo en español:** nombres, comentarios y textos. Sigue el estilo del código que tengas alrededor.
- **Textos de la interfaz:** van con `_("texto en español")`, y cada texto nuevo necesita su traducción en
  `comun/lang_en.py`, `lang_de.py`, `lang_ru.py` y `lang_zh.py`. No llames `_` a ninguna variable en
  una función que use `_()`.
- **Carpetas:** `linux/` (GTK), `windows/` (PySide6) y `comun/` (lo compartido). Si cambias algo de un lado,
  mira si el otro necesita lo mismo. Si solo lo haces para un sistema, dilo en el PR.
- **Widgets opcionales = packs:** `linux/pack_<id>.py` y/o `windows/pack_<id>.py`, uno por widget, registrados en
  `CATALOGO` de `comun/packs.py` (con los módulos de `comun/` que usen). Los packs hacen `from __main__ import *`
  y usan `M.<NOMBRE>` (`import __main__ as M`) para lo que cambia en marcha (colores del tema, ANCHO...).
  Los widgets nuevos empiezan ocultos.
- **Esferas y velocímetros** van en `comun/esferas.py`, dibujados con la API de lienzo (LienzoCairo / LienzoQt).
- **Tarjetas:** las filas que sobran cuando la tarjeta es baja se marcan como prescindibles
  (`add_w(..., prescindible=n)`) en vez de recortarse. Para mostrarlas u ocultarlas usa `poner_visible(w, ver)`,
  no `set_visible`/`setVisible`, o parpadean.
- **Windows:** `Monitor` no es un QObject: los temporizadores se crean como `QTimer()` sin padre
  (un `QTimer(self)` cerraba la app al arrancar). En `Tarjeta.add` solo se estiran `Grafica` y las clases con
  `ESTIRA = True`.
- **No toques** `comun/version.py` ni hagas releases o etiquetas.
- **Secretos:** `secreto_discord.py` y la carpeta `secretos/` nunca van al repo. Sin ellos, el widget de Discord
  no conecta con la aplicación de serie; para lo demás no hace falta.
