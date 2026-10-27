"""Packs de widgets: MoonDeck trae el pack Básico; los demás se pueden borrar y volver a descargar.

Cada pack es un archivo pack_<id>.py (uno para Linux y otro para Windows, cada cual en su
carpeta) más los módulos compartidos que solo usa él. Todo va suelto en la carpeta de la app,
como el resto: así un actualizador viejo también los copia.

Un pack_<id>.py puede definir:
    WIDGETS            claves de sus tarjetas
    class Metodos      métodos que se añaden a Monitor (se escriben como si estuvieran en él)
    iniciar(app)       en Monitor.__init__, antes de construir las tarjetas
    construir(app, s)  crea sus tarjetas (app.tarjeta(...))
    arrancar(app)      tras construir: primeras lecturas y temporizadores
    aplicar(app, s)    con cada lectura de los sensores
    menu(app, tarjeta, menu)        su parte del clic derecho (solo si la tarjeta es suya)
    acciones(app, menu, ...)        su parte del menú general (bandeja)
    ajustes(ventana, cont)          su parte de Configuración > Widgets
    visibles(app, claves)           cuáles de sus tarjetas se ven (para no leer datos de más)
    salir(app)

Descargar un pack baja el zip del release de esta misma versión y saca solo sus archivos,
así siempre casan con el resto de la app.
"""

import importlib
import json
import os
import shutil
import sys
import tempfile
import threading
import traceback
import urllib.error
import urllib.request
import zipfile

from version import REPO, VERSION

from idioma import _

AGENTE = f"MoonDeck/{VERSION}"
ZIPS = {"linux": "MoonDeck-Linux.zip", "win32": "MoonDeck-Windows.zip"}

# (id, nombre, descripción, widgets que trae, módulos compartidos que solo usa él)
CATALOGO = (
    ("basico", "Básico", "Lo esencial. Viene con MoonDeck y no se puede borrar.",
     ("CPU", "GPU", "Memoria", "Almacenamiento", "Red", "Reloj", "Calendario", "Tiempo", "Multimedia",
      "Dispositivos de audio"), ()),
    ("hardware", "Hardware", "Más datos del equipo y de la conexión.",
     ("Sensores", "FPS", "Test de velocidad") if sys.platform == "win32" else ("Sensores", "Test de velocidad"),
     ("velocidad.py",)),
    ("discord", "Discord", "El canal de voz en el que estás, con los que hablan y sus volúmenes.",
     ("Discord",), ("discord_voz.py",)),
    ("escritorio", "Escritorio", "Un lanzador con tus aplicaciones.",
     ("Aplicaciones",), ("lanzador.py",)),
    ("ocio", "Ocio", "Minijuegos para los ratos muertos.",
     ("Juegos",), ("juegos.py", "dino_sprite.py")),
    ("servidor", "Servidor", "Para quien tiene un servidor en casa: Immich y contenedores de Docker.",
     ("Immich", "Docker"), ("immich.py", "contenedores.py")),
)


def info(ident):
    return next(p for p in CATALOGO if p[0] == ident)


def archivos(ident):
    return [f"pack_{ident}.py", *info(ident)[4]]


def borrable(ident):
    return ident != "basico"


def instalado(carpeta, ident):
    return not borrable(ident) or os.path.isfile(os.path.join(carpeta, f"pack_{ident}.py"))


def omitidos(borrados):
    """Archivos que no hay que copiar al actualizar: los de los packs que el usuario borró."""
    return {n for ident in borrados if any(p[0] == ident for p in CATALOGO) and borrable(ident)
            for n in archivos(ident)}


def cargar(carpeta, log=print):
    """Importa los pack_<id>.py que haya. Uno roto no impide arrancar: se apunta y se salta."""
    cargados = []
    for ident, *_resto in CATALOGO:
        if not borrable(ident) or not instalado(carpeta, ident):
            continue
        try:
            cargados.append(importlib.import_module(f"pack_{ident}"))
        except Exception:  # noqa: BLE001 - falta un módulo, versión distinta...
            log(f"No se pudo cargar el pack {ident}:\n" + traceback.format_exc())
    return cargados


def llamar(modulos, gancho, *args):
    """Llama al gancho de cada pack que lo tenga. Devuelve lo que devuelvan (sin los None)."""
    salida = []
    for m in modulos:
        fn = getattr(m, gancho, None)
        if fn:
            r = fn(*args)
            if r is not None:
                salida.append(r)
    return salida


class Gestor:
    """Borra y descarga packs. La descarga corre en un hilo; la interfaz lee `estado` y `error`."""

    def __init__(self, carpeta_app, config, guardar):
        self.carpeta = os.path.abspath(carpeta_app)
        self.config = config        # guarda la lista "packs_borrados"
        self.guardar = guardar
        self.estado = None          # None, descargando, listo, error
        self.ocupado_con = None     # el pack que se está descargando
        self.error = None
        self.cambiado = False       # hay que reiniciar para verlo
        self._hilo = None

    @property
    def desde_codigo(self):
        """Ejecutando desde el repositorio: ahí no se borra nada."""
        return os.path.isdir(os.path.join(self.carpeta, "..", "comun"))

    @property
    def ocupado(self):
        return self._hilo is not None and self._hilo.is_alive()

    def instalado(self, ident):
        return instalado(self.carpeta, ident)

    def _apuntar(self, ident, borrado):
        lista = [i for i in self.config.get("packs_borrados", []) if i != ident]
        if borrado:
            lista.append(ident)
        self.config["packs_borrados"] = lista
        self.guardar()

    def borrar(self, ident):
        if not borrable(ident) or self.desde_codigo or self.ocupado:
            return
        for n in archivos(ident):
            ruta = os.path.join(self.carpeta, n)
            if os.path.isfile(ruta):
                os.remove(ruta)
        shutil.rmtree(os.path.join(self.carpeta, "__pycache__"), ignore_errors=True)
        self._apuntar(ident, True)
        self.cambiado = True

    def descargar(self, ident):
        if self.ocupado:
            return
        self.error, self.estado, self.ocupado_con = None, "descargando", ident

        def trabajo():
            try:
                self._descargar(ident)
                self._apuntar(ident, False)
                self.cambiado = True
                self.estado = "listo"
            except Exception as e:  # noqa: BLE001 - sin internet, release sin zip...
                self.error, self.estado = str(e), "error"
            self.ocupado_con = None
        self._hilo = threading.Thread(target=trabajo, daemon=True)
        self._hilo.start()

    def _descargar(self, ident):
        etiqueta = f"v{VERSION}"
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/tags/{etiqueta}",
                                     headers={"User-Agent": AGENTE, "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                datos = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RuntimeError(_("La versión {v} no está publicada en GitHub.").format(v=VERSION)) from e
            raise RuntimeError(_("GitHub ha respondido {codigo}.").format(codigo=e.code)) from e
        nombre = ZIPS.get("win32" if sys.platform == "win32" else "linux")
        url = next((a["browser_download_url"] for a in datos.get("assets", []) if a.get("name") == nombre), None)
        if not url:
            raise RuntimeError(_("La versión {v} no trae {zip}.").format(v=VERSION, zip=nombre))
        with tempfile.TemporaryDirectory(prefix="moondeck-") as tmp:
            zip_ruta = os.path.join(tmp, "app.zip")
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENTE}),
                                        timeout=30) as r, open(zip_ruta, "wb") as f:
                shutil.copyfileobj(r, f)
            buscados = set(archivos(ident))
            with zipfile.ZipFile(zip_ruta) as z:
                # Los archivos de la app están junto a monitor.py (MoonDeck-Linux/ o MoonDeck/app/).
                base = next((n[:-len("monitor.py")] for n in z.namelist() if n.endswith("/monitor.py")), None)
                encontrados = {n[len(base):]: n for n in z.namelist()
                               if base is not None and n.startswith(base) and n[len(base):] in buscados}
                if f"pack_{ident}.py" not in encontrados:
                    raise RuntimeError(_("El zip descargado no trae ese pack."))
                for corto, largo in encontrados.items():
                    with z.open(largo) as origen, open(os.path.join(self.carpeta, corto), "wb") as destino:
                        shutil.copyfileobj(origen, destino)
