"""Actualizar MoonDeck a la última versión estable publicada en GitHub (Releases).

Solo cuando el usuario lo pide (botón en Configuración > General). Pasos:
1. Pregunta a la API de GitHub por el último release estable (los "pre-release" no cuentan).
2. Descarga el zip de su sistema, guarda una copia de la versión actual en
   "<carpeta>.anterior" (para "Volver a la versión anterior") y copia encima los
   archivos nuevos. Lo que no viene en el zip (la configuración, secreto_discord.py,
   el entorno de Python, las DLL de sensores...) no se toca.
3. En Windows, si cambian las librerías (requirements.txt), las instala.
4. La interfaz reinicia la app.

Todo corre en un hilo; la interfaz lee `estado`, `progreso`, `error`... cada poco.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile

from version import REPO, VERSION

from idioma import _

AGENTE = f"MoonDeck/{VERSION}"
ZIPS = {"linux": "MoonDeck-Linux.zip", "win32": "MoonDeck-Windows.zip"}
EXTENSIONES = (".py", ".bat", ".ps1", ".txt", ".sh")  # los archivos de la app (no carpetas)


def numero(version):
    """ "v1.2.10" -> (1, 2, 10), para comparar versiones."""
    partes = []
    for p in version.lstrip("vV").split("."):
        digitos = "".join(c for c in p if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    return tuple(partes)


class Actualizador:
    def __init__(self, carpeta_app):
        self.carpeta = os.path.abspath(carpeta_app)   # donde está monitor.py
        self.estado = None      # None, buscando, al_dia, nueva, descargando, instalando, listo, error
        self.version_nueva = None
        self.notas = ""
        self.progreso = 0.0
        self.error = None
        self._url = None
        self._hilo = None

    # --- datos para la interfaz ------------------------------------------------

    @property
    def version(self):
        return VERSION

    @property
    def desde_codigo(self):
        """Ejecutando desde el repositorio (git): ahí se actualiza con git pull."""
        return os.path.isdir(os.path.join(self.carpeta, "..", "comun"))

    @property
    def ocupado(self):
        return self._hilo is not None and self._hilo.is_alive()

    def carpeta_anterior(self):
        return self.carpeta.rstrip("\\/") + ".anterior"

    def hay_anterior(self):
        return os.path.isfile(os.path.join(self.carpeta_anterior(), "monitor.py"))

    def _lanzar(self, trabajo):
        if self.ocupado:
            return
        self.error = None

        def envoltorio():
            try:
                trabajo()
            except Exception as e:  # noqa: BLE001 - sin internet, sin permisos, zip roto...
                self.error = str(e)
                self.estado = "error"
        self._hilo = threading.Thread(target=envoltorio, daemon=True)
        self._hilo.start()

    # --- buscar ------------------------------------------------------------------

    def buscar(self):
        self._lanzar(self._buscar)

    def _buscar(self):
        self.estado = "buscando"
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest",
                                     headers={"User-Agent": AGENTE, "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                datos = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RuntimeError(_("Todavía no hay ninguna versión publicada.")) from e
            raise RuntimeError(_("GitHub ha respondido {codigo}.").format(codigo=e.code)) from e
        etiqueta = datos.get("tag_name", "")
        self.version_nueva = etiqueta.lstrip("vV")
        self.notas = (datos.get("body") or "").strip()
        nombre = ZIPS.get("win32" if sys.platform == "win32" else "linux")
        self._url = next((a["browser_download_url"] for a in datos.get("assets", []) if a.get("name") == nombre), None)
        if numero(etiqueta) <= numero(VERSION):
            self.estado = "al_dia"
        elif not self._url:
            raise RuntimeError(_("La versión {v} no trae {zip}.").format(v=self.version_nueva, zip=nombre))
        else:
            self.estado = "nueva"

    # --- actualizar ----------------------------------------------------------------

    def actualizar(self):
        self._lanzar(self._actualizar)

    def _actualizar(self):
        if not self._url:
            raise RuntimeError(_("Primero busca actualizaciones."))
        self.estado, self.progreso = "descargando", 0.0
        with tempfile.TemporaryDirectory(prefix="moondeck-") as tmp:
            zip_ruta = os.path.join(tmp, "nueva.zip")
            req = urllib.request.Request(self._url, headers={"User-Agent": AGENTE})
            with urllib.request.urlopen(req, timeout=30) as r, open(zip_ruta, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                leido = 0
                while True:
                    trozo = r.read(64 * 1024)
                    if not trozo:
                        break
                    f.write(trozo)
                    leido += len(trozo)
                    self.progreso = leido / total if total else 0.5
            self.estado = "instalando"
            extraido = os.path.join(tmp, "x")
            with zipfile.ZipFile(zip_ruta) as z:
                z.extractall(extraido)
            origen = self._carpeta_de_la_app(extraido)
            nuevos = [n for n in os.listdir(origen)
                      if os.path.isfile(os.path.join(origen, n)) and n.endswith(EXTENSIONES)]
            # En Windows, el LEEME y el README van fuera de app\, junto a instalar.bat.
            leemes = [os.path.join(os.path.dirname(origen), n) for n in ("LEEME.txt", "README.txt")]
            requisitos_antes = self._leer(os.path.join(self.carpeta, "requirements.txt"))
            self._copia_de_seguridad()
            for n in nuevos:
                shutil.copy2(os.path.join(origen, n), os.path.join(self.carpeta, n))
            for leeme in leemes:
                if os.path.isfile(leeme) and os.path.dirname(origen) != extraido:
                    shutil.copy2(leeme, os.path.join(self.carpeta, os.path.basename(leeme)))
            if sys.platform == "win32" and self._leer(os.path.join(self.carpeta, "requirements.txt")) != requisitos_antes:
                self._instalar_librerias()
        self.estado = "listo"

    @staticmethod
    def _carpeta_de_la_app(extraido):
        """La carpeta del zip que tiene monitor.py (MoonDeck-Linux/ o MoonDeck/app/)."""
        for raiz, _dirs, archivos in os.walk(extraido):
            if "monitor.py" in archivos:
                return raiz
        raise RuntimeError(_("El zip descargado no trae la app."))

    @staticmethod
    def _leer(ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None

    def _copia_de_seguridad(self):
        anterior = self.carpeta_anterior()
        shutil.rmtree(anterior, ignore_errors=True)
        os.makedirs(anterior)
        for n in os.listdir(self.carpeta):
            ruta = os.path.join(self.carpeta, n)
            if os.path.isfile(ruta) and n.endswith(EXTENSIONES):
                shutil.copy2(ruta, os.path.join(anterior, n))

    def _instalar_librerias(self):
        python = os.path.join(self.carpeta, ".venv", "Scripts", "python.exe")
        r = subprocess.run([python, "-m", "pip", "install", "-r", "requirements.txt", "--quiet",
                            "--disable-pip-version-check"], cwd=self.carpeta, capture_output=True, text=True,
                           creationflags=0x08000000)  # sin ventana
        if r.returncode != 0:
            raise RuntimeError(_("No se pudieron instalar las librerías nuevas:") + "\n" + (r.stderr or r.stdout)[-600:])

    # --- volver atrás --------------------------------------------------------------

    def volver_atras(self):
        self._lanzar(self._volver_atras)

    def _volver_atras(self):
        anterior = self.carpeta_anterior()
        if not self.hay_anterior():
            raise RuntimeError(_("No hay ninguna versión anterior guardada."))
        self.estado = "instalando"
        for n in os.listdir(anterior):
            shutil.copy2(os.path.join(anterior, n), os.path.join(self.carpeta, n))
        if sys.platform == "win32":
            self._instalar_librerias()
        shutil.rmtree(anterior, ignore_errors=True)
        self.estado = "listo"

    # --- reiniciar -------------------------------------------------------------------

    def reiniciar(self, salir):
        """Abre la app de nuevo (con un pequeño retraso, cuando esta ya se haya cerrado) y sale."""
        script = os.path.join(self.carpeta, "monitor.py")
        if sys.platform == "win32":
            # Hereda los permisos de administrador de esta (la tarea/acceso la abrió así).
            subprocess.Popen(["cmd", "/c", f'timeout /t 2 /nobreak >nul & start "" "{sys.executable}" "{script}"'],
                             creationflags=0x08000000 | 0x00000008, close_fds=True)  # sin ventana, desligado
        else:
            subprocess.Popen(["sh", "-c", f'sleep 1.5; exec "{sys.executable}" "{script}"'], start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        salir()
