"""Widget de Immich (fotos), para administrarlo: espacio del disco, lo que ocupa la
biblioteca (por tipo y por usuario) y las tareas en cola, por su API.

Hace falta la dirección del servidor y una clave de API de un administrador (en Immich:
Ajustes de la cuenta > Claves de API). Se guardan en immich.json, en la carpeta de
configuración (solo para el usuario). Todo va en un hilo; la interfaz lee `instantanea()`.
"""

import json
import os
import threading
import urllib.error
import urllib.request

URL_POR_DEFECTO = "http://localhost:2283"
AGENTE = "MoonDeck (widget de Immich)"

# Nombres de las colas de tareas de Immich.
COLAS = {"thumbnailGeneration": "Miniaturas", "metadataExtraction": "Metadatos", "videoConversion": "Conversión de vídeos",
         "faceDetection": "Detección de caras", "facialRecognition": "Reconocimiento facial",
         "smartSearch": "Búsqueda inteligente", "duplicateDetection": "Duplicados", "sidecar": "Archivos sidecar",
         "library": "Bibliotecas externas", "storageTemplateMigration": "Plantilla de almacenamiento",
         "migration": "Migración", "backgroundTask": "Tareas de fondo", "search": "Búsqueda",
         "notifications": "Notificaciones", "backupDatabase": "Copia de la base de datos", "ocr": "Texto en fotos"}


class Immich:
    def __init__(self, carpeta):
        self.ruta_config = os.path.join(carpeta, "immich.json")
        self.cfg = self._cargar()
        self.lock = threading.Lock()
        self.estado = "sin_config" if not self.cfg.get("clave") else "conectando"
        self.error = None
        self.datos = {}        # version, disco, fotos, videos, uso*, usuarios, tareas
        self.version = 0
        self._despertar = threading.Event()
        self._activo = threading.Event()
        threading.Thread(target=self._bucle, daemon=True).start()

    def permitir(self, si):
        """Con el widget oculto no consulta nada."""
        (self._activo.set if si else self._activo.clear)()

    # --- configuración -------------------------------------------------------

    def _cargar(self):
        try:
            with open(self.ruta_config) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def url(self):
        return (self.cfg.get("url") or URL_POR_DEFECTO).rstrip("/")

    def configurar(self, url, clave):
        self.cfg = {"url": url.strip() or URL_POR_DEFECTO, "clave": clave.strip()}
        try:
            fd = os.open(self.ruta_config, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # es una contraseña
            with os.fdopen(fd, "w") as f:
                json.dump(self.cfg, f, indent=1)
        except OSError:
            pass
        self._cambio(estado="conectando" if self.cfg["clave"] else "sin_config", error=None)
        self._despertar.set()

    def _cambio(self, **campos):
        with self.lock:
            for k, v in campos.items():
                setattr(self, k, v)
            self.version += 1

    # --- API -------------------------------------------------------------------

    def _api(self, ruta, metodo="GET", cuerpo=None):
        req = urllib.request.Request(self.url() + ruta, method=metodo, headers={
            "x-api-key": self.cfg.get("clave", ""), "User-Agent": AGENTE, "Accept": "application/json",
            **({"Content-Type": "application/json"} if cuerpo is not None else {})},
            data=None if cuerpo is None else json.dumps(cuerpo).encode())
        with urllib.request.urlopen(req, timeout=15) as r:
            datos = r.read()
            return json.loads(datos) if datos else None

    def _opcional(self, *rutas):
        """La primera de las rutas que responda (cambian entre versiones de Immich), o None."""
        for ruta in rutas:
            try:
                return self._api(ruta)
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    raise
            except (OSError, ValueError):
                pass
        return None

    def _bucle(self):
        while True:
            self._activo.wait()
            if self.cfg.get("clave"):
                try:
                    self._leer()
                except urllib.error.HTTPError as e:
                    self._cambio(estado="error", error="clave" if e.code in (401, 403) else f"HTTP {e.code}")
                except (OSError, ValueError) as e:
                    self._cambio(estado="error", error="conexion" if isinstance(e, OSError) else str(e))
            self._despertar.wait(30 if self.estado == "ok" else 20)
            self._despertar.clear()

    def _leer(self):
        version = self._api("/api/server/version")
        datos = {"version": "{major}.{minor}.{patch}".format(**version), "disco": None, "fotos": None,
                 "videos": None, "uso": None, "uso_fotos": None, "uso_videos": None, "usuarios": [], "tareas": None}
        disco = self._opcional("/api/server/storage")
        if disco:
            datos["disco"] = {"usado": disco.get("diskUseRaw", 0), "total": disco.get("diskSizeRaw", 0),
                              "pct": disco.get("diskUsagePercentage", 0)}
        stats = self._opcional("/api/server/statistics")  # solo con clave de administrador
        if stats:
            datos.update(fotos=stats.get("photos"), videos=stats.get("videos"), uso=stats.get("usage"),
                         uso_fotos=stats.get("usagePhotos"), uso_videos=stats.get("usageVideos"))
            datos["usuarios"] = sorted(({"nombre": u.get("userName") or "?", "uso": u.get("usage", 0)}
                                        for u in stats.get("usageByUser", [])), key=lambda u: -u["uso"])
        else:
            propias = self._opcional("/api/assets/statistics") or {}
            datos.update(fotos=propias.get("images"), videos=propias.get("videos"))
        colas = self._opcional("/api/queues", "/api/jobs")
        if colas is not None:
            datos["tareas"] = _tareas(colas)
        self._cambio(estado="ok", error=None, datos=datos)

    def poner_ia(self, activa):
        """Activa o desactiva el aprendizaje automático en los ajustes de Immich (para que, con
        su contenedor parado, no intente usarlo). En segundo plano."""
        def hacer():
            try:
                cfg = self._api("/api/system-config")
                cfg.setdefault("machineLearning", {})["enabled"] = activa
                self._api("/api/system-config", "PUT", cfg)
            except (urllib.error.HTTPError, OSError, ValueError):
                pass
        threading.Thread(target=hacer, daemon=True).start()

    def instantanea(self):
        with self.lock:
            return {"version": self.version, "estado": self.estado, "error": self.error, "datos": dict(self.datos)}


def _tareas(colas):
    """Colas con trabajo: [(nombre, en marcha, en espera)], de la que más tiene a la que menos.
    Acepta las dos formas de la API: {cola: {"jobCounts": …}} o [{"name", "statistics"}]."""
    if isinstance(colas, dict):
        colas = [{"name": k, "statistics": v.get("jobCounts") or v.get("statistics") or {}}
                 for k, v in colas.items() if isinstance(v, dict)]
    lista = []
    for c in colas:
        n = c.get("statistics") or c.get("jobCounts") or {}
        activas = n.get("active", 0)
        esperando = n.get("waiting", 0) + n.get("delayed", 0) + n.get("paused", 0)
        if activas or esperando:
            lista.append((COLAS.get(c.get("name"), c.get("name", "?")), activas, esperando))
    return sorted(lista, key=lambda t: -(t[1] + t[2]))


def tam_legible(n):
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unidad == "TB":
            return f"{n:.0f} {unidad}" if unidad in ("B", "KB") else f"{n:.1f} {unidad}"
        n /= 1024
