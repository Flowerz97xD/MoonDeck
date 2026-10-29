"""Multimedia en Windows: qué suena en cada app (con controles) y volumen por app.

- Reproductores: el control multimedia del sistema (GlobalSystemMediaTransportControls),
  el mismo que usan las teclas multimedia. Ahí se registran Spotify, Chrome, Edge,
  Firefox, el Reproductor multimedia... Va en un hilo con su propio bucle asyncio.
- Mezclador: las sesiones de audio de Windows vía pycaw (como el mezclador de volumen).
  Usa COM, así que se llama desde el hilo de la interfaz.
"""

import asyncio
import datetime
import threading
import time

from sensores import ES_WINDOWS

from idioma import _

NOMBRES_APPS = (
    ("spotify", "Spotify"), ("chrome", "Chrome"), ("msedge", "Edge"),
    ("308046b0af4a39cb", "Firefox"), ("firefox", "Firefox"), ("opera", "Opera"),
    ("brave", "Brave"), ("vivaldi", "Vivaldi"), ("zunemusic", "Reproductor multimedia"),
    ("zunevideo", "Películas y TV"), ("vlc", "VLC"), ("discord", "Discord"),
    ("applemusic", "Apple Music"), ("tidal", "TIDAL"), ("deezer", "Deezer"),
    ("steam", "Steam"), ("teams", "Teams"), ("whatsapp", "WhatsApp"),
)


def nombre_app(identificador):
    """Nombre legible a partir de un AppUserModelID o un nombre de ejecutable."""
    bajo = identificador.lower()
    for clave, nombre in NOMBRES_APPS:
        if clave in bajo:
            return nombre
    nombre = identificador.split("!")[-1].split("\\")[-1]
    if nombre.lower().endswith(".exe"):
        nombre = nombre[:-4]
    return nombre[:1].upper() + nombre[1:] if nombre else identificador


class Reproductores:
    """Sesiones multimedia activas: título, artista, portada, progreso y controles."""

    MAX_PORTADAS = 30

    def __init__(self):
        self.ok = False
        self.error = None
        self.sesiones = []     # lista de dicts para la interfaz
        self.portadas = {}     # clave de canción -> bytes de la imagen
        self._objetos = {}     # id -> objeto de sesión WinRT
        self._inicios = {}     # id -> segundos del principio de la línea de tiempo
        self._cerrar = False
        self.lock = threading.Lock()
        if not ES_WINDOWS:
            self.error = _("Solo disponible en Windows")
            return
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._hilo, daemon=True).start()

    def _hilo(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._principal())

    async def _principal(self):
        try:
            # Se importa aquí para que WinRT inicialice COM en este hilo y no en
            # el de la interfaz (que Qt ya tiene en otro modo).
            from winrt.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as Gestor,
                GlobalSystemMediaTransportControlsSessionPlaybackStatus as Estado)
            self.Estado = Estado
            self.gestor = await Gestor.request_async()
            self.ok = True
        except Exception as e:  # noqa: BLE001 - p. ej. falta el paquete winrt
            self.error = _("Control multimedia no disponible: {error}").format(error=e)
            return
        while not self._cerrar:
            try:
                await self._actualizar()
                self.error = None
            except Exception as e:  # noqa: BLE001 - una sesión rara no debe pararlo todo
                self.error = _("Error leyendo reproductores: {error}").format(error=e)
            await asyncio.sleep(1)

    async def _actualizar(self):
        lista = []
        objetos = {}
        inicios = {}
        ahora = datetime.datetime.now(datetime.timezone.utc)
        for i, s in enumerate(self.gestor.get_sessions()):
            app = s.source_app_user_model_id
            ident = f"{app}#{i}"
            objetos[ident] = s
            props = await s.try_get_media_properties_async()
            titulo = (props.title if props else "") or ""
            artista = (props.artist if props else "") or ""
            info = s.get_playback_info()
            estado = info.playback_status
            ctr = info.controls

            tl = s.get_timeline_properties()
            dur = (tl.end_time - tl.start_time).total_seconds()
            inicios[ident] = tl.start_time.total_seconds()
            pos = (tl.position - tl.start_time).total_seconds()
            reproduciendo = estado == self.Estado.PLAYING
            if reproduciendo and dur > 0:
                # La posición se informa de vez en cuando: se avanza con el reloj.
                actualizado = tl.last_updated_time
                if actualizado.tzinfo is None:
                    actualizado = actualizado.replace(tzinfo=datetime.timezone.utc)
                if actualizado.year > 1601:
                    pos += max((ahora - actualizado).total_seconds(), 0)
            pos = min(max(pos, 0), dur) if dur > 0 else 0

            portada = f"{app}|{titulo}|{artista}"
            if props and props.thumbnail and portada not in self.portadas:
                self.portadas[portada] = await self._leer_portada(props.thumbnail)
                while len(self.portadas) > self.MAX_PORTADAS:
                    self.portadas.pop(next(iter(self.portadas)))

            if not titulo and estado not in (self.Estado.PLAYING, self.Estado.PAUSED):
                continue
            lista.append({
                "id": ident, "app": nombre_app(app), "titulo": titulo or _("(sin título)"),
                "artista": artista, "reproduciendo": reproduciendo,
                "pos": pos, "dur": dur, "portada": portada,
                "anterior": ctr.is_previous_enabled, "siguiente": ctr.is_next_enabled,
                "play_pausa": ctr.is_play_pause_toggle_enabled or ctr.is_play_enabled or ctr.is_pause_enabled,
                "buscar": bool(ctr.is_playback_position_enabled and dur > 0),
            })
        # Lo que está sonando, primero.
        lista.sort(key=lambda x: not x["reproduciendo"])
        with self.lock:
            self.sesiones = lista
            self._objetos = objetos
            self._inicios = inicios

    async def _leer_portada(self, referencia):
        try:
            from winrt.windows.storage.streams import Buffer, DataReader, InputStreamOptions
            stream = await referencia.open_read_async()
            tam = stream.size
            if not tam or tam > 8 * 2**20:
                return None
            buf = Buffer(tam)
            await stream.read_async(buf, tam, InputStreamOptions.READ_AHEAD)
            datos = bytearray(buf.length)
            DataReader.from_buffer(buf).read_bytes(datos)
            return bytes(datos)
        except Exception:  # noqa: BLE001 - sin portada no pasa nada
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
        asyncio.run_coroutine_threadsafe(self._orden(ident, accion), self.loop)

    async def _orden(self, ident, accion):
        with self.lock:
            s = self._objetos.get(ident)
        if s is None:
            return
        metodo = {"anterior": s.try_skip_previous_async, "siguiente": s.try_skip_next_async,
                  "play_pausa": s.try_toggle_play_pause_async}[accion]
        try:
            await metodo()
        except Exception:  # noqa: BLE001 - la app puede haberse cerrado
            pass

    def buscar(self, ident, segundos):
        """Lleva la canción o el vídeo al segundo indicado."""
        if not self.ok:
            return
        asyncio.run_coroutine_threadsafe(self._buscar(ident, segundos), self.loop)

    async def _buscar(self, ident, segundos):
        with self.lock:
            s = self._objetos.get(ident)
            inicio = self._inicios.get(ident, 0.0)
        if s is None:
            return
        try:
            # En unidades de 100 ns, contando desde el principio de la línea de tiempo.
            await s.try_change_playback_position_async(int((inicio + segundos) * 10_000_000))
        except Exception:  # noqa: BLE001 - la app puede haberse cerrado
            pass

    def close(self):
        self._cerrar = True


class Mezclador:
    """Volumen general y por app (sesiones de audio de Windows)."""

    def __init__(self):
        self.ok = False
        self.error = None
        self._sesiones = {}   # nombre visible -> [sesiones pycaw]
        self._altavoz = None
        if not ES_WINDOWS:
            self.error = _("Solo disponible en Windows")
            return
        try:
            from pycaw.pycaw import AudioUtilities
            self.AU = AudioUtilities
            self.ok = True
        except Exception as e:  # noqa: BLE001
            self.error = _("Mezclador no disponible: {error}").format(error=e)

    def leer(self):
        """{"dispositivo", "general": (vol, mute), "apps": [(nombre, vol, mute)]} o None."""
        if not self.ok:
            return None
        try:
            altavoz = self.AU.GetSpeakers()
            ep = altavoz.EndpointVolume
            self._altavoz = ep
            general = (ep.GetMasterVolumeLevelScalar(), bool(ep.GetMute()))
            dispositivo = altavoz.FriendlyName or _("Altavoces")

            grupos = {}
            for s in self.AU.GetAllSessions():
                proc = s.Process
                if proc is None or s.State == 2:  # sin proceso (sonidos del sistema) o caducada
                    continue
                grupos.setdefault(nombre_app(proc.name()), []).append(s)
            self._sesiones = grupos
            apps = []
            for nombre in sorted(grupos, key=str.lower):
                v = grupos[nombre][0].SimpleAudioVolume
                apps.append((nombre, v.GetMasterVolume(), bool(v.GetMute())))
            self.error = None
            return {"dispositivo": dispositivo, "general": general, "apps": apps}
        except Exception as e:  # noqa: BLE001 - p. ej. se desconectan los auriculares
            self.error = _("Error del mezclador: {error}").format(error=e)
            return None

    def volumen(self, nombre, valor):
        """nombre None = volumen general. valor de 0 a 1."""
        try:
            if nombre is None:
                if self._altavoz:
                    self._altavoz.SetMasterVolumeLevelScalar(valor, None)
            else:
                for s in self._sesiones.get(nombre, []):
                    s.SimpleAudioVolume.SetMasterVolume(valor, None)
        except Exception as e:  # noqa: BLE001
            self.error = _("No se pudo cambiar el volumen: {error}").format(error=e)

    def silencio(self, nombre, activo):
        try:
            if nombre is None:
                if self._altavoz:
                    self._altavoz.SetMute(activo, None)
            else:
                for s in self._sesiones.get(nombre, []):
                    s.SimpleAudioVolume.SetMute(activo, None)
        except Exception as e:  # noqa: BLE001
            self.error = _("No se pudo silenciar: {error}").format(error=e)


class Dispositivos:
    """Dispositivos de audio de salida y de entrada: cuál es el predeterminado,
    cambiarlo con un clic y silenciar el micrófono."""

    def __init__(self):
        self.ok = False
        self.error = None
        self._mics = []   # volumen de los micrófonos predeterminados (uno por función)
        if not ES_WINDOWS:
            self.error = _("Solo disponible en Windows")
            return
        try:
            from pycaw.pycaw import DEVICE_STATE, AudioUtilities, EDataFlow, ERole
            self.AU, self.Flujo, self.Rol, self.Estado = AudioUtilities, EDataFlow, ERole, DEVICE_STATE
            self.ok = True
        except Exception as e:  # noqa: BLE001
            self.error = _("Dispositivos de audio no disponibles: {error}").format(error=e)

    def leer(self):
        """{"salida": [(id, nombre, predeterminado)], "entrada": [...], "mic_silenciado": bool o None}"""
        if not self.ok:
            return None
        try:
            enumerador = self.AU.GetDeviceEnumerator()
            datos = {"mic_silenciado": None}
            for clave, flujo in (("salida", self.Flujo.eRender), ("entrada", self.Flujo.eCapture)):
                try:
                    pred = enumerador.GetDefaultAudioEndpoint(flujo.value, self.Rol.eMultimedia.value)
                except Exception:  # noqa: BLE001 - no hay ningún dispositivo de ese tipo
                    pred = None
                id_pred = pred.GetId() if pred else None
                activos = self.AU.GetAllDevices(flujo.value, self.Estado.ACTIVE.value)
                datos[clave] = [(d.id, d.FriendlyName or _("Dispositivo"), d.id == id_pred) for d in activos]
            # Windows tiene un micrófono predeterminado por función: sistema,
            # multimedia y comunicaciones (el de Discord, Teams, juegos...). Pueden
            # ser distintos, así que se silencian todos.
            mics = {}
            for rol in (self.Rol.eConsole, self.Rol.eMultimedia, self.Rol.eCommunications):
                try:
                    d = enumerador.GetDefaultAudioEndpoint(self.Flujo.eCapture.value, rol.value)
                    mics.setdefault(d.GetId(), d)
                except Exception:  # noqa: BLE001 - sin micrófono para esa función
                    pass
            self._mics = [self._volumen(d) for d in mics.values()]
            if self._mics:
                datos["mic_silenciado"] = all(bool(m.GetMute()) for m in self._mics)
            self.error = None
            return datos
        except Exception as e:  # noqa: BLE001
            self.error = _("Error leyendo dispositivos: {error}").format(error=e)
            return None

    def _volumen(self, dispositivo):
        """El control de volumen (y silencio) de un dispositivo. Las versiones de pycaw
        cambian cómo se saca: primero la cómoda y, si no está, directamente por COM."""
        try:
            return self.AU.CreateDevice(dispositivo).EndpointVolume
        except AttributeError:
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import IAudioEndpointVolume
            return dispositivo.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None).QueryInterface(
                IAudioEndpointVolume)

    def predeterminar(self, ident):
        """Lo hace predeterminado para todo (multimedia, sistema y comunicaciones)."""
        try:
            self.AU.SetDefaultDevice(ident, roles=[self.Rol.eConsole, self.Rol.eMultimedia,
                                                   self.Rol.eCommunications])
        except Exception as e:  # noqa: BLE001
            self.error = _("No se pudo cambiar el dispositivo: {error}").format(error=e)

    def silenciar_mic(self, activo):
        """Silencia (o activa) todos los micrófonos predeterminados y lo comprueba.
        Devuelve un texto para el registro."""
        try:
            for m in self._mics:
                m.SetMute(1 if activo else 0, None)
            estados = [bool(m.GetMute()) for m in self._mics]
        except Exception as e:  # noqa: BLE001
            self.error = _("No se pudo silenciar el micrófono: {error}").format(error=e)
            return self.error
        if not self._mics:
            self.error = _("No hay ningún micrófono predeterminado")
        elif any(e != activo for e in estados):
            self.error = _("Windows no ha aplicado el silencio a algún micrófono")
        else:
            self.error = None
        return f"micrófonos: {len(self._mics)}, pedido {'silencio' if activo else 'activar'}, estado {estados}"
