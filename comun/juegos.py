"""Minijuegos del widget Juegos: Buscaminas, 2048 y el dinosaurio de Chrome (los demás, en minijuegos.py).

La lógica es la de los originales, pasada a Python:
  - 2048: github.com/gabrielecirulli/2048 (licencia MIT, Copyright (c) 2014 Gabriele Cirulli).
  - Dinosaurio: el juego sin conexión de Chromium (licencia BSD, Copyright (c) 2014 The
    Chromium Authors), con sus constantes, colisiones y dibujos (dino_sprite.py).
  - Buscaminas: las reglas de siempre (primer clic seguro, abrir en cadena los huecos
    y "acorde": clic en un número con sus banderas puestas abre los vecinos).

Se dibujan con el mismo lienzo que los relojes (esferas.py), más
    sprite(sx, sy, sw, sh, dx, dy, dw, dh, tinta)   trozo de la hoja del dinosaurio
y cada versión (Linux / Windows) les pasa el ratón y el teclado:
    pulsar(x, y, boton) / soltar(x, y, boton) / mover(x, y) / tecla(nombre, pulsada)
con boton 1 (izquierdo), 2 (central) o 3 (derecho) y teclas "izquierda", "derecha",
"arriba", "abajo", "espacio" o "n". Devuelven True si el juego ha usado el evento
(si no, el clic derecho abre el menú de la tarjeta).
"""

import math
import random
import time

from esferas import con_alfa, mezcla, px_que_quepa
from idioma import _

JUEGOS = (("buscaminas", "Buscaminas"), ("2048", "2048"), ("dino", "Dinosaurio"), ("atrapa", "Atrapa la comida"),
          ("serpiente", "Serpiente"), ("pesca", "Pesca"), ("topos", "Topos"), ("masomenos", "Más o menos"),
          ("faltas", "Faltas"))

# Quien quiera premiar las partidas (la mascota: monedas) pone aquí una función(monedas).
AL_GANAR = None

_FRAME = [None]


def reloj():
    """La hora para mover las cosas: la del frame que se está dibujando si quien dibuja la sabe
    (Windows: el momento en que se verá, al refrescar la pantalla, así todo avanza a pasos iguales)
    o la de ahora. perf_counter: en Windows, time.monotonic va a saltos de ~16 ms."""
    return _FRAME[0] if _FRAME[0] is not None else time.perf_counter()


def poner_frame(t):
    """La hora del frame que se va a dibujar (None al acabar)."""
    _FRAME[0] = t


def _premiar(monedas):
    if AL_GANAR and monedas > 0:
        AL_GANAR(int(monedas))


def crear(nombre, guardado, al_guardar):
    """guardado: dict del juego en la configuración (récords y partida); al_guardar: guarda la config."""
    import minijuegos  # los otros juegos (minijuegos.py importa este módulo)
    clase = {"buscaminas": Buscaminas, "2048": Juego2048, "dino": Dino, **minijuegos.CLASES}.get(nombre, Buscaminas)
    return clase(guardado, al_guardar)


def tinta_sprite(rgba, tinta):
    """Colores de la hoja del dinosaurio para el tema: tal cual en los temas claros (tinta
    None); en los oscuros, invertidos y teñidos con el color del texto (como el modo
    oscuro de Chrome). rgba: bytes RGBA de la imagen. Devuelve bytes nuevos."""
    if tinta is None:
        return bytes(rgba)
    tr, tg, tb = (round(c * 255) for c in tinta[:3])
    salida = bytearray(rgba)
    for i in range(0, len(salida), 4):
        if salida[i + 3]:
            v = 255 - salida[i]  # la hoja es en grises: basta un canal
            salida[i], salida[i + 1], salida[i + 2] = tr * v // 255, tg * v // 255, tb * v // 255
    return bytes(salida)


def tema_oscuro(pal):
    r, g, b = pal["texto"][:3]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.5


class Juego:
    nombre = ""

    def __init__(self, guardado, al_guardar):
        self.guardado = guardado
        self.al_guardar = al_guardar

    # Cuándo hay que volver a dibujar: milisegundos o None si no hace falta.
    def siguiente_frame(self):
        return None

    def pulsar(self, x, y, boton):
        return False

    def soltar(self, x, y, boton):
        return False

    def mover(self, x, y):
        return False

    def tecla(self, nombre, pulsada):
        return False

    def nueva(self):
        pass

    def dibujar(self, l, pal, w, h):
        self.w, self.h = w, h


def _mensaje(l, pal, x, y, w, h, titulo, subtitulo=""):
    """Velo sobre el tablero con un mensaje (ganado, perdido...)."""
    l.rect(x, y, w, h, 8, con_alfa(mezcla(pal["tenue"], (0, 0, 0), 0.85), 0.72))
    px = px_que_quepa(l, titulo, w * 0.85, min(h * 0.2, 34), "negrita")
    _, th = l.medir(titulo, px, "negrita")
    chico = max(9.0, min(14.0, h * 0.08))
    if subtitulo:
        chico = px_que_quepa(l, subtitulo, w * 0.94, chico, "normal")
    _, sh = l.medir(subtitulo, chico, "normal") if subtitulo else (0, 0)
    arriba = y + (h - th - sh - 4) / 2
    l.texto(titulo, x, arriba, w, th, px, pal["texto"], "negrita")
    if subtitulo:
        l.texto(subtitulo, x, arriba + th + 4, w, sh, chico, pal["gris"], "normal")


# ---------------------------------------------------------------------------
# Buscaminas
# ---------------------------------------------------------------------------

class Buscaminas(Juego):
    nombre = "buscaminas"
    CELDA = 24          # tamaño buscado de cada casilla al empezar
    DENSIDAD = 0.16     # minas por casilla
    HUD = 26

    def __init__(self, guardado, al_guardar):
        super().__init__(guardado, al_guardar)
        self.w = self.h = 0
        self.cols = self.filas = 0
        self.estado = "nuevo"   # nuevo (aún sin minas), jugando, ganado, perdido
        self.minas = set()
        self.abiertas = set()
        self.banderas = set()
        self.explotada = None
        self.inicio = self.fin = 0.0
        self.record_nuevo = False

    def _medidas(self, w, h):
        cols = max(6, min(30, int(w // self.CELDA)))
        filas = max(5, min(16, int((h - self.HUD) // self.CELDA)))
        return cols, filas

    def nueva(self):
        self.cols, self.filas = self._medidas(self.w, self.h) if self.w else (9, 9)
        self.n_minas = max(3, round(self.cols * self.filas * self.DENSIDAD))
        self.estado = "nuevo"
        self.minas, self.abiertas, self.banderas = set(), set(), set()
        self.explotada = None
        self.record_nuevo = False

    def clave_record(self):
        return f"{self.cols}x{self.filas}"

    def record(self):
        return self.guardado.get("records", {}).get(self.clave_record())

    def siguiente_frame(self):
        return 1000 if self.estado == "jugando" else None

    # --- geometría
    def _tablero(self):
        celda = min(self.w / self.cols, (self.h - self.HUD) / self.filas)
        ancho, alto = celda * self.cols, celda * self.filas
        return (self.w - ancho) / 2, self.HUD + (self.h - self.HUD - alto) / 2, celda

    def _casilla(self, x, y):
        x0, y0, celda = self._tablero()
        c, f = int((x - x0) // celda), int((y - y0) // celda)
        if 0 <= c < self.cols and 0 <= f < self.filas and x >= x0 and y >= y0:
            return f, c
        return None

    def _vecinos(self, f, c):
        for df in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if (df or dc) and 0 <= f + df < self.filas and 0 <= c + dc < self.cols:
                    yield f + df, c + dc

    def _cuenta(self, f, c):
        return sum(v in self.minas for v in self._vecinos(f, c))

    # --- jugar
    def _poner_minas(self, segura):
        # El primer clic nunca es mina (ni sus vecinas): así siempre se abre un hueco.
        prohibidas = {segura, *self._vecinos(*segura)}
        libres = [(f, c) for f in range(self.filas) for c in range(self.cols) if (f, c) not in prohibidas]
        self.minas = set(random.sample(libres, min(self.n_minas, len(libres))))
        self.estado = "jugando"
        self.inicio = reloj()

    def _abrir(self, f, c):
        if (f, c) in self.banderas or (f, c) in self.abiertas:
            return
        if (f, c) in self.minas:
            self.estado, self.explotada, self.fin = "perdido", (f, c), reloj()
            return
        pendientes = [(f, c)]
        while pendientes:  # los huecos (0) abren a sus vecinos en cadena
            casilla = pendientes.pop()
            if casilla in self.abiertas or casilla in self.banderas:
                continue
            self.abiertas.add(casilla)
            if self._cuenta(*casilla) == 0:
                pendientes.extend(v for v in self._vecinos(*casilla) if v not in self.abiertas)
        if len(self.abiertas) == self.filas * self.cols - len(self.minas):
            self._ganar()

    def _ganar(self):
        self.estado, self.fin = "ganado", reloj()
        _premiar(3 + len(self.minas) // 10)
        self.banderas = set(self.minas)
        segundos = round(self.fin - self.inicio)
        records = self.guardado.setdefault("records", {})
        if self.clave_record() not in records or segundos < records[self.clave_record()]:
            records[self.clave_record()] = segundos
            self.record_nuevo = True
            self.al_guardar()

    def _acorde(self, f, c):
        """Clic en un número con todas sus banderas: abre el resto de vecinos."""
        vecinos = list(self._vecinos(f, c))
        if sum(v in self.banderas for v in vecinos) == self._cuenta(f, c):
            for v in vecinos:
                if self.estado == "jugando":
                    self._abrir(*v)

    def pulsar(self, x, y, boton):
        x0, _y0, _celda = self._tablero()
        # El botón de nueva partida, en el centro de la barra de arriba.
        if y < self.HUD and abs(x - self.w / 2) < 40:
            if boton == 1:
                self.nueva()
                return True
            return False
        if self.estado in ("ganado", "perdido"):
            if boton == 1:
                self.nueva()
                return True
            return False
        casilla = self._casilla(x, y)
        if casilla is None:
            return False  # fuera del tablero: el clic derecho abre el menú
        if boton == 3:
            if self.estado == "jugando" and casilla not in self.abiertas:
                self.banderas ^= {casilla}
            return True
        if boton == 1:
            if self.estado == "nuevo":
                self._poner_minas(casilla)
            if casilla in self.abiertas:
                self._acorde(*casilla)
            else:
                self._abrir(*casilla)
            return True
        if boton == 2 and casilla in self.abiertas:
            self._acorde(*casilla)
            return True
        return False

    def tecla(self, nombre, pulsada):
        if nombre == "n" and pulsada:
            self.nueva()
            return True
        return False

    # --- dibujo
    COLORES_NUM = {1: "azul", 2: "verde", 3: "rojo", 4: "morado", 5: "naranja", 6: "amarillo", 7: "texto", 8: "gris"}

    def dibujar(self, l, pal, w, h):
        cambia = (w, h) != (self.w, self.h)
        self.w, self.h = w, h
        if not self.cols or (cambia and self.estado == "nuevo" and self._medidas(w, h) != (self.cols, self.filas)):
            self.nueva()  # sin empezar, el tablero se ajusta al tamaño de la tarjeta
        x0, y0, celda = self._tablero()
        # Barra de arriba: minas que quedan, botón de nueva partida y tiempo.
        px = min(14.0, self.HUD * 0.55)
        quedan = self.n_minas - len(self.banderas)
        self._mina(l, pal, x0 + 9, self.HUD / 2, 6, pal["texto"])
        l.texto(str(quedan), x0 + 20, 0, 60, self.HUD, px, pal["texto"], "negrita", 0.0)
        cara = {"ganado": ":)", "perdido": ":(", "jugando": ":|"}.get(self.estado, ":)")
        l.rect(w / 2 - 22, 2, 44, self.HUD - 4, 6, con_alfa(pal["tenue"], 0.12))
        l.texto(cara, w / 2 - 22, 2, 44, self.HUD - 4, px, pal["texto"], "negrita")
        if self.estado == "jugando":
            segundos = int(reloj() - self.inicio)
        elif self.estado in ("ganado", "perdido"):
            segundos = int(self.fin - self.inicio)
        else:
            segundos = 0
        l.texto(f"{segundos} s", x0 + celda * self.cols - 80, 0, 80, self.HUD, px, pal["texto"], "negrita", 1.0)
        # Casillas.
        hueco = max(1.0, celda * 0.06)
        px_num = celda * 0.62
        fin = self.estado in ("ganado", "perdido")
        for f in range(self.filas):
            for c in range(self.cols):
                x, y = x0 + c * celda, y0 + f * celda
                casilla = (f, c)
                abierta = casilla in self.abiertas or (fin and casilla in self.minas)
                if abierta:
                    fondo = con_alfa(pal["rojo"], 0.55) if casilla == self.explotada else con_alfa(pal["tenue"], 0.035)
                else:
                    fondo = con_alfa(pal["tenue"], 0.14)
                l.rect(x + hueco / 2, y + hueco / 2, celda - hueco, celda - hueco, max(2.0, celda * 0.12), fondo)
                if casilla in self.banderas and not (self.estado == "perdido" and casilla in self.minas):
                    self._bandera(l, pal, x, y, celda)
                    if self.estado == "perdido" and casilla not in self.minas:  # bandera equivocada
                        l.linea(x + celda * 0.2, y + celda * 0.2, x + celda * 0.8, y + celda * 0.8, 2, pal["rojo"], True)
                elif abierta and casilla in self.minas:
                    self._mina(l, pal, x + celda / 2, y + celda / 2, celda * 0.26, pal["texto"])
                elif casilla in self.abiertas:
                    n = self._cuenta(f, c)
                    if n:
                        l.texto(str(n), x, y, celda, celda, px_num, pal.get(self.COLORES_NUM[n], pal["texto"]), "negrita")
        if fin:
            tablero = (x0, y0, celda * self.cols, celda * self.filas)
            if self.estado == "ganado":
                segundos = round(self.fin - self.inicio)
                sub = _("¡Récord nuevo!") if self.record_nuevo else _("Récord: {s} s").format(s=self.record())
                _mensaje(l, pal, *tablero, _("¡Has ganado en {s} s!").format(s=segundos), sub)
            else:
                _mensaje(l, pal, *tablero, _("¡Boom!"), _("Clic para jugar otra"))

    @staticmethod
    def _mina(l, pal, cx, cy, r, color):
        for k in range(4):
            a = k * math.pi / 4
            l.linea(cx - math.cos(a) * r * 1.35, cy - math.sin(a) * r * 1.35,
                    cx + math.cos(a) * r * 1.35, cy + math.sin(a) * r * 1.35, max(1.0, r * 0.28), color, True)
        l.circulo(cx, cy, r, color)

    @staticmethod
    def _bandera(l, pal, x, y, celda):
        mastil = x + celda * 0.38
        l.linea(mastil, y + celda * 0.2, mastil, y + celda * 0.8, max(1.0, celda * 0.07), pal["texto"], True)
        l.poligono([(mastil, y + celda * 0.2), (x + celda * 0.75, y + celda * 0.34), (mastil, y + celda * 0.5)],
                   pal["rojo"])
        l.rect(x + celda * 0.26, y + celda * 0.76, celda * 0.3, max(1.5, celda * 0.07), 1, pal["texto"])


# ---------------------------------------------------------------------------
# 2048
# ---------------------------------------------------------------------------

class Ficha:
    __slots__ = ("valor", "f", "c", "antes", "fusion", "nueva")

    def __init__(self, valor, f, c):
        self.valor, self.f, self.c = valor, f, c
        self.antes = None     # (f, c) de antes del último movimiento, para animarla
        self.fusion = None    # las dos fichas que se han juntado en esta
        self.nueva = True


# Colores del original: de 2 a 2048, y el de las mayores.
COLORES_2048 = {2: "#eee4da", 4: "#ede0c8", 8: "#f2b179", 16: "#f59563", 32: "#f67c5f", 64: "#f65e3b",
                128: "#edcf72", 256: "#edcc61", 512: "#edc850", 1024: "#edc53f", 2048: "#edc22e"}


def _hex(c):
    return tuple(int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))


class Juego2048(Juego):
    nombre = "2048"
    TAM = 4
    HUD = 28
    DESLIZAR = 0.1   # segundos de la animación de movimiento
    APARECER = 0.12

    def __init__(self, guardado, al_guardar):
        super().__init__(guardado, al_guardar)
        self.w = self.h = 0
        self.t_mov = 0.0
        self.arrastre = None
        partida = guardado.get("partida")
        if partida:  # la partida sigue donde se dejó (también tras reiniciar)
            self.puntos = partida["puntos"]
            self.ganado, self.seguir = partida["ganado"], partida["seguir"]
            self.celdas = [[Ficha(v, f, c) if v else None for c, v in enumerate(fila)]
                           for f, fila in enumerate(partida["celdas"])]
            self.terminado = not self._quedan_movimientos()
        else:
            self.nueva()

    def nueva(self):
        self.celdas = [[None] * self.TAM for _x in range(self.TAM)]
        self.puntos = 0
        self.ganado = self.seguir = self.terminado = False
        self._ficha_al_azar()
        self._ficha_al_azar()
        self.t_mov = reloj()
        self._guardar()

    def _guardar(self):
        self.guardado["partida"] = {"puntos": self.puntos, "ganado": self.ganado, "seguir": self.seguir,
                                    "celdas": [[x.valor if x else 0 for x in fila] for fila in self.celdas]}
        if self.puntos > self.guardado.get("record", 0):
            self.guardado["record"] = self.puntos
        self.al_guardar()

    def _libres(self):
        return [(f, c) for f in range(self.TAM) for c in range(self.TAM) if not self.celdas[f][c]]

    def _ficha_al_azar(self):
        libres = self._libres()
        if libres:
            f, c = random.choice(libres)
            self.celdas[f][c] = Ficha(2 if random.random() < 0.9 else 4, f, c)

    def _quedan_movimientos(self):
        if self._libres():
            return True
        for f in range(self.TAM):
            for c in range(self.TAM):
                v = self.celdas[f][c].valor
                if (c + 1 < self.TAM and self.celdas[f][c + 1].valor == v) or \
                   (f + 1 < self.TAM and self.celdas[f + 1][c].valor == v):
                    return True
        return False

    def mover(self, x, y):
        return False

    def desplazar(self, direccion):
        """direccion: "arriba", "derecha", "abajo" o "izquierda" (como move() del original)."""
        if self.terminado or (self.ganado and not self.seguir):
            return False
        df, dc = {"arriba": (-1, 0), "abajo": (1, 0), "izquierda": (0, -1), "derecha": (0, 1)}[direccion]
        filas = list(range(self.TAM))
        cols = list(range(self.TAM))
        if df == 1:
            filas.reverse()  # siempre desde la casilla más lejana en esa dirección
        if dc == 1:
            cols.reverse()
        for fila in self.celdas:
            for x in fila:
                if x:
                    x.antes, x.fusion, x.nueva = (x.f, x.c), None, False
        movido = False
        for f in filas:
            for c in cols:
                ficha = self.celdas[f][c]
                if not ficha:
                    continue
                # Lo más lejos posible hasta topar con algo.
                nf, nc = f, c
                while 0 <= nf + df < self.TAM and 0 <= nc + dc < self.TAM and not self.celdas[nf + df][nc + dc]:
                    nf, nc = nf + df, nc + dc
                sig = (nf + df, nc + dc)
                otra = (self.celdas[sig[0]][sig[1]]
                        if 0 <= sig[0] < self.TAM and 0 <= sig[1] < self.TAM else None)
                if otra and otra.valor == ficha.valor and not otra.fusion:
                    # Solo una fusión por ficha en cada movimiento.
                    junta = Ficha(ficha.valor * 2, *sig)
                    junta.nueva = False
                    junta.fusion = (ficha, otra)
                    ficha.f, ficha.c = sig
                    self.celdas[f][c] = None
                    self.celdas[sig[0]][sig[1]] = junta
                    self.puntos += junta.valor
                    if junta.valor == 2048 and not self.ganado:
                        self.ganado = True
                        _premiar(25)
                    movido = True
                elif (nf, nc) != (f, c):
                    self.celdas[f][c] = None
                    self.celdas[nf][nc] = ficha
                    ficha.f, ficha.c = nf, nc
                    movido = True
        if movido:
            self._ficha_al_azar()
            self.terminado = not self._quedan_movimientos()
            if self.terminado:
                _premiar(min(30, self.puntos // 400))
            self.t_mov = reloj()
            self._guardar()
        return movido

    def siguiente_frame(self):
        return 16 if reloj() - self.t_mov < self.DESLIZAR + self.APARECER else None

    def tecla(self, nombre, pulsada):
        if not pulsada:
            return False
        if nombre == "n":
            self.nueva()
            return True
        if nombre in ("arriba", "abajo", "izquierda", "derecha"):
            self.desplazar(nombre)
            return True
        return False

    def pulsar(self, x, y, boton):
        if boton != 1:
            return False
        if self.terminado:
            self.nueva()
            return True
        if self.ganado and not self.seguir:
            self.seguir = True  # "¡2048! Sigue jugando"
            self._guardar()
            return True
        self.arrastre = (x, y)
        return True

    def soltar(self, x, y, boton):
        if boton != 1 or not self.arrastre:
            return False
        dx, dy = x - self.arrastre[0], y - self.arrastre[1]
        self.arrastre = None
        if max(abs(dx), abs(dy)) >= 18:  # arrastrar con el ratón como en el móvil
            self.desplazar(("derecha" if dx > 0 else "izquierda") if abs(dx) > abs(dy)
                           else ("abajo" if dy > 0 else "arriba"))
        return True

    def dibujar(self, l, pal, w, h):
        self.w, self.h = w, h
        px = min(14.0, self.HUD * 0.5)
        record = max(self.guardado.get("record", 0), self.puntos)
        puntos, mejor = _("Puntos: {n}").format(n=self.puntos), _("Récord: {n}").format(n=record)
        if w >= h + 110:
            # Tarjeta ancha y baja: el marcador a la izquierda y el tablero con todo el alto.
            lado = max(40.0, h - 4)
            x0, y0 = w - lado, (h - lado) / 2
            l.texto(puntos, 0, h / 2 - self.HUD, x0 - 8, self.HUD, px, pal["texto"], "negrita", 0.0)
            l.texto(mejor, 0, h / 2, x0 - 8, self.HUD, px, pal["gris"], "normal", 0.0)
        else:
            l.texto(puntos, 0, 0, w / 2, self.HUD, px, pal["texto"], "negrita", 0.0)
            l.texto(mejor, w / 2, 0, w / 2, self.HUD, px, pal["gris"], "normal", 1.0)
            lado = max(40.0, min(w, h - self.HUD - 4))
            x0, y0 = (w - lado) / 2, self.HUD + (h - self.HUD - lado) / 2
        hueco = lado * 0.03
        celda = (lado - hueco * (self.TAM + 1)) / self.TAM
        l.rect(x0, y0, lado, lado, max(4.0, lado * 0.02), con_alfa(pal["tenue"], 0.07))

        def pos(f, c):
            return x0 + hueco + c * (celda + hueco), y0 + hueco + f * (celda + hueco)

        for f in range(self.TAM):
            for c in range(self.TAM):
                x, y = pos(f, c)
                l.rect(x, y, celda, celda, max(3.0, celda * 0.06), con_alfa(pal["tenue"], 0.07))
        t = reloj() - self.t_mov
        deslizar = min(1.0, t / self.DESLIZAR)
        aparecer = min(1.0, max(0.0, t - self.DESLIZAR) / self.APARECER)
        for fila in self.celdas:
            for ficha in fila:
                if not ficha:
                    continue
                if ficha.fusion and deslizar < 1:
                    for vieja in ficha.fusion:  # las dos que se juntan, aún de camino
                        self._ficha(l, pal, vieja, pos, celda, deslizar, 1.0)
                    continue
                escala = 1.0
                if ficha.nueva:
                    if deslizar < 1:
                        continue
                    escala = aparecer
                elif ficha.fusion:
                    escala = 1 + 0.15 * math.sin(math.pi * aparecer)  # el "pop" al juntarse
                self._ficha(l, pal, ficha, pos, celda, deslizar if not ficha.fusion else 1.0, escala)
        if self.terminado:
            _mensaje(l, pal, x0, y0, lado, lado, _("Fin de la partida"), _("Clic para jugar otra"))
        elif self.ganado and not self.seguir:
            _mensaje(l, pal, x0, y0, lado, lado, _("¡2048!"), _("Clic para seguir jugando"))

    @staticmethod
    def _ficha(l, pal, ficha, pos, celda, deslizar, escala):
        if escala <= 0:
            return
        x1, y1 = pos(ficha.f, ficha.c)
        if ficha.antes and deslizar < 1:
            x0, y0 = pos(*ficha.antes)
            x1, y1 = x0 + (x1 - x0) * deslizar, y0 + (y1 - y0) * deslizar
        lado = celda * escala
        x, y = x1 + (celda - lado) / 2, y1 + (celda - lado) / 2
        fondo = _hex(COLORES_2048.get(ficha.valor, "#3c3a32"))
        l.rect(x, y, lado, lado, max(3.0, lado * 0.06), fondo)
        color = _hex("#776e65") if ficha.valor <= 4 else _hex("#f9f6f2")
        texto = str(ficha.valor)
        px = px_que_quepa(l, texto, lado * 0.8, lado * (0.5 if len(texto) <= 2 else 0.4), "negrita")
        l.texto(texto, x, y, lado, lado, px, color, "negrita")


# ---------------------------------------------------------------------------
# Dinosaurio de Chrome
# ---------------------------------------------------------------------------

# Posiciones en la hoja de 1x (spriteDefinition.LDPI de Chromium).
SPRITE = {"CACTUS_LARGE": (332, 2), "CACTUS_SMALL": (228, 2), "CLOUD": (86, 2), "HORIZON": (2, 54),
          "PTERODACTYL": (134, 2), "RESTART": (2, 2), "TEXT_SPRITE": (655, 2), "TREX": (848, 2)}

FPS = 60
MS_POR_FRAME = 1000 / FPS
ALTO_MUNDO = 150

CONFIG = {"ACCELERATION": 0.001, "BG_CLOUD_SPEED": 0.2, "CLEAR_TIME": 3000, "CLOUD_FREQUENCY": 0.5,
          "GAMEOVER_CLEAR_TIME": 750, "GAP_COEFFICIENT": 0.6, "MAX_CLOUDS": 6, "MAX_OBSTACLE_DUPLICATION": 2,
          "MAX_SPEED": 13, "SPEED": 6}

TREX = {"DROP_VELOCITY": -5, "GRAVITY": 0.6, "HEIGHT": 47, "HEIGHT_DUCK": 25, "INITIAL_JUMP_VELOCITY": -10,
        "MAX_JUMP_HEIGHT": 30, "MIN_JUMP_HEIGHT": 30, "SPEED_DROP_COEFFICIENT": 3, "START_X_POS": 50,
        "WIDTH": 44, "WIDTH_DUCK": 59, "BOTTOM_PAD": 10}

# Cajas de colisión (x, y, ancho, alto) del original.
CAJAS_TREX = {"DUCKING": [(1, 18, 55, 25)],
              "RUNNING": [(22, 0, 17, 16), (1, 18, 30, 9), (10, 35, 14, 8), (1, 24, 29, 5), (5, 30, 21, 4),
                          (9, 34, 15, 4)]}

FRAMES_TREX = {"WAITING": ([44, 0], 1000 / 3), "RUNNING": ([88, 132], 1000 / 12), "CRASHED": ([220], 1000 / 60),
               "JUMPING": ([0], 1000 / 60), "DUCKING": ([264, 323], 1000 / 8)}

OBSTACULOS = [
    {"type": "CACTUS_SMALL", "width": 17, "height": 35, "yPos": [105], "multipleSpeed": 4, "minGap": 120,
     "minSpeed": 0, "boxes": [(0, 7, 5, 27), (4, 0, 6, 34), (10, 4, 7, 14)]},
    {"type": "CACTUS_LARGE", "width": 25, "height": 50, "yPos": [90], "multipleSpeed": 7, "minGap": 120,
     "minSpeed": 0, "boxes": [(0, 12, 7, 38), (8, 0, 7, 49), (13, 10, 10, 38)]},
    {"type": "PTERODACTYL", "width": 46, "height": 40, "yPos": [100, 75, 50], "multipleSpeed": 999,
     "minSpeed": 8.5, "minGap": 150, "boxes": [(15, 15, 16, 5), (18, 21, 24, 6), (2, 14, 4, 3), (6, 10, 4, 7),
                                               (10, 8, 6, 9)],
     "numFrames": 2, "frameRate": 1000 / 6, "speedOffset": 0.8},
]
MAX_GAP_COEFICIENTE = 1.5
MAX_LARGO_OBSTACULO = 3


def _choca(a, b):
    return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[3] + a[1] > b[1]


class Obstaculo:
    def __init__(self, tipo, ancho_mundo, velocidad):
        self.tipo = tipo
        self.tam = random.randint(1, MAX_LARGO_OBSTACULO)
        if self.tam > 1 and tipo["multipleSpeed"] > velocidad:
            self.tam = 1  # solo se agrupan cactus a partir de cierta velocidad
        self.ancho = tipo["width"] * self.tam
        self.x = ancho_mundo + tipo["width"]
        self.y = random.choice(tipo["yPos"])
        self.cajas = [list(c) for c in tipo["boxes"]]
        if self.tam > 1:  # la caja central se estira con el grupo
            self.cajas[1][2] = self.ancho - self.cajas[0][2] - self.cajas[2][2]
            self.cajas[2][0] = self.ancho - self.cajas[2][2]
        self.desfase = (tipo["speedOffset"] if random.random() > 0.5 else -tipo["speedOffset"]) \
            if tipo.get("speedOffset") else 0
        min_gap = round(self.ancho * velocidad + tipo["minGap"] * CONFIG["GAP_COEFFICIENT"])
        self.hueco = random.randint(min_gap, round(min_gap * MAX_GAP_COEFICIENTE))
        self.frame = 0
        self.timer = 0.0
        self.siguiente_creado = False

    def actualizar(self, dt, velocidad):
        self.x -= (velocidad + self.desfase) * FPS / 1000 * dt
        if self.tipo.get("numFrames"):
            self.timer += dt
            if self.timer >= self.tipo["frameRate"]:
                self.frame = (self.frame + 1) % self.tipo["numFrames"]
                self.timer = 0

    def visible(self):
        return self.x + self.ancho > 0


class Dino(Juego):
    nombre = "dino"

    def __init__(self, guardado, al_guardar):
        super().__init__(guardado, al_guardar)
        self.ancho_mundo = 600
        self.ultimo = None
        self.nueva()

    def nueva(self):
        self.estado = "esperando"   # esperando, jugando, chocado
        self.velocidad = CONFIG["SPEED"]
        self.distancia = 0.0
        self.tiempo = 0.0
        self.obstaculos = []
        self.historial = []
        self.nubes = []
        self.suelo_x = [0.0, 600.0]
        self.suelo_tipo = [0, 0]
        self.t_choque = 0.0
        suelo = ALTO_MUNDO - TREX["HEIGHT"] - TREX["BOTTOM_PAD"]
        self.rex = {"x": TREX["START_X_POS"], "y": suelo, "suelo": suelo, "vel": 0.0, "saltando": False,
                    "agachado": False, "caida": False, "altura_min": False, "estado": "WAITING",
                    "frame": 0, "timer": 0.0}
        self.ultimo = None

    def record(self):
        return self.guardado.get("record", 0)

    def puntos(self):
        return math.ceil(math.ceil(self.distancia) * 0.025)

    # --- controles
    def _saltar(self):
        r = self.rex
        if self.estado == "chocado":
            if reloj() - self.t_choque >= CONFIG["GAMEOVER_CLEAR_TIME"] / 1000:
                self.nueva()
                self._saltar()
            return
        if self.estado == "esperando":
            self.estado = "jugando"
            self.ultimo = None
        if not r["saltando"]:
            self._poner_estado("JUMPING")
            r["vel"] = TREX["INITIAL_JUMP_VELOCITY"] - self.velocidad / 10
            r["saltando"], r["altura_min"], r["caida"] = True, False, False

    def _fin_salto(self):
        r = self.rex
        if r["altura_min"] and r["vel"] < TREX["DROP_VELOCITY"]:
            r["vel"] = TREX["DROP_VELOCITY"]  # soltar pronto = salto más bajo

    def _agachar(self, si):
        r = self.rex
        if si and r["saltando"]:
            r["caida"], r["vel"] = True, 1  # abajo en el aire: cae en picado
        elif si and r["estado"] != "DUCKING" and self.estado == "jugando":
            self._poner_estado("DUCKING")
            r["agachado"] = True
        elif not si and r["estado"] == "DUCKING":
            self._poner_estado("RUNNING")
            r["agachado"] = False

    def _poner_estado(self, estado):
        self.rex["estado"], self.rex["frame"], self.rex["timer"] = estado, 0, 0.0

    def tecla(self, nombre, pulsada):
        if nombre in ("espacio", "arriba"):
            if pulsada:
                self._saltar()
            else:
                self._fin_salto()
            return True
        if nombre == "abajo":
            self._agachar(pulsada)
            return True
        return False

    def pulsar(self, x, y, boton):
        if boton != 1:
            return False
        self._saltar()
        return True

    def soltar(self, x, y, boton):
        if boton != 1:
            return False
        self._fin_salto()
        return True

    def siguiente_frame(self):
        return 16 if self.estado == "jugando" else None

    # --- simulación (Runner.update de Chromium)
    def _actualizar(self):
        ahora = reloj()
        dt = 0.0 if self.ultimo is None else (ahora - self.ultimo) * 1000
        self.ultimo = ahora
        dt = min(dt, 50.0)  # si la ventana estuvo oculta, sin teletransportes
        if self.estado != "jugando" or not dt:
            return
        r = self.rex
        if r["saltando"]:
            frames = dt / FRAMES_TREX[r["estado"]][1]
            r["y"] += r["vel"] * (TREX["SPEED_DROP_COEFFICIENT"] if r["caida"] else 1) * frames
            r["vel"] += TREX["GRAVITY"] * frames
            if r["y"] < r["suelo"] - TREX["MIN_JUMP_HEIGHT"] or r["caida"]:
                r["altura_min"] = True
            if r["y"] < TREX["MAX_JUMP_HEIGHT"] or r["caida"]:
                self._fin_salto()
            if r["y"] > r["suelo"]:
                r.update(y=r["suelo"], vel=0.0, saltando=False, caida=False)
                self._poner_estado("DUCKING" if r["agachado"] else "RUNNING")
        self.tiempo += dt
        hay_obstaculos = self.tiempo > CONFIG["CLEAR_TIME"]
        self._suelo(dt)
        self._nubes(dt)
        if hay_obstaculos:
            self._obstaculos(dt)
            if self.obstaculos and self._choque(self.obstaculos[0]):
                self.estado = "chocado"
                self._poner_estado("CRASHED")
                self.t_choque = reloj()
                _premiar(min(20, self.puntos() // 100))
                if self.puntos() > self.record():
                    self.guardado["record"] = self.puntos()
                    self.al_guardar()
                return
        self.distancia += self.velocidad * dt / MS_POR_FRAME
        if self.velocidad < CONFIG["MAX_SPEED"]:
            self.velocidad += CONFIG["ACCELERATION"] * dt / MS_POR_FRAME
        frames, ms = FRAMES_TREX[r["estado"]]
        r["timer"] += dt
        if r["timer"] >= ms:
            r["frame"] = (r["frame"] + 1) % len(frames)
            r["timer"] = 0.0

    def _suelo(self, dt):
        paso = self.velocidad * FPS / 1000 * dt
        for i in (0, 1):
            self.suelo_x[i] -= paso
        for i in (0, 1):
            if self.suelo_x[i] <= -600:
                self.suelo_x[i] += 1200
                self.suelo_tipo[i] = 600 if random.random() > 0.3 else 0  # con baches o sin

    def _nubes(self, dt):
        paso = CONFIG["BG_CLOUD_SPEED"] / 1000 * dt * self.velocidad
        for n in self.nubes:
            n["x"] -= math.ceil(paso)
        self.nubes = [n for n in self.nubes if n["x"] + 46 > 0]
        ultima = self.nubes[-1] if self.nubes else None
        if not ultima or (len(self.nubes) < CONFIG["MAX_CLOUDS"] and self.ancho_mundo - ultima["x"] > ultima["hueco"]
                          and CONFIG["CLOUD_FREQUENCY"] > random.random()):
            self.nubes.append({"x": self.ancho_mundo, "y": random.randint(30, 71), "hueco": random.randint(100, 400)})

    def _obstaculos(self, dt):
        for o in self.obstaculos:
            o.actualizar(dt, self.velocidad)
        self.obstaculos = [o for o in self.obstaculos if o.visible()]
        if self.obstaculos:
            ultimo = self.obstaculos[-1]
            if not ultimo.siguiente_creado and ultimo.x + ultimo.ancho + ultimo.hueco < self.ancho_mundo:
                self._nuevo_obstaculo()
                ultimo.siguiente_creado = True
        else:
            self._nuevo_obstaculo()

    def _nuevo_obstaculo(self):
        while True:
            tipo = random.choice(OBSTACULOS)
            repetido = len(self.historial) >= CONFIG["MAX_OBSTACLE_DUPLICATION"] and \
                all(t == tipo["type"] for t in self.historial[:CONFIG["MAX_OBSTACLE_DUPLICATION"]])
            if not repetido and self.velocidad >= tipo["minSpeed"]:
                break
        self.obstaculos.append(Obstaculo(tipo, self.ancho_mundo, self.velocidad))
        self.historial = [tipo["type"]] + self.historial[:CONFIG["MAX_OBSTACLE_DUPLICATION"] - 1]

    def _choque(self, o):
        r = self.rex
        caja_rex = (r["x"] + 1, r["y"] + 1, TREX["WIDTH"] - 2, TREX["HEIGHT"] - 2)
        caja_obs = (o.x + 1, o.y + 1, o.ancho - 2, o.tipo["height"] - 2)
        if not _choca(caja_rex, caja_obs):
            return False
        for a in CAJAS_TREX["DUCKING" if r["agachado"] else "RUNNING"]:
            for b in o.cajas:
                if _choca((a[0] + caja_rex[0], a[1] + caja_rex[1], a[2], a[3]),
                          (b[0] + caja_obs[0], b[1] + caja_obs[1], b[2], b[3])):
                    return True
        return False

    # --- dibujo
    def dibujar(self, l, pal, w, h):
        self._actualizar()
        s = h / ALTO_MUNDO   # el mundo mide 150 de alto; a lo ancho se ve lo que quepa
        self.ancho_mundo = max(200.0, w / s)
        tinta = pal["texto"] if tema_oscuro(pal) else None

        def spr(nombre, dx_hoja, sw, sh, x, y, ancho=None, alto=None):
            sx, sy = SPRITE[nombre]
            l.sprite(sx + dx_hoja, sy, sw, sh, x * s, y * s, (ancho or sw) * s, (alto or sh) * s, tinta)

        for n in self.nubes:
            spr("CLOUD", 0, 46, 14, n["x"], n["y"])
        for i in (0, 1):  # el suelo: dos tramos de 600 que se van turnando
            x = self.suelo_x[i]
            while x < self.ancho_mundo:
                spr("HORIZON", self.suelo_tipo[i], 600, 12, x, 127)
                x += 1200
        for o in self.obstaculos:
            t = o.tipo
            dx = t["width"] * o.tam * (0.5 * (o.tam - 1)) + t["width"] * o.frame
            spr(t["type"], dx, t["width"] * o.tam, t["height"], o.x, o.y)
        r = self.rex
        frames, _ms = FRAMES_TREX[r["estado"]]
        dx = frames[r["frame"] % len(frames)]
        if r["agachado"] and r["estado"] != "CRASHED":
            spr("TREX", dx, TREX["WIDTH_DUCK"], TREX["HEIGHT"], r["x"], r["y"])
        else:
            spr("TREX", dx, TREX["WIDTH"], TREX["HEIGHT"], r["x"], r["y"])
        # Marcador con las cifras de la hoja: "HI 00123  00042".
        cifras = f"{self.puntos():05d}"
        x = self.ancho_mundo - len(cifras) * 11 - 6
        for k, c in enumerate(cifras):
            spr("TEXT_SPRITE", int(c) * 10, 10, 13, x + k * 11, 5)
        if self.record():
            x_hi = x - 12 - len(cifras) * 11 - 33  # "HI 00042  00039", con un hueco entre los dos
            spr("TEXT_SPRITE", 100, 20, 13, x_hi, 5)  # "HI"
            for k, c in enumerate(f"{self.record():05d}"):
                spr("TEXT_SPRITE", int(c) * 10, 10, 13, x_hi + 33 + k * 11, 5)
        if self.estado == "chocado":
            centro = self.ancho_mundo / 2
            sx, sy = SPRITE["TEXT_SPRITE"]
            l.sprite(sx, sy + 13, 191, 11, (centro - 95.5) * s, 42 * s, 191 * s, 11 * s, tinta)  # GAME OVER
            spr("RESTART", 0, 36, 32, centro - 18, 70)
        elif self.estado == "esperando":
            chico = max(9.0, min(13.0, h * 0.09))
            l.texto(_("Espacio, ↑ o clic para saltar · ↓ para agacharse"), 0, 30 * s, w, 40 * s, chico,
                    pal["gris"], "normal")
