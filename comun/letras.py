"""Letras sincronizadas de lo que suena (widget Letra del pack Ocio).

Salen de LRCLIB (lrclib.net): una base de datos libre de letras con el tiempo de cada frase,
sin registro ni clave. Solo se da por buena una letra si su duración casa con la de lo que
suena (así un vídeo o un directo cualquiera no encuentra nada) y si el título y el artista son
los de la canción: la búsqueda de LRCLIB es aproximada y trae otras con nombre parecido.

Un disco entero en un solo vídeo también vale: se busca su lista de canciones (buscar_disco)
y se pone la letra de la que toca.

Los navegadores pasan el título del vídeo tal cual ("Artista - Canción (Official Video)") y
el canal como artista ("ArtistaVEVO", "Artista - Topic"): se limpian antes de buscar.
"""

import difflib
import json
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from version import REPO, VERSION

AGENTE = f"MoonDeck/{VERSION} (https://github.com/{REPO})"
API = "https://lrclib.net/api"
MARGEN = 5        # segundos de diferencia de duración que se aceptan
MAX_CACHE = 60

# Lo que sobra en los títulos de YouTube: (Official Video), [Lyrics], (Audio)...
_RUIDO = re.compile(
    r"\s*[\(\[][^\)\]]*\b(official|oficial|video|vídeo|videoclip|lyrics?|letra|audio|visuali[sz]er|"
    r"remaster(ed)?|hd|4k|mv|clip|live|en vivo|directo)\b[^\)\]]*[\)\]]", re.I)
_CANAL = re.compile(r"\s*(vevo|official|oficial|- topic|music)\s*$", re.I)
_TIEMPO = re.compile(r"\[(\d+):(\d+(?:[.:]\d+)?)\]")


def _normal(texto, artista=False):
    """Para comparar: sin tildes, mayúsculas, "(Vídeo Oficial)", "feat. ..." ni signos.
    En los artistas, además, "L4 P4nt3r4" se lee "la pantera"."""
    texto = _RUIDO.sub("", texto or "")
    texto = re.sub(r"[\(\[][^\)\]]*[\)\]]", " ", texto)  # (Remix), [Prod. ...]: sobran al comparar
    texto = re.split(r"\s+(?:ft\.?|feat\.?|featuring)\s+", texto, maxsplit=1, flags=re.I)[0]
    texto = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)).lower()
    if artista:
        texto = texto.translate(str.maketrans("4310$", "aeios"))
    return " ".join(re.sub(r"[^\w]+", " ", texto).split())


def _parecido(a, b, umbral=0.85):
    return bool(a and b) and (a == b or difflib.SequenceMatcher(None, a, b).ratio() >= umbral)


def _titulo_casa(resultado, cancion, exacto=False):
    """El título del resultado es el de la canción (también si viene como "Artista - Canción")."""
    crudo = resultado.get("trackName") or ""
    partes = [crudo] + [x for sep in (" - ", " – ", " | ") if sep in crudo for x in crudo.split(sep, 1)]
    buscada = _normal(cancion)
    return any(_normal(x) == buscada if exacto else _parecido(_normal(x), buscada) for x in partes)


def _artista_casa(resultado, artistas):
    """Alguno de los artistas posibles está entre los del resultado ("A, B & C")."""
    suyo = _normal(resultado.get("artistName"), True)
    for a in artistas:
        a = _normal(a, True)
        if a and (a in suyo or suyo in a or _parecido(a, suyo, 0.8)
                  or any(_parecido(a, x, 0.8) for x in re.split(r" (?:x|y|and|feat|ft|con) | ", suyo))):
            return True
    return False


def _artista_principal(texto):
    """El primero de "A x B", "A feat. B", "A, B", "A & B"."""
    return re.split(r"\s+(?:x|ft\.?|feat\.?|featuring|con|y|and|&)\s+|,\s*", texto, maxsplit=1, flags=re.I)[0].strip()


def candidatos(titulo, artista):
    """[(artista, canción)] para buscar, de lo más probable a lo menos. Los títulos de YouTube
    suelen ser "Artista - Canción", pero a veces van al revés ("Canción - Artistas")."""
    titulo = _RUIDO.sub("", titulo or "").strip()
    canal = _CANAL.sub("", (artista or "").strip()).strip()
    lista = []
    for sep in (" - ", " – ", " — ", " || ", " | "):
        if sep in titulo:
            izquierda, derecha = (_RUIDO.sub("", x).strip() for x in titulo.split(sep, 1))
            lista += [(_artista_principal(izquierda), derecha), (_artista_principal(derecha), izquierda),
                      (canal, derecha), (canal, izquierda)]
            break
    else:
        lista.append((canal, titulo))
    vistos, unicos = set(), []
    for a, c in lista:
        if c and (a.lower(), c.lower()) not in vistos:
            vistos.add((a.lower(), c.lower()))
            unicos.append((a, c))
    return unicos


def limpiar(titulo, artista):
    """El (artista, canción) más probable."""
    return (candidatos(titulo, artista) or [(artista, titulo)])[0]


def leer_lrc(texto):
    """[(segundos, frase)] ordenado. Las frases vacías (instrumentales) quedan como "♪"."""
    lineas = []
    for linea in (texto or "").splitlines():
        tiempos = _TIEMPO.findall(linea)
        frase = _TIEMPO.sub("", linea).strip() or "♪"
        for m, s in tiempos:
            lineas.append((int(m) * 60 + float(s.replace(":", ".")), frase))
    lineas.sort(key=lambda x: x[0])
    # Dos "♪" seguidos sobran
    return [l for i, l in enumerate(lineas) if not (l[1] == "♪" and i and lineas[i - 1][1] == "♪")]


def _pedir(ruta, **params):
    url = f"{API}/{ruta}?" + urllib.parse.urlencode(params)
    for intento in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENTE}), timeout=8) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code < 500 or intento == 2:
                raise
            time.sleep(1.5 * (intento + 1))  # el servidor da 503 a ratos


def buscar(titulo, artista, duracion):
    """La letra sincronizada [(segundos, frase)] o None si no hay ninguna que case. Si alguna
    búsqueda falló (servidor caído) y no se encontró nada, lanza el error: se reintenta luego."""
    pares = candidatos(titulo, artista)
    artistas = {a for a, _c in pares if a} | {artista or ""}

    def vale(r, cancion, margen=MARGEN):
        if not r or not r.get("syncedLyrics"):
            return False
        if duracion > 0 and abs((r.get("duration") or 0) - duracion) > margen:
            return False
        if not _titulo_casa(r, cancion):
            return False
        # El artista tiene que ser uno de los posibles; si no se puede saber (el canal no es el
        # artista), solo vale con el título idéntico y la duración casi exacta.
        return _artista_casa(r, artistas) or (_titulo_casa(r, cancion, exacto=True) and duracion > 0
                                             and abs((r.get("duration") or 0) - duracion) <= 2)

    busquedas = [({"track_name": c, "artist_name": a}, c) for a, c in pares if a]
    busquedas += [({"q": f"{a} {c}".strip()}, c) for a, c in pares if a]
    busquedas += [({"track_name": c}, c) for _a, c in pares]
    fallo = None
    hechas = set()
    for params, cancion in busquedas:
        clave = tuple(sorted((k, v.lower()) for k, v in params.items()))
        if clave in hechas:
            continue
        hechas.add(clave)
        try:
            resultados = [r for r in (_pedir("search", **params) or []) if vale(r, cancion)]
        except (urllib.error.URLError, OSError, ValueError) as e:
            fallo = e
            continue
        if resultados:
            # La de duración más parecida
            mejor = min(resultados, key=lambda r: abs((r.get("duration") or 0) - duracion))
            return leer_lrc(mejor["syncedLyrics"])
    if fallo:
        raise fallo
    return None


# ---------------------------------------------------------------------------
# Discos enteros: un vídeo largo con todo el disco ("Artista - Disco (Álbum completo)").
# Se busca la lista de canciones en orden y con su duración (Deezer, si no MusicBrainz),
# se da por buena si la duración total casa con la del vídeo y, con el segundo por el que
# va, se sabe qué canción suena y por dónde va dentro de ella.
# ---------------------------------------------------------------------------

_DISCO = re.compile(r"full\s*album|[áa]lbum\s+(completo|entero)|disco\s+(completo|entero)|"
                    r"[\(\[]\s*([áa]lbum|disco)\s*[\)\]]|album\s+stream", re.I)
MIN_DISCO = 15 * 60   # un vídeo así de largo puede ser un disco aunque el título no lo diga


def es_disco(titulo, duracion):
    return bool(_DISCO.search(titulo or "")) or duracion >= MIN_DISCO


def _pedir_url(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENTE}), timeout=10) as r:
        return json.load(r)


def _discos_deezer(artista, disco):
    """[(título, artista, [(canción, artista, segundos)])] de los discos que se parecen."""
    datos = _pedir_url("https://api.deezer.com/search/album?" + urllib.parse.urlencode({"q": f"{artista} {disco}"}))
    salida = []
    for d in (datos.get("data") or [])[:4]:
        pistas = _pedir_url(f"https://api.deezer.com/album/{d['id']}/tracks?limit=100").get("data") or []
        salida.append((d.get("title", ""), (d.get("artist") or {}).get("name", ""),
                       [(p["title"], (p.get("artist") or {}).get("name", ""), p.get("duration") or 0) for p in pistas]))
    return salida


def _discos_musicbrainz(artista, disco):
    consulta = f'release:"{disco}"' + (f' AND artist:"{artista}"' if artista else "")
    datos = _pedir_url("https://musicbrainz.org/ws/2/release/?" + urllib.parse.urlencode(
        {"query": consulta, "fmt": "json", "limit": 3}))
    salida = []
    for d in (datos.get("releases") or [])[:2]:
        time.sleep(1.1)  # MusicBrainz pide como mucho una petición por segundo
        info = _pedir_url(f"https://musicbrainz.org/ws/2/release/{d['id']}?inc=recordings+artist-credits&fmt=json")
        nombre = "".join(c.get("name", "") + c.get("joinphrase", "") for c in d.get("artist-credit", []))
        pistas = [(t.get("title", ""), nombre, (t.get("length") or 0) / 1000)
                  for m in info.get("media", []) for t in m.get("tracks", [])]
        salida.append((d.get("title", ""), nombre, pistas))
    return salida


def buscar_disco(titulo, artista, duracion):
    """Las canciones del disco que suena: [(inicio en el vídeo, duración en el vídeo, canción,
    artista, duración original)], o None si no es un disco conocido."""
    limpio = _DISCO.sub("", titulo or "")
    limpio = re.sub(r"\s*[\(\[]\s*[\)\]]", "", limpio).strip(" -|")
    pares = [(a, c) for a, c in candidatos(limpio, artista) if a] or [(artista or "", limpio)]
    artistas = {a for a, _c in pares} | {artista or ""}
    mejor = None
    fuentes = (_discos_deezer, _discos_musicbrainz) if _DISCO.search(titulo or "") else (_discos_deezer,)
    for fuente in fuentes:
        for a, nombre_disco in pares[:2]:
            try:
                discos = fuente(a, nombre_disco)
            except (urllib.error.URLError, OSError, ValueError):
                continue
            for titulo_d, artista_d, pistas in discos:
                total = sum(s for _c, _a, s in pistas)
                if not pistas or not total or not _artista_casa({"artistName": artista_d}, artistas):
                    continue
                if not _parecido(_normal(titulo_d), _normal(nombre_disco), 0.7) and \
                        _normal(nombre_disco) not in _normal(titulo_d) and _normal(titulo_d) not in _normal(nombre_disco):
                    continue
                diferencia = abs(total - duracion)
                if diferencia <= max(90, total * 0.04) and (not mejor or diferencia < mejor[0]):
                    mejor = (diferencia, total, pistas)
            if mejor:
                break
        if mejor:
            break
    if not mejor:
        return None
    _d, total, pistas = mejor
    escala = duracion / total  # pausas entre canciones o un intro: se reparten por todo el disco
    salida, inicio = [], 0.0
    for cancion, artista_p, segundos in pistas:
        salida.append((inicio, segundos * escala, cancion, artista_p, segundos))
        inicio += segundos * escala
    return salida


class Letras:
    """Busca en segundo plano y recuerda lo ya buscado (también lo que no tiene letra)."""

    def __init__(self):
        self._cache = {}       # canción -> lista de frases o None
        self._discos = {}      # vídeo -> canciones del disco (buscar_disco) o None si no es un disco
        self._en_video = {}    # (vídeo, canción n.º) -> frases con los tiempos del vídeo
        self._buscando = set()
        self._fallos = {}      # clave -> cuándo falló (sin conexión): se reintenta al rato
        self.error = None
        self.lock = threading.Lock()

    @staticmethod
    def clave(titulo, artista, duracion):
        return f"{artista}|{titulo}|{round(duracion)}"

    def pedir(self, titulo, artista, duracion, pos=0.0):
        """(estado, frases, pista). estado: "ok", "buscando" o "sin_letra"; frases con los tiempos
        de lo que suena; pista: (n.º, de cuántas, canción) si suena un disco entero, si no None.
        No bloquea."""
        if es_disco(titulo, duracion):
            video = self.clave(titulo, artista, duracion)
            with self.lock:
                hecho = video in self._discos
                pistas = self._discos.get(video)
                if not hecho:
                    self._lanzar(("disco", video), self._buscar_disco, video, titulo, artista, duracion)
            if not hecho:
                return "buscando", None, None
            if pistas:
                i = max(0, max((n for n, p in enumerate(pistas) if p[0] <= pos), default=0))
                inicio, dura, cancion, artista_p, segundos = pistas[i]
                pista = (i + 1, len(pistas), cancion)
                estado, frases = self._cancion(cancion, artista_p, segundos)
                if estado != "ok":
                    return estado, None, pista
                with self.lock:
                    if (video, i) not in self._en_video:
                        escala = dura / segundos if segundos else 1
                        self._en_video[(video, i)] = [(inicio + t * escala, f) for t, f in frases]
                    return "ok", self._en_video[(video, i)], pista
            # No es un disco conocido: como una canción suelta
        estado, frases = self._cancion(titulo, artista, duracion)
        return estado, frases, None

    def _cancion(self, titulo, artista, duracion):
        clave = self.clave(titulo, artista, duracion)
        with self.lock:
            if clave in self._cache:
                frases = self._cache[clave]
                return ("ok", frases) if frases else ("sin_letra", None)
            self._lanzar(clave, self._buscar, clave, titulo, artista, duracion)
        return "buscando", None

    def _lanzar(self, clave, funcion, *args):
        """Con el lock cogido: busca en otro hilo si no se está buscando ya ni falló hace poco."""
        if clave not in self._buscando and time.monotonic() - self._fallos.get(clave, -1e9) > 30:
            self._buscando.add(clave)
            threading.Thread(target=funcion, args=args, daemon=True).start()

    def _buscar(self, clave, titulo, artista, duracion):
        try:
            frases = buscar(titulo, artista, duracion)
            self.error = None
        except Exception as e:  # noqa: BLE001 - sin conexión: se vuelve a intentar con la siguiente canción
            frases, self.error = None, str(e)
        with self.lock:
            self._buscando.discard(clave)
            if self.error is not None:
                self._fallos[clave] = time.monotonic()
            else:
                self._cache[clave] = frases
                while len(self._cache) > MAX_CACHE:
                    self._cache.pop(next(iter(self._cache)))

    def _buscar_disco(self, video, titulo, artista, duracion):
        try:
            pistas, fallo = buscar_disco(titulo, artista, duracion), None
        except Exception as e:  # noqa: BLE001
            pistas, fallo = None, e
        with self.lock:
            self._buscando.discard(("disco", video))
            if fallo is not None:
                self._fallos[("disco", video)] = time.monotonic()
            else:
                self._discos[video] = pistas
                while len(self._discos) > 10:
                    self._discos.pop(next(iter(self._discos)))
