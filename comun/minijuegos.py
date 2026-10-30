"""Más minijuegos del widget Juegos (además de los de juegos.py): Atrapa la comida, Serpiente,
Pesca, Topos, Más o menos y Faltas. Se dibujan con el mismo lienzo y reciben el ratón y las
teclas igual que los otros (ver juegos.py). Al terminar dan monedas (juegos.AL_GANAR), con un
tope por partida para que no sean un truco.

Todo lo que se mueve va con el tiempo real (time.perf_counter: en Windows time.monotonic
solo avanza a saltos de ~16 ms y el movimiento iba a trompicones) y se avanza al dibujar.

También están aquí los iconos de todos los juegos y las monedas que da cada uno, para el
selector de juegos.
"""

import math
import random

from esferas import con_alfa, mezcla, px_que_quepa
from idioma import _

import juegos
from juegos import Juego, _mensaje, reloj
HUD = 24
# Quien tenga una mascota pone aquí una función(l, cx, abajo, lado, expresion) que la dibuja
# centrada en cx y con los pies en `abajo` (devuelve False si no hay): en Atrapa la comida juega
# ella; si no, una cesta.
DIBUJAR_MASCOTA = None

# Las monedas que da como mucho cada juego por partida (para el selector)
MONEDAS = {"buscaminas": 12, "2048": 55, "dino": 20, "atrapa": 25, "serpiente": 25, "pesca": 25,
           "topos": 25, "masomenos": 20, "faltas": 20}


def _cabecera(l, pal, w, izquierda, derecha=""):
    px = 12.0
    l.texto(izquierda, 4, 0, w / 2, HUD, px, pal["texto"], "negrita", 0.0)
    if derecha:
        l.texto(derecha, w / 2, 0, w / 2 - 4, HUD, px, pal["gris"], "normal", 1.0)


def _record(guardado, valor):
    """Apunta el récord si lo es. Devuelve True si lo ha sido."""
    if valor > guardado.get("record", 0):
        guardado["record"] = valor
        return True
    return False


def _boton(l, pal, x, y, w, h, texto, color=None):
    l.rect(x, y, w, h, min(10.0, h / 2), color or con_alfa(pal["tenue"], 0.14))
    l.texto(texto, x, y, w, h, px_que_quepa(l, texto, w - 10, min(15.0, h * 0.5), "negrita"), pal["texto"], "negrita")


def _flotante(l, efectos, ahora, duracion=0.8):
    """Los textos que suben y se apagan (+1, ¡x2!...): (cuándo, x, y, texto, color)."""
    for cuando, x, y, texto, color in efectos:
        k = (ahora - cuando) / duracion
        l.texto(texto, x - 40, y - 18 - k * 22, 80, 20, 13, con_alfa(color, max(0.0, 1 - k)), "negrita")


def _estrella(l, cx, cy, r, color):
    puntos = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        puntos.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    l.poligono(puntos, color)


def _corazon(l, cx, cy, r, color):
    l.circulo(cx - r * 0.45, cy - r * 0.2, r * 0.52, color)
    l.circulo(cx + r * 0.45, cy - r * 0.2, r * 0.52, color)
    l.poligono([(cx - r * 0.95, cy - r * 0.05), (cx + r * 0.95, cy - r * 0.05), (cx, cy + r * 0.95)], color)


# ---------------------------------------------------------------------------
# Atrapa la comida
# ---------------------------------------------------------------------------

class Atrapa(Juego):
    """La mascota (o una cesta) atrapa la comida que cae; las piedras y las bombas quitan una
    vida. Atrapar seguido sube el combo (x2, x3, x4) y dejar caer comida lo corta. A veces caen
    premios: estrella (puntos dobles), corazón (una vida), reloj (cámara lenta) e imán (atrae la
    comida). Cada vez cae más rápido y algunas cosas bajan haciendo eses."""
    nombre = "atrapa"
    BUENAS = ("manzana", "naranja", "cereza", "galleta")
    MALAS = ("piedra", "bomba")
    PREMIOS = ("estrella", "corazon", "reloj", "iman")
    VIDAS = 3
    MAX_VIDAS = 5

    def __init__(self, guardado, al_guardar):
        super().__init__(guardado, al_guardar)
        self.w = self.h = 0
        self.estado = "esperando"
        self._preparar()

    def _preparar(self):
        self.x = self.objetivo = 0.5
        self.cosas = []          # dicts: x, y (0-1), v, tipo, onda (eses), fase
        self.puntos = 0
        self.vidas = self.VIDAS
        self.combo = 0
        self.dir = 0
        self.t = self.inicio = reloj()
        self.siguiente = 0.6
        self.efectos = []        # (cuándo, x px, y px, texto, color)
        self.poderes = {}        # nombre -> hasta cuándo
        self.temblor = 0.0

    def nueva(self):
        self.estado = "jugando"
        self._preparar()

    def multiplicador(self):
        return min(4, 1 + self.combo // 5) * (2 if self._activo("estrella") else 1)

    def _activo(self, poder):
        return self.poderes.get(poder, 0) > reloj()

    def siguiente_frame(self):
        return 16 if self.estado == "jugando" or self.efectos else None

    def pulsar(self, x, y, boton):
        if boton != 1:
            return False
        if self.estado != "jugando":
            self.nueva()
            self.mover(x, y)
        return True

    def mover(self, x, y):
        if self.estado == "jugando" and self.w:
            self.objetivo = min(0.95, max(0.05, x / self.w))
            return True
        return False

    def tecla(self, nombre, pulsada):
        if nombre in ("izquierda", "derecha"):
            self.dir = (-1 if nombre == "izquierda" else 1) if pulsada else 0
            return True
        if nombre in ("espacio", "n") and pulsada and self.estado != "jugando":
            self.nueva()
            return True
        return False

    def _soltar_cosa(self, nivel):
        r = random.random()
        if r < 0.05 and len(self.poderes) < 3:
            tipo = random.choice(self.PREMIOS)
        elif r < 0.05 + min(0.33, 0.12 + self.puntos / 250):
            tipo = random.choice(self.MALAS)
        else:
            tipo = random.choice(self.BUENAS)
        onda = random.uniform(0.05, 0.12) if random.random() < min(0.4, self.puntos / 120) else 0.0
        self.cosas.append({"x": random.uniform(0.08, 0.92), "y": -0.05, "v": random.uniform(0.2, 0.3) * nivel,
                           "tipo": tipo, "onda": onda, "fase": random.uniform(0, 6.3), "x0": None})

    def _avanzar(self):
        ahora = reloj()
        dt = max(0.0, min(0.05, ahora - self.t))  # (un frame dibujado por un clic va con la hora de ahora)
        self.t = max(self.t, ahora)
        lento = 0.45 if self._activo("reloj") else 1.0
        # La mascota va hacia el ratón con suavidad (y con las flechas, a su velocidad)
        if self.dir:
            self.objetivo = min(0.95, max(0.05, self.objetivo + self.dir * dt * 1.1))
        self.x += (self.objetivo - self.x) * min(1.0, dt * 18)
        nivel = 1 + self.puntos / 40
        self.siguiente -= dt * lento
        if self.siguiente <= 0:
            self._soltar_cosa(nivel)
            self.siguiente = max(0.25, 0.85 / nivel) * random.uniform(0.7, 1.2)
        quedan = []
        iman = self._activo("iman")
        boca_y = 1 - 0.08
        for c in self.cosas:
            c["y"] += c["v"] * dt * lento
            if c["x0"] is None:
                c["x0"] = c["x"]
            if c["onda"]:
                c["x"] = min(0.95, max(0.05, c["x0"] + math.sin(c["y"] * 9 + c["fase"]) * c["onda"]))
            if iman and c["tipo"] not in self.MALAS and c["y"] > 0.35:
                c["x0"] += (self.x - c["x0"]) * min(1.0, dt * 3)
                c["x"] = c["x0"] if not c["onda"] else c["x"]
            px, py = c["x"] * self.w, HUD + c["y"] * (self.h - HUD)
            if boca_y - 0.12 <= c["y"] <= boca_y + 0.04 and abs(c["x"] - self.x) < 0.085:
                self._comer(c, px, py, ahora)
                continue
            if c["y"] >= 1.02:
                if c["tipo"] in self.BUENAS and self.combo >= 5:
                    self.efectos.append((ahora, px, py - 10, _("¡Combo roto!"), (0.75, 0.75, 0.8)))
                if c["tipo"] in self.BUENAS:
                    self.combo = 0
                continue
            quedan.append(c)
        self.cosas = quedan
        self.efectos = [e for e in self.efectos if ahora - e[0] < 0.8]
        self.temblor = max(0.0, self.temblor - dt)
        if self.vidas <= 0:
            self.estado = "fin"
            if _record(self.guardado, self.puntos):
                self.al_guardar()
            juegos._premiar(min(MONEDAS["atrapa"], self.puntos // 6))

    def _comer(self, c, px, py, ahora):
        tipo = c["tipo"]
        if tipo in self.MALAS:
            self.vidas -= 1
            self.combo = 0
            self.temblor = 0.35 if tipo == "bomba" else 0.15
            self.efectos.append((ahora, px, py, "-1 ♥", (1.0, 0.35, 0.35)))
        elif tipo == "corazon":
            self.vidas = min(self.MAX_VIDAS, self.vidas + 1)
            self.efectos.append((ahora, px, py, "+1 ♥", (1.0, 0.45, 0.6)))
        elif tipo in self.PREMIOS:
            self.poderes[tipo] = ahora + (7 if tipo == "estrella" else 6)
            texto = {"estrella": _("¡Puntos x2!"), "reloj": _("¡Cámara lenta!"), "iman": _("¡Imán!")}[tipo]
            self.efectos.append((ahora, px, py, texto, (1.0, 0.85, 0.3)))
        else:
            self.combo += 1
            n = self.multiplicador()
            self.puntos += n
            self.efectos.append((ahora, px, py, f"+{n}", (0.35, 0.9, 0.5)))
            if self.combo % 5 == 0 and self.combo <= 15:
                self.efectos.append((ahora, px, py - 18, _("¡Combo x{n}!").format(n=1 + self.combo // 5),
                                     (1.0, 0.85, 0.3)))

    @staticmethod
    def dibujar_cosa(l, tipo, cx, cy, r, t=0.0):
        if tipo == "manzana":
            l.circulo(cx, cy, r, (0.9, 0.2, 0.25))
            l.circulo(cx - r * 0.35, cy - r * 0.35, r * 0.28, (1, 0.6, 0.6))
            l.linea(cx, cy - r, cx + r * 0.2, cy - r * 1.4, max(1.5, r * 0.2), (0.4, 0.25, 0.1))
            l.circulo(cx + r * 0.45, cy - r * 1.2, r * 0.3, (0.3, 0.7, 0.3))
        elif tipo == "naranja":
            l.circulo(cx, cy, r, (1.0, 0.6, 0.15))
            l.circulo(cx - r * 0.35, cy - r * 0.35, r * 0.25, (1, 0.85, 0.5))
            l.circulo(cx, cy - r * 0.95, r * 0.2, (0.3, 0.6, 0.25))
        elif tipo == "cereza":
            for dx in (-0.45, 0.45):
                l.circulo(cx + r * dx, cy + r * 0.2, r * 0.6, (0.75, 0.05, 0.15))
                l.linea(cx + r * dx, cy - r * 0.3, cx, cy - r * 1.2, max(1.2, r * 0.15), (0.3, 0.55, 0.2))
        elif tipo == "galleta":
            l.circulo(cx, cy, r, (0.85, 0.62, 0.35))
            for dx, dy in ((-0.3, -0.2), (0.3, 0.1), (-0.1, 0.4), (0.25, -0.4)):
                l.circulo(cx + r * dx, cy + r * dy, r * 0.14, (0.3, 0.17, 0.08))
        elif tipo == "piedra":
            l.poligono([(cx - r, cy + r * 0.6), (cx - r * 0.7, cy - r * 0.6), (cx + r * 0.2, cy - r),
                        (cx + r, cy - r * 0.2), (cx + r * 0.8, cy + r * 0.7)], (0.5, 0.5, 0.55))
            l.circulo(cx - r * 0.2, cy - r * 0.3, r * 0.2, (0.65, 0.65, 0.7))
        elif tipo == "bomba":
            l.circulo(cx, cy, r, (0.15, 0.15, 0.18))
            l.circulo(cx - r * 0.35, cy - r * 0.35, r * 0.22, (0.45, 0.45, 0.5))
            l.linea(cx + r * 0.5, cy - r * 0.7, cx + r * 0.9, cy - r * 1.3, max(1.5, r * 0.15), (0.6, 0.45, 0.3))
            chispa = 0.22 + 0.1 * math.sin(t * 25)
            l.circulo(cx + r * 0.95, cy - r * 1.35, r * chispa, (1.0, 0.75, 0.2))
        else:  # los premios, con un halo que late
            halo = 1.35 + 0.15 * math.sin(t * 6)
            l.circulo(cx, cy, r * halo, (1.0, 0.95, 0.6, 0.25))
            if tipo == "estrella":
                _estrella(l, cx, cy, r * 1.1, (1.0, 0.82, 0.2))
            elif tipo == "corazon":
                _corazon(l, cx, cy, r, (1.0, 0.35, 0.5))
            elif tipo == "reloj":
                l.poligono([(cx - r * 0.7, cy - r), (cx + r * 0.7, cy - r), (cx, cy)], (0.55, 0.8, 1.0))
                l.poligono([(cx - r * 0.7, cy + r), (cx + r * 0.7, cy + r), (cx, cy)], (0.55, 0.8, 1.0))
                l.rect(cx - r * 0.8, cy - r * 1.1, r * 1.6, r * 0.2, 1, (0.6, 0.42, 0.25))
                l.rect(cx - r * 0.8, cy + r * 0.9, r * 1.6, r * 0.2, 1, (0.6, 0.42, 0.25))
            else:  # imán
                l.arco(cx, cy, r * 0.7, math.pi, 2 * math.pi, r * 0.45, (0.9, 0.2, 0.25))
                l.rect(cx - r * 0.92, cy - r * 0.05, r * 0.45, r * 0.7, 1, (0.9, 0.2, 0.25))
                l.rect(cx + r * 0.47, cy - r * 0.05, r * 0.45, r * 0.7, 1, (0.9, 0.2, 0.25))
                l.rect(cx - r * 0.92, cy + r * 0.45, r * 0.45, r * 0.25, 0, (0.92, 0.92, 0.95))
                l.rect(cx + r * 0.47, cy + r * 0.45, r * 0.45, r * 0.25, 0, (0.92, 0.92, 0.95))

    def dibujar(self, l, pal, w, h):
        self.w, self.h = w, h
        if self.estado == "jugando":
            self._avanzar()
        ahora = reloj()
        record = max(self.guardado.get("record", 0), self.puntos)
        izquierda = _("Puntos: {n}").format(n=self.puntos) + "   " + "♥" * self.vidas
        if self.estado == "jugando" and self.multiplicador() > 1:
            izquierda += f"   x{self.multiplicador()}"
        _cabecera(l, pal, w, izquierda, _("Récord: {n}").format(n=record))
        sx = math.sin(ahora * 70) * 4 * self.temblor / 0.35 if self.temblor else 0.0
        y0, alto = HUD, h - HUD
        if self._activo("reloj"):
            l.rect(0, y0, w, alto, 8, (0.4, 0.6, 1.0, 0.08))
        l.rect(sx, y0 + alto - 4, w, 4, 2, con_alfa(pal["tenue"], 0.12))
        r = max(6.0, min(w, alto) * 0.045)
        for c in self.cosas:
            self.dibujar_cosa(l, c["tipo"], c["x"] * w + sx, y0 + c["y"] * alto, r, ahora)
        # La mascota (o la cesta), abajo
        lado = max(24.0, min(alto * 0.26, w * 0.2))
        cx, abajo = self.x * w + sx, y0 + alto - 4
        if self._activo("iman"):
            l.circulo(cx, abajo - lado * 0.5, lado * (0.75 + 0.08 * math.sin(ahora * 8)), (0.9, 0.3, 0.35, 0.12))
        comiendo = any(ahora - e[0] < 0.25 and e[3].startswith("+") for e in self.efectos)
        if not (DIBUJAR_MASCOTA and DIBUJAR_MASCOTA(l, cx, abajo, lado, "comiendo" if comiendo else "feliz")):
            l.poligono([(cx - lado / 2, abajo - lado * 0.5), (cx + lado / 2, abajo - lado * 0.5),
                        (cx + lado * 0.38, abajo), (cx - lado * 0.38, abajo)], (0.75, 0.5, 0.25))
            for i in range(3):
                l.linea(cx - lado * 0.42, abajo - lado * (0.4 - i * 0.13), cx + lado * 0.42,
                        abajo - lado * (0.4 - i * 0.13), 1.5, (0.55, 0.35, 0.15))
        # Los premios activos, con lo que les queda
        x = w - 8
        for poder, hasta in sorted(self.poderes.items()):
            queda = hasta - ahora
            if queda > 0:
                self.dibujar_cosa(l, poder, x - 9, y0 + 14, 7, ahora)
                l.arco(x - 9, y0 + 14, 11, -math.pi / 2, -math.pi / 2 + 2 * math.pi * min(1, queda / 7), 2,
                       con_alfa(pal["texto"], 0.6))
                x -= 28
        _flotante(l, self.efectos, ahora)
        if self.estado == "esperando":
            _mensaje(l, pal, 0, y0, w, alto, _("Atrapa la comida"),
                     _("Ratón o flechas · esquiva piedras y bombas"))
        elif self.estado == "fin":
            _mensaje(l, pal, 0, y0, w, alto, _("¡Se acabó!"),
                     _("{n} puntos · clic para jugar otra").format(n=self.puntos))


# ---------------------------------------------------------------------------
# Serpiente
# ---------------------------------------------------------------------------

class Serpiente(Juego):
    """Come y crece sin chocar contra las paredes, las rocas ni contra ti. Se mueve suave entre
    casillas y recuerda los giros rápidos (hasta dos). Cada 4 comidas sale una roca; a veces
    aparece una manzana dorada que vale 3 pero se va enseguida."""
    nombre = "serpiente"
    CELDA = 16

    def __init__(self, guardado, al_guardar):
        super().__init__(guardado, al_guardar)
        self.w = self.h = 0
        self.estado = "esperando"
        self.cols, self.filas = 18, 12
        self._preparar()

    def _preparar(self):
        c, f = self.cols // 2, self.filas // 2
        self.cuerpo = [(c, f), (c - 1, f), (c - 2, f)]
        self.antes = list(self.cuerpo)
        self.dir = (1, 0)
        self.giros = []
        self.rocas = set()
        self.comida = self._sitio()
        self.dorada = None       # (casilla, hasta cuándo)
        self.comidas = 0
        self.puntos = 0
        self.t = reloj()
        self.efectos = []

    def nueva(self):
        self.estado = "jugando"
        self._preparar()

    def _sitio(self, lejos_de_cabeza=0):
        cabeza = self.cuerpo[0]
        ocupado = set(self.cuerpo) | self.rocas | {getattr(self, "comida", None)}
        libres = [(c, f) for c in range(self.cols) for f in range(self.filas) if (c, f) not in ocupado
                  and abs(c - cabeza[0]) + abs(f - cabeza[1]) > lejos_de_cabeza]
        return random.choice(libres) if libres else None

    def _paso(self):
        return max(0.07, 0.15 - self.comidas * 0.003)

    def siguiente_frame(self):
        return 16 if self.estado == "jugando" else None

    def pulsar(self, x, y, boton):
        if boton == 1 and self.estado != "jugando":
            self.nueva()
            return True
        return False

    def tecla(self, nombre, pulsada):
        dirs = {"izquierda": (-1, 0), "derecha": (1, 0), "arriba": (0, -1), "abajo": (0, 1)}
        if not pulsada:
            return nombre in dirs
        if nombre in dirs:
            d = dirs[nombre]
            if self.estado != "jugando":
                self.nueva()
                if d == (-1, 0):
                    return True
            ultima = self.giros[-1] if self.giros else self.dir
            if d != ultima and (d[0] + ultima[0], d[1] + ultima[1]) != (0, 0) and len(self.giros) < 2:
                self.giros.append(d)
            return True
        if nombre in ("espacio", "n") and self.estado != "jugando":
            self.nueva()
            return True
        return False

    def _avanzar(self):
        ahora = reloj()
        if self.dorada and ahora > self.dorada[1]:
            self.dorada = None
        while ahora - self.t >= self._paso() and self.estado == "jugando":
            self.t += self._paso()
            if self.giros:
                self.dir = self.giros.pop(0)
            cabeza = (self.cuerpo[0][0] + self.dir[0], self.cuerpo[0][1] + self.dir[1])
            fuera = not (0 <= cabeza[0] < self.cols and 0 <= cabeza[1] < self.filas)
            if fuera or cabeza in self.cuerpo[:-1] or cabeza in self.rocas:
                self.estado = "fin"
                if _record(self.guardado, self.puntos):
                    self.al_guardar()
                juegos._premiar(min(MONEDAS["serpiente"], self.puntos // 2))
                return
            self.antes = list(self.cuerpo)
            self.cuerpo.insert(0, cabeza)
            if cabeza == self.comida:
                self.comidas += 1
                self.puntos += 1
                self.efectos.append((ahora, cabeza, "+1"))
                self.comida = self._sitio()
                if self.comidas % 4 == 0:
                    roca = self._sitio(lejos_de_cabeza=4)
                    if roca:
                        self.rocas.add(roca)
                if not self.dorada and random.random() < 0.3:
                    sitio = self._sitio(lejos_de_cabeza=3)
                    if sitio:
                        self.dorada = (sitio, ahora + 5)
                self.antes.append(self.antes[-1])  # crece: la cola se queda donde estaba
            elif self.dorada and cabeza == self.dorada[0]:
                self.comidas += 1
                self.puntos += 3
                self.efectos.append((ahora, cabeza, "+3"))
                self.dorada = None
                self.antes.append(self.antes[-1])
            else:
                self.cuerpo.pop()
        self.efectos = [e for e in self.efectos if ahora - e[0] < 0.8]

    def dibujar(self, l, pal, w, h):
        self.w, self.h = w, h
        if self.estado == "esperando":  # el tablero, del tamaño del widget (antes de empezar)
            cols = max(8, min(30, int(w // self.CELDA)))
            filas = max(6, min(20, int((h - HUD) // self.CELDA)))
            if (cols, filas) != (self.cols, self.filas):
                self.cols, self.filas = cols, filas
                self._preparar()
        elif self.estado == "jugando":
            self._avanzar()
        ahora = reloj()
        record = max(self.guardado.get("record", 0), self.puntos)
        _cabecera(l, pal, w, _("Puntos: {n}").format(n=self.puntos), _("Récord: {n}").format(n=record))
        celda = min(w / self.cols, (h - HUD) / self.filas)
        x0, y0 = (w - celda * self.cols) / 2, HUD + (h - HUD - celda * self.filas) / 2
        l.rect(x0, y0, celda * self.cols, celda * self.filas, 6, con_alfa(pal["tenue"], 0.06))
        for c, f in self.rocas:
            Atrapa.dibujar_cosa(l, "piedra", x0 + (c + 0.5) * celda, y0 + (f + 0.5) * celda, celda * 0.42)
        if self.comida:
            Atrapa.dibujar_cosa(l, "manzana", x0 + (self.comida[0] + 0.5) * celda,
                                y0 + (self.comida[1] + 0.55) * celda, celda * 0.36)
        if self.dorada:
            (c, f), hasta = self.dorada
            if hasta - ahora > 1.5 or int(ahora * 8) % 2:  # parpadea cuando se va a ir
                l.circulo(x0 + (c + 0.5) * celda, y0 + (f + 0.55) * celda, celda * 0.42, (1.0, 0.9, 0.4, 0.3))
                l.circulo(x0 + (c + 0.5) * celda, y0 + (f + 0.55) * celda, celda * 0.34, (1.0, 0.78, 0.15))
                l.circulo(x0 + (c + 0.38) * celda, y0 + (f + 0.42) * celda, celda * 0.1, (1, 1, 0.85))
        # El cuerpo, entre la casilla de antes y la de ahora (así se mueve suave)
        k = min(1.0, (ahora - self.t) / self._paso()) if self.estado == "jugando" else 1.0
        n = len(self.cuerpo)
        verde, oscuro = (0.35, 0.8, 0.4), (0.2, 0.6, 0.3)
        puntos = []
        for i in range(n):
            a = self.antes[i] if i < len(self.antes) else self.cuerpo[i]
            b = self.cuerpo[i]
            puntos.append((a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k))
        for i in range(n - 1, -1, -1):
            px, py = puntos[i]
            t_color = 1 - i / max(1, n - 1)
            tam = celda * (0.92 if i == 0 else 0.84 - 0.2 * (i / max(1, n - 1)))
            l.rect(x0 + (px + 0.5) * celda - tam / 2, y0 + (py + 0.5) * celda - tam / 2, tam, tam, tam * 0.4,
                   mezcla(oscuro, verde, t_color))
            if i + 1 < n:  # el hueco entre dos trozos, relleno
                qx, qy = puntos[i + 1]
                mx, my = (px + qx) / 2, (py + qy) / 2
                l.rect(x0 + (mx + 0.5) * celda - tam / 2, y0 + (my + 0.5) * celda - tam / 2, tam, tam, tam * 0.4,
                       mezcla(oscuro, verde, t_color))
        cx, cy = puntos[0]
        for lado in (-1, 1):  # los ojos, mirando hacia donde va
            ox = 0.5 + self.dir[0] * 0.2 + (self.dir[1] * 0.22 * lado)
            oy = 0.5 + self.dir[1] * 0.2 + (self.dir[0] * 0.22 * lado)
            l.circulo(x0 + (cx + ox) * celda, y0 + (cy + oy) * celda, celda * 0.13, (1, 1, 1))
            l.circulo(x0 + (cx + ox + self.dir[0] * 0.04) * celda, y0 + (cy + oy + self.dir[1] * 0.04) * celda,
                      celda * 0.07, (0.05, 0.05, 0.05))
        _flotante(l, [(t, x0 + (c + 0.5) * celda, y0 + f * celda, texto, (1.0, 0.85, 0.3))
                      for t, (c, f), texto in self.efectos], ahora)
        if self.estado == "esperando":
            _mensaje(l, pal, x0, y0, celda * self.cols, celda * self.filas, _("Serpiente"),
                     _("Flechas para empezar"))
        elif self.estado == "fin":
            _mensaje(l, pal, x0, y0, celda * self.cols, celda * self.filas, _("¡Choque!"),
                     _("{n} puntos · flechas o clic para jugar otra").format(n=self.puntos))


# ---------------------------------------------------------------------------
# Pesca
# ---------------------------------------------------------------------------

class Pesca(Juego):
    """Mantén pulsado para cargar el lanzamiento y suelta: cuanto más lejos, peces mejores (y
    más espera). El corcho da toquecitos de mentira; cuando se hunde de verdad y sale «¡!»,
    pulsa. Luego la lucha: mantén pulsado para recoger sin que la tensión pase de la zona verde
    (el sedal se rompe) ni baje del todo (el pez se escapa). Los peces buenos tiran más fuerte.
    6 lanzamientos por partida."""
    nombre = "pesca"
    LANZAMIENTOS = 6
    # nombre, puntos, fuerza, distancia de la lucha, ventana para picar (s), color, largo
    PECES = (("Bota vieja", 0, 0.2, 0.5, 1.0, (0.45, 0.35, 0.25), 0.8),
             ("Sardina", 1, 0.35, 0.7, 0.9, (0.65, 0.75, 0.85), 0.8),
             ("Pez payaso", 3, 0.55, 1.0, 0.7, (1.0, 0.55, 0.15), 1.0),
             ("Pez globo", 5, 0.75, 1.2, 0.55, (0.95, 0.85, 0.35), 1.1),
             ("Pez dorado", 8, 1.0, 1.5, 0.45, (1.0, 0.8, 0.2), 1.3))
    ZONA = (0.35, 0.8)   # tensión buena

    def __init__(self, guardado, al_guardar):
        super().__init__(guardado, al_guardar)
        self.w = self.h = 0
        self.nueva()
        self.estado = "esperando"

    def nueva(self):
        self.estado = "listo"     # listo, cargando, esperando_pez, pica, lucha, resultado, fin
        self.puntos = 0
        self.quedan = self.LANZAMIENTOS
        self.t = reloj()
        self.pez = None
        self.resultado = ""
        self.pescado = False
        self.pulsado = False
        self.lejos = 0.5
        self.picotazos = []

    def siguiente_frame(self):
        if self.estado in ("esperando", "fin"):
            return None
        return 33 if self.estado == "listo" else 16  # (listo: solo las olas)

    # La entrada: pulsar y soltar (ratón o espacio)
    def _apretar(self):
        ahora = reloj()
        self.pulsado = True
        if self.estado in ("esperando", "fin"):
            self.nueva()
            self.pulsado = False
        elif self.estado == "listo":
            self.estado, self.t = "cargando", ahora
        elif self.estado == "esperando_pez":
            self._fin_lanzamiento(_("¡Demasiado pronto! Se ha asustado."), 0)
        elif self.estado == "pica":
            self.estado, self.t = "lucha", ahora
            self.tension, self.distancia, self.flojo = 0.5, 1.0, 0.0
            self.tiron, self.siguiente_tiron = 0.0, ahora + random.uniform(0.6, 1.4)
            self.pez_x = 0.62
        elif self.estado == "resultado":
            self.estado = "listo" if self.quedan else "fin"
            self.pulsado = False
        return True

    def _soltar(self):
        self.pulsado = False
        if self.estado == "cargando":
            self.lejos = self._carga()
            self.estado, self.t = "esperando_pez", reloj()
            self.espera = random.uniform(1.5, 3.0) + self.lejos * 2.0
            # Más lejos, más probable un pez bueno
            pesos = [max(0.02, p) for p in (0.18 - self.lejos * 0.1, 0.5 - self.lejos * 0.3, 0.22 + self.lejos * 0.05,
                                            0.08 + self.lejos * 0.17, 0.02 + self.lejos * 0.1)]
            self.pez = random.choices(self.PECES, weights=pesos)[0]
            self.picotazos = sorted(random.uniform(0.5, self.espera - 0.4) for _i in range(random.randint(0, 3)))
        return True

    def _carga(self):
        return abs(math.sin((reloj() - self.t) * 1.6))

    def pulsar(self, x, y, boton):
        return boton == 1 and self._apretar()

    def soltar(self, x, y, boton):
        return boton == 1 and self._soltar()

    def tecla(self, nombre, pulsada):
        if nombre == "espacio":
            return self._apretar() if pulsada else self._soltar()
        return False

    def _fin_lanzamiento(self, texto, puntos, pescado=False):
        self.puntos += puntos
        self.quedan -= 1
        self.resultado, self.estado, self.t = texto, "resultado", reloj()
        self.pescado = pescado
        if not self.quedan:
            if _record(self.guardado, self.puntos):
                self.al_guardar()
            juegos._premiar(min(MONEDAS["pesca"], self.puntos // 2))

    def _avanzar(self):
        ahora = reloj()
        if self.estado == "esperando_pez" and ahora - self.t > self.espera:
            self.estado, self.t = "pica", ahora
        elif self.estado == "pica" and ahora - self.t > self.pez[4]:
            self._fin_lanzamiento(_("Se ha escapado…"), 0)
        elif self.estado == "lucha":
            self._luchar(ahora)
        elif self.estado == "resultado" and ahora - self.t > 2.2:
            self.estado = "listo" if self.quedan else "fin"

    def _luchar(self, ahora):
        dt = max(0.0, min(0.05, ahora - getattr(self, "_t_lucha", ahora)))
        self._t_lucha = max(ahora, getattr(self, "_t_lucha", ahora))
        nombre, puntos, fuerza, distancia, _v, _c, _l = self.pez
        if ahora >= self.siguiente_tiron:  # el pez da un tirón
            self.tiron = 0.35 + fuerza * 0.55
            self.siguiente_tiron = ahora + random.uniform(0.7, 1.6) / (0.6 + fuerza * 0.6)
        self.tiron = max(0.0, self.tiron - dt * 1.4)
        if self.pulsado:
            self.tension += dt * (0.55 + fuerza * 0.2)
            if self.ZONA[0] <= self.tension <= self.ZONA[1]:
                self.distancia -= dt * 0.32 / distancia
        else:
            self.tension -= dt * 0.65
        self.tension += self.tiron * dt * 1.6
        self.tension = max(0.0, self.tension)
        self.pez_x = 0.62 + math.sin(ahora * (1.5 + fuerza * 2)) * 0.12 * (0.5 + fuerza)
        self.flojo = self.flojo + dt if self.tension < 0.1 else 0.0
        if self.tension > 1.0:
            self._fin_lanzamiento(_("¡Se ha roto el sedal!"), 0)
        elif self.flojo > 1.2:
            self._fin_lanzamiento(_("Se ha escapado…"), 0)
        elif self.distancia <= 0:
            if puntos:
                kilos = round(random.uniform(0.6, 1.4) * (0.3 + puntos * 0.4), 1)
                texto = _("¡{pez}! {kg} kg · +{n}").format(pez=_(nombre), kg=kilos, n=puntos)
            else:
                texto = _("¡{pez}! Vaya…").format(pez=_(nombre))
            self._fin_lanzamiento(texto, puntos, pescado=True)

    @staticmethod
    def dibujar_pez(l, cx, cy, largo, color, bota=False):
        if bota:
            l.rect(cx - largo * 0.15, cy - largo * 0.45, largo * 0.32, largo * 0.6, 2, color)
            l.rect(cx - largo * 0.15, cy + largo * 0.05, largo * 0.6, largo * 0.25, largo * 0.1, color)
            l.rect(cx - largo * 0.15, cy + largo * 0.25, largo * 0.62, largo * 0.06, 1, (0.2, 0.15, 0.1))
            return
        l.rect(cx - largo / 2, cy - largo * 0.28, largo, largo * 0.56, largo * 0.28, color)
        l.poligono([(cx - largo * 0.42, cy), (cx - largo * 0.75, cy - largo * 0.3), (cx - largo * 0.75, cy + largo * 0.3)],
                   mezcla(color, (0, 0, 0), 0.2))
        l.circulo(cx + largo * 0.28, cy - largo * 0.06, largo * 0.08, (1, 1, 1))
        l.circulo(cx + largo * 0.3, cy - largo * 0.06, largo * 0.04, (0.05, 0.05, 0.1))

    def dibujar(self, l, pal, w, h):
        self.w, self.h = w, h
        self._avanzar()
        t = reloj()
        record = max(self.guardado.get("record", 0), self.puntos)
        _cabecera(l, pal, w, _("Puntos: {n}").format(n=self.puntos) + "   " +
                  _("Cañas: {n}").format(n=self.quedan), _("Récord: {n}").format(n=record))
        y0, alto = HUD, h - HUD
        agua = y0 + alto * 0.32
        fondo_agua = y0 + alto
        l.rect(0, y0, w, agua - y0, 6, (0.55, 0.78, 0.98))
        for i in range(5):
            l.rect(0, agua + (fondo_agua - agua) * i / 5, w, (fondo_agua - agua) / 5 + 1, 0,
                   mezcla((0.2, 0.55, 0.85), (0.05, 0.22, 0.45), i / 4))
        for i in range(int(w / 30) + 1):  # olitas
            l.linea(i * 30 + math.sin(t + i) * 4, agua + 2, i * 30 + 12 + math.sin(t + i) * 4, agua + 2, 2, (1, 1, 1, 0.5))
        for i in range(3):  # peces nadando abajo
            fx = (t * (25 + i * 12) + i * w * 0.4) % (w + 80) - 40
            self.dibujar_pez(l, fx, agua + (fondo_agua - agua) * (0.45 + 0.17 * i), 22, (0.75, 0.85, 0.95, 0.35))
        # El muelle y la caña (se dobla con la tensión)
        muelle = w * 0.16
        l.rect(0, agua - 10, muelle, 10, 0, (0.55, 0.38, 0.22))
        l.rect(muelle * 0.7, agua, 6, alto * 0.3, 0, (0.45, 0.3, 0.18))
        curva = getattr(self, "tension", 0) * 14 if self.estado == "lucha" else 0
        punta = (muelle * 0.9 + curva * 0.4, agua - alto * 0.22 + curva)
        l.linea(muelle * 0.4, agua - 10, punta[0], punta[1], 3, (0.4, 0.28, 0.15))
        corcho_x = muelle + (w * 0.9 - muelle) * (0.25 + self.lejos * 0.75)
        if self.estado == "cargando":  # dónde caerá
            carga = self._carga()
            destino = muelle + (w * 0.9 - muelle) * (0.25 + carga * 0.75)
            l.circulo(destino, agua + 3, 6, (1, 1, 1, 0.35))
            bw = w * 0.5
            bx = (w - bw) / 2
            l.rect(bx, fondo_agua - 22, bw, 10, 5, (0, 0, 0, 0.35))
            l.rect(bx + 2, fondo_agua - 20, (bw - 4) * carga, 6, 3, mezcla((0.4, 0.8, 1.0), (1.0, 0.85, 0.3), carga))
            l.texto(_("Suelta para lanzar"), 0, fondo_agua - 44, w, 20, 12, (1, 1, 1, 0.9), "negrita")
        if self.estado in ("esperando_pez", "pica"):
            ahora = t - self.t
            picoteo = any(0 <= ahora - p < 0.18 for p in self.picotazos) if self.estado == "esperando_pez" else False
            hunde = 8 if self.estado == "pica" else (3 if picoteo else 0)
            corcho = (corcho_x, agua + 2 + math.sin(t * 3) * 1.5 + hunde)
            l.linea(punta[0], punta[1], corcho[0], corcho[1] - 4, 1.2, (1, 1, 1, 0.7))
            if self.estado == "pica":
                l.circulo(corcho[0], agua + 4, 10 + 6 * math.sin(t * 12) ** 2, (1, 1, 1, 0.25))
            l.circulo(corcho[0], corcho[1] - 4, 5, (0.9, 0.2, 0.2))
            l.circulo(corcho[0], corcho[1] + 1, 5, (1, 1, 1))
            if self.estado == "pica":
                l.texto("¡!", corcho[0] - 20, corcho[1] - 42, 40, 26, 24, pal["amarillo"], "negrita")
        if self.estado == "lucha":
            nombre, puntos, fuerza, _d, _v, color, largo = self.pez
            # El pez, bajo el agua: se acerca al muelle según recoges
            px = muelle + (w * 0.9 - muelle) * (0.15 + 0.85 * max(0, self.distancia)) * (self.pez_x / 0.62)
            py = agua + (fondo_agua - agua) * 0.35
            l.linea(punta[0], punta[1], px, py, 1.4, (1, 1, 1, 0.8 if self.tension > 0.2 else 0.4))
            self.dibujar_pez(l, px, py, 30 * largo, con_alfa((0.05, 0.12, 0.25), 0.55))
            for i in range(3):  # salpicones con los tirones
                if self.tiron > 0.2:
                    l.circulo(px + (i - 1) * 9, agua + 1, 2 + self.tiron * 3, (1, 1, 1, 0.6))
            # La tensión
            bw = w * 0.62
            bx, by = (w - bw) / 2, fondo_agua - 26
            l.rect(bx, by, bw, 14, 7, (0, 0, 0, 0.4))
            l.rect(bx + bw * self.ZONA[0], by, bw * (self.ZONA[1] - self.ZONA[0]), 14, 0, (0.3, 0.9, 0.4, 0.35))
            l.rect(bx + bw * 0.92, by, bw * 0.08, 14, 0, (1.0, 0.3, 0.3, 0.35))
            marca = bx + bw * min(1.0, self.tension)
            color_t = (0.3, 0.9, 0.4) if self.ZONA[0] <= self.tension <= self.ZONA[1] else (1.0, 0.8, 0.3)
            if self.tension > 0.9:
                color_t = (1.0, 0.3, 0.3)
            l.rect(marca - 3, by - 3, 6, 20, 3, color_t)
            l.texto(_("Tensión"), bx - 64, by - 3, 60, 20, 11, (1, 1, 1, 0.8), "negrita", 1.0)
            # Lo que falta por recoger
            l.rect(bx, by - 12, bw, 4, 2, (0, 0, 0, 0.3))
            l.rect(bx, by - 12, bw * (1 - max(0, self.distancia)), 4, 2, (0.55, 0.8, 1.0))
            consejo = _("Mantén pulsado para recoger") if not self.pulsado else _("¡Cuidado con la tensión!")
            l.texto(consejo, 0, agua + 8, w, 18, 12, (1, 1, 1, 0.85), "negrita")
        if self.estado == "resultado":
            if self.pescado:  # el pez colgando de la caña
                _n, _p, _f, _d, _v, color, largo = self.pez
                l.linea(punta[0], punta[1], punta[0] + 30, punta[1] + 30, 1.2, (1, 1, 1, 0.7))
                self.dibujar_pez(l, punta[0] + 30, punta[1] + 44, 32 * largo, color, bota=not self.pez[1])
            l.texto(self.resultado, 0, y0 + alto * 0.45, w, 24, 15, pal["texto"], "negrita")
        if self.estado == "listo":
            l.texto(_("Mantén pulsado para lanzar"), 0, y0 + alto * 0.45, w, 24, 14, pal["texto"], "negrita")
        elif self.estado == "esperando":
            _mensaje(l, pal, 0, y0, w, alto, _("Pesca"), _("Lanza lejos, espera al «¡!» y lucha con el pez"))
        elif self.estado == "fin":
            _mensaje(l, pal, 0, y0, w, alto, _("¡Buena pesca!"),
                     _("{n} puntos · clic para jugar otra").format(n=self.puntos))


# ---------------------------------------------------------------------------
# Topos
# ---------------------------------------------------------------------------

class Topos(Juego):
    """Asoman topos por los agujeros: dales con el martillo antes de que se escondan. El dorado
    vale 3, el del casco necesita dos golpes, el del reloj da 3 segundos más y al de la bomba
    no hay que darle. Acertar seguido sube el combo; fallar lo corta. Partidas de 30 segundos."""
    nombre = "topos"
    DURACION = 30

    def __init__(self, guardado, al_guardar):
        super().__init__(guardado, al_guardar)
        self.w = self.h = 0
        self.huecos = []
        self.raton = None
        self.golpe = -1.0
        self.nueva()
        self.estado = "esperando"

    def nueva(self):
        self.estado = "jugando"
        self.puntos = 0
        self.combo = 0
        self.inicio = reloj()
        self.extra = 0.0
        self.topos = {}          # hueco -> dict(salio, dura, tipo, golpes)
        self.efectos = []
        self.siguiente = reloj() + 0.5

    def _queda(self, ahora):
        return self.DURACION + self.extra - (ahora - self.inicio)

    def siguiente_frame(self):
        return 16 if self.estado == "jugando" or self.efectos else None

    def _tipo(self):
        r = random.random()
        return "bomba" if r < 0.12 else "dorado" if r < 0.22 else "casco" if r < 0.34 else \
            "reloj" if r < 0.38 else "normal"

    def _avanzar(self):
        ahora = reloj()
        jugado = ahora - self.inicio
        for hueco, topo in list(self.topos.items()):
            if ahora - topo["salio"] > topo["dura"]:
                del self.topos[hueco]
        if ahora >= self.siguiente and len(self.topos) < 4:
            libres = [i for i in range(9) if i not in self.topos]
            if libres:
                rapidez = 1 - min(0.5, jugado / 50)
                self.topos[random.choice(libres)] = {"salio": ahora, "dura": random.uniform(0.75, 1.2) * rapidez,
                                                     "tipo": self._tipo(), "golpes": 0}
            self.siguiente = ahora + random.uniform(0.3, 0.75) * (1 - min(0.45, jugado / 60))
        self.efectos = [e for e in self.efectos if ahora - e[0] < 0.8]
        if self._queda(ahora) <= 0:
            self.estado = "fin"
            self.topos = {}
            if _record(self.guardado, self.puntos):
                self.al_guardar()
            juegos._premiar(min(MONEDAS["topos"], self.puntos // 4))

    def mover(self, x, y):
        self.raton = (x, y)
        return True

    def pulsar(self, x, y, boton):
        if boton != 1:
            return False
        if self.estado != "jugando":
            self.nueva()
            return True
        ahora = reloj()
        self.golpe = ahora
        self.raton = (x, y)
        for i, (hx, hy, r) in enumerate(self.huecos):
            if (x - hx) ** 2 + (y - hy + r * 0.6) ** 2 < (r * 1.15) ** 2 and i in self.topos:
                topo = self.topos[i]
                tipo = topo["tipo"]
                if tipo == "casco" and topo["golpes"] == 0:
                    topo["golpes"] = 1
                    topo["dura"] += 0.4
                    self.efectos.append((ahora, hx, hy - r, _("¡Clonk!"), (0.8, 0.8, 0.85)))
                    return True
                del self.topos[i]
                if tipo == "bomba":
                    self.puntos = max(0, self.puntos - 3)
                    self.combo = 0
                    self.efectos.append((ahora, hx, hy - r, "-3", (1.0, 0.35, 0.35)))
                    return True
                if tipo == "reloj":
                    self.extra += 3
                    self.efectos.append((ahora, hx, hy - r, _("+3 s"), (0.55, 0.8, 1.0)))
                self.combo += 1
                multi = min(3, 1 + self.combo // 5)
                base = 3 if tipo == "dorado" else 2 if tipo == "casco" else 1
                self.puntos += base * multi
                self.efectos.append((ahora, hx, hy - r * 0.6, f"+{base * multi}", (1.0, 0.85, 0.3)))
                return True
        if self.combo >= 5:
            self.efectos.append((ahora, x, y, _("¡Combo roto!"), (0.75, 0.75, 0.8)))
        self.combo = 0
        return True

    def tecla(self, nombre, pulsada):
        if nombre in ("espacio", "n") and pulsada and self.estado != "jugando":
            self.nueva()
            return True
        return False

    def _topo(self, l, hx, cy, r, subida, topo):
        tipo = topo["tipo"]
        piel = {"dorado": (0.95, 0.75, 0.25), "bomba": (0.5, 0.42, 0.45)}.get(tipo, (0.55, 0.38, 0.25))
        l.rect(hx - r * 0.6, cy - r * 0.55, r * 1.2, r * 0.9 * subida + r * 0.1, r * 0.5, piel)
        l.rect(hx - r * 0.3, cy - r * 0.05, r * 0.6, r * 0.4, r * 0.2, mezcla(piel, (1, 1, 1), 0.35))
        ojo = (0.05, 0.05, 0.05)
        if tipo == "bomba":  # cara de malo
            l.linea(hx - r * 0.34, cy - r * 0.42, hx - r * 0.1, cy - r * 0.32, 2, ojo)
            l.linea(hx + r * 0.34, cy - r * 0.42, hx + r * 0.1, cy - r * 0.32, 2, ojo)
        l.circulo(hx - r * 0.22, cy - r * 0.25, r * 0.1, ojo)
        l.circulo(hx + r * 0.22, cy - r * 0.25, r * 0.1, ojo)
        l.circulo(hx, cy - r * 0.02, r * 0.14, (1.0, 0.55, 0.65))
        if tipo == "casco":
            gris = (0.65, 0.68, 0.72) if topo["golpes"] == 0 else (0.5, 0.52, 0.55)
            l.arco(hx, cy - r * 0.35, r * 0.62, math.pi, 2 * math.pi, r * 0.3, gris)
            l.rect(hx - r * 0.75, cy - r * 0.4, r * 1.5, r * 0.12, 2, gris)
        elif tipo == "bomba":
            Atrapa.dibujar_cosa(l, "bomba", hx + r * 0.55, cy - r * 0.55, r * 0.3, reloj())
        elif tipo == "reloj":
            l.circulo(hx, cy - r * 0.75, r * 0.26, (0.95, 0.95, 1.0))
            l.linea(hx, cy - r * 0.75, hx, cy - r * 0.9, 1.5, (0.2, 0.2, 0.3))
            l.linea(hx, cy - r * 0.75, hx + r * 0.12, cy - r * 0.75, 1.5, (0.2, 0.2, 0.3))
        elif tipo == "dorado":
            _estrella(l, hx + r * 0.5, cy - r * 0.6, r * 0.18, (1, 1, 0.8))

    def _martillo(self, l, x, y, ahora):
        k = (ahora - self.golpe) / 0.15
        giro = 0.0 if k >= 1 else math.sin(k * math.pi) * 0.9  # baja y vuelve
        a = -0.9 + giro
        mx, my = x + 18, y - 18                             # el puño
        cx, cy = mx + math.cos(a - math.pi / 2) * 26, my + math.sin(a - math.pi / 2) * 26
        l.linea(mx, my, cx, cy, 5, (0.55, 0.38, 0.22), True)
        dx, dy = math.cos(a) * 13, math.sin(a) * 13
        l.linea(cx - dx, cy - dy, cx + dx, cy + dy, 13, (0.85, 0.3, 0.3), True)
        l.linea(cx - dx * 0.9, cy - dy * 0.9, cx - dx * 0.5, cy - dy * 0.5, 13, (0.95, 0.5, 0.5), False)

    def dibujar(self, l, pal, w, h):
        self.w, self.h = w, h
        if self.estado == "jugando":
            self._avanzar()
        ahora = reloj()
        queda = max(0, self._queda(ahora)) if self.estado == "jugando" else self.DURACION
        record = max(self.guardado.get("record", 0), self.puntos)
        izquierda = _("Puntos: {n}").format(n=self.puntos) + f"   ⏱ {queda:.0f}"
        if self.combo >= 5 and self.estado == "jugando":
            izquierda += f"   x{min(3, 1 + self.combo // 5)}"
        _cabecera(l, pal, w, izquierda, _("Récord: {n}").format(n=record))
        y0, alto = HUD, h - HUD
        l.rect(0, y0, w, alto, 8, (0.42, 0.7, 0.35))
        for i in range(14):  # matas de hierba
            gx, gy = (i * 97 % 100) / 100 * w, y0 + ((i * 53) % 100) / 100 * alto
            l.linea(gx, gy, gx - 3, gy - 6, 1.5, (0.35, 0.6, 0.28))
            l.linea(gx, gy, gx + 3, gy - 6, 1.5, (0.35, 0.6, 0.28))
        celda_w, celda_h = w / 3, alto / 3
        r = min(celda_w, celda_h) * 0.3
        self.huecos = []
        for i in range(9):
            hx, hy = (i % 3 + 0.5) * celda_w, y0 + (i // 3 + 0.65) * celda_h
            self.huecos.append((hx, hy, r))
            l.rect(hx - r * 1.1, hy - r * 0.35, r * 2.2, r * 0.7, r * 0.35, (0.25, 0.16, 0.08))
            if i in self.topos:
                topo = self.topos[i]
                k = (ahora - topo["salio"]) / topo["dura"]
                subida = max(0.0, min(1, k * 6, (1 - k) * 6))  # sube, se queda y baja
                self._topo(l, hx, hy - r * 0.6 * subida, r, subida, topo)
            l.rect(hx - r * 1.1, hy, r * 2.2, r * 0.35, r * 0.17, (0.35, 0.6, 0.28))  # el borde de delante
        _flotante(l, self.efectos, ahora)
        if self.estado == "jugando" and self.raton:
            self._martillo(l, self.raton[0], self.raton[1], ahora)
        if self.estado == "esperando":
            _mensaje(l, pal, 0, y0, w, alto, _("Topos"),
                     _("Dale a los topos · {n} segundos").format(n=self.DURACION))
        elif self.estado == "fin":
            _mensaje(l, pal, 0, y0, w, alto, _("¡Tiempo!"),
                     _("{n} puntos · clic para jugar otra").format(n=self.puntos))


# ---------------------------------------------------------------------------
# Más o menos
# ---------------------------------------------------------------------------

class MasOMenos(Juego):
    """Adivina si la siguiente carta será mayor o menor. Se juega con una baraja de verdad (52
    cartas, sin volver a salir), así que contar las que han salido ayuda. Acertar lo difícil
    vale doble. Tienes un comodín por partida para cambiar la carta. Si fallas pierdes lo
    acumulado; plántate cuando quieras para cobrarlo en monedas."""
    nombre = "masomenos"
    PALOS = ("♠", "♥", "♦", "♣")
    FIGURAS = {1: "A", 11: "J", 12: "Q", 13: "K"}

    def __init__(self, guardado, al_guardar):
        super().__init__(guardado, al_guardar)
        self.botones = []
        self.w = self.h = 0
        self.nueva()

    def nueva(self):
        self.baraja = [(v, p) for v in range(1, 14) for p in range(4)]
        random.shuffle(self.baraja)
        self.carta = self.baraja.pop()
        self.anterior = None
        self.racha = 0
        self.puntos = 0
        self.comodin = True
        self.estado = "jugando"     # jugando, perdido, cobrado
        self.mensaje = ""
        self.t = reloj()

    def siguiente_frame(self):
        return 16 if reloj() - self.t < 0.4 else None

    def _probabilidad(self, mayor):
        valor = self.carta[0]
        buenas = sum(1 for v, _p in self.baraja if (v > valor if mayor else v < valor) or v == valor)
        return buenas / max(1, len(self.baraja))

    def _apostar(self, mayor):
        if self.estado != "jugando":
            self.nueva()
            return
        prob = self._probabilidad(mayor)
        nueva = self.baraja.pop()
        self.anterior, self.carta, self.t = self.carta, nueva, reloj()
        if nueva[0] == self.anterior[0]:
            self.mensaje = _("¡Igual! La racha sigue")
        elif (nueva[0] > self.anterior[0]) == mayor:
            self.racha += 1
            gana = 2 if prob < 0.4 else 1
            self.puntos += gana
            self.mensaje = _("¡Arriesgado! +2") if gana == 2 else _("¡Acierto!")
            if _record(self.guardado, self.puntos):
                self.al_guardar()
        else:
            self.mensaje = _("¡Fallo! Pierdes {n} puntos").format(n=self.puntos)
            self.puntos = 0
            self.estado = "perdido"
            return
        if not self.baraja:
            self._plantarse()

    def _cambiar(self):
        if self.estado == "jugando" and self.comodin and self.baraja:
            self.comodin = False
            self.baraja.insert(0, self.carta)
            self.anterior, self.carta, self.t = None, self.baraja.pop(), reloj()
            self.mensaje = _("Comodín: carta nueva")

    def _plantarse(self):
        if self.estado != "jugando":
            self.nueva()
            return
        if self.puntos:
            juegos._premiar(min(MONEDAS["masomenos"], self.puntos))
        self.mensaje = _("Te plantas con {n} puntos").format(n=self.puntos)
        self.estado = "cobrado"

    def pulsar(self, x, y, boton):
        if boton != 1:
            return False
        for bx, by, bw, bh, accion in self.botones:
            if bx <= x <= bx + bw and by <= y <= by + bh:
                accion()
                return True
        if self.estado != "jugando":
            self.nueva()
            return True
        return False

    def tecla(self, nombre, pulsada):
        if not pulsada:
            return False
        acciones = {"arriba": lambda: self._apostar(True), "abajo": lambda: self._apostar(False),
                    "espacio": self._plantarse, "n": self.nueva, "derecha": self._cambiar}
        if nombre in acciones:
            acciones[nombre]()
            return True
        return False

    def _carta(self, l, carta, x, y, cw, ch, dorso=False):
        l.rect(x + 2, y + 3, cw, ch, cw * 0.1, (0, 0, 0, 0.25))
        if dorso:
            l.rect(x, y, cw, ch, cw * 0.1, (0.95, 0.95, 0.97))
            l.rect(x + cw * 0.08, y + ch * 0.06, cw * 0.84, ch * 0.88, cw * 0.06, (0.3, 0.4, 0.8))
            for i in range(4):
                l.linea(x + cw * 0.12, y + ch * (0.2 + i * 0.2), x + cw * 0.88, y + ch * (0.1 + i * 0.2), 1.5,
                        (1, 1, 1, 0.25))
            return
        valor, palo = carta
        rojo = palo in (1, 2)
        color = (0.85, 0.15, 0.2) if rojo else (0.12, 0.12, 0.15)
        l.rect(x, y, cw, ch, cw * 0.1, (0.98, 0.98, 0.96))
        texto = self.FIGURAS.get(valor, str(valor))
        l.texto(texto, x + cw * 0.08, y + ch * 0.04, cw * 0.4, ch * 0.2, ch * 0.16, color, "negrita", 0.0)
        l.texto(self.PALOS[palo], x + cw * 0.08, y + ch * 0.2, cw * 0.4, ch * 0.16, ch * 0.13, color, "normal", 0.0)
        l.texto(self.PALOS[palo], x, y + ch * 0.3, cw, ch * 0.5, ch * 0.38, color, "normal")

    def dibujar(self, l, pal, w, h):
        self.w, self.h = w, h
        record = self.guardado.get("record", 0)
        _cabecera(l, pal, w, _("Puntos: {n}").format(n=self.puntos) + "   " +
                  _("Cartas: {n}").format(n=len(self.baraja)), _("Récord: {n}").format(n=record))
        y0, alto = HUD, h - HUD
        boton_h = max(26.0, min(36.0, alto * 0.14))
        zona = alto - boton_h - 34
        ch = max(40.0, min(zona * 0.92, w * 0.42 * 1.4))
        cw = ch / 1.4
        cx = w / 2
        k = min(1.0, (reloj() - self.t) / 0.3)
        k = 1 - (1 - k) ** 3
        # El mazo, a la derecha
        mazo_x = min(w - cw * 0.7 - 6, cx + cw / 2 + 14)
        for i in range(min(4, len(self.baraja) // 10 + 1)):
            self._carta(l, None, mazo_x + i * 1.5, y0 + 6 + ch * 0.15 - i * 1.5, cw * 0.7, ch * 0.7, dorso=True)
        if self.anterior:  # la de antes, a la izquierda y más pequeña
            self._carta(l, self.anterior, max(4.0, cx - cw / 2 - cw * 0.7 - 14), y0 + 6 + ch * 0.15, cw * 0.7,
                        ch * 0.7)
        # La nueva sale del mazo
        x = mazo_x + (cx - cw / 2 - mazo_x) * k
        self._carta(l, self.carta, x, y0 + 6 + ch * 0.15 * (1 - k), cw * (0.7 + 0.3 * k), ch * (0.7 + 0.3 * k))
        color = pal["rojo"] if self.estado == "perdido" else pal["verde"] if self.mensaje.startswith("¡") else pal["texto"]
        l.texto(self.mensaje, 0, y0 + 8 + ch, w, 22, 13, color, "negrita")
        self.botones = []
        if self.estado == "jugando":
            opciones = [(_("▲ Mayor"), lambda: self._apostar(True), None),
                        (_("▼ Menor"), lambda: self._apostar(False), None)]
            if self.comodin:
                opciones.append((_("Comodín"), self._cambiar, con_alfa(pal["morado"], 0.35)))
            opciones.append((_("Plantarse ({n})").format(n=min(MONEDAS["masomenos"], self.puntos)), self._plantarse,
                             con_alfa(pal["amarillo"], 0.35)))
        else:
            opciones = [(_("Jugar otra"), self.nueva, con_alfa(pal["azul"], 0.45))]
        hueco = 6
        ancho = (w - hueco * (len(opciones) + 1)) / len(opciones)
        for i, (texto, accion, color) in enumerate(opciones):
            bx = hueco + i * (ancho + hueco)
            by = h - boton_h - 4
            _boton(l, pal, bx, by, ancho, boton_h, texto, color)
            self.botones.append((bx, by, ancho, boton_h, accion))


# ---------------------------------------------------------------------------
# Faltas
# ---------------------------------------------------------------------------

class Faltas(Juego):
    """Lanzamientos de falta, cada uno desde un sitio distinto (más cerca o más lejos, a un
    lado o al centro) y con la barrera colocada de otra forma (3 a 5 jugadores, que a veces
    saltan). Apunta con el ratón y haz clic; mientras sube y baja la fuerza, mueve el ratón a
    los lados para darle efecto (rosca) y haz clic otra vez para tirar. El portero se mueve y se
    lanza: cuanto más fuerte y más a la escuadra, menos le da tiempo. Cada tiro es más difícil.
    5 tiros por tanda; un gol vale 2, a la escuadra 3 y desde lejos uno más."""
    nombre = "faltas"
    TIROS = 5
    K_BARRERA = 0.45      # en qué punto del camino está la barrera (0 = el balón, 1 = la portería)
    ALTO_BARRERA = 0.72   # en alturas de portería
    ANCHO_JUGADOR = 0.105  # en anchos de portería

    def __init__(self, guardado, al_guardar):
        super().__init__(guardado, al_guardar)
        self.w = self.h = 0
        self.mira = (0.5, 0.7)
        self.nueva()
        self.estado = "esperando"

    def nueva(self):
        self.estado = "apuntar"     # apuntar, fuerza, vuelo, resultado, fin
        self.goles = 0
        self.puntos = 0
        self.tiro = 0
        self._colocar()

    def _colocar(self):
        """El sitio del tiro, la barrera y el portero de este lanzamiento."""
        self.lado = random.choice((-1, 1)) * random.uniform(0.0, 0.42)   # dónde está el balón (respecto al centro)
        self.lejos = random.random()                                     # 0 = frontal cerca, 1 = lejos
        self.n_barrera = random.choice((3, 4, 4, 5)) if self.lejos < 0.6 else random.choice((3, 4))
        # La barrera tapa el palo cercano (o el centro si el tiro es frontal)
        cerca = 0.5 + self.lado * 1.1
        self.barrera = min(0.75, max(0.25, cerca + random.uniform(-0.1, 0.1)))
        self.salta = random.random() < 0.25 + self.tiro * 0.08
        # El portero, hacia el lado que no tapa la barrera
        self.portero_base = min(0.7, max(0.3, 0.5 - (self.barrera - 0.5) * 0.7 + random.uniform(-0.05, 0.05)))
        self.portero = self.portero_base
        self.fase_portero = random.uniform(0, 6.3)
        self.fuerza = 0.0
        self.efecto = 0.0
        self.x0 = 0.5 + self.lado   # el balón, en coordenadas de la portería
        self.t = reloj()
        self.resultado = ""
        self.gol = False

    # Lo difícil que es (sube con cada tiro)
    def _velocidad_portero(self):
        return 1.0 + self.tiro * 0.12

    def _reaccion(self):
        return max(0.1, 0.2 - self.tiro * 0.02)

    def siguiente_frame(self):
        return 33 if self.estado == "apuntar" else 16 if self.estado in ("fuerza", "vuelo", "resultado") else None

    # Geometría: la portería (con perspectiva: más pequeña de lejos y desplazada según el lado)
    def _porteria(self):
        w, h = self.w, self.h
        pw = w * (0.6 - 0.16 * self.lejos)
        ph = pw * 0.34
        x0 = w / 2 - (0.5 + self.lado) * pw   # el balón está siempre abajo en el centro
        py = HUD + (h - HUD) * (0.07 + 0.06 * self.lejos)
        return x0, py, pw, ph

    def _balon_inicio(self):
        return self.w / 2, self.h - (self.h - HUD) * 0.12

    def _en_pantalla(self, gx, gy):
        """Un punto de la portería (gx 0-1 a lo ancho, gy 0-1 de alto) en el widget."""
        x0, py, pw, ph = self._porteria()
        return x0 + gx * pw, py + ph * (1 - gy)

    def _profundidad(self, k):
        """Cuánto del camino en pantalla lleva el balón en k (lo cercano avanza más deprisa)."""
        return k + 0.35 / self.K_BARRERA * k * (1 - k)

    def mover(self, x, y):
        if not self.w:
            return False
        x0, py, pw, ph = self._porteria()
        if self.estado == "apuntar":
            self.mira = (min(1.12, max(-0.12, (x - x0) / pw)), min(1.3, max(0.0, (py + ph - y) / ph)))
            self._raton_x = x
            return True
        if self.estado == "fuerza":
            self.efecto = min(1.0, max(-1.0, (x - self._raton_x) / (self.w * 0.18)))
            return True
        return False

    def _accion(self):
        if self.estado in ("esperando", "fin"):
            self.nueva()
        elif self.estado == "apuntar":
            self.estado, self.t = "fuerza", reloj()
            self.efecto = 0.0
            self._raton_x = getattr(self, "_raton_x", self.w / 2)
        elif self.estado == "fuerza":
            self._tirar()
        elif self.estado == "resultado":
            self._siguiente()
        return True

    def pulsar(self, x, y, boton):
        if boton != 1:
            return False
        if self.estado == "apuntar":
            self.mover(x, y)
        return self._accion()

    def tecla(self, nombre, pulsada):
        if not pulsada:
            return False
        if nombre in ("izquierda", "derecha", "arriba", "abajo"):
            if self.estado == "apuntar":
                dx = {"izquierda": -0.04, "derecha": 0.04}.get(nombre, 0)
                dy = {"arriba": 0.06, "abajo": -0.06}.get(nombre, 0)
                self.mira = (min(1.12, max(-0.12, self.mira[0] + dx)), min(1.3, max(0.0, self.mira[1] + dy)))
            elif self.estado == "fuerza" and nombre in ("izquierda", "derecha"):
                self.efecto = min(1.0, max(-1.0, self.efecto + (0.25 if nombre == "derecha" else -0.25)))
            return True
        if nombre == "espacio":
            return self._accion()
        return False

    def _fuerza_ahora(self):
        return abs(math.sin((reloj() - self.t) * (2.0 + self.tiro * 0.25)))  # sube y baja, cada vez más rápida

    # La trayectoria, en coordenadas de la portería: x a lo ancho y altura (0 suelo, 1 larguero)
    def _x(self, k, destino=None, efecto=None):
        destino = self.destino[0] if destino is None else destino
        efecto = self.efecto if efecto is None else efecto
        return self.x0 + (destino - self.x0) * k + efecto * 0.32 * math.sin(math.pi * k)

    def _altura(self, k, destino=None, fuerza=None):
        destino = self.destino[1] if destino is None else destino
        fuerza = self.fuerza if fuerza is None else fuerza
        return destino * k + (0.35 + 0.35 * fuerza) * math.sin(math.pi * k) * (1 - 0.4 * k)

    def _escala(self, k):
        """Lo grande que se ve algo a k del camino (en la portería, 1)."""
        return 1 + (1 - self._profundidad(k)) * 0.9

    def _punto(self, gx, altura, k):
        """En el widget: algo a k del camino, en gx (a lo ancho de la portería) y a cierta altura.
        Visto desde detrás del balón, lo que tapa una parte de la portería cae justo encima de ella."""
        x0, py, pw, ph = self._porteria()
        _bx, by = self._balon_inicio()
        suelo = by + (py + ph - by) * self._profundidad(k)
        return x0 + gx * pw, suelo - altura * ph * self._escala(k), suelo

    def _tirar(self):
        self.fuerza = self._fuerza_ahora()
        mx, my = self.mira
        # Con mucha fuerza va más alto y menos preciso
        self.alcance = 0.3
        error = random.gauss(0, 0.015 + max(0.0, self.fuerza - 0.75) * 0.12)
        altura = my + (self.fuerza - 0.62) * 0.9 + random.gauss(0, 0.02)
        # El efecto curva el balón: llega más hacia donde gira
        self.destino = (mx + error + self.efecto * 0.08, altura)
        self.vuelo = 1.05 - 0.45 * self.fuerza + 0.25 * self.lejos
        dx, alto = self.destino
        # ¿Barrera? El balón pasa por la línea de la barrera en K_BARRERA del camino
        xb, hb = self._x(self.K_BARRERA), self._altura(self.K_BARRERA)
        mitad = self.n_barrera * self.ANCHO_JUGADOR / 2
        alto_barrera = self.ALTO_BARRERA + (0.12 if self.salta else 0)
        self.para_en = None
        if abs(xb - self.barrera) < mitad and hb < alto_barrera:
            self.resultado, self.gol, self.para_en = _("¡Barrera!"), False, self.K_BARRERA
        elif alto > 1.02:
            self.resultado, self.gol = _("¡Por encima del larguero!"), False
        elif dx < -0.02 or dx > 1.02:
            self.resultado, self.gol = _("¡Fuera!"), False
        elif dx < 0.03 or dx > 0.97 or 0.97 < alto <= 1.02:
            self.resultado, self.gol = _("¡Al palo!"), False
        else:
            # El portero: reacciona (tarde si no lo ve por la barrera) y se lanza
            tapado = abs(xb - self.barrera) < mitad + 0.1
            tiempo = max(0.0, self.vuelo - self._reaccion() - (0.12 if tapado else 0))
            alcance = 0.13 + self._velocidad_portero() * tiempo * 0.55
            self.alcance = alcance
            if alto > 0.75:
                alcance *= 0.72   # a la escuadra cuesta más
            elif alto < 0.2:
                alcance *= 0.9
            if abs(dx - self.portero) <= alcance:
                self.resultado, self.gol = _("¡Parada del portero!"), False
                self.para_en = 1.0
            else:
                escuadra = alto > 0.72 and (dx < 0.2 or dx > 0.8)
                self.resultado, self.gol = (_("¡Golazo por la escuadra!") if escuadra else _("¡GOOOL!")), True
                self.valor = 2 + (1 if escuadra else 0) + (1 if self.lejos > 0.65 else 0)
        self.portero_desde = self.portero
        self.estado, self.t = "vuelo", reloj()

    def _siguiente(self):
        if self.tiro < self.TIROS:
            self.estado = "apuntar"
            self._colocar()
        else:
            self.estado = "fin"

    def _avanzar(self):
        ahora = reloj()
        if self.estado == "vuelo" and ahora - self.t > self.vuelo * (self.para_en or 1.0):
            self.estado, self.t = "resultado", ahora
            self.tiro += 1
            if self.gol:
                self.goles += 1
                self.puntos += self.valor
            if self.tiro >= self.TIROS:
                if _record(self.guardado, self.puntos):
                    self.al_guardar()
                bonus = 4 if self.goles == self.TIROS else 0
                juegos._premiar(min(MONEDAS["faltas"], self.puntos + bonus))
        elif self.estado == "resultado" and ahora - self.t > 1.8:
            self._siguiente()
        elif self.estado in ("apuntar", "fuerza"):  # el portero se recoloca, nervioso
            self.portero = self.portero_base + math.sin(ahora * (1.4 + self.tiro * 0.3) + self.fase_portero) * \
                (0.05 + self.tiro * 0.012)

    def _jugador(self, l, cx, pie, alto, camiseta, brazos=False, ancho=None):
        ancho = ancho or alto * 0.32
        l.rect(cx - ancho / 2, pie - alto * 0.75, ancho, alto * 0.45, alto * 0.08, camiseta)
        if brazos:
            l.rect(cx - alto * 0.3, pie - alto * 0.95, alto * 0.1, alto * 0.35, alto * 0.05, camiseta)
            l.rect(cx + alto * 0.2, pie - alto * 0.95, alto * 0.1, alto * 0.35, alto * 0.05, camiseta)
        l.rect(cx - alto * 0.14, pie - alto * 0.32, alto * 0.11, alto * 0.32, 0, (0.15, 0.15, 0.2))
        l.rect(cx + alto * 0.03, pie - alto * 0.32, alto * 0.11, alto * 0.32, 0, (0.15, 0.15, 0.2))
        l.circulo(cx, pie - alto * 0.86, alto * 0.13, (0.95, 0.78, 0.62))

    def _portero_dibujo(self, l, cx, pie, alto, estirada, altura):
        """De pie o tirado hacia un lado (estirada -1..1) a cierta altura (0-1)."""
        amarillo, guantes = (0.95, 0.75, 0.15), (0.3, 0.8, 0.4)
        if abs(estirada) < 0.15:
            self._jugador(l, cx, pie, alto, amarillo, brazos=True)
            l.circulo(cx - alto * 0.25, pie - alto * 0.97, alto * 0.07, guantes)
            l.circulo(cx + alto * 0.25, pie - alto * 0.97, alto * 0.07, guantes)
            return
        # En el aire: el cuerpo tumbado hacia el lado del balón
        s = 1 if estirada > 0 else -1
        cy = pie - alto * (0.35 + 0.55 * altura) * min(1, abs(estirada) * 1.5)
        largo = alto * 0.9
        l.rect(cx - largo / 2, cy - alto * 0.13, largo, alto * 0.26, alto * 0.12, amarillo)
        l.rect(cx - s * largo * 0.6 - alto * 0.12, cy - alto * 0.08, alto * 0.25, alto * 0.16, 2, (0.15, 0.15, 0.2))
        l.circulo(cx + s * largo * 0.5, cy - alto * 0.04, alto * 0.13, (0.95, 0.78, 0.62))
        l.rect(cx + s * largo * 0.55 - alto * 0.05, cy - alto * 0.25, alto * 0.42 * s, alto * 0.09, 2, amarillo)
        l.circulo(cx + s * (largo * 0.55 + alto * 0.42), cy - alto * 0.2, alto * 0.08, guantes)

    def dibujar(self, l, pal, w, h):
        self.w, self.h = w, h
        self._avanzar()
        ahora = reloj()
        record = self.guardado.get("record", 0)
        marcas = "".join("●" if i < self.tiro else "○" for i in range(self.TIROS))
        _cabecera(l, pal, w, _("Puntos: {n}").format(n=self.puntos) + f"   {marcas}", _("Récord: {n}").format(n=record))
        y0, alto = HUD, h - HUD
        for i in range(7):  # el césped, a rayas
            l.rect(0, y0 + alto * i / 7, w, alto / 7 + 1, 0 if i else 6, (0.3, 0.62, 0.3) if i % 2 else (0.34, 0.68, 0.33))
        x0, py, pw, ph = self._porteria()
        # La línea del área, que ayuda a ver de dónde se tira
        l.linea(0, py + ph + 2, w, py + ph + 2, 2, (1, 1, 1, 0.5))
        # La red y los palos
        l.rect(x0, py, pw, ph, 0, (1, 1, 1, 0.12))
        for i in range(1, 12):
            l.linea(x0 + pw * i / 12, py, x0 + pw * i / 12, py + ph, 1, (1, 1, 1, 0.25))
        for i in range(1, 5):
            l.linea(x0, py + ph * i / 5, x0 + pw, py + ph * i / 5, 1, (1, 1, 1, 0.25))
        grosor = max(3.0, pw * 0.012)
        l.linea(x0, py + ph, x0, py, grosor, (1, 1, 1))
        l.linea(x0 + pw, py + ph, x0 + pw, py, grosor, (1, 1, 1))
        l.linea(x0 - grosor / 2, py, x0 + pw + grosor / 2, py, grosor, (1, 1, 1))
        # El portero
        alto_jug = ph * 0.85
        estirada, altura_salto, portero = 0.0, 0.0, self.portero
        if self.estado in ("vuelo", "resultado") and hasattr(self, "destino"):
            dur = self.vuelo * (self.para_en or 1.0)
            k = min(1.0, (ahora - self.t) / max(0.01, dur)) if self.estado == "vuelo" else 1.0
            dx, da = self.destino
            reaccion = self._reaccion() / max(0.01, self.vuelo)
            if k > reaccion:
                kk = min(1.0, (k - reaccion) / max(0.01, 1 - reaccion) * 1.3)
                tope = min(0.45, self.alcance * (1.0 if self.para_en == 1.0 else 0.85))
                hacia = max(-tope, min(tope, dx - self.portero_desde))
                portero = self.portero_desde + hacia * kk
                estirada = (hacia / 0.45) * kk if abs(hacia) > 0.08 else 0.0
                altura_salto = min(1.0, max(0.0, da))
        self._portero_dibujo(l, x0 + pw * portero, py + ph, alto_jug, estirada, altura_salto)
        # La barrera, entre el balón y la portería
        # La barrera: cada jugador tapa justo el trozo de portería que tiene detrás
        _sx, _sy, barrera_y = self._punto(0, 0, self.K_BARRERA)
        alto_b = self.ALTO_BARRERA * ph * self._escala(self.K_BARRERA)
        salto = 0.0
        if self.salta and self.estado == "vuelo":
            k = min(1.0, (ahora - self.t) / 0.5)
            salto = math.sin(math.pi * k) * 0.12 * ph * self._escala(self.K_BARRERA)
        for i in range(self.n_barrera):
            gx = self.barrera + (i - (self.n_barrera - 1) / 2) * self.ANCHO_JUGADOR
            self._jugador(l, x0 + gx * pw, barrera_y - salto, alto_b, (0.85, 0.2, 0.25),
                          ancho=self.ANCHO_JUGADOR * pw * 0.86)
        # El balón
        radio0 = max(4.0, alto * 0.045)
        k = 0.0
        if self.estado in ("vuelo", "resultado") and hasattr(self, "destino"):
            k = min(1.0, (ahora - self.t) / max(0.01, self.vuelo)) if self.estado == "vuelo" else (self.para_en or 1.0)
            k = min(k, self.para_en or 1.0)
            bx, by, suelo = self._punto(self._x(k), self._altura(k), k)
        else:
            bx, by, suelo = self._punto(self.x0, 0, 0)
            by -= radio0
            suelo = by + radio0
        radio = radio0 * self._escala(k) / self._escala(0)
        l.circulo(bx, suelo, radio * 0.9, (0, 0, 0, 0.18))  # la sombra, en el suelo
        l.circulo(bx, by, radio, (1, 1, 1))
        giro = ahora * 12 if self.estado == "vuelo" else 0
        for a in (0.3, 2.4, 4.4):
            l.circulo(bx + math.cos(a + giro) * radio * 0.45, by + math.sin(a + giro) * radio * 0.45, radio * 0.25,
                      (0.1, 0.1, 0.12))
        # La mira y la curva que llevará
        if self.estado in ("apuntar", "fuerza"):
            mx, my = self.mira
            cx, cy = self._en_pantalla(mx, min(my, 1.3))
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                l.linea(cx + dx * 4, cy + dy * 4, cx + dx * 11, cy + dy * 11, 2, (1, 0.95, 0.4))
            l.circulo(cx, cy, 2.5, (1, 0.95, 0.4))
            if self.estado == "fuerza" and abs(self.efecto) > 0.05:  # por dónde irá (más o menos)
                previo = self._punto(self.x0, 0, 0)[:2]
                for i in range(1, 11):
                    k = i / 10
                    p = self._punto(self._x(k, mx, self.efecto), self._altura(k, my, 0.6), k)[:2]
                    l.linea(previo[0], previo[1], p[0], p[1], 2, (1, 0.95, 0.4, 0.45))
                    previo = p
        # La fuerza: una barra que sube y baja
        if self.estado in ("fuerza", "vuelo"):
            fuerza = self._fuerza_ahora() if self.estado == "fuerza" else self.fuerza
            bw, bh = 14, alto * 0.55
            fx, fy = w - bw - 10, y0 + (alto - bh) / 2
            l.rect(fx, fy, bw, bh, 7, (0, 0, 0, 0.35))
            l.rect(fx, fy + bh * (1 - 0.78), bw, bh * 0.3, 0, (0.3, 0.9, 0.4, 0.35))  # la zona buena
            color = mezcla((0.3, 0.9, 0.4), (0.95, 0.3, 0.3), max(0, fuerza - 0.7) * 3)
            l.rect(fx + 2, fy + bh * (1 - fuerza), bw - 4, bh * fuerza, 5, color)
        if self.estado == "apuntar":
            l.texto(_("Apunta y haz clic"), 0, h - 22, w, 20, 12, (1, 1, 1, 0.85), "negrita")
        elif self.estado == "fuerza":
            l.texto(_("Mueve a los lados para el efecto · clic para tirar"), 0, h - 22, w, 20,
                    px_que_quepa(l, _("Mueve a los lados para el efecto · clic para tirar"), w - 10, 12, "negrita"),
                    (1, 1, 1, 0.85), "negrita")
        elif self.estado == "resultado":
            color = pal["amarillo"] if self.gol else (1, 1, 1)
            texto = self.resultado + (f"  +{self.valor}" if self.gol else "")
            l.texto(texto, 0, y0 + alto * 0.55, w, 30, px_que_quepa(l, texto, w - 16, 20, "negrita"), color, "negrita")
        elif self.estado == "esperando":
            _mensaje(l, pal, 0, y0, w, alto, _("Faltas"), _("Apunta, dale efecto y supera al portero"))
        elif self.estado == "fin":
            _mensaje(l, pal, 0, y0, w, alto, _("¡Fin de la tanda!"),
                     _("{n} de {m} goles · {p} puntos · clic para otra").format(n=self.goles, m=self.TIROS,
                                                                                p=self.puntos))


CLASES = {"atrapa": Atrapa, "serpiente": Serpiente, "pesca": Pesca, "topos": Topos, "masomenos": MasOMenos,
          "faltas": Faltas}


# ---------------------------------------------------------------------------
# Iconos para el selector de juegos
# ---------------------------------------------------------------------------

def dibujar_icono(clave, l, x, y, tam, pal):
    """Un dibujito de cada juego en el cuadrado (x, y, tam)."""
    cx, cy, r = x + tam / 2, y + tam / 2, tam / 2
    if clave == "buscaminas":
        for f in range(3):
            for c in range(3):
                l.rect(x + tam * (0.12 + c * 0.27), y + tam * (0.12 + f * 0.27), tam * 0.24, tam * 0.24, 3,
                       (0.75, 0.78, 0.85) if (f + c) % 2 else (0.62, 0.66, 0.75))
        l.circulo(cx, cy, r * 0.22, (0.1, 0.1, 0.12))
        l.linea(x + tam * 0.75, y + tam * 0.2, x + tam * 0.75, y + tam * 0.45, 2, (0.3, 0.3, 0.3))
        l.poligono([(x + tam * 0.75, y + tam * 0.2), (x + tam * 0.9, y + tam * 0.26), (x + tam * 0.75, y + tam * 0.32)],
                   (0.9, 0.2, 0.25))
    elif clave == "2048":
        for (c, f), (texto, color) in zip(((0, 0), (1, 0), (0, 1), (1, 1)), (("2", (0.93, 0.89, 0.85)),
                                                                          ("4", (0.93, 0.88, 0.78)),
                                                                          ("8", (0.95, 0.69, 0.47)),
                                                                          ("2048", (0.93, 0.76, 0.18)))):
            bx, by = x + tam * (0.1 + c * 0.42), y + tam * (0.1 + f * 0.42)
            l.rect(bx, by, tam * 0.38, tam * 0.38, 4, color)
            l.texto(texto, bx, by, tam * 0.38, tam * 0.38, px_que_quepa(l, texto, tam * 0.32, tam * 0.16, "negrita"),
                    (0.35, 0.3, 0.27), "negrita")
    elif clave == "dino":
        l.rect(x, y + tam * 0.78, tam, 2, 0, pal["gris"])
        l.rect(x + tam * 0.2, y + tam * 0.4, tam * 0.3, tam * 0.3, 3, pal["texto"])
        l.rect(x + tam * 0.4, y + tam * 0.25, tam * 0.25, tam * 0.2, 3, pal["texto"])
        l.rect(x + tam * 0.25, y + tam * 0.7, tam * 0.07, tam * 0.08, 0, pal["texto"])
        l.rect(x + tam * 0.4, y + tam * 0.7, tam * 0.07, tam * 0.08, 0, pal["texto"])
        l.rect(x + tam * 0.75, y + tam * 0.5, tam * 0.1, tam * 0.28, 2, (0.3, 0.7, 0.35))
    elif clave == "atrapa":
        Atrapa.dibujar_cosa(l, "manzana", cx - r * 0.3, y + tam * 0.3, r * 0.22)
        Atrapa.dibujar_cosa(l, "naranja", cx + r * 0.35, y + tam * 0.18, r * 0.18)
        if not (DIBUJAR_MASCOTA and DIBUJAR_MASCOTA(l, cx, y + tam * 0.97, tam * 0.5, "feliz")):
            l.poligono([(cx - r * 0.5, y + tam * 0.65), (cx + r * 0.5, y + tam * 0.65), (cx + r * 0.38, y + tam * 0.92),
                        (cx - r * 0.38, y + tam * 0.92)], (0.75, 0.5, 0.25))
    elif clave == "serpiente":
        for i, (c, f) in enumerate(((0, 2), (1, 2), (2, 2), (2, 1), (3, 1))):
            l.rect(x + tam * (0.08 + c * 0.2), y + tam * (0.15 + f * 0.2), tam * 0.18, tam * 0.18, tam * 0.06,
                   mezcla((0.2, 0.6, 0.3), (0.35, 0.8, 0.4), i / 4))
        Atrapa.dibujar_cosa(l, "manzana", x + tam * 0.8, y + tam * 0.72, tam * 0.1)
    elif clave == "pesca":
        l.rect(x, y + tam * 0.45, tam, tam * 0.55, 6, (0.2, 0.5, 0.85))
        Pesca.dibujar_pez(l, cx + r * 0.1, y + tam * 0.72, tam * 0.4, (1.0, 0.55, 0.15))
        l.linea(x + tam * 0.1, y + tam * 0.08, x + tam * 0.6, y + tam * 0.4, 2, (0.5, 0.35, 0.2))
        l.circulo(x + tam * 0.6, y + tam * 0.45, tam * 0.06, (0.9, 0.2, 0.2))
    elif clave == "topos":
        l.rect(x + tam * 0.1, y + tam * 0.62, tam * 0.8, tam * 0.2, tam * 0.1, (0.25, 0.16, 0.08))
        l.rect(x + tam * 0.3, y + tam * 0.3, tam * 0.4, tam * 0.4, tam * 0.18, (0.55, 0.38, 0.25))
        for dx in (-0.08, 0.08):
            l.circulo(cx + tam * dx, y + tam * 0.42, tam * 0.03, (0.05, 0.05, 0.05))
        l.circulo(cx, y + tam * 0.5, tam * 0.045, (1.0, 0.55, 0.65))
        l.rect(x + tam * 0.1, y + tam * 0.72, tam * 0.8, tam * 0.1, tam * 0.05, (0.35, 0.6, 0.28))
    elif clave == "masomenos":
        for i, (texto, color) in enumerate((("7", (0.12, 0.12, 0.15)), ("K", (0.85, 0.15, 0.2)))):
            bx, by = x + tam * (0.12 + i * 0.32), y + tam * (0.15 + i * 0.08)
            l.rect(bx, by, tam * 0.45, tam * 0.62, 5, (0.98, 0.98, 0.96))
            l.texto(texto, bx, by, tam * 0.45, tam * 0.62, tam * 0.3, color, "negrita")
    elif clave == "faltas":
        l.rect(x + tam * 0.1, y + tam * 0.15, tam * 0.8, tam * 0.35, 0, (1, 1, 1, 0.15))
        l.linea(x + tam * 0.1, y + tam * 0.5, x + tam * 0.1, y + tam * 0.15, 2.5, (1, 1, 1))
        l.linea(x + tam * 0.9, y + tam * 0.5, x + tam * 0.9, y + tam * 0.15, 2.5, (1, 1, 1))
        l.linea(x + tam * 0.1, y + tam * 0.15, x + tam * 0.9, y + tam * 0.15, 2.5, (1, 1, 1))
        l.circulo(cx, y + tam * 0.75, tam * 0.13, (1, 1, 1))
        for a in (0.3, 2.4, 4.4):
            l.circulo(cx + math.cos(a) * tam * 0.06, y + tam * 0.75 + math.sin(a) * tam * 0.06, tam * 0.03,
                      (0.1, 0.1, 0.12))
