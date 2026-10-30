"""Packs de widgets: MoonDeck trae el pack Básico; los demás se pueden borrar y volver a descargar.

Cada pack es un archivo pack_<id>.py (uno para Linux y otro para Windows, cada cual en su
carpeta) más los módulos compartidos que usa (solo los de los packs). Todo va suelto en la carpeta de la app,
como el resto: así un actualizador viejo también los copia.

Un pack_<id>.py puede definir:
    WIDGETS            claves de sus tarjetas
    class Metodos      métodos que se añaden a Monitor (se escriben como si estuvieran en él)
    iniciar(app)       en Monitor.__init__, antes de construir las tarjetas
    construir(app, s)  crea sus tarjetas (app.tarjeta(...))
    arrancar(app)      tras construir: primeras lecturas y temporizadores
    aplicar(app, s)    con cada lectura de los sensores
    menu(app, tarjeta, menu)        su parte del clic derecho (solo si la tarjeta es suya)
    titulo(app, tarjeta, punto)     el clic en el título de su tarjeta: si enseña algo suyo devuelve
                                    True; si no, sale el menú de opciones. `punto`: en Windows, el
                                    QPoint de debajo del título; en Linux, el evento del clic
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

# (id, nombre, descripción, widgets que trae, módulos compartidos que solo usan los packs)
# Un widget por pack (salvo el Básico): así cada cual instala solo lo que usa.
CATALOGO = tuple(p for p in (
    ("basico", "Básico", "Lo esencial. Viene con MoonDeck y no se puede borrar.",
     ("CPU", "GPU", "Memoria", "Almacenamiento", "Red", "Reloj", "Calendario", "Tiempo", "Multimedia",
      "Dispositivos de audio"), ()),
    ("sensores", "Sensores", "Temperaturas, ventiladores y demás sensores del equipo, los que elijas.",
     ("Sensores",), ()),
    ("fps", "FPS", "Los FPS del juego o la app 3D que tengas abiertos (con PresentMon).",
     ("FPS",), ()) if sys.platform == "win32" else None,
    ("velocidad", "Test de velocidad", "Mide el ping, la bajada y la subida de tu conexión.",
     ("Test de velocidad",), ("velocidad.py",)),
    ("discord", "Discord", "El canal de voz en el que estás, con los que hablan y sus volúmenes.",
     ("Discord",), ("discord_voz.py",)),
    ("escritorio", "Aplicaciones", "Un lanzador con tus aplicaciones.",
     ("Aplicaciones",), ("lanzador.py",)),
    ("ocio", "Juegos", "Minijuegos para los ratos muertos.",
     ("Juegos",), ("juegos.py", "minijuegos.py", "dino_sprite.py")),
    ("letras", "Letras", "La letra de lo que suena, sincronizada como en Spotify (también con discos enteros).",
     ("Letras",), ("letras.py",)),
    ("mascota", "Mascota", "Una mascota en pixel art que cuidar, que reacciona a lo que pasa en tu PC.",
     ("Mascota",), ("mascota.py", "letras.py")),
    ("movil", "Móvil", "Tu Android en el escritorio: sus apps en ventanas o el control total (con scrcpy).",
     ("Móvil",), ("movil.py",)) if sys.platform != "win32" else None,
    ("immich", "Immich", "Tu servidor de fotos Immich: espacio, biblioteca, tareas y la IA.",
     ("Immich",), ("immich.py", "contenedores.py")),
    ("docker", "Docker", "Tus contenedores de Docker: su estado, pararlos y arrancarlos.",
     ("Docker",), ("contenedores.py",)),
) if p)

# Los packs de antes (1.4.6–1.4.10) traían varios widgets: en qué se han partido.
PARTIDOS = {"hardware": ("sensores", "fps", "velocidad"), "servidor": ("immich", "docker")}


def info(ident):
    return next(p for p in CATALOGO if p[0] == ident)


def archivos(ident):
    return [f"pack_{ident}.py", *info(ident)[4]]


def borrable(ident):
    return ident != "basico"


def instalado(carpeta, ident):
    return not borrable(ident) or os.path.isfile(os.path.join(carpeta, f"pack_{ident}.py"))


def omitidos(borrados):
    """Archivos que no hay que copiar al actualizar: los de los packs que el usuario borró
    (menos los módulos que también usa otro pack que sí tiene)."""
    borrados = {i for i in borrados if any(p[0] == i for p in CATALOGO) and borrable(i)}
    usados = {n for p in CATALOGO if p[0] not in borrados for n in archivos(p[0])}
    return {n for ident in borrados for n in archivos(ident)} - usados


def migrar(carpeta, ruta_config):
    """Pasa los packs borrados de antes a los de ahora y quita los pack_*.py que ya no existen.
    Devuelve los ids borrados (para no cargarlos aunque un actualizador viejo copiara sus archivos)."""
    try:
        with open(ruta_config, encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, ValueError):
        config = {}
    borrados = config.get("packs_borrados", [])
    if any(i in PARTIDOS for i in borrados):
        borrados = list(dict.fromkeys(n for i in borrados for n in PARTIDOS.get(i, (i,))))
        config["packs_borrados"] = borrados
        try:
            with open(ruta_config, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except OSError:
            pass
    for viejo in PARTIDOS:
        try:
            os.remove(os.path.join(carpeta, f"pack_{viejo}.py"))
        except OSError:
            pass
    return set(borrados)


def cargar(carpeta, log=print, ruta_config=None):
    """Importa los pack_<id>.py que haya. Uno roto no impide arrancar: se apunta y se salta."""
    borrados = migrar(carpeta, ruta_config) if ruta_config else set()
    cargados = []
    for ident, *_resto in CATALOGO:
        if not borrable(ident) or ident in borrados or not instalado(carpeta, ident):
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
        return instalado(self.carpeta, ident) and ident not in self.config.get("packs_borrados", [])

    def _apuntar(self, ident, borrado):
        lista = [i for i in self.config.get("packs_borrados", []) if i != ident]
        if borrado:
            lista.append(ident)
        self.config["packs_borrados"] = lista
        self.guardar()

    def borrar(self, ident):
        if not borrable(ident) or self.desde_codigo or self.ocupado:
            return
        # Los módulos compartidos se quedan si otro pack instalado los usa (contenedores.py).
        usados = {n for p in CATALOGO if p[0] != ident and self.instalado(p[0]) for n in archivos(p[0])}
        for n in set(archivos(ident)) - usados:
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
