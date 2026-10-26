"""Canal de voz de Discord por su RPC local (el socket discord-ipc-N del cliente).

En Linux se conecta al socket discord-ipc-N; en Windows, a la tubería con nombre.

Discord solo deja controlar la voz a aplicaciones registradas: hace falta el
Client ID y el Client Secret de una aplicación creada en discord.com/developers
(con http://localhost como Redirect). La primera vez Discord pide autorizar;
después se reutiliza el token guardado en ~/.config/MoonDeck/discord.json.

Todo va en un hilo: se conecta (y reconecta si Discord se cierra), escucha los
eventos y guarda el estado; la interfaz lo lee con `instantanea()`.
"""

import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from idioma import _

CLIENT_ID_POR_DEFECTO = "1563906637423583313"
# Secreto de la aplicación de Discord del autor (solo para sus colegas, que deben estar
# añadidos como testers de la aplicación). No está en el repositorio: construir.sh lo mete
# en los zips desde secretos/. Quien use su propia aplicación lo pone en el widget.
try:
    from secreto_discord import CLIENT_SECRET as CLIENT_SECRET_POR_DEFECTO
except ImportError:
    CLIENT_SECRET_POR_DEFECTO = ""
SCOPES = ["rpc", "rpc.voice.read", "rpc.voice.write", "identify"]
REDIRECT = "http://localhost"
API = "https://discord.com/api/v10"
AGENTE = "MoonDeck (widget de voz, 0.1)"

HANDSHAKE, FRAME, CLOSE, PING, PONG = range(5)


class TuberiaWindows:
    r"""El cliente de Discord en Windows escucha en \\.\pipe\discord-ipc-N. Se abre en modo
    "overlapped" para que leer en un hilo no bloquee las escrituras del otro (con un
    archivo normal, Windows haría esperar a cada orden hasta que llegase un mensaje)."""

    def __init__(self, ruta):
        import _winapi
        self.w = _winapi
        self.h = _winapi.CreateFile(ruta, _winapi.GENERIC_READ | _winapi.GENERIC_WRITE, 0, _winapi.NULL,
                                    _winapi.OPEN_EXISTING, _winapi.FILE_FLAG_OVERLAPPED, _winapi.NULL)

    def sendall(self, datos):
        ov, _err = self.w.WriteFile(self.h, datos, overlapped=True)
        _n, err = ov.GetOverlappedResult(True)
        if err:
            raise ConnectionError(f"error {err} escribiendo a Discord")

    def recv(self, n):
        ov, _err = self.w.ReadFile(self.h, n, overlapped=True)
        leidos, err = ov.GetOverlappedResult(True)
        if err and err != 234:  # 234 = ERROR_MORE_DATA: llegaron n bytes y hay más
            raise ConnectionError(f"error {err} leyendo de Discord")
        return bytes(ov.getbuffer()[:leidos])

    def close(self):
        if self.h:
            h, self.h = self.h, None
            self.w.CloseHandle(h)  # también despierta al hilo que está leyendo


def rutas_socket():
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    carpetas = [base, f"{base}/app/com.discordapp.Discord", f"{base}/app/dev.vencord.Vesktop",
                f"{base}/app/com.discordapp.DiscordCanary", f"{base}/snap.discord", "/tmp"]
    return [f"{c}/discord-ipc-{i}" for c in carpetas for i in range(10)]


def abrir_discord():
    """Abre Discord minimizado en la bandeja. Devuelve False si no lo encuentra instalado."""
    if sys.platform == "win32":
        base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Discord", "Update.exe")
        ordenes = [[base, "--processStart", "Discord.exe", "--process-start-args", "--start-minimized"]] \
            if os.path.exists(base) else []
    else:
        ordenes = [[p, "--start-minimized"] for p in ("discord", "Discord", "vesktop", "discord-canary")
                   if shutil.which(p)]
        for app in ("com.discordapp.Discord", "dev.vencord.Vesktop", "com.discordapp.DiscordCanary"):
            if any(os.path.isdir(os.path.join(c, "app", app)) for c in
                   ("/var/lib/flatpak", os.path.expanduser("~/.local/share/flatpak"))):
                ordenes.append(["flatpak", "run", app, "--start-minimized"])
    for orden in ordenes:
        try:
            subprocess.Popen(orden, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=sys.platform != "win32")
            return True
        except OSError:
            continue
    return False


class Discord:
    def __init__(self, carpeta):
        self.ruta_config = os.path.join(carpeta, "discord.json")
        self.cfg = self._cargar()
        self.lock = threading.Lock()
        self.estado = "sin_config" if not self.secreto() or self.cfg.get("olvidado") else "desconectado"
        self.error = None
        self.yo = None              # id de mi usuario
        self.canal = None           # {"id", "nombre", "servidor"}
        self.miembros = {}          # user_id -> dict
        self.ids = []               # ids en el orden de Discord
        self.hablando = set()
        self.ajustes = {}           # mute, deaf, entrada, salida
        self.avatares = {}          # url -> bytes
        self.canales_voz = None     # canales de voz de mis servidores elegidos (None: aún sin mirar)
        self.servidores = []        # mis servidores: [{"id", "nombre"}]
        self.version = 0            # sube con cada cambio: la interfaz solo repinta entonces
        self._servidores = {}
        self._sock = None
        self._esperando = {}        # nonce -> función con la respuesta
        self._suscrito = None
        self._despertar = threading.Event()
        self._permitido = threading.Event()  # solo se conecta con el widget a la vista
        self._vigilados = set()     # ids de los servidores cuyos canales se muestran
        self._explorar = threading.Event()
        threading.Thread(target=self._bucle, daemon=True).start()
        threading.Thread(target=self._bucle_explorar, daemon=True).start()

    def permitir(self, si):
        """Con el widget oculto no se conecta (ni pide autorizar a quien no lo usa)."""
        if si and not self._permitido.is_set():
            self._permitido.set()
        elif not si:
            self._permitido.clear()

    # --- configuración -------------------------------------------------------

    def _cargar(self):
        try:
            with open(self.ruta_config) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _guardar(self):
        try:
            fd = os.open(self.ruta_config, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # es una contraseña
            with os.fdopen(fd, "w") as f:
                json.dump(self.cfg, f, indent=1)
        except OSError:
            pass

    def client_id(self):
        return self.cfg.get("client_id") or CLIENT_ID_POR_DEFECTO

    def secreto(self):
        """El secreto propio del usuario o, con la aplicación de serie, el que trae la app."""
        if self.cfg.get("client_secret"):
            return self.cfg["client_secret"]
        return CLIENT_SECRET_POR_DEFECTO if self.client_id() == CLIENT_ID_POR_DEFECTO else ""

    def configurar(self, client_id, client_secret):
        self.cfg = {"client_id": client_id.strip(), "client_secret": client_secret.strip()}
        if self.cfg["client_id"] == CLIENT_ID_POR_DEFECTO and not self.cfg["client_secret"]:
            del self.cfg["client_secret"]  # la aplicación de serie, con su secreto
        self._guardar()
        self._cambio(estado="desconectado", error=None)
        self._cerrar_socket()
        self._despertar.set()

    def olvidar(self):
        """Borra la autorización (y el secreto propio, si se puso uno)."""
        self.cfg = {"client_id": self.client_id(), "olvidado": True}
        self._guardar()
        self._cerrar_socket()
        self._cambio(estado="sin_config", canal=None)

    def _cambio(self, **campos):
        with self.lock:
            for k, v in campos.items():
                setattr(self, k, v)
            self.version += 1

    # --- conexión -------------------------------------------------------------

    def _bucle(self):
        while True:
            self._permitido.wait()
            if self.secreto() and not self.cfg.get("olvidado"):
                try:
                    self._sesion()
                except (OSError, ConnectionError, ValueError, struct.error) as e:
                    if self.estado not in ("sin_config", "error"):
                        self._cambio(estado="desconectado", canal=None, error=None, canales_voz=None)
                    if not isinstance(e, (FileNotFoundError, ConnectionRefusedError, ConnectionError)):
                        self._cambio(error=_("Conexión con Discord perdida: {error}").format(error=e))
                finally:
                    self._cerrar_socket()
            self._despertar.wait(5)
            self._despertar.clear()

    def _conectar(self):
        if sys.platform == "win32":
            for i in range(10):
                try:
                    return TuberiaWindows(rf"\\.\pipe\discord-ipc-{i}")
                except OSError:
                    continue
            raise FileNotFoundError("Discord no está abierto")
        for ruta in rutas_socket():
            if os.path.exists(ruta):
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    s.connect(ruta)
                    return s
                except OSError:
                    s.close()
        raise FileNotFoundError("Discord no está abierto")

    def _cerrar_socket(self):
        s, self._sock = self._sock, None
        self._suscrito = None
        if s:
            try:
                s.close()
            except OSError:
                pass

    def _enviar(self, op, datos):
        s = self._sock
        if not s:
            return
        cuerpo = json.dumps(datos).encode()
        with self.lock:
            s.sendall(struct.pack("<II", op, len(cuerpo)) + cuerpo)

    def _recibir(self):
        cab = self._leer(8)
        op, largo = struct.unpack("<II", cab)
        return op, json.loads(self._leer(largo) or b"{}")

    def _leer(self, n):
        datos = b""
        while len(datos) < n:
            trozo = self._sock.recv(n - len(datos)) if self._sock else b""
            if not trozo:
                raise ConnectionError("Discord cerró la conexión")
            datos += trozo
        return datos

    def orden(self, cmd, args=None, evt=None, respuesta=None):
        """Envía un comando; `respuesta(datos, error)` se llama desde el hilo al contestar."""
        nonce = str(uuid.uuid4())
        if respuesta:
            self._esperando[nonce] = respuesta
        msg = {"cmd": cmd, "args": args or {}, "nonce": nonce}
        if evt:
            msg["evt"] = evt
        try:
            self._enviar(FRAME, msg)
        except OSError:
            self._esperando.pop(nonce, None)

    def _sesion(self):
        self._sock = self._conectar()
        self._enviar(HANDSHAKE, {"v": 1, "client_id": self.client_id()})
        self._cambio(estado="conectando", error=None)
        while True:
            op, msg = self._recibir()
            if op == PING:
                self._enviar(PONG, msg)
                continue
            if op == CLOSE:
                codigo = msg.get("code")
                texto = msg.get("message", "")
                if codigo == 4000 or "client_id" in texto.lower():
                    self._cambio(estado="error", error=_("Discord no reconoce ese Client ID."))
                raise ConnectionError(texto or "Discord cerró la conexión")
            self._mensaje(msg)

    def _mensaje(self, msg):
        cmd, evt, datos = msg.get("cmd"), msg.get("evt"), msg.get("data") or {}
        if cmd == "DISPATCH":
            if evt == "READY":
                threading.Thread(target=self._autenticar, daemon=True).start()
            else:
                self._evento(evt, datos)
            return
        f = self._esperando.pop(msg.get("nonce"), None)
        if f:
            f(None if evt == "ERROR" else datos, datos.get("message") if evt == "ERROR" else None)

    # --- autorización ----------------------------------------------------------

    def _llamar(self, cmd, args=None, timeout=60):
        """Versión que espera la respuesta (solo desde hilos que no sean el lector)."""
        hecho = threading.Event()
        caja = {}

        def respuesta(datos, error):
            caja["datos"], caja["error"] = datos, error
            hecho.set()
        self.orden(cmd, args, respuesta=respuesta)
        if not hecho.wait(timeout):
            raise TimeoutError(_("Discord no respondió a {cmd}").format(cmd=cmd))
        return caja["datos"], caja["error"]

    def _token(self, campos):
        cuerpo = urllib.parse.urlencode(dict(campos, client_id=self.client_id(),
                                             client_secret=self.secreto())).encode()
        req = urllib.request.Request(f"{API}/oauth2/token", data=cuerpo, headers={
            "Content-Type": "application/x-www-form-urlencoded", "User-Agent": AGENTE})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                t = json.load(r)
        except urllib.error.HTTPError as e:
            try:
                detalle = json.load(e).get("error_description") or e.reason
            except ValueError:
                detalle = e.reason
            raise PermissionError(detalle) from e
        self.cfg.update(access_token=t["access_token"], refresh_token=t.get("refresh_token"),
                        expira=time.time() + t.get("expires_in", 604800) - 60)
        self._guardar()

    def _autenticar(self):
        try:
            if self.cfg.get("refresh_token") and time.time() > self.cfg.get("expira", 0):
                try:
                    self._token({"grant_type": "refresh_token", "refresh_token": self.cfg["refresh_token"]})
                except PermissionError:
                    self.cfg.pop("access_token", None)
            datos = None
            if self.cfg.get("access_token"):
                datos, error = self._llamar("AUTHENTICATE", {"access_token": self.cfg["access_token"]})
            if not datos:
                # Discord muestra la ventana de "Autorizar" en su app.
                self._cambio(estado="autorizando")
                codigo, error = self._llamar("AUTHORIZE", {"client_id": self.client_id(), "scopes": SCOPES},
                                             timeout=300)
                if not codigo:
                    pista = (" " + _("¿Has aceptado la invitación de tester de esta aplicación de Discord? "
                                   "Sin eso, Discord no deja autorizarla.") if self.client_id() == CLIENT_ID_POR_DEFECTO
                             else "")
                    self._cambio(estado="error", error=_("Discord no ha autorizado: {error}.").format(error=error) + pista)
                    return
                self._token({"grant_type": "authorization_code", "code": codigo["code"], "redirect_uri": REDIRECT})
                datos, error = self._llamar("AUTHENTICATE", {"access_token": self.cfg["access_token"]})
                if not datos:
                    self._cambio(estado="error", error=_("Discord rechazó el acceso: {error}").format(error=error))
                    return
            self._cambio(estado="conectado", yo=datos.get("user", {}).get("id"), error=None, canales_voz=None)
            self._explorar.set()
            for evt in ("VOICE_CHANNEL_SELECT", "VOICE_SETTINGS_UPDATE"):
                self.orden("SUBSCRIBE", evt=evt)
            self.orden("GET_VOICE_SETTINGS", respuesta=lambda d, e: d and self._ajustes(d))
            self._leer_canal()
        except PermissionError as e:
            self._cambio(estado="error", error=_("Discord rechazó la autorización: {error}. Revisa el Client Secret y que el Redirect "
                                                 "sea http://localhost.").format(error=e))
        except (TimeoutError, OSError) as e:
            self._cambio(estado="error", error=str(e))

    # --- estado de voz -----------------------------------------------------------

    def _leer_canal(self):
        self.orden("GET_SELECTED_VOICE_CHANNEL", respuesta=lambda d, e: self._canal(d))

    def _canal(self, d):
        anterior = self._suscrito
        if anterior and (not d or d.get("id") != anterior):
            for evt in ("VOICE_STATE_CREATE", "VOICE_STATE_UPDATE", "VOICE_STATE_DELETE",
                        "SPEAKING_START", "SPEAKING_STOP"):
                self.orden("UNSUBSCRIBE", {"channel_id": anterior}, evt=evt)
            self._suscrito = None
        if not d:
            self._cambio(canal=None, miembros={}, ids=[], hablando=set())
            self._explorar.set()
            return
        miembros, ids = {}, []
        for vs in d.get("voice_states", []):
            m = self._miembro(vs)
            miembros[m["id"]] = m
            ids.append(m["id"])
        guild = d.get("guild_id")
        canal = {"id": d["id"], "nombre": d.get("name", "?"), "servidor": self._servidores.get(guild, ""),
                 "guild_id": guild}
        self._cambio(canal=canal, miembros=miembros, ids=ids, hablando=set())
        if guild and guild not in self._servidores:
            self.orden("GET_GUILD", {"guild_id": guild}, respuesta=lambda g, e: self._servidor(guild, g))
        if self._suscrito != d["id"]:
            for evt in ("VOICE_STATE_CREATE", "VOICE_STATE_UPDATE", "VOICE_STATE_DELETE",
                        "SPEAKING_START", "SPEAKING_STOP"):
                self.orden("SUBSCRIBE", {"channel_id": d["id"]}, evt=evt)
            self._suscrito = d["id"]
        for m in miembros.values():
            self._pedir_avatar(m["avatar"])

    def _servidor(self, guild, g):
        if g:
            self._servidores[guild] = g.get("name", "")
            if self.canal and self.canal.get("guild_id") == guild:
                self._cambio(canal=dict(self.canal, servidor=g.get("name", "")))

    def _miembro(self, vs):
        u = vs.get("user", {})
        estado = vs.get("voice_state", {})
        avatar = (f"https://cdn.discordapp.com/avatars/{u['id']}/{u['avatar']}.png?size=64"
                  if u.get("avatar") else None)
        return {
            "id": u.get("id"), "nombre": vs.get("nick") or u.get("global_name") or u.get("username", "?"),
            "avatar": avatar, "volumen": vs.get("volume", 100), "silenciado_local": bool(vs.get("mute")),
            "micro_off": bool(estado.get("self_mute") or estado.get("mute") or estado.get("suppress")),
            "ensordecido": bool(estado.get("self_deaf") or estado.get("deaf")), "bot": bool(u.get("bot")),
        }

    def _ajustes(self, d):
        self._cambio(ajustes={"mute": bool(d.get("mute")), "deaf": bool(d.get("deaf")),
                              "entrada": (d.get("input") or {}).get("volume"),
                              "salida": (d.get("output") or {}).get("volume")})

    def _evento(self, evt, d):
        if evt == "VOICE_CHANNEL_SELECT":
            self._leer_canal()
        elif evt == "VOICE_SETTINGS_UPDATE":
            self._ajustes(d)
        elif evt in ("VOICE_STATE_CREATE", "VOICE_STATE_UPDATE"):
            m = self._miembro(d)
            with self.lock:
                if m["id"] not in self.miembros:
                    self.ids.append(m["id"])
                self.miembros[m["id"]] = m
                self.version += 1
            self._pedir_avatar(m["avatar"])
        elif evt == "VOICE_STATE_DELETE":
            uid = d.get("user", {}).get("id")
            with self.lock:
                self.miembros.pop(uid, None)
                self.ids = [i for i in self.ids if i != uid]
                self.hablando.discard(uid)
                self.version += 1
        elif evt in ("SPEAKING_START", "SPEAKING_STOP"):
            uid = d.get("user_id")
            with self.lock:
                (self.hablando.add if evt == "SPEAKING_START" else self.hablando.discard)(uid)
                self.version += 1

    # --- canales con gente ------------------------------------------------------------

    def vigilar(self, ids):
        """Servidores cuyos canales de voz se muestran (con quién hay en cada uno)."""
        ids = set(ids)
        if ids != self._vigilados:
            self._vigilados = ids
            self._explorar.set()

    def _bucle_explorar(self):
        """Mientras no estoy en voz, mira cada 20 s quién hay en los canales de mis servidores."""
        while True:
            self._explorar.wait(20)
            self._explorar.clear()
            if self.estado != "conectado":
                continue
            try:
                datos, _error = self._llamar("GET_GUILDS", timeout=10)
                servidores = [{"id": g["id"], "nombre": g.get("name", "")} for g in (datos or {}).get("guilds", [])]
                self._servidores.update((g["id"], g["nombre"]) for g in servidores)
                canales = []
                vigilados = self._vigilados
                for g in servidores:
                    if self.canal or g["id"] not in vigilados:
                        continue
                    datos, _error = self._llamar("GET_CHANNELS", {"guild_id": g["id"]}, timeout=10)
                    for c in (datos or {}).get("channels", []):
                        if c.get("type") != 2:  # 2 = canal de voz
                            continue
                        datos, _error = self._llamar("GET_CHANNEL", {"channel_id": c["id"]}, timeout=10)
                        personas = [self._miembro(vs)["nombre"] for vs in (datos or {}).get("voice_states", [])]
                        canales.append({"id": c["id"], "nombre": c.get("name", "?"), "servidor": g["nombre"],
                                        "guild_id": g["id"], "personas": personas})
                self._cambio(servidores=servidores, canales_voz=canales)
            except (TimeoutError, OSError):
                pass

    def _pedir_avatar(self, url):
        if not url or url in self.avatares:
            return
        self.avatares[url] = None

        def bajar():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
                with urllib.request.urlopen(req, timeout=10) as r:
                    self.avatares[url] = r.read(2 * 2**20)
                self._cambio()
            except (OSError, ValueError):
                pass
        threading.Thread(target=bajar, daemon=True).start()

    def instantanea(self):
        with self.lock:
            return {
                "version": self.version, "estado": self.estado, "error": self.error, "yo": self.yo,
                "canal": dict(self.canal) if self.canal else None,
                "miembros": [dict(self.miembros[i]) for i in self.ids if i in self.miembros],
                "hablando": set(self.hablando), "ajustes": dict(self.ajustes),
                "canales_voz": None if self.canales_voz is None else [dict(c) for c in self.canales_voz],
                "servidores": list(self.servidores),
            }

    # --- acciones ------------------------------------------------------------------

    def _tras_error(self, _d, error):
        if error:
            self._cambio(error=f"Discord: {error}")

    def silenciar(self, activo):
        self.orden("SET_VOICE_SETTINGS", {"mute": activo}, respuesta=self._tras_error)

    def ensordecer(self, activo):
        self.orden("SET_VOICE_SETTINGS", {"deaf": activo}, respuesta=self._tras_error)

    def volumen_entrada(self, v):
        self.orden("SET_VOICE_SETTINGS", {"input": {"volume": v}}, respuesta=self._tras_error)

    def volumen_salida(self, v):
        self.orden("SET_VOICE_SETTINGS", {"output": {"volume": v}}, respuesta=self._tras_error)

    def volumen_usuario(self, uid, v):
        self.orden("SET_USER_VOICE_SETTINGS", {"user_id": uid, "volume": v}, respuesta=self._tras_error)
        with self.lock:
            if uid in self.miembros:
                self.miembros[uid]["volumen"] = v

    def silenciar_usuario(self, uid, activo):
        self.orden("SET_USER_VOICE_SETTINGS", {"user_id": uid, "mute": activo}, respuesta=self._tras_error)
        with self.lock:
            if uid in self.miembros:
                self.miembros[uid]["silenciado_local"] = activo
                self.version += 1

    def salir(self):
        self.orden("SELECT_VOICE_CHANNEL", {"channel_id": None}, respuesta=self._tras_error)

    def entrar(self, channel_id):
        self.orden("SELECT_VOICE_CHANNEL", {"channel_id": channel_id, "force": True}, respuesta=self._tras_error)
