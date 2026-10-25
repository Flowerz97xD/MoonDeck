"""Multimedia en Linux: qué suena en cada app (con controles) y volumen por app.

- Reproductores: MPRIS por D-Bus, el estándar que usan Spotify, Firefox, Chrome,
  VLC, Rhythmbox... (lo mismo que las teclas multimedia).
- Mezclador y dispositivos: PipeWire/PulseAudio a través de `pactl`.

Todo se lee en hilos aparte; la interfaz solo recoge el último resultado.
"""

import os
import queue
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from idioma import _

NOMBRES_APPS = (
    ("spotify", "Spotify"), ("chrom", "Chrome"), ("firefox", "Firefox"), ("brave", "Brave"),
    ("opera", "Opera"), ("vivaldi", "Vivaldi"), ("edge", "Edge"), ("vlc", "VLC"),
    ("discord", "Discord"), ("vesktop", "Discord"), ("steam", "Steam"), ("rhythmbox", "Rhythmbox"),
    ("elisa", "Elisa"), ("totem", "Vídeos"), ("mpv", "mpv"), ("strawberry", "Strawberry"),
    ("telegram", "Telegram"), ("tidal", "TIDAL"), ("deezer", "Deezer"),
)


def nombre_app(identificador):
    bajo = (identificador or "").lower()
    for clave, nombre in NOMBRES_APPS:
        if clave in bajo:
            return nombre
    nombre = identificador or "App"
    return nombre[:1].upper() + nombre[1:]


# ---------------------------------------------------------------------------
# Reproductores (MPRIS)
# ---------------------------------------------------------------------------

MPRIS = "org.mpris.MediaPlayer2"


class Reproductores:
    """Sesiones multimedia activas: título, artista, portada, progreso y controles."""

    MAX_PORTADAS = 30

    def __init__(self):
        self.ok = False
        self.error = None
        self.sesiones = []
        self.portadas = {}
        self._cerrar = False
        self.lock = threading.Lock()
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            self.ok = True
        except GLib.Error as e:
            self.error = _("Control multimedia no disponible: {error}").format(error=e.message)
            return
        try:
            self._actualizar()
        except Exception as e:  # noqa: BLE001
            self.error = _("Error leyendo reproductores: {error}").format(error=e)
        threading.Thread(target=self._hilo, daemon=True).start()

    def _llamar(self, destino, interfaz, metodo, args=None, tipo=None):
        return self.bus.call_sync(destino, "/org/mpris/MediaPlayer2", interfaz, metodo, args,
                                  GLib.VariantType(tipo) if tipo else None,
                                  Gio.DBusCallFlags.NONE, 1500, None)

    def _hilo(self):
        while not self._cerrar:
            try:
                self._actualizar()
                self.error = None
            except Exception as e:  # noqa: BLE001 - un reproductor raro no debe pararlo todo
                self.error = _("Error leyendo reproductores: {error}").format(error=e)
            time.sleep(1)

    def _actualizar(self):
        nombres = self.bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus",
                                     "org.freedesktop.DBus", "ListNames", None, None,
                                     Gio.DBusCallFlags.NONE, 1500, None).unpack()[0]
        lista = []
        for destino in sorted(n for n in nombres if n.startswith(MPRIS + ".")):
            if destino == MPRIS + ".playerctld":  # es un intermediario: repetiría otro reproductor
                continue
            try:
                props = self._llamar(destino, "org.freedesktop.DBus.Properties", "GetAll",
                                     GLib.Variant("(s)", (MPRIS + ".Player",))).unpack()[0]
                try:
                    identidad = self._llamar(destino, "org.freedesktop.DBus.Properties", "Get",
                                             GLib.Variant("(ss)", (MPRIS, "Identity"))).unpack()[0]
                except GLib.Error:
                    identidad = destino.split(".")[3]
            except GLib.Error:
                continue  # la app se ha cerrado mientras se leía
            meta = props.get("Metadata", {}) or {}
            estado = props.get("PlaybackStatus", "Stopped")
            titulo = str(meta.get("xesam:title", "") or "")
            artista = meta.get("xesam:artist", "") or ""
            if isinstance(artista, (list, tuple)):
                artista = ", ".join(str(a) for a in artista)
            if not titulo and estado not in ("Playing", "Paused"):
                continue
            dur = (meta.get("mpris:length") or 0) / 1e6
            pos = (props.get("Position") or 0) / 1e6
            pos = min(max(pos, 0), dur) if dur > 0 else 0
            portada = str(meta.get("mpris:artUrl", "") or "")
            if portada and portada not in self.portadas:
                self.portadas[portada] = self._leer_portada(portada)
                while len(self.portadas) > self.MAX_PORTADAS:
                    self.portadas.pop(next(iter(self.portadas)))
            puede = props.get("CanControl", True)
            pista = str(meta.get("mpris:trackid", "") or "")
            if not GLib.Variant.is_object_path(pista) or pista.endswith("/NoTrack"):
                pista = ""  # sin pista válida se salta con Seek (relativo) en vez de SetPosition
            lista.append({
                "id": destino, "app": nombre_app(identidad), "titulo": titulo or _("(sin título)"),
                "artista": artista, "reproduciendo": estado == "Playing",
                "pos": pos, "dur": dur, "portada": portada,
                "anterior": bool(puede and props.get("CanGoPrevious", False)),
                "siguiente": bool(puede and props.get("CanGoNext", False)),
                "play_pausa": bool(puede and (props.get("CanPlay", False) or props.get("CanPause", False))),
                "buscar": bool(puede and props.get("CanSeek", False) and dur > 0), "pista": pista,
            })
        lista.sort(key=lambda x: not x["reproduciendo"])  # lo que suena, primero
        with self.lock:
            self.sesiones = lista

    @staticmethod
    def _leer_portada(url):
        try:
            if url.startswith("file://"):
                ruta = urllib.parse.unquote(urllib.parse.urlparse(url).path)
                if os.path.getsize(ruta) > 8 * 2**20:
                    return None
                with open(ruta, "rb") as f:
                    return f.read()
            if url.startswith(("http://", "https://")):
                with urllib.request.urlopen(url, timeout=5) as r:
                    return r.read(8 * 2**20)
        except (OSError, ValueError):
            pass
        return None

    def leer(self):
        with self.lock:
            return list(self.sesiones)

    def portada(self, clave):
        return self.portadas.get(clave)

    def orden(self, ident, accion):
        """accion: "anterior", "play_pausa" o "siguiente"."""
        if not self.ok:
            return
        metodo = {"anterior": "Previous", "siguiente": "Next", "play_pausa": "PlayPause"}[accion]

        def enviar():
            try:
                self._llamar(ident, MPRIS + ".Player", metodo)
            except GLib.Error:
                pass  # la app puede haberse cerrado
        threading.Thread(target=enviar, daemon=True).start()

    def buscar(self, ident, segundos):
        """Lleva la canción o el vídeo al segundo indicado."""
        if not self.ok:
            return
        with self.lock:
            s = next((x for x in self.sesiones if x["id"] == ident), None)
        if not s or not s["buscar"]:
            return

        def enviar():
            try:
                if s["pista"]:
                    self._llamar(ident, MPRIS + ".Player", "SetPosition",
                                 GLib.Variant("(ox)", (s["pista"], int(segundos * 1e6))))
                else:
                    self._llamar(ident, MPRIS + ".Player", "Seek",
                                 GLib.Variant("(x)", (int((segundos - s["pos"]) * 1e6),)))
            except GLib.Error:
                pass
        threading.Thread(target=enviar, daemon=True).start()

    def close(self):
        self._cerrar = True


# ---------------------------------------------------------------------------
# PipeWire / PulseAudio (pactl)
# ---------------------------------------------------------------------------

ENTORNO = dict(os.environ, LANG="C.UTF-8", LC_ALL="C.UTF-8")  # salida en inglés, fácil de leer


def pactl(*args, timeout=3):
    return subprocess.run(["pactl", *args], capture_output=True, text=True, timeout=timeout,
                          env=ENTORNO).stdout


def bloques(texto):
    """Parte la salida de `pactl list ...` en diccionarios (con "Properties" anidado)."""
    out = []
    actual = None
    for linea in texto.splitlines():
        if linea and not linea[0].isspace():
            m = re.match(r"(\w[\w ]*) #(\d+)", linea)
            actual = {"_indice": m.group(2) if m else "", "Properties": {}}
            out.append(actual)
        elif actual is not None and linea.startswith("\t\t") and " = " in linea:
            k, v = linea.strip().split(" = ", 1)
            actual["Properties"][k] = v.strip('"')
        elif actual is not None and ":" in linea and linea.startswith("\t") and not linea.startswith("\t\t"):
            k, v = linea.strip().split(":", 1)
            if k != "Properties":
                actual[k] = v.strip()
    return out


def volumen_de(bloque):
    """Media de los canales en tanto por uno (100 % = 1.0)."""
    pcts = [int(x) for x in re.findall(r"(\d+)%", bloque.get("Volume", ""))]
    return (sum(pcts) / len(pcts) / 100) if pcts else 0.0


class _Pulse:
    """Un hilo lee todo el audio cada segundo; las órdenes van por una cola."""

    _instancia = None

    @classmethod
    def compartido(cls):
        if cls._instancia is None:
            cls._instancia = cls()
        return cls._instancia

    def __init__(self):
        self.ok = bool(shutil.which("pactl"))
        self.error = None if self.ok else _("Falta pactl (paquete pulseaudio-utils)")
        self.datos = None
        self.lock = threading.Lock()
        self.ordenes = queue.Queue()
        self.despertar = threading.Event()
        if self.ok:
            try:
                self._leer()  # la primera lectura, ya: el panel calcula la cuadrícula con ella
            except Exception as e:  # noqa: BLE001
                self.error = _("Error leyendo el audio: {error}").format(error=e)
            threading.Thread(target=self._hilo, daemon=True).start()
            threading.Thread(target=self._ejecutor, daemon=True).start()

    def _hilo(self):
        while True:
            try:
                self._leer()
                self.error = None
            except Exception as e:  # noqa: BLE001 - el hilo no debe morir
                self.error = _("Error leyendo el audio: {error}").format(error=e)
            self.despertar.wait(1.0)
            self.despertar.clear()

    def _leer(self):
        pred_salida = pactl("get-default-sink").strip()
        pred_entrada = pactl("get-default-source").strip()
        salidas = bloques(pactl("list", "sinks"))
        entradas = [b for b in bloques(pactl("list", "sources"))
                    if b["Properties"].get("device.class") != "monitor" and not b.get("Name", "").endswith(".monitor")]
        apps = bloques(pactl("list", "sink-inputs"))

        general = next((b for b in salidas if b.get("Name") == pred_salida), None)
        grupos = {}
        for b in apps:
            p = b["Properties"]
            nombre = p.get("application.name") or p.get("application.process.binary") or p.get("media.name") or "App"
            if p.get("media.role") == "event":  # sonidos del sistema
                continue
            grupos.setdefault(nombre_app(nombre), []).append(b)
        lista_apps = [(n, [b["_indice"] for b in bs], volumen_de(bs[0]), bs[0].get("Mute") == "yes")
                      for n, bs in sorted(grupos.items(), key=lambda x: x[0].lower())]

        def nombre(b):
            return b.get("Description") or b["Properties"].get("node.nick") or b.get("Name", _("Dispositivo"))

        datos = {
            "dispositivo": nombre(general) if general else _("Altavoces"),
            "general": (volumen_de(general), general.get("Mute") == "yes") if general else None,
            "apps": lista_apps,
            "salida": [(("sink", b.get("Name")), nombre(b), b.get("Name") == pred_salida) for b in salidas],
            "entrada": [(("source", b.get("Name")), nombre(b), b.get("Name") == pred_entrada) for b in entradas],
            "mic_silenciado": next((b.get("Mute") == "yes" for b in entradas if b.get("Name") == pred_entrada), None),
        }
        with self.lock:
            self.datos = datos

    def _ejecutor(self):
        while True:
            clave, args = self.ordenes.get()
            # Si llegan varias del mismo control (arrastrar un deslizador), solo la última.
            pendientes = {clave: args}
            try:
                while True:
                    c, a = self.ordenes.get_nowait()
                    pendientes[c] = a
            except queue.Empty:
                pass
            for lista in pendientes.values():
                for a in lista:
                    try:
                        pactl(*a)
                    except (OSError, subprocess.TimeoutExpired) as e:
                        self.error = _("No se pudo cambiar el audio: {error}").format(error=e)
            self.despertar.set()

    def orden(self, clave, *comandos):
        self.ordenes.put((clave, list(comandos)))

    def leer(self):
        with self.lock:
            return self.datos


class Mezclador:
    """Volumen general (salida predeterminada) y por app."""

    def __init__(self):
        self.p = _Pulse.compartido()
        self.ok = self.p.ok
        self._indices = {}

    @property
    def error(self):
        return self.p.error

    def leer(self):
        """{"dispositivo", "general": (vol, mute), "apps": [(nombre, vol, mute)]} o None."""
        d = self.p.leer()
        if not d or d["general"] is None:
            return None
        self._indices = {n: idx for n, idx, _, _ in d["apps"]}
        return {"dispositivo": d["dispositivo"], "general": d["general"],
                "apps": [(n, v, m) for n, _, v, m in d["apps"]]}

    def volumen(self, nombre, valor):
        pct = f"{round(valor * 100)}%"
        if nombre is None:
            self.p.orden("vol-general", ("set-sink-volume", "@DEFAULT_SINK@", pct))
        else:
            self.p.orden(f"vol-{nombre}", *(("set-sink-input-volume", i, pct) for i in self._indices.get(nombre, [])))

    def silencio(self, nombre, activo):
        v = "1" if activo else "0"
        if nombre is None:
            self.p.orden("mute-general", ("set-sink-mute", "@DEFAULT_SINK@", v))
        else:
            self.p.orden(f"mute-{nombre}", *(("set-sink-input-mute", i, v) for i in self._indices.get(nombre, [])))


class Dispositivos:
    """Salidas y entradas de audio: cuál es la predeterminada, cambiarla y silenciar el micro."""

    def __init__(self):
        self.p = _Pulse.compartido()
        self.ok = self.p.ok

    @property
    def error(self):
        return self.p.error

    def leer(self):
        """{"salida": [(id, nombre, predeterminado)], "entrada": [...], "mic_silenciado": bool o None}"""
        d = self.p.leer()
        if not d:
            return None
        return {k: d[k] for k in ("salida", "entrada", "mic_silenciado")}

    def predeterminar(self, ident):
        tipo, nombre = ident
        comando = "set-default-sink" if tipo == "sink" else "set-default-source"
        self.p.orden(f"pred-{tipo}", (comando, nombre))

    def silenciar_mic(self, activo):
        self.p.orden("mic", ("set-source-mute", "@DEFAULT_SOURCE@", "1" if activo else "0"))
        return f"micrófono predeterminado: pedido {'silencio' if activo else 'activar'}"

    def esperar(self, segundos=0.6):
        """Da tiempo a que se aplique una orden antes de volver a leer."""
        self.p.despertar.set()
