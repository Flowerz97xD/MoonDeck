"""Mascota del widget Mascota (pack Ocio): un tamagotchi que vive en el escritorio.

Se elige especie, colores, nombre y complementos. Tiene cuatro necesidades (comida, ánimo,
energía e higiene) que bajan con el tiempo, también con MoonDeck cerrado (al abrirlo se
calcula lo que ha pasado, a medio ritmo y sin bajar de un mínimo: nunca muere, como mucho
se pone triste). Crece (bebé, joven, adulto) con las horas que pasa bien cuidada.

Reacciona a lo que pasa en el PC (contexto que le pasa la app en cada fotograma):
    musica   suena una canción: baila   calor    CPU o GPU muy calientes: suda
    video    se reproduce otra cosa: lo mira comiendo palomitas
    jugando  hay un juego con FPS: mira la pantalla con un mando
    discord  estás en un canal de voz: se pone los auriculares
y de madrugada se duerme sola. Las partidas ganadas en los minijuegos dan monedas
(juegos.AL_GANAR) para la tienda (comida especial, complementos y fondos), y cada día que
pasáis juntos también (más si es una racha de días seguidos). Caben como mucho MAX_MONEDAS.

Se dibuja en pixel art (16 x 16) con el lienzo de los relojes y los juegos (esferas.py),
así los colores se cambian sin imágenes y queda nítida a cualquier tamaño.
"""

import colorsys
import math
import random
import time

from esferas import con_alfa, mezcla, px_que_quepa
from idioma import _

ESPECIES = (("gato", "Gato"), ("perro", "Perro"), ("carlino", "Carlino"), ("cocker", "Cocker spaniel"),
            ("conejo", "Conejo"), ("zorro", "Zorro"), ("panda", "Panda"), ("pinguino", "Pingüino"), ("rana", "Rana"),
            ("dragon", "Dragón"), ("fantasma", "Fantasma"), ("robot", "Robot"), ("slime", "Slime"))
# Colores por defecto de cada especie: cuerpo, manchas, ojos
COLORES = {
    "gato": ("#f0a35e", "#b8642a", "#2b2b2b"), "perro": ("#d9b38c", "#8a5a36", "#2b2b2b"),
    "carlino": ("#e6c79c", "#2e2622", "#120d0b"), "cocker": ("#d9a35b", "#a8692b", "#2b1d14"),
    "zorro": ("#f08a3c", "#c45f1c", "#2b1d14"), "panda": ("#f4f4f4", "#262626", "#1a1a1a"),
    "pinguino": ("#33415a", "#1d2533", "#111111"), "rana": ("#6cc04a", "#3f8a2a", "#1d2b14"),
    "conejo": ("#f2f2f2", "#d4c4c4", "#3a2b2b"), "dragon": ("#5cc46a", "#2f7d3c", "#2b2b2b"),
    "fantasma": ("#e8ecf5", "#aab6d0", "#2b3550"), "robot": ("#a7b9cc", "#56708a", "#39d2ff"),
    "slime": ("#7fd6f0", "#3f9cc0", "#1f3b4d"),
}
# (clave, nombre, precio), de más barato a más caro
COMPLEMENTOS = (("chupete", "Chupete", 8), ("lazo", "Lazo", 10), ("flor", "Flor", 10), ("gorra", "Gorra", 12),
                ("gorra_atras", "Gorra hacia atrás", 12), ("pajarita", "Pajarita", 12), ("parche", "Parche pirata", 12),
                ("gafas", "Gafas de sol", 15), ("gorro", "Gorro de fiesta", 15), ("santa", "Gorro de Papá Noel", 15),
                ("cuernos", "Cuernos de diablo", 15), ("bigote", "Bigote y monóculo", 15), ("chef", "Gorro de chef", 15),
                ("bufanda", "Bufanda", 20), ("calabaza", "Calabaza", 20), ("mago", "Sombrero de mago", 30),
                ("auriculares_rgb", "Auriculares RGB", 35), ("corona", "Corona", 40), ("capa", "Capa de superhéroe", 45),
                ("halo", "Halo", 50), ("astronauta", "Casco de astronauta", 50))
# (clave, nombre, precio, efecto)
COMIDAS = (("galleta", "Galleta", 4, {"hambre": 10, "felicidad": 15}),
           ("helado", "Helado", 5, {"hambre": 15, "felicidad": 25}),
           ("sandia", "Sandía", 6, {"hambre": 20, "felicidad": 10}),
           ("cafe", "Café", 6, {"energia": 25}),
           ("pastel", "Pastel", 8, {"hambre": 45, "felicidad": 15}),
           ("pizza", "Pizza", 9, {"hambre": 40, "felicidad": 10}),
           ("energetica", "Bebida energética", 10, {"energia": 40, "felicidad": 5}),
           ("hamburguesa", "Hamburguesa", 10, {"hambre": 55, "felicidad": 5}),
           ("ramen", "Ramen", 11, {"hambre": 45, "energia": 10}),
           ("sushi", "Sushi", 12, {"hambre": 40, "felicidad": 20}))
# (clave, nombre, precio): los de precio 0 se tienen desde el principio
FONDOS = (("ninguno", "Ninguno", 0), ("habitacion", "Habitación", 0), ("jardin", "Jardín", 0),
          ("playa", "Playa", 20), ("nieve", "Nieve", 25), ("noche", "Noche estrellada", 25),
          ("otono", "Bosque de otoño", 25), ("ciudad", "Ciudad de noche", 30), ("dulces", "Mundo dulce", 35),
          ("mar", "Fondo del mar", 35), ("espacio", "Espacio", 40), ("gamer", "Setup gamer", 45),
          ("concierto", "Concierto", 50))
# (clave, nombre, precio, para qué sirve): objetos, la caja sorpresa y los pelajes
ESPECIALES = (("pelota", "Pelota", 15, "Al jugar, sube más el ánimo."),
              ("caja", "Caja sorpresa", 18, "Un complemento al azar de los que no tienes."),
              ("peluche", "Peluche", 25, "Duerme abrazada a él y se despierta más contenta."),
              ("camita", "Camita", 40, "Duerme en ella y recupera la energía más rápido."),
              ("dorado", "Pelaje dorado", 60, "Dorado, con un brillo que la recorre. Se elige en Personalizar."),
              ("arcoiris", "Pelaje arcoíris", 80, "Franjas de colores que se mueven. Se elige en Personalizar."))
PELAJES = ("dorado", "arcoiris")
NECESIDADES = (("hambre", "Comida"), ("felicidad", "Ánimo"), ("energia", "Energía"), ("limpieza", "Higiene"))
ETAPAS = ((0, "Bebé", 0.62), (24, "Joven", 0.82), (96, "Adulto", 1.0))  # horas bien cuidada

# Lo que baja cada necesidad por hora: despierta / dormida (negativo: sube)
RITMO = {"hambre": (6, 3), "felicidad": (4, 1), "energia": (5, -15), "limpieza": (3, 1.5)}
AUSENTE = 600      # s sin fotogramas: MoonDeck estaba cerrado (o el PC dormido)
MINIMO_AUSENTE = 10
MAX_HORAS = 72
AVISO_CADA = 3 * 3600
MONEDAS_INICIALES = 15
MAX_MONEDAS = 400          # la hucha: caben varias compras grandes, pero hay que gastar
PREMIO_DIA = (15, 3, 30)   # monedas por cada día: base, + por día seguido de racha, tope


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


# ---------------------------------------------------------------------------
# Sprites de 32 x 32. Cada especie se dibuja con formas (óvalos, triángulos, trazos) sobre una
# cuadrícula de códigos; el contorno y el volumen se calculan solos. Todas comparten dónde van
# los ojos (filas 14-17, columnas 9-11 y 20-22) y la boca (filas 20-22, columnas 14-17), así
# las expresiones y los complementos les valen a todas.
#   b cuerpo  m manchas  c crema  p rosa  w blanco  k negro  y naranja  r rojo  g gris  e oscuro
#   (mayúsculas: lo mismo pero sin contorno alrededor ni volumen, para detalles por dentro)
# ---------------------------------------------------------------------------

N = 32
_FIJOS = {"p": (1.0, 0.58, 0.66), "w": (0.97, 0.97, 0.98), "k": (0.12, 0.11, 0.12), "y": (1.0, 0.65, 0.15),
          "r": (0.88, 0.22, 0.28), "g": (0.62, 0.66, 0.72)}


class _Rejilla:
    def __init__(self):
        self.g = [["."] * N for _ in range(N)]

    def punto(self, f, c, v):
        if 0 <= f < N and 0 <= c < N:
            self.g[f][c] = v

    def ovalo(self, cy, cx, ry, rx, v, espejo=False):
        for f in range(N):
            for c in range(N):
                if ((f + 0.5 - cy) / ry) ** 2 + ((c + 0.5 - cx) / rx) ** 2 <= 1:
                    self.punto(f, c, v)
                    if espejo:
                        self.punto(f, N - 1 - c, v)

    def triangulo(self, a, b, c_, v, espejo=False):
        """Vértices (fila, columna)."""
        def lado(p, q, r):
            return (q[1] - p[1]) * (r[0] - p[0]) - (q[0] - p[0]) * (r[1] - p[1])
        for f in range(N):
            for c in range(N):
                pt = (f + 0.5, c + 0.5)
                d1, d2, d3 = lado(a, b, pt), lado(b, c_, pt), lado(c_, a, pt)
                if not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0)):
                    self.punto(f, c, v)
                    if espejo:
                        self.punto(f, N - 1 - c, v)

    def rect(self, f0, c0, f1, c1, v, espejo=False):
        for f in range(f0, f1 + 1):
            for c in range(c0, c1 + 1):
                self.punto(f, c, v)
                if espejo:
                    self.punto(f, N - 1 - c, v)

    def trazo(self, puntos, grosor, v):
        """Una línea gruesa por varios puntos (colas, cuernos)."""
        for (f0, c0), (f1, c1) in zip(puntos, puntos[1:]):
            pasos = int(max(abs(f1 - f0), abs(c1 - c0)) * 2) + 1
            for i in range(pasos + 1):
                t = i / pasos
                self.ovalo(f0 + (f1 - f0) * t, c0 + (c1 - c0) * t, grosor, grosor, v)

    def acabar(self):
        """Contorno: los huecos que tocan algo dibujado (salvo los detalles en mayúscula y lo
        que ya es contorno). Devuelve la cuadrícula."""
        g = self.g
        borde = []
        for f in range(N):
            for c in range(N):
                if g[f][c] != ".":
                    continue
                for df, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ff, cc = f + df, c + dc
                    if 0 <= ff < N and 0 <= cc < N and g[ff][cc].islower():
                        borde.append((f, c))
                        break
        for f, c in borde:
            g[f][c] = "o"
        return g


def _base(r, cuerpo="b", barriga="c"):
    """Cabeza grande y cuerpo pequeño, con patitas."""
    r.ovalo(25.5, 16, 6, 8.5, cuerpo)           # cuerpo
    r.ovalo(29.5, 11, 2.4, 3, cuerpo)            # patas
    r.ovalo(29.5, 21, 2.4, 3, cuerpo)
    if barriga:
        r.ovalo(26.5, 16, 4, 5, barriga)
    r.ovalo(14, 16, 9, 12.8, cuerpo)            # cabeza


def _gato():
    r = _Rejilla()
    r.trazo([(27, 23), (25, 27), (21, 29), (17, 28)], 1.4, "b")       # cola enroscada
    for f, c in ((24, 26), (20, 29)):
        r.punto(f, c, "M")
    r.triangulo((9, 4), (0.5, 5), (8, 13), "b", espejo=True)          # orejas
    _base(r)
    r.triangulo((8, 6.5), (3, 6.8), (8, 11), "P", espejo=True)        # el rosa de dentro
    for c in (13, 16, 18):                                             # rayas de atigrado
        r.rect(5, c, 7 if c != 16 else 8, c, "M")
    r.rect(5, 15, 7, 15, "M")
    r.rect(11, 3, 11, 5, "M", espejo=True)
    r.rect(13, 3, 13, 4, "M", espejo=True)
    r.rect(27, 9, 29, 9, "M", espejo=True)
    r.ovalo(19.2, 16, 1.2, 1.6, "P")                                   # nariz
    r.rect(18, 0, 18, 3, "W", espejo=True)                             # bigotes
    r.rect(20, 0, 20, 3, "W", espejo=True)
    r.ovalo(30, 11, 1, 2, "W", espejo=True)                            # patitas blancas
    return r.acabar()


def _perro():
    r = _Rejilla()
    r.trazo([(26, 23), (23, 27), (20, 28)], 1.3, "b")                # cola
    _base(r)
    r.ovalo(18, 4, 7, 3.2, "m", espejo=True)                           # orejas caídas
    r.ovalo(19.5, 16, 3.8, 5.5, "C")                                   # hocico
    r.ovalo(17.8, 16, 1.3, 2.2, "K")                                   # nariz
    r.punto(17, 15, "W")
    r.ovalo(13, 22, 3.5, 3.5, "M")                                     # mancha en un ojo
    r.ovalo(7, 16, 1.5, 3, "M")
    return r.acabar()


def _carlino():
    r = _Rejilla()
    r.trazo([(25, 23), (22, 26), (22, 23)], 1.5, "b")                # cola enroscada
    _base(r)
    r.triangulo((6, 3.5), (5, 9.5), (11, 4.5), "k", espejo=True)      # orejitas dobladas
    for c0, c1 in ((12, 14), (17, 19)):                                # arrugas
        r.rect(7, c0, 7, c1, "O")
    r.rect(9, 14, 9, 17, "O")
    r.ovalo(15.5, 10, 3.6, 3.4, "K", espejo=True)                     # antifaz
    r.ovalo(20.5, 16, 4, 6.5, "K")                                     # hocico negro
    r.ovalo(18.6, 16, 1, 2, "E")                                       # nariz
    return r.acabar()


def _cocker():
    r = _Rejilla()
    _base(r)
    for lado in (4.6,):                                                # orejas largas y onduladas
        r.ovalo(19, lado, 10, 4.4, "m", espejo=True)
    for f in range(11, 29, 3):                                         # las ondas
        r.rect(f, 2, f, 6, "M", espejo=True)
        r.punto(f + 1, 3, "M")
        r.punto(f + 1, 28, "M")
    r.ovalo(6.5, 16, 3, 5, "M")                                        # flequillo
    r.rect(5, 14, 7, 14, "B")
    r.rect(5, 17, 7, 17, "B")
    r.ovalo(19.5, 16, 3.6, 5, "C")                                     # hocico
    r.ovalo(17.8, 16, 1.3, 2.2, "K")
    r.punto(17, 15, "W")
    return r.acabar()


def _conejo():
    r = _Rejilla()
    r.ovalo(26, 26, 2.5, 2.5, "w")                                     # colita de algodón
    r.ovalo(5, 11, 7, 3, "b", espejo=True)                            # orejas largas
    _base(r)
    r.ovalo(5.5, 11, 5.2, 1.4, "P", espejo=True)
    r.ovalo(19, 16, 1, 1.5, "P")                                       # nariz
    r.rect(22, 15, 23, 16, "W")                                        # dientecitos
    r.punto(22, 15, "W")
    return r.acabar()


def _zorro():
    r = _Rejilla()
    r.trazo([(27, 22), (24, 27), (19, 29), (15, 28)], 2.4, "b")       # cola grande
    r.ovalo(15.5, 28, 2.5, 2.2, "w")                                   # con la punta blanca
    r.triangulo((10, 3), (0, 3), (8, 12), "b", espejo=True)           # orejas
    r.triangulo((3, 3), (0, 3), (3, 5.5), "k", espejo=True)            # puntas negras
    r.triangulo((8, 5), (3, 5), (8, 10), "W", espejo=True)            # blanco de dentro
    _base(r, barriga="w")
    r.ovalo(19, 9, 3.5, 6, "W", espejo=True)                          # mejillas blancas
    r.ovalo(21, 16, 2.5, 4, "W")
    r.ovalo(18.8, 16, 1, 1.6, "K")                                     # nariz
    r.ovalo(30, 11, 1.6, 3, "k", espejo=True)                          # calcetines negros
    return r.acabar()


def _panda():
    r = _Rejilla()
    r.ovalo(5, 6.5, 3.5, 3.5, "k", espejo=True)                       # orejas
    _base(r, barriga="")
    r.ovalo(23.5, 9, 3.5, 3, "k", espejo=True)                        # brazos
    r.ovalo(29.5, 11, 2.4, 3, "k", espejo=True)                       # patas
    r.ovalo(15.5, 10.3, 3.8, 3, "K", espejo=True)                     # antifaz
    r.ovalo(19, 16, 1.2, 2, "K")                                       # nariz
    return r.acabar()


def _pinguino():
    r = _Rejilla()
    r.ovalo(24, 6.5, 4, 2, "b", espejo=True)                          # aletas
    _base(r, barriga="")
    r.ovalo(16, 10.5, 5, 5, "W", espejo=True)                         # cara blanca (un corazón)
    r.ovalo(19, 16, 4, 6, "W")
    r.ovalo(26, 16, 5, 6, "W")                                         # barriga
    r.triangulo((18, 14), (18, 18), (20.5, 16), "Y")                  # pico
    r.ovalo(30.5, 11, 1.2, 3, "y", espejo=True)                        # patas
    return r.acabar()


def _rana():
    r = _Rejilla()
    r.ovalo(7.5, 9.5, 4.5, 4.5, "b", espejo=True)                     # los bultos de los ojos
    _base(r)
    r.ovalo(15, 16, 9.5, 13.5, "b")                                    # cabeza más ancha
    for f, c in ((7, 15), (10, 18), (9, 13), (25, 12), (24, 20)):     # manchitas
        r.ovalo(f, c, 1, 1, "M")
    r.rect(20, 10, 20, 21, "O")                                        # sonrisa de rana
    r.punto(19, 9, "O")
    r.punto(19, 22, "O")
    r.ovalo(29.5, 11, 1.8, 3.5, "b", espejo=True)                     # patas palmeadas
    return r.acabar()


def _dragon():
    r = _Rejilla()
    r.triangulo((19, 7), (14, 0), (27, 3), "m", espejo=True)          # alas
    r.triangulo((18, 3), (16, 0), (22, 2), "M", espejo=True)
    r.trazo([(28, 23), (27, 27), (24, 29)], 1.4, "b")                # cola
    r.triangulo((22, 29), (25, 31), (26, 28), "m")                    # con su punta
    r.trazo([(7, 8), (3, 6), (1, 7)], 1.1, "c")                       # cuernos
    r.trazo([(7, 23), (3, 25), (1, 24)], 1.1, "c")
    _base(r)
    for c in (13, 16, 19):                                             # cresta
        r.triangulo((6, c - 1.5), (2.5, c), (6, c + 1.5), "m")
    for f in (24, 26, 28):                                             # escamas de la barriga
        r.rect(f, 12, f, 19, "M")
    r.punto(18, 13, "K")                                               # orificios de la nariz
    r.punto(18, 18, "K")
    return r.acabar()


def _fantasma():
    r = _Rejilla()
    r.ovalo(14, 16, 10, 12.5, "b")
    r.rect(14, 4, 26, 27, "b")
    for c in (6, 12, 19, 25):                                          # el borde ondulado
        r.ovalo(27, c + 0.5, 2.5, 3.2, "b")
    r.ovalo(20, 2.5, 2, 2, "b", espejo=True)                          # manitas
    return r.acabar()


def _robot():
    r = _Rejilla()
    r.rect(2, 15, 5, 16, "g")                                          # antena
    r.ovalo(1.5, 16, 1.5, 1.5, "r")
    r.ovalo(25.5, 16, 6, 9, "b")                                       # cuerpo
    r.rect(27, 8, 31, 12, "b", espejo=True)                           # piernas
    r.rect(22, 4, 26, 6, "g", espejo=True)                            # brazos
    r.rect(5, 4, 22, 27, "b")                                          # cabeza cuadrada
    r.rect(13, 1, 16, 3, "g", espejo=True)                            # tornillos de las orejas
    r.rect(9, 7, 19, 24, "K")                                          # la pantalla de la cara
    r.rect(24, 12, 28, 19, "M")                                        # panel del pecho
    for c, v in ((13, "R"), (16, "Y"), (18, "G")):
        r.punto(26, c, v)
    return r.acabar()


def _slime():
    r = _Rejilla()
    r.ovalo(21, 16, 10.5, 15, "b")
    r.rect(21, 1, 30, 30, "b")
    r.ovalo(31, 8, 1.5, 3, "b")                                        # una gota
    r.ovalo(13, 9, 2.5, 1.6, "W")                                      # brillos
    r.ovalo(11, 12, 1, 1, "W")
    return r.acabar()


_SPRITES = {"gato": _gato, "perro": _perro, "carlino": _carlino, "cocker": _cocker, "conejo": _conejo,
            "dragon": _dragon, "fantasma": _fantasma, "robot": _robot, "slime": _slime, "zorro": _zorro,
            "panda": _panda, "pinguino": _pinguino, "rana": _rana}
_CACHE_SPRITES = {}


def sprite(especie):
    if especie not in _CACHE_SPRITES:
        _CACHE_SPRITES[especie] = (_SPRITES.get(especie) or _gato)()
    return _CACHE_SPRITES[especie]


def _volumen(g, f, c):
    """Más claro junto al borde de arriba y a la izquierda, más oscuro junto al de abajo y a la
    derecha (la luz viene de arriba a la izquierda)."""
    def borde(ff, cc):
        return not (0 <= ff < N and 0 <= cc < N) or g[ff][cc] in ".o"
    if borde(f - 1, c) or borde(f - 2, c) and borde(f, c - 2):
        return 0.18
    if borde(f, c - 1):
        return 0.1
    if borde(f + 1, c) or borde(f, c + 1):
        return -0.16
    if borde(f + 2, c):
        return -0.07
    return 0.0


# ---------------------------------------------------------------------------
# Complementos y objetos, dibujados con formas y colores (como las mascotas, con el contorno
# calculado solo). Los complementos van en la cuadrícula de la mascota (32 x 32): la cabeza
# empieza en la fila 5, los ojos en las filas 12-17 y el cuello en la 21.
# ---------------------------------------------------------------------------

class _Pintura:
    """Una cuadrícula de colores (o None) del tamaño pedido."""

    def __init__(self, n=N):
        self.n = n
        self.g = [[None] * n for _ in range(n)]

    def punto(self, f, c, color):
        f, c = int(f), int(c)
        if 0 <= f < self.n and 0 <= c < self.n:
            self.g[f][c] = color

    def ovalo(self, cy, cx, ry, rx, color, hueco=0.0):
        """Un óvalo (o un anillo, con `hueco` = la fracción vacía por dentro)."""
        for f in range(self.n):
            for c in range(self.n):
                d = ((f + 0.5 - cy) / ry) ** 2 + ((c + 0.5 - cx) / rx) ** 2
                if d <= 1 and d >= hueco ** 2:
                    self.g[f][c] = color

    def rect(self, f0, c0, f1, c1, color):
        for f in range(int(f0), int(f1) + 1):
            for c in range(int(c0), int(c1) + 1):
                self.punto(f, c, color)

    def triangulo(self, a, b, c_, color):
        def lado(p, q, r):
            return (q[1] - p[1]) * (r[0] - p[0]) - (q[0] - p[0]) * (r[1] - p[1])
        for f in range(self.n):
            for c in range(self.n):
                pt = (f + 0.5, c + 0.5)
                d1, d2, d3 = lado(a, b, pt), lado(b, c_, pt), lado(c_, a, pt)
                if not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0)):
                    self.g[f][c] = color

    def trazo(self, puntos, grosor, color):
        for (f0, c0), (f1, c1) in zip(puntos, puntos[1:]):
            pasos = int(max(abs(f1 - f0), abs(c1 - c0)) * 2) + 1
            for i in range(pasos + 1):
                k = i / pasos
                self.ovalo(f0 + (f1 - f0) * k, c0 + (c1 - c0) * k, grosor, grosor, color)

    def pixeles(self, contorno=True):
        """[(fila, columna, color)], con un contorno oscuro alrededor de lo pintado."""
        g, n = self.g, self.n
        salida = [(f, c, g[f][c]) for f in range(n) for c in range(n) if g[f][c] is not None]
        if contorno:
            for f in range(n):
                for c in range(n):
                    if g[f][c] is not None:
                        continue
                    vecinos = [g[ff][cc] for ff, cc in ((f + 1, c), (f - 1, c), (f, c + 1), (f, c - 1))
                               if 0 <= ff < n and 0 <= cc < n and g[ff][cc] is not None and len(g[ff][cc]) == 3]
                    if vecinos:
                        salida.append((f, c, mezcla(vecinos[0], (0.05, 0.03, 0.08), 0.6)))
        return salida


def _brillo(color, k=0.35):
    return mezcla(color, (1, 1, 1), k)


def _sombra(color, k=0.3):
    return mezcla(color, (0, 0, 0), k)


_ORO = (1.0, 0.8, 0.22)


def _hacer_complemento(clave, t=0.0):
    p = _Pintura()
    if clave == "lazo":
        rosa = (1.0, 0.45, 0.65)
        p.triangulo((4, 18), (10, 18), (7, 23), rosa)
        p.triangulo((4, 28), (10, 28), (7, 23), rosa)
        p.rect(5, 19, 5, 20, _brillo(rosa))
        p.rect(5, 26, 5, 27, _brillo(rosa))
        p.ovalo(7.5, 23.5, 1.6, 1.6, _sombra(rosa, 0.2))
    elif clave == "flor":
        for cy, cx in ((5, 7), (5, 11), (9, 7), (9, 11), (7, 5), (7, 13)):
            p.ovalo(cy, cx, 2.1, 2.1, (1, 1, 1))
        p.ovalo(7, 9, 2, 2, (1.0, 0.8, 0.2))
        p.punto(6, 8, (1, 0.95, 0.6))
        p.triangulo((10, 11), (13, 15), (11, 9), (0.35, 0.7, 0.3))
    elif clave in ("gorra", "gorra_atras"):
        color = (0.25, 0.5, 0.95) if clave == "gorra" else (0.9, 0.25, 0.3)
        p.ovalo(7.5, 16, 5.5, 9.5, color)
        p.rect(7, 6, 8, 25, color)
        if clave == "gorra":
            p.rect(7, 22, 8, 29, _sombra(color))                         # visera hacia delante
            p.ovalo(5.5, 16, 1.6, 1.6, (1, 1, 1))                         # el logo
        else:
            p.rect(7, 2, 8, 9, _sombra(color))                            # visera hacia atrás
            p.rect(3, 15, 3, 16, _brillo(color, 0.5))
        p.rect(3, 11, 3, 13, _brillo(color))
        p.punto(2, 16, _sombra(color))                                     # el botón de arriba
    elif clave == "pajarita":
        morado = (0.55, 0.3, 0.85)
        p.triangulo((20, 10), (25, 10), (22.5, 15.5), morado)
        p.triangulo((20, 21), (25, 21), (22.5, 15.5), morado)
        p.ovalo(22.5, 15.5, 1.8, 1.8, _sombra(morado, 0.25))
        for f, c in ((21, 11), (23, 12), (21, 19), (23, 20)):
            p.punto(f, c, _brillo(morado, 0.5))
    elif clave == "parche":
        negro = (0.1, 0.1, 0.12)
        p.trazo([(7, 5), (10, 13), (11, 19)], 0.6, negro)                  # la cinta
        p.ovalo(15, 21.5, 3.6, 3.4, negro)
        p.punto(13, 20, (0.4, 0.4, 0.45))
    elif clave == "gafas":
        negro = (0.08, 0.08, 0.1)
        for cx in (10, 21.5):
            p.ovalo(15, cx, 3.2, 4.2, negro)
            p.trazo([(14, cx - 2), (13, cx - 1)], 0.4, (0.5, 0.55, 0.65))  # el reflejo
        p.rect(14, 14, 14, 17, negro)
        p.rect(13, 3, 13, 5, negro)
        p.rect(13, 26, 13, 28, negro)
    elif clave == "gorro":
        azul, rojo, amarillo = (0.3, 0.55, 1.0), (0.95, 0.3, 0.35), (1.0, 0.8, 0.25)
        p.triangulo((0, 16), (8, 9), (8, 23), azul)
        for f, color in ((2, rojo), (5, amarillo)):
            for c in range(9, 24):
                if p.g[f][c] is not None:
                    p.punto(f, c, color)
                    p.punto(f + 1, c, color)
        p.ovalo(0.5, 16, 1.8, 1.8, amarillo)
    elif clave == "santa":
        rojo, blanco = (0.85, 0.15, 0.2), (1, 1, 1)
        p.triangulo((1, 20), (8, 7), (8, 25), rojo)
        p.trazo([(1, 20), (3, 25), (6, 27)], 1.2, rojo)                    # la punta, caída
        p.rect(7, 5, 9, 26, blanco)
        p.ovalo(7, 28, 2.4, 2.4, blanco)                                  # la borla
        for c in range(6, 26, 3):
            p.punto(8, c, (0.85, 0.87, 0.9))
    elif clave == "cuernos":
        rojo = (0.8, 0.12, 0.18)
        p.trazo([(7, 8), (4, 7), (1, 8)], 1.1, rojo)
        p.trazo([(7, 23), (4, 24), (1, 23)], 1.1, rojo)
        p.punto(0, 8, (1, 0.4, 0.4))
        p.punto(0, 23, (1, 0.4, 0.4))
    elif clave == "bigote":
        pelo, oro = (0.32, 0.2, 0.1), _ORO
        p.trazo([(19, 15), (20, 12), (19, 10), (18, 9)], 0.9, pelo)
        p.trazo([(19, 16), (20, 19), (19, 21), (18, 22)], 0.9, pelo)
        p.ovalo(14.8, 21.5, 4, 4, oro, hueco=0.72)                         # el monóculo
        p.trazo([(18, 24), (22, 25), (26, 24)], 0.3, oro)                  # y su cadenita
    elif clave == "chef":
        blanco, sombra = (1, 1, 1), (0.84, 0.86, 0.9)
        for cy, cx in ((3, 11), (2, 16), (3, 21), (5, 13), (5, 19)):
            p.ovalo(cy, cx, 3.2, 3.6, blanco)
        p.rect(5, 10, 8, 22, blanco)
        p.rect(8, 10, 9, 22, sombra)
        for c in (13, 16, 19):
            p.rect(4, c, 7, c, sombra)
    elif clave == "bufanda":
        rojo, raya = (0.88, 0.2, 0.25), (1, 1, 1)
        p.ovalo(21.5, 16, 2.6, 10, rojo)
        p.rect(22, 18, 29, 21, rojo)                                       # la punta que cuelga
        for f in (24, 27):
            p.rect(f, 18, f, 21, raya)
        for c in (9, 13, 17, 21):
            p.rect(21, c, 22, c, raya)
        p.rect(30, 18, 30, 18, rojo)
        p.rect(30, 20, 30, 20, rojo)
    elif clave == "calabaza":
        naranja, oscuro, verde, cara = (1.0, 0.55, 0.1), (0.85, 0.38, 0.05), (0.3, 0.6, 0.2), (0.3, 0.12, 0.02)
        p.ovalo(5, 16, 4.6, 8, naranja)
        for c in (12, 16, 20):
            p.rect(2, c, 8, c, oscuro)
        p.rect(0, 16, 1, 17, verde)
        p.punto(0, 18, verde)
        p.triangulo((3, 12), (3, 14), (5, 13), cara)                      # la cara tallada
        p.triangulo((3, 18), (3, 20), (5, 19), cara)
        p.rect(6, 13, 6, 19, cara)
    elif clave == "mago":
        morado, estrella = (0.4, 0.25, 0.75), (1.0, 0.85, 0.3)
        p.triangulo((-1, 19), (7, 10), (7, 22), morado)
        p.ovalo(7.5, 16, 1.6, 11, _sombra(morado, 0.25))                   # el ala
        for f, c in ((2, 17), (5, 14), (4, 19)):
            p.punto(f, c, estrella)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            p.punto(2 + dy, 17 + dx, (1, 1, 0.7))
    elif clave in ("auriculares", "auriculares_rgb"):
        negro = (0.12, 0.12, 0.14)

        def color(k):
            if clave == "auriculares":
                return (0.3, 0.9, 0.5) if k == 0 else negro
            return colorsys.hsv_to_rgb((t * 0.25 + k) % 1, 0.75, 1.0)
        p.ovalo(13, 16, 10, 13.5, negro, hueco=0.88)                        # la diadema
        for f in range(13, 32):
            for c in range(32):
                p.g[f][c] = None if p.g[f][c] is negro else p.g[f][c]
        for cx in (3, 28):
            p.ovalo(15.5, cx, 4, 2.6, negro)
            p.ovalo(15.5, cx, 2.6, 1.4, color(cx / 32))
        if clave == "auriculares_rgb":
            for c in range(6, 26, 2):
                if p.g[4][c] is not None or p.g[5][c] is not None:
                    p.punto(4 if p.g[4][c] is not None else 5, c, color(c / 32))
    elif clave == "corona":
        p.rect(5, 9, 8, 22, _ORO)
        for c in (9, 15.5, 22):
            p.triangulo((5, c - 2.5), (0, c), (5, c + 2.5), _ORO)
        for c, gema in ((12, (0.9, 0.2, 0.3)), (16, (0.3, 0.5, 1.0)), (20, (0.3, 0.8, 0.4))):
            p.ovalo(6.5, c, 1.1, 1.1, gema)
        p.rect(5, 10, 5, 21, _brillo(_ORO, 0.5))
    elif clave == "capa":  # detrás: asoma por los lados y abajo, ondeando
        rojo = (0.85, 0.15, 0.25)
        for f in range(18, 32):
            vuelo = 1 if math.sin(t * 4 + f * 0.6) > 0.1 else 0
            ancho = 4 + (f - 18) // 4 + vuelo
            for c in range(7 - ancho, 9):
                p.punto(f, c, rojo if c > 7 - ancho + 1 else _sombra(rojo))
                p.punto(f, 31 - c, rojo if c > 7 - ancho + 1 else _sombra(rojo))
        p.rect(31, 6, 31, 25, _sombra(rojo))
    elif clave == "halo":
        p.ovalo(2.5, 16, 2.2, 7.5, _ORO, hueco=0.6)
    elif clave == "astronauta":
        salida = []
        for f in range(0, 27):
            for c in range(0, 32):
                d = math.hypot(c + 0.5 - 16, (f + 0.5 - 13.5) * 1.05)
                if 13.4 <= d < 15.2:
                    salida.append((f, c, (0.86, 0.88, 0.92) if d < 14.4 else (0.6, 0.63, 0.7)))
                elif d < 13.4:
                    salida.append((f, c, (0.6, 0.8, 1.0, 0.13)))
        for f, c in ((5, 8), (4, 9), (3, 10), (6, 7), (4, 10)):
            salida.append((f, c, (1, 1, 1, 0.75)))
        return salida
    elif clave == "chupete":
        p.ovalo(21.5, 15.5, 2.2, 4.5, (0.4, 0.7, 1.0))
        p.ovalo(21.5, 15.5, 1.2, 1.4, (1.0, 0.7, 0.8))
        p.ovalo(24.5, 15.5, 1.5, 1.8, _ORO, hueco=0.3)
    elif clave == "mando":
        gris, oscuro = (0.3, 0.3, 0.36), (0.18, 0.18, 0.22)
        p.ovalo(26, 11, 2.8, 3.2, gris)
        p.ovalo(26, 20, 2.8, 3.2, gris)
        p.rect(24, 11, 27, 20, gris)
        p.rect(25, 9, 27, 9, oscuro)                                       # la cruceta
        p.rect(26, 8, 26, 10, oscuro)
        for f, c, color in ((25, 20, (0.9, 0.3, 0.3)), (26, 21, (0.3, 0.8, 0.4)), (27, 20, (0.3, 0.6, 1.0)),
                            (26, 19, (1.0, 0.85, 0.3))):
            p.punto(f, c, color)
    return p.pixeles()


_CACHE_COMPLEMENTOS = {}
_ANIMADOS = {"capa", "auriculares_rgb"}


def _pixeles_complemento(clave, t=0.0):
    if clave in _ANIMADOS:
        return _hacer_complemento(clave, t)
    if clave not in _CACHE_COMPLEMENTOS:
        _CACHE_COMPLEMENTOS[clave] = _hacer_complemento(clave)
    return _CACHE_COMPLEMENTOS[clave]


# Detrás del cuerpo (lo demás va encima) y lo último de todo (el casco, que es de cristal)
_DETRAS, _ENCIMA = ("capa",), ("astronauta",)
# Lo que va en la cabeza: en el slime, que la tiene más baja, una fila más abajo
_CABEZA = {"santa", "cuernos", "calabaza", "gorra", "gorra_atras", "gorro", "chef", "corona", "mago", "halo",
           "auriculares", "auriculares_rgb", "lazo", "flor"}


def _tabla(cuerpo, manchas, especie):
    tabla = {"o": mezcla(cuerpo, (0, 0, 0), 0.55), "b": cuerpo, "m": manchas,
             "c": mezcla(cuerpo, (1, 1, 1), 0.55), "e": (0.32, 0.27, 0.27), **_FIJOS}
    if especie == "fantasma":
        tabla["o"] = mezcla(cuerpo, (0.2, 0.25, 0.4), 0.45)
    return tabla


# Caras a 32 x 32: (fila, columna) del ojo izquierdo; el derecho es su reflejo
# El ojo izquierdo (columnas 8-12, filas 12-17); el derecho es el mismo, 11 columnas más allá
# (sin reflejar: los brillos van del mismo lado en los dos, la luz viene de arriba a la izquierda).
#   l contorno  i iris (el color elegido)  k pupila  W brillo grande  w brillo pequeño
_OJO = [".lll.", "lWWil", "lWkkl", "likkl", "liiwl", ".lll."]
_OJO_CERRADO = [(15, 8), (16, 9), (16, 10), (16, 11), (15, 12)]
_OJO_FELIZ = [(16, 8), (15, 9), (14, 10), (15, 11), (16, 12)]
_LINEA_OJOS = (0.12, 0.09, 0.1)
_BOCAS = {
    "normal": [(21, 14), (22, 15), (22, 16), (21, 17)],
    "feliz": [(20, 13), (21, 14), (22, 15), (22, 16), (21, 17), (20, 18)],
    "triste": [(22, 13), (21, 14), (20, 15), (20, 16), (21, 17), (22, 18)],
    "comiendo": [(20, 15), (20, 16), (21, 14), (21, 17), (22, 15), (22, 16)],
}
_SIN_COLORETES = {"panda", "carlino", "robot", "pinguino"}


def dibujar_mascota(l, x, y, px, especie, colores, expresion="normal", complementos=(), sucia=False,
                    t=0.0, pelaje=None):
    """La mascota en (x, y); `px` es el tamaño de un cuadro de 16 x 16 (la mascota mide 16 * px)
    y se dibuja con el doble de detalle, a 32 x 32. expresion: normal, parpadeo, feliz, triste,
    dormido, comiendo. pelaje: None (sus colores), "dorado" (con un brillo que la recorre) o
    "arcoiris" (franjas de colores que bajan)."""
    cuerpo, manchas, ojos = (hex_rgb(c) for c in colores)
    if pelaje == "dorado":
        cuerpo, manchas = (1.0, 0.8, 0.25), (0.85, 0.55, 0.1)
    tabla = _tabla(cuerpo, manchas, especie)
    g = sprite(especie)
    p = px / 2

    def punto(f, c, color, tam=1):
        # Lo semitransparente, sin solapar (si no, se ve una rejilla más oscura)
        a = p * tam if len(color) == 4 else p * tam + 0.6
        l.rect(x + c * p, y + f * p, a, a, 0, color)

    def color_pelaje(f, c, v):
        base = v.lower()
        if pelaje == "arcoiris" and base in "bmc":
            arco = colorsys.hsv_to_rgb((f / 28 - t * 0.2) % 1, 0.5, 1.0)
            color = _tabla(arco, mezcla(arco, (0, 0, 0), 0.3), especie)[base]
        elif pelaje == "dorado" and base in "bc" and (c + f - t * 20) % 28 < 3:
            return mezcla(tabla[base], (1, 1, 1), 0.6)  # el brillo que la recorre
        else:
            color = tabla[base]
        if v in "bmc":  # el volumen, solo en lo grande (no en los detalles, en mayúscula)
            luz = _volumen(g, f, c)
            if luz:
                return mezcla(color, (1, 1, 1) if luz > 0 else (0, 0, 0), abs(luz))
        return color

    def complemento(clave):
        baja = 5 if especie == "slime" and clave in _CABEZA else 0  # el slime tiene la cabeza más baja
        for f, c, color in _pixeles_complemento(clave, t):
            punto(f + baja, c, color)

    for clave in complementos:
        if clave in _DETRAS:
            complemento(clave)
    for f, fila in enumerate(g):
        for c, v in enumerate(fila):
            if v != ".":
                punto(f, c, color_pelaje(f, c, v))
    if sucia:
        for f, c in ((11, 7), (21, 24), (25, 12), (8, 19)):
            punto(f, c, mezcla(cuerpo, (0.35, 0.25, 0.15), 0.6), 2)
    # Coloretes
    if especie not in _SIN_COLORETES:
        for f, c in ((18, 5), (18, 6), (18, 7), (19, 6), (19, 7)):
            punto(f, c, (1.0, 0.5, 0.6, 0.55))
            punto(f, 31 - c, (1.0, 0.5, 0.6, 0.55))
    # Ojos
    if "gafas" not in complementos:
        linea = ojos if especie == "robot" else _LINEA_OJOS
        if expresion in ("dormido", "parpadeo", "feliz"):
            for f, c in (_OJO_FELIZ if expresion == "feliz" else _OJO_CERRADO):
                punto(f, c, linea)
                punto(f, c + 11, linea)
        else:
            colores_ojo = {"l": linea, "i": ojos, "k": mezcla(ojos, (0, 0, 0), 0.65), "W": (1, 1, 1),
                           "w": mezcla(ojos, (1, 1, 1), 0.7)}
            for f, fila in enumerate(_OJO):
                for c, v in enumerate(fila):
                    if v != ".":
                        punto(12 + f, 8 + c, colores_ojo[v])
                        punto(12 + f, 19 + c, colores_ojo[v])
            if expresion == "triste":
                for f in (18, 19, 20):
                    punto(f, 9, (0.45, 0.7, 1.0))
    # Boca
    if especie != "pinguino":  # el pingüino tiene el pico
        boca = tabla["o"] if especie != "robot" else ojos
        forma = _BOCAS.get(expresion, _BOCAS["normal"]) if expresion != "dormido" else _BOCAS["normal"]
        for f, c in forma:
            punto(f, c, boca)
        if expresion in ("feliz", "comiendo"):
            punto(21 if expresion == "comiendo" else 21, 15, (0.95, 0.4, 0.5))
            punto(21, 16, (0.95, 0.4, 0.5))
        if especie == "carlino":  # saca la lengua
            for f, c in ((23, 15), (23, 16), (24, 15), (24, 16)):
                punto(f, c, (0.95, 0.45, 0.52))
    for clave in sorted(complementos, key=lambda k: k in _ENCIMA):
        if clave not in _DETRAS:
            complemento(clave)


# Objetos de la tienda en pixel art (también sus miniaturas en la tienda)
def _hacer_objeto(clave):
    """Comida y objetos de la tienda, a 16 x 16."""
    p = _Pintura(16)
    if clave == "galleta":
        masa, choco = (0.85, 0.62, 0.35), (0.3, 0.17, 0.08)
        p.ovalo(8, 8, 6.5, 6.5, masa)
        p.ovalo(6.5, 6.5, 3, 3, _brillo(masa, 0.15))
        for f, c in ((5, 6), (6, 10), (9, 5), (10, 9), (8, 12), (12, 7), (4, 9)):
            p.rect(f, c, f + 1, c, choco)
    elif clave == "helado":
        cucurucho, rosa, menta = (0.85, 0.6, 0.3), (1.0, 0.62, 0.75), (0.6, 0.92, 0.75)
        p.triangulo((8, 4), (8, 12), (15.5, 8), cucurucho)
        for f in range(9, 15, 2):
            for c in range(4, 13, 2):
                if p.g[f][c] is not None:
                    p.punto(f, c, _sombra(cucurucho, 0.2))
        p.ovalo(6.5, 6, 3, 3, menta)
        p.ovalo(5.5, 10, 3.2, 3.2, rosa)
        p.ovalo(2.5, 8, 2.4, 2.4, rosa)
        p.punto(1, 8, (0.85, 0.15, 0.25))                                   # la guinda
        p.punto(4, 9, _brillo(rosa, 0.5))
    elif clave == "sandia":
        rojo, verde = (0.95, 0.3, 0.35), (0.25, 0.65, 0.3)
        p.ovalo(4, 8, 10, 8, verde)
        p.ovalo(4, 8, 9, 7, (0.95, 0.95, 0.85))
        p.ovalo(4, 8, 8, 6.2, rojo)
        p.rect(0, 0, 3, 15, None)
        for f, c in ((5, 5), (7, 8), (5, 11), (9, 6), (9, 10)):
            p.punto(f, c, (0.15, 0.1, 0.1))
    elif clave == "cafe":
        taza, cafe = (1, 1, 1), (0.45, 0.28, 0.15)
        p.rect(6, 3, 14, 11, taza)
        p.ovalo(10, 12.5, 2.8, 2.4, taza, hueco=0.45)                       # el asa
        p.rect(6, 4, 7, 10, cafe)
        p.rect(15, 2, 15, 12, (0.85, 0.85, 0.9))                            # el platito
        for f, c in ((1, 5), (2, 6), (3, 5), (1, 8), (2, 9), (3, 8)):       # el vapor
            p.punto(f, c, (0.9, 0.9, 0.95, 0.7))
    elif clave == "pastel":
        bizcocho, crema, fresa = (0.95, 0.8, 0.55), (1.0, 0.75, 0.82), (0.9, 0.15, 0.25)
        p.rect(7, 2, 14, 13, bizcocho)
        p.rect(10, 2, 11, 13, crema)
        p.rect(5, 2, 7, 13, crema)
        for c in range(3, 13, 3):
            p.punto(8, c, crema)
        p.ovalo(3.5, 8, 2, 2, fresa)
        p.punto(2, 9, (0.3, 0.7, 0.3))
    elif clave == "pizza":
        masa, queso, tomate = (0.85, 0.55, 0.25), (1.0, 0.82, 0.3), (0.85, 0.2, 0.2)
        p.triangulo((2, 1), (2, 15), (15, 8), queso)
        p.rect(1, 1, 3, 14, masa)
        for f, c in ((5, 6), (6, 10), (9, 8), (12, 8)):
            p.ovalo(f, c, 1.2, 1.2, tomate)
        p.punto(7, 5, (0.3, 0.6, 0.25))
        p.punto(10, 10, (0.3, 0.6, 0.25))
    elif clave == "energetica":
        lata, rayo = (0.25, 0.45, 0.95), (1.0, 0.85, 0.25)
        p.rect(2, 4, 14, 11, lata)
        p.rect(1, 5, 1, 10, (0.75, 0.78, 0.85))
        p.rect(15, 5, 15, 10, (0.75, 0.78, 0.85))
        p.triangulo((4, 9), (8, 6), (8, 9), rayo)
        p.triangulo((8, 7), (8, 10), (12, 6), rayo)
        p.rect(3, 5, 13, 5, _brillo(lata, 0.35))
    elif clave == "hamburguesa":
        pan, carne, lechuga, queso, tomate = (0.9, 0.6, 0.25), (0.4, 0.22, 0.12), (0.35, 0.75, 0.3), (1.0, 0.8, 0.2), \
            (0.9, 0.25, 0.25)
        p.ovalo(5, 8, 3.8, 7, pan)
        p.rect(7, 1, 8, 14, lechuga)
        p.rect(9, 1, 9, 14, tomate)
        p.rect(10, 1, 11, 14, carne)
        p.rect(9, 3, 10, 12, queso)
        p.rect(12, 2, 13, 13, pan)
        for c in (5, 8, 11):
            p.punto(3, c, (1, 0.95, 0.85))                                 # sésamo
    elif clave == "ramen":
        bol, caldo, fideos = (0.9, 0.25, 0.25), (0.95, 0.8, 0.5), (1.0, 0.9, 0.55)
        p.ovalo(9, 8, 6, 7.5, bol)
        p.rect(0, 0, 8, 15, None)
        p.ovalo(8, 8, 2, 7.5, caldo)
        p.trazo([(8, 3), (6, 4), (8, 6), (6, 8)], 0.5, fideos)
        p.ovalo(7.5, 11, 1.5, 1.8, (1, 1, 1))                               # el huevo
        p.punto(7, 11, (1.0, 0.7, 0.2))
        p.trazo([(1, 12), (8, 9)], 0.4, (0.7, 0.5, 0.3))                    # los palillos
        p.trazo([(1, 14), (8, 10)], 0.4, (0.7, 0.5, 0.3))
    elif clave == "sushi":
        arroz, salmon = (1, 1, 1), (1.0, 0.55, 0.4)
        p.ovalo(10, 8, 3.2, 6.5, arroz)
        p.ovalo(7, 8, 2.6, 7, salmon)
        for c in (4, 7, 10, 13):
            p.punto(7, c, (1.0, 0.85, 0.8))
        p.rect(7, 7, 12, 8, (0.15, 0.2, 0.15))                              # la tira de alga
    elif clave == "pelota":
        rojo, amarillo = (0.9, 0.25, 0.3), (1.0, 0.85, 0.3)
        p.ovalo(8, 8, 6.5, 6.5, rojo)
        p.trazo([(2, 6), (8, 8), (14, 10)], 1.1, amarillo)
        p.ovalo(5, 5.5, 1.3, 1.3, (1, 1, 1))
    elif clave == "peluche":
        marron, claro = (0.65, 0.45, 0.28), (0.85, 0.7, 0.55)
        for cx in (4, 12):
            p.ovalo(3, cx, 2.2, 2.2, marron)
            p.ovalo(3, cx, 1, 1, claro)
        p.ovalo(6.5, 8, 4.5, 5.2, marron)
        p.ovalo(12.5, 8, 3.5, 4.5, marron)
        p.ovalo(8, 8, 1.6, 2.2, claro)
        p.ovalo(12.5, 8, 2, 2.4, claro)
        for c in (6, 10):
            p.punto(6, c, (0.1, 0.08, 0.06))
        p.punto(7, 8, (0.1, 0.08, 0.06))
    elif clave == "caja":
        amarillo, rojo = (1.0, 0.82, 0.3), (0.9, 0.25, 0.3)
        p.rect(6, 2, 15, 13, amarillo)
        p.rect(4, 1, 6, 14, _brillo(amarillo, 0.15))
        p.rect(4, 7, 15, 8, rojo)
        p.triangulo((4, 7.5), (0, 3), (1, 7), rojo)
        p.triangulo((4, 8), (0, 12.5), (1, 8.5), rojo)
        p.punto(11, 4, (1, 1, 1))
    elif clave == "camita":
        madera, colcha = (0.55, 0.35, 0.2), (0.35, 0.55, 0.95)
        p.rect(3, 0, 14, 1, madera)
        p.rect(8, 14, 14, 15, madera)
        p.rect(7, 1, 10, 14, (1, 1, 1))
        p.ovalo(7, 3.5, 1.6, 2.2, (1, 1, 1))
        p.rect(8, 5, 11, 14, colcha)
        p.rect(12, 1, 12, 14, madera)
        for c in (7, 10, 13):
            p.punto(9, c, _brillo(colcha, 0.4))
    elif clave == "palomitas":  # el cubo de cuando ve un vídeo (10 x 10 de los 16)
        rojo, blanco, palomita = (0.9, 0.2, 0.25), (1, 1, 1), (1.0, 0.95, 0.8)
        p.triangulo((4, 0.5), (4, 9.5), (10, 5), blanco)
        p.rect(4, 1, 9, 8, blanco)
        for c in (2, 5, 8):
            p.rect(4, c, 9, c, rojo)
        for cy, cx in ((3, 2), (2, 4.5), (3, 7), (1.5, 6), (2, 3)):
            p.ovalo(cy, cx, 1.4, 1.4, palomita)
        p.punto(2, 5, (1.0, 0.85, 0.4))
        p.punto(3, 7, (1.0, 0.85, 0.4))
    return p.pixeles()


_CACHE_OBJETOS = {}


_COLORES_OBJETOS = {"o": (0.15, 0.15, 0.2), "y": (1.0, 0.85, 0.3), "r": (0.9, 0.25, 0.3), "b": (0.65, 0.45, 0.28),
                    "e": (0.1, 0.08, 0.06), "c": (0.85, 0.7, 0.55), "w": (0.95, 0.95, 1.0), "B": (0.35, 0.55, 0.95),
                    "M": (0.55, 0.35, 0.2), "g": (0.35, 0.75, 0.3), "k": (0.15, 0.15, 0.18),
                    "n": (0.85, 0.55, 0.25), "s": (1.0, 0.55, 0.45), "p": (1.0, 0.6, 0.75)}


def dibujar_objeto(l, x, y, px, clave):
    """Un objeto de 8 x 8 (o la camita, que se dibuja en dos partes: la cama detrás de la
    mascota y la manta encima, tapándola)."""
    lado = px + 0.6
    madera, blanco, azul = _COLORES_OBJETOS["M"], _COLORES_OBJETOS["w"], _COLORES_OBJETOS["B"]
    if clave == "camita_detras":  # (x, y) = esquina de abajo a la izquierda de la mascota
        l.rect(x - px * 2, y - px * 10, px * 1.6, px * 11, px * 0.5, madera)       # cabecero
        l.rect(x + px * 16.4, y - px * 6, px * 1.6, px * 7, px * 0.5, madera)      # pies
        l.rect(x - px * 1, y - px * 8.5, px * 4, px * 2.4, px * 0.8, blanco)        # almohada
        l.rect(x - px * 0.5, y - px * 2.2, px * 17, px * 1.4, px * 0.3, blanco)    # colchón
        l.rect(x - px * 2, y - px * 1, px * 20, px * 1.6, px * 0.3, madera)         # base
        return
    if clave == "camita_manta":   # tapándola de la cintura para abajo
        l.rect(x - px * 0.5, y - px * 6, px * 17, px * 4.6, px * 0.9, azul)
        l.rect(x - px * 0.5, y - px * 6, px * 17, px * 0.9, px * 0.4, (0.75, 0.85, 1.0))  # el embozo
        for c in range(1, 16, 3):
            l.rect(x + c * px, y - px * 3.6, lado * 0.8, lado * 0.8, 0, (0.55, 0.72, 1.0))
        return
    if clave not in _CACHE_OBJETOS:
        _CACHE_OBJETOS[clave] = _hacer_objeto(clave)
    q = px / 2  # dibujados a 16 x 16: miden lo mismo que antes (8 x px) con el doble de detalle
    for f, c, color in _CACHE_OBJETOS[clave]:
        a = q if len(color) == 4 else q + 0.5
        l.rect(x + c * q, y + f * q, a, a, 0, color)


def dibujar_huevo(l, x, y, px, t):
    """El huevo de antes de adoptar, que se balancea."""
    forma = ["......oooo......", ".....obbbbo.....", "....obbbbbbo....", "....obmbbbbo....",
             "...obbbbbmbbo...", "...obbbbbbbbo...", "...obmbbbbbbo...", "...obbbbbmbbo...",
             "...obbbbbbbbo...", "....obbbbbbo....", ".....oooooo....."]
    tabla = {"o": (0.55, 0.5, 0.45), "b": (0.97, 0.94, 0.86), "m": (0.55, 0.75, 0.95)}
    dx = math.sin(t * 2.5) * px * 0.6 if int(t) % 4 == 0 else 0
    for f, fila in enumerate(forma):
        for c, v in enumerate(fila):
            if v != ".":
                l.rect(x + dx + c * px, y + (f + 4) * px, px + 0.6, px + 0.6, 0, tabla[v])


# ---------------------------------------------------------------------------
# Fondos: escenas en el mismo pixel art, dibujadas por código. Los de fuera
# cambian con la hora de verdad (día, atardecer, noche).
# ---------------------------------------------------------------------------

# Colores de las notas cuando baila: van cambiando, y solo se usan los que se distinguen del fondo
_COLORES_NOTAS = ((1.0, 0.42, 0.62), (1.0, 0.82, 0.25), (0.35, 0.85, 0.45), (1.0, 0.58, 0.2),
                  (0.68, 0.45, 1.0), (1.0, 0.3, 0.3), (0.3, 0.6, 1.0), (1.0, 1.0, 1.0))


def color_de_fondo(clave, hora, pal, clima=None):
    """El color que más se ve detrás de la mascota (para elegir colores que se lean encima)."""
    if clave in ("jardin", "playa", "otono", "nieve", "noche", "ciudad"):
        return estado_cielo(clima, hora, noche=True if clave in ("noche", "ciudad") else None)["color"]
    fijos = {"habitacion": (0.93, 0.86, 0.74), "noche": (0.07, 0.08, 0.2), "dulces": (1.0, 0.82, 0.9),
             "espacio": (0.05, 0.03, 0.12), "gamer": (0.11, 0.08, 0.18), "ciudad": (0.06, 0.07, 0.18),
             "mar": (0.08, 0.34, 0.6), "concierto": (0.06, 0.04, 0.1)}
    if clave in fijos:
        return fijos[clave]
    # Sin fondo: la tarjeta, oscura si el texto del tema es claro
    return (0.12, 0.13, 0.16) if sum(pal["texto"][:3]) > 1.5 else (0.95, 0.95, 0.96)


def _luz(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def se_distingue(color, fondo):
    """Bastante distinto en tono y en luz como para leerse encima."""
    distancia = sum((a - b) ** 2 for a, b in zip(color[:3], fondo[:3])) ** 0.5
    return distancia > 0.6 or (distancia > 0.4 and abs(_luz(color) - _luz(fondo)) > 0.12)


# ---------------------------------------------------------------------------
# El cielo de los fondos de fuera: con el tiempo de verdad de tu ciudad (el del widget del
# tiempo) si lo hay. Día y noche por la salida y la puesta del sol, nubes, lluvia, nieve,
# tormenta o niebla según el tiempo que hace, y la luna en su fase de hoy.
# ---------------------------------------------------------------------------

def fase_luna(cuando=None):
    """0 = luna nueva, 0.25 cuarto creciente, 0.5 llena, 0.75 cuarto menguante."""
    dias = ((time.time() if cuando is None else cuando) - 947182440) / 86400  # luna nueva: 6-1-2000 18:14 UTC
    return (dias / 29.530588853) % 1


def tipo_clima(codigo):
    """Del código del tiempo (WMO, el que da Open-Meteo) a lo que se dibuja."""
    if codigo is None or codigo in (0, 1):
        return "despejado"
    if codigo == 2:
        return "nubes"
    if codigo == 3:
        return "cubierto"
    if codigo in (45, 48):
        return "niebla"
    if 71 <= codigo <= 77 or codigo in (85, 86):
        return "nieve"
    if codigo >= 95:
        return "tormenta"
    if 51 <= codigo <= 67 or 80 <= codigo <= 82:
        return "lluvia"
    return "nubes"


def _minutos(hhmm, defecto):
    try:
        return int(hhmm[:2]) * 60 + int(hhmm[3:5])
    except (TypeError, ValueError):
        return defecto


def estado_cielo(clima=None, hora=None, noche=None):
    """Cómo está el cielo: {"tipo", "noche", "atardecer", "arriba", "abajo", "color"}.
    clima: {"codigo", "salida", "puesta"} del widget del tiempo, o None (despejado y horas
    normales). hora: para las pruebas; noche: forzarla (los fondos que son siempre de noche)."""
    ahora = time.localtime()
    minuto = ahora.tm_hour * 60 + ahora.tm_min if hora is None else hora * 60
    tipo = tipo_clima(clima.get("codigo")) if clima else "despejado"
    salida = _minutos(clima.get("salida") if clima else None, 7 * 60 + 45)
    puesta = _minutos(clima.get("puesta") if clima else None, 19 * 60 + 15)
    es_noche = not (salida <= minuto < puesta) if noche is None else noche
    atardecer = not es_noche and (abs(minuto - puesta) < 45 or abs(minuto - salida) < 40)
    gris = tipo in ("cubierto", "lluvia", "nieve", "niebla")
    if tipo == "tormenta":
        arriba, abajo = ((0.06, 0.06, 0.1), (0.14, 0.15, 0.2)) if es_noche else ((0.25, 0.27, 0.33), (0.42, 0.44, 0.5))
    elif es_noche:
        arriba, abajo = ((0.07, 0.08, 0.13), (0.15, 0.16, 0.23)) if gris else ((0.03, 0.04, 0.13), (0.1, 0.12, 0.3))
    elif atardecer:
        arriba, abajo = ((0.45, 0.42, 0.55), (0.85, 0.6, 0.5)) if gris else ((0.35, 0.35, 0.7), (1.0, 0.62, 0.4))
    elif gris:
        arriba, abajo = (0.55, 0.6, 0.68), (0.76, 0.79, 0.83)
    else:
        arriba, abajo = (0.33, 0.62, 0.95), (0.7, 0.87, 1.0)
    return {"tipo": tipo, "noche": es_noche, "atardecer": atardecer, "arriba": arriba, "abajo": abajo,
            "color": mezcla(arriba, abajo, 0.5)}


_NUBE = [".....xxxx.......", "...xxxxxxxx.xx..", ".xxxxxxxxxxxxxx.", "xxxxxxxxxxxxxxxx", ".ssssssssssssss."]


def dibujar_cielo(l, x, y, w, alto, est, t, q, azar, luna_grande=False):
    """El cielo en (x, y, w, alto) con píxeles de `q`: degradado, sol o luna, estrellas y nubes."""
    bandas = max(4, int(alto / (q * 2)))
    for i in range(bandas):
        l.rect(x, y + alto * i / bandas, w, alto / bandas + 1, 0, mezcla(est["arriba"], est["abajo"], i / (bandas - 1)))
    tipo, noche = est["tipo"], est["noche"]
    tapado = tipo in ("cubierto", "lluvia", "nieve", "tormenta", "niebla")
    if noche and not tapado:  # estrellas: unas titilan, alguna con destello en cruz
        for i in range(int(w * alto / (q * q * 55))):
            sx, sy = azar.uniform(0, w), azar.uniform(0, alto * 0.85)
            a = 0.45 + 0.55 * math.sin(t * (1.2 + i % 4 * 0.5) + i * 1.7)
            l.rect(x + sx, y + sy, q, q, 0, (1, 1, 0.92, max(0.15, a)))
            if i % 7 == 0 and a > 0.75:
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    l.rect(x + sx + dx * q, y + sy + dy * q, q, q, 0, (1, 1, 0.92, 0.5))
    cx, cy = x + w * 0.8, y + alto * (0.2 if not est["atardecer"] else 0.62)
    if noche and tipo != "tormenta":
        r = 8 if luna_grande else 6
        _luna(l, cx, y + alto * 0.24, r, q, fase_luna(), tapado)
    elif not noche and not tapado:
        _sol(l, cx, cy, 5, q, t, est["atardecer"])
    # Nubes: cuantas y de qué color según el tiempo
    cuantas = {"despejado": 2, "nubes": 4, "cubierto": 7, "lluvia": 6, "nieve": 6, "niebla": 3, "tormenta": 7}[tipo]
    if noche:
        color = (0.3, 0.32, 0.42) if tipo != "tormenta" else (0.15, 0.15, 0.2)
    else:
        color = {"tormenta": (0.38, 0.4, 0.46), "lluvia": (0.66, 0.69, 0.74), "nieve": (0.86, 0.88, 0.92),
                 "cubierto": (0.8, 0.82, 0.86)}.get(tipo, (1.0, 1.0, 1.0))
        if est["atardecer"]:
            color = mezcla(color, (1.0, 0.75, 0.65), 0.45)
    sombra = mezcla(color, (0.3, 0.3, 0.4), 0.25)
    for i in range(cuantas):
        escala = q * (1.0 if i % 3 else 1.3)
        ancho = 16 * escala
        nx = (azar.uniform(0, w) + t * escala * (0.25 + 0.1 * (i % 3))) % (w + ancho * 2) - ancho
        ny = alto * (0.05 + 0.5 * ((i * 0.37) % 1)) * (1 if tapado else 0.7)
        for f, fila in enumerate(_NUBE):
            for c, v in enumerate(fila):
                if v != ".":
                    l.rect(x + nx + c * escala, y + ny + f * escala, escala + 0.5, escala + 0.5, 0,
                           color if v == "x" else sombra)


def _luna(l, cx, cy, r, q, fase, tapada=False):
    """La luna en su fase: la parte iluminada clara, la otra apenas se ve; con cráteres y un halo."""
    if tapada:
        l.circulo(cx, cy, r * q * 1.3, (0.9, 0.9, 1.0, 0.12))  # tras las nubes: un resplandor
        return
    l.circulo(cx + q / 2, cy + q / 2, r * q * 1.45, (0.9, 0.92, 1.0, 0.04 + 0.06 * (1 - abs(fase - 0.5) * 2)))
    l.circulo(cx + q / 2, cy + q / 2, (r + 0.4) * q, (0.35, 0.37, 0.5, 0.5))  # la parte en sombra, apenas se ve
    crateres = {(-2, -1), (-3, -1), (1, 2), (2, 2), (2, -3), (-1, 3), (3, 0)}
    for f in range(-r, r + 1):
        for c in range(-r, r + 1):
            if (c + 0.5) ** 2 + (f + 0.5) ** 2 > (r + 0.3) ** 2:
                continue
            u, v = (c + 0.5) / (r + 0.5), (f + 0.5) / (r + 0.5)
            limite = math.sqrt(max(0.0, 1 - v * v))
            if fase < 0.5:   # creciente: se ilumina por la derecha
                luz = u > limite * math.cos(2 * math.pi * fase)
            else:            # menguante: le queda la izquierda
                luz = u < limite * math.cos(2 * math.pi * (fase - 0.5))
            if luz:
                color = (0.84, 0.82, 0.72) if (c, f) in crateres else (0.98, 0.96, 0.86)
                l.rect(cx + c * q, cy + f * q, q + 0.5, q + 0.5, 0, color)


def _sol(l, cx, cy, r, q, t, atardecer):
    centro = (1.0, 0.62, 0.3) if atardecer else (1.0, 0.86, 0.3)
    l.circulo(cx + q / 2, cy + q / 2, r * q * 1.6, (*centro, 0.1))
    for i in range(8):  # rayos que laten
        a = i * math.pi / 4 + t * 0.15
        largo = r + 2.5 + math.sin(t * 2 + i) * 0.8
        for k in range(int(r + 1.5), int(largo) + 1):
            l.rect(cx + math.cos(a) * k * q - q / 2, cy + math.sin(a) * k * q - q / 2, q, q, 0, (*centro, 0.8))
    for f in range(-r, r + 1):
        for c in range(-r, r + 1):
            if (c + 0.5) ** 2 + (f + 0.5) ** 2 <= (r + 0.3) ** 2:
                brillo = 0.4 if c + f < -r * 0.6 else 0.0
                l.rect(cx + c * q, cy + f * q, q + 0.5, q + 0.5, 0, mezcla(centro, (1, 1, 0.9), brillo))


def dibujar_clima(l, x, y, w, h, est, t, q, azar):
    """Lo que cae del cielo, por encima del paisaje: lluvia, nieve, relámpagos o niebla."""
    tipo = est["tipo"]
    if tipo in ("lluvia", "tormenta"):
        gotas = 45 if tipo == "tormenta" else 30
        for i in range(gotas):
            gx = (azar.uniform(0, w) - t * q * 6) % w
            gy = (azar.uniform(0, h) + t * q * (28 + i % 5 * 4)) % h
            l.linea(x + gx, y + gy, x + gx - q * 0.8, y + gy + q * 3, max(1.0, q * 0.45), (0.75, 0.85, 1.0, 0.6))
    if tipo == "nieve":
        for i in range(34):
            nx = (azar.uniform(0, w) + math.sin(t * 0.8 + i) * q * 3) % w
            ny = (azar.uniform(0, h) + t * q * (3 + i % 3)) % h
            lado = q * (1 if i % 3 else 1.5)
            l.rect(x + nx, y + ny, lado, lado, lado / 2, (1, 1, 1, 0.9))
    if tipo == "tormenta" and (t % 7) < 0.18:  # un relámpago de vez en cuando
        l.rect(x, y, w, h, 0, (1, 1, 1, 0.35))
        bx = x + w * (0.2 + 0.6 * ((int(t / 7) * 0.37) % 1))
        puntos = [(bx, y)]
        for i in range(5):
            puntos.append((puntos[-1][0] + (q * 3 if i % 2 else -q * 3), puntos[-1][1] + h * 0.1))
        for a, b in zip(puntos, puntos[1:]):
            l.linea(a[0], a[1], b[0], b[1], max(1.5, q), (1, 1, 0.85, 0.95))
    if tipo == "niebla":
        for i in range(3):
            fy = h * (0.3 + 0.2 * i) + math.sin(t * 0.3 + i) * q * 2
            l.rect(x, y + fy, w, h * 0.16, h * 0.08, (0.9, 0.92, 0.95, 0.28))


_FLOR = [".a.a.", "aacaa", ".aaa.", "..t..", ".tt..", "..t.."]
_PETALOS = ((1.0, 0.35, 0.45), (1.0, 0.6, 0.8), (1.0, 0.85, 0.25), (0.65, 0.5, 1.0), (1.0, 1.0, 1.0))


def _flor(l, fx, fy, q, petalo, noche):
    tallo = (0.2, 0.5, 0.2) if not noche else (0.12, 0.3, 0.14)
    centro = (1.0, 0.8, 0.2) if petalo != (1.0, 0.85, 0.25) else (0.85, 0.45, 0.1)
    if noche:
        petalo, centro = mezcla(petalo, (0.1, 0.1, 0.3), 0.55), mezcla(centro, (0.1, 0.1, 0.3), 0.55)
    for f, fila in enumerate(_FLOR):
        for c, v in enumerate(fila):
            if v != ".":
                color = {"a": petalo, "c": centro, "t": tallo}[v]
                l.rect(fx + c * q, fy + f * q, q + 0.5, q + 0.5, 0, color)


def dibujar_fondo(l, x, y, w, h, clave, t, hora=None, musica=False, clima=None):
    """Dibuja el fondo `clave` en el rectángulo. Devuelve la y del suelo (donde van los pies
    de la mascota), o None si no hay fondo."""
    if clave not in dict((k, n) for k, n, _p in FONDOS) or clave == "ninguno" or h < 30:
        return None
    recortar = getattr(l, "recortar", None)  # que nubes y estrellas no se salgan del marco
    if recortar:
        recortar(x, y, w, h, 8)
    try:
        return _fondo(l, x, y, w, h, clave, t, hora, musica, clima)
    finally:
        if recortar:
            l.sin_recorte()


def _fondo(l, x, y, w, h, clave, t, hora, musica, clima):
    hora = time.localtime().tm_hour if hora is None else hora
    p = 2 * max(1, round(h / 48))   # el píxel del fondo (par: el fino, la mitad, también entero)
    radio = 8
    azar = random.Random(f"{clave}{int(w)}{int(h)}")

    def bloque(bx, by, bw, bh, color):
        l.rect(x + bx, y + by, bw, bh, 0, color)

    def pixel(cx, cy, color, tam=1):
        """Un píxel del fondo en (cx, cy) contados en píxeles de fondo."""
        l.rect(x + cx * p, y + cy * p, p * tam + 0.6, p * tam + 0.6, 0, color)

    def base(color):
        l.rect(x, y, w, h, radio, color)

    def suelo(desde, color):
        l.rect(x, y + desde, w, h - desde, radio, color)
        bloque(0, desde, w, min(radio, h - desde), color)

    def estrellas(n, hasta, brillo=1.0):
        for i in range(n):
            sx, sy = azar.uniform(0, w / p), azar.uniform(0, hasta / p)
            a = brillo * (0.55 + 0.45 * math.sin(t * (1.5 + i % 3) + i))
            pixel(int(sx), int(sy), (1, 1, 0.9, max(0.1, a)))

    def nube(cx, cy, color):
        for dx, dy in ((0, 0), (1, 0), (2, 0), (3, 0), (1, -1), (2, -1), (4, 0), (-1, 0)):
            pixel(cx + dx, cy + dy, color)

    columnas = int(w / p) + 1
    est = estado_cielo(clima, hora, noche=True if clave in ("noche", "ciudad") else None)
    noche = est["noche"]
    q = p / 2  # el píxel fino, para los detalles
    hasta = lambda fr: round(h * fr / p) * p  # noqa: E731 - una altura redondeada a píxeles

    def colinas(desde, alto, color, onda, fase=0.0):
        for c in range(int(w / q) + 1):
            a = alto * (0.55 + 0.45 * math.sin(c * onda + fase) * math.cos(c * onda * 0.37 + fase))
            l.rect(x + c * q, y + desde - a, q + 0.5, a + 1, 0, color)

    def suelo_degradado(desde, arriba_c, abajo_c):
        suelo(desde, abajo_c)
        bandas = 4
        alto = (h - desde) / bandas
        for i in range(bandas - 1):
            bloque(0, desde + alto * i, w, alto + 1, mezcla(arriba_c, abajo_c, i / (bandas - 1)))

    def matas(desde, color, oscuro):
        for c in range(0, int(w / q) + 1, 2):
            alto = 1 + (c * 7 % 5 == 0) + (c * 3 % 7 == 0)
            l.rect(x + c * q, y + desde - alto * q, q + 0.5, alto * q + 1, 0, color if c % 4 else oscuro)

    if clave == "habitacion":
        pared, franja = (0.93, 0.86, 0.74), (0.9, 0.82, 0.69)
        base(pared)
        for c in range(0, columnas, 4):
            bloque(c * p, 0, p, h, franja)
        zocalo = hasta(0.64)
        bloque(0, zocalo - p, w, p, (0.8, 0.62, 0.45))
        suelo(zocalo, (0.64, 0.44, 0.29))
        for fila in range(int(zocalo / p) + 2, int(h / p), 2):
            desplaz = 3 if fila % 4 else 0
            for c in range(desplaz, columnas, 7):
                pixel(c, fila, (0.55, 0.37, 0.24))
        l.rect(x + w * 0.3, y + zocalo + (h - zocalo) * 0.45, w * 0.4, (h - zocalo) * 0.35, p, (0.75, 0.35, 0.4))  # alfombra
        # Ventana: por ella se ve el cielo y el tiempo de verdad
        vx, vy, vw, vh = x + w * 0.07, y + p * 1.5, p * 9, p * 7.5
        recortar = getattr(l, "recortar", None)
        if recortar:
            recortar(vx, vy, vw, vh, 0)
        dibujar_cielo(l, vx, vy, vw, vh, est, t, q * 0.75, random.Random("ventana"))
        dibujar_clima(l, vx, vy, vw, vh, est, t, q * 0.75, random.Random("ventana"))
        if recortar:
            l.sin_recorte()
        marco = (0.98, 0.97, 0.94)
        for rx, ry, rw, rh in ((0, 0, vw, q * 1.5), (0, vh - q * 1.5, vw, q * 1.5), (0, 0, q * 1.5, vh),
                               (vw - q * 1.5, 0, q * 1.5, vh), (vw / 2 - q * 0.7, 0, q * 1.4, vh),
                               (0, vh / 2 - q * 0.7, vw, q * 1.4)):
            l.rect(vx + rx, vy + ry, rw, rh, 0, marco)
        l.rect(vx - q * 2, vy + vh, vw + q * 4, q * 1.6, 0, (0.85, 0.75, 0.6))  # alféizar
        for lado_c in (vx - q * 3, vx + vw - q):  # cortinas
            l.rect(lado_c, vy - q, q * 4, vh * 0.85, q, (0.85, 0.45, 0.5))
            l.rect(lado_c + q, vy - q, q, vh * 0.85, 0, (0.75, 0.38, 0.43))
        qx = int(w / p * 0.78)
        for c in range(5):
            for f in range(4):
                borde = c in (0, 4) or f in (0, 3)
                pixel(qx + c, 3 + f, (0.55, 0.36, 0.2) if borde else ((0.45, 0.72, 0.4) if f == 2 else (0.6, 0.8, 0.95)))
        return y + zocalo + (h - zocalo) * 0.62
    if clave == "jardin":
        hierba = hasta(0.66)
        dibujar_cielo(l, x, y, w, hierba, est, t, q, azar)
        lejos = mezcla((0.35, 0.6, 0.45), est["color"], 0.5) if not noche else (0.1, 0.16, 0.2)
        colinas(hierba, h * 0.16, lejos, 0.09, 1.0)
        verde, verde_bajo = ((0.42, 0.75, 0.35), (0.3, 0.6, 0.27)) if not noche else ((0.16, 0.32, 0.2), (0.1, 0.22, 0.14))
        suelo_degradado(hierba, verde, verde_bajo)
        matas(hierba, verde, mezcla(verde, (0, 0, 0), 0.25))
        for i in range(8):
            fx = azar.uniform(0, w - 6 * q)
            fy = azar.uniform(hierba + q, h - 6 * q)
            _flor(l, x + fx, y + fy, q, _PETALOS[i % len(_PETALOS)], noche)
        dibujar_clima(l, x, y, w, h, est, t, q, azar)
        return y + hierba + (h - hierba) * 0.55
    if clave == "playa":
        mar, arena = hasta(0.5), hasta(0.7)
        dibujar_cielo(l, x, y, w, mar, est, t, q, azar)
        agua_arriba, agua_abajo = ((0.25, 0.6, 0.88), (0.12, 0.42, 0.72)) if not noche else ((0.08, 0.14, 0.3), (0.05, 0.09, 0.2))
        if est["tipo"] in ("cubierto", "lluvia", "tormenta", "niebla"):
            agua_arriba, agua_abajo = mezcla(agua_arriba, (0.5, 0.55, 0.6), 0.4), mezcla(agua_abajo, (0.4, 0.45, 0.5), 0.4)
        for i in range(4):
            bloque(0, mar + (arena - mar) * i / 4, w, (arena - mar) / 4 + 1, mezcla(agua_arriba, agua_abajo, i / 3))
        if est["tipo"] in ("despejado", "nubes"):  # el reflejo del sol o la luna en el agua
            for i in range(5):
                ancho = q * (5 - i) * (1 + 0.3 * math.sin(t * 2 + i))
                l.rect(x + w * 0.8 - ancho / 2, y + mar + q * (1 + i * 1.6), ancho, q, 0,
                       (1, 0.95, 0.8, 0.5) if not noche else (0.9, 0.92, 1.0, 0.35))
        for i in range(10):  # olas
            ox = (azar.uniform(0, w) + t * q * 2) % w
            oy = mar + (arena - mar) * azar.uniform(0.15, 0.85)
            l.rect(x + ox, y + oy, q * 3, q * 0.8, 0, (1, 1, 1, 0.55))
        arena_c = (0.96, 0.86, 0.62) if not noche else (0.45, 0.42, 0.38)
        suelo_degradado(arena, mezcla(arena_c, (1, 1, 1), 0.15), arena_c)
        for c in range(int(w / q) + 1):  # la espuma de la orilla, que va y viene
            alto = 1 + (math.sin(c * 0.5 + t * 2) > 0.3)
            l.rect(x + c * q, y + arena - q * alto * 0.5, q + 0.5, q * alto, 0, (1, 1, 1, 0.85))
        for i in range(4):  # conchas y estrellas de mar
            sx, sy = x + azar.uniform(0, w - 4 * q), y + azar.uniform(arena + 3 * q, h - 4 * q)
            if i % 2:
                for dx, dy in ((1, 0), (0, 1), (1, 1), (2, 1), (1, 2), (0, 3), (2, 3)):
                    l.rect(sx + dx * q, sy + dy * q, q + 0.5, q + 0.5, 0, (1.0, 0.5, 0.35))
            else:
                l.rect(sx, sy, q * 3, q * 2, q, (1.0, 0.82, 0.78))
        dibujar_clima(l, x, y, w, h, est, t, q, azar)
        return y + arena + (h - arena) * 0.55
    if clave == "noche":
        colina = hasta(0.7)
        dibujar_cielo(l, x, y, w, colina, est, t, q, azar, luna_grande=True)
        colinas(colina, h * 0.2, (0.12, 0.15, 0.27), 0.07, 2.0)
        colinas(colina, h * 0.1, (0.09, 0.12, 0.2), 0.13, 0.5)
        suelo(colina, (0.08, 0.11, 0.18))
        for i in range(6):  # luciérnagas
            fx = w * (0.1 + 0.8 * ((i * 0.37 + t * 0.03) % 1))
            fy = h * (0.55 + 0.12 * math.sin(t * 0.8 + i * 2))
            brillo = 0.5 + 0.5 * math.sin(t * 3 + i)
            l.circulo(x + fx, y + fy, q * 2.2, (1, 0.95, 0.4, 0.15 * brillo))
            l.rect(x + fx - q / 2, y + fy - q / 2, q, q, 0, (1, 0.95, 0.5, brillo))
        dibujar_clima(l, x, y, w, h, est, t, q, azar)
        return y + colina + (h - colina) * 0.55
    if clave == "ciudad":
        calle = hasta(0.72)
        dibujar_cielo(l, x, y, w, calle, est, t, q, azar)
        c = 0.0
        while c < w:
            ancho_e = azar.randint(7, 12) * q
            alto_e = azar.uniform(0.28, 0.6) * h
            arriba = calle - alto_e
            color_e = azar.choice(((0.13, 0.13, 0.25), (0.16, 0.14, 0.28), (0.11, 0.12, 0.22)))
            bloque(c, arriba, ancho_e + 0.6, alto_e, color_e)
            bloque(c, arriba, q, alto_e, mezcla(color_e, (1, 1, 1), 0.08))
            for f in range(int(arriba / q) + 2, int(calle / q) - 2, 3):
                for cc in range(int(c / q) + 2, int((c + ancho_e) / q) - 1, 3):
                    if azar.random() < 0.6 and math.sin(t * 0.2 + cc * 7 + f * 3) > -0.85:
                        l.rect(x + cc * q, y + f * q, q * 1.5, q * 1.5, 0, (1.0, 0.85, 0.45))
            if azar.random() < 0.5:  # antena con su luz roja
                ax = c + ancho_e / 2
                bloque(ax, arriba - q * 4, q * 0.6, q * 4, (0.3, 0.3, 0.38))
                if math.sin(t * 2 + c) > 0:
                    l.rect(x + ax - q / 2, y + arriba - q * 5, q * 1.5, q * 1.5, q, (1, 0.25, 0.25))
            c += ancho_e
        nx = w * 0.18
        brillo = 1.0 if math.sin(t * 3) > -0.7 else 0.35
        l.rect(x + nx, y + h * 0.3, q * 10, q * 2, q, (1.0 * brillo, 0.3 * brillo, 0.75 * brillo))
        l.rect(x + nx - q, y + h * 0.3 - q, q * 12, q * 4, q * 2, (1.0, 0.3, 0.75, 0.15 * brillo))
        suelo(calle, (0.18, 0.18, 0.22))
        for cc in range(0, int(w / q), 8):
            l.rect(x + cc * q, y + calle + (h - calle) * 0.45, q * 4, q, 0, (0.95, 0.85, 0.3))
        for fx in (0.08, 0.92):  # farolas
            bloque(w * fx, calle - h * 0.3, q, h * 0.3, (0.3, 0.3, 0.36))
            l.circulo(x + w * fx + q / 2, y + calle - h * 0.3, q * 4, (1, 0.9, 0.5, 0.18))
            l.rect(x + w * fx - q, y + calle - h * 0.3 - q, q * 3, q * 2, q, (1, 0.92, 0.6))
        dibujar_clima(l, x, y, w, h, est, t, q, azar)
        return y + calle + (h - calle) * 0.5
    if clave == "nieve":
        manto = hasta(0.68)
        dibujar_cielo(l, x, y, w, manto, est, t, q, azar)
        for mx_, alto_m in ((0.25, 0.32), (0.6, 0.4), (0.9, 0.28)):  # montañas con la cumbre nevada
            cima = manto - h * alto_m
            l.poligono([(x + w * (mx_ - 0.28), y + manto), (x + w * mx_, y + cima), (x + w * (mx_ + 0.28), y + manto)],
                       (0.55, 0.62, 0.74) if not noche else (0.2, 0.24, 0.35))
            l.poligono([(x + w * (mx_ - 0.07), y + cima + h * alto_m * 0.25), (x + w * mx_, y + cima),
                        (x + w * (mx_ + 0.07), y + cima + h * alto_m * 0.25)], (0.97, 0.98, 1.0))
        suelo_degradado(manto, (1.0, 1.0, 1.0), (0.85, 0.9, 0.98))
        for fx in (0.1, 0.86):  # abetos con nieve en las ramas
            cx = x + w * fx
            for i, (ancho, alto) in enumerate(((7, 4), (5.5, 4), (4, 3.5))):
                base_y = y + manto - q * (2 + i * 3.2)
                l.poligono([(cx - ancho * q, base_y), (cx, base_y - alto * q), (cx + ancho * q, base_y)], (0.1, 0.35, 0.22))
                l.poligono([(cx - ancho * q * 0.5, base_y - alto * q * 0.5), (cx, base_y - alto * q),
                            (cx + ancho * q * 0.5, base_y - alto * q * 0.5)], (0.95, 0.97, 1.0))
            l.rect(cx - q, y + manto - q * 2, q * 2, q * 2, 0, (0.4, 0.25, 0.12))
        nevando = dict(est, tipo="nieve") if est["tipo"] not in ("lluvia", "tormenta") else est
        dibujar_clima(l, x, y, w, h, nevando, t, q, azar)
        return y + manto + (h - manto) * 0.55
    if clave == "otono":
        hierba = hasta(0.68)
        dibujar_cielo(l, x, y, w, hierba, est, t, q, azar)
        tierra = (0.6, 0.42, 0.22) if not noche else (0.28, 0.2, 0.12)
        suelo_degradado(hierba, tierra, mezcla(tierra, (0, 0, 0), 0.2))
        hojas = ((0.95, 0.5, 0.15), (0.85, 0.25, 0.15), (1.0, 0.75, 0.2), (0.75, 0.4, 0.12))
        for fx in (0.13, 0.86):  # árboles: tronco con ramas y una copa de hojas de colores
            cx = x + w * fx
            l.rect(cx - q * 1.5, y + hierba - h * 0.32, q * 3, h * 0.32, 0, (0.4, 0.25, 0.12))
            l.linea(cx, y + hierba - h * 0.25, cx - q * 5, y + hierba - h * 0.36, q * 1.2, (0.4, 0.25, 0.12))
            l.linea(cx, y + hierba - h * 0.22, cx + q * 5, y + hierba - h * 0.33, q * 1.2, (0.4, 0.25, 0.12))
            for i in range(55):
                a, r = azar.uniform(0, math.tau), azar.uniform(0, 1) ** 0.5
                hx, hy = cx + math.cos(a) * r * q * 9, y + hierba - h * 0.42 + math.sin(a) * r * q * 6
                l.rect(hx, hy, q * 1.6, q * 1.6, 0, mezcla(azar.choice(hojas), (0.1, 0.1, 0.3), 0.5 if noche else 0))
        for i in range(14):  # hojas en el suelo
            l.rect(x + azar.uniform(0, w), y + azar.uniform(hierba + q, h - q), q * 1.5, q, 0, azar.choice(hojas))
        for i in range(10):  # y las que caen
            hx = (azar.uniform(0, w) + math.sin(t * 1.3 + i) * q * 6) % w
            hy = (azar.uniform(0, h) + t * q * (2.4 + i % 3)) % h
            l.rect(x + hx, y + hy, q * 1.6, q * 1.2, q * 0.4, hojas[i % len(hojas)])
        dibujar_clima(l, x, y, w, h, est, t, q, azar)
        return y + hierba + (h - hierba) * 0.55
    if clave == "gamer":
        pared = (0.1, 0.07, 0.17)
        base(pared)
        for c in range(int(w / q) + 1):  # tira de LED arriba, con el arcoíris corriendo
            l.rect(x + c * q, y, q + 0.5, q * 1.5, 0, colorsys.hsv_to_rgb((c / 40 - t * 0.3) % 1, 0.8, 1.0))
            l.rect(x + c * q, y + q * 1.5, q + 0.5, q * 3, 0, (*colorsys.hsv_to_rgb((c / 40 - t * 0.3) % 1, 0.8, 1.0), 0.12))
        # Póster en la pared
        px0, py0 = x + w * 0.08, y + h * 0.12
        l.rect(px0, py0, q * 9, q * 12, 0, (0.95, 0.95, 0.98))
        l.rect(px0 + q, py0 + q, q * 7, q * 10, 0, (0.2, 0.15, 0.35))
        l.poligono([(px0 + q * 2, py0 + q * 9), (px0 + q * 4.5, py0 + q * 4), (px0 + q * 7, py0 + q * 9)], (1.0, 0.4, 0.6))
        l.circulo(px0 + q * 5.5, py0 + q * 3, q * 1.2, (1.0, 0.85, 0.3))
        mesa = hasta(0.6)
        bloque(0, mesa, w, q * 2.5, (0.32, 0.24, 0.22))
        bloque(0, mesa, w, q * 0.6, (0.45, 0.35, 0.3))
        for fx in (0.05, 0.93):
            bloque(w * fx, mesa + q * 2.5, q * 1.5, h, (0.22, 0.16, 0.15))
        # Monitor con un juego en marcha: un personajito que salta plataformas
        mw, mh = q * 22, q * 13
        mx0, my0 = x + w * 0.5, y + mesa - mh - q * 3
        l.rect(mx0 - q, my0 - q, mw + q * 2, mh + q * 2, q, (0.08, 0.08, 0.1))
        for i in range(4):
            l.rect(mx0, my0 + mh * i / 4, mw, mh / 4 + 1, 0, mezcla((0.35, 0.6, 0.95), (0.6, 0.85, 1.0), i / 3))
        suelo_juego = my0 + mh - q * 2.5
        desp = (t * q * 6) % (q * 8)
        for i in range(5):
            bx = mx0 + ((i * q * 8 - desp) % (mw + q * 4)) - q * 2
            if mx0 <= bx <= mx0 + mw - q * 3:
                l.rect(bx, suelo_juego - q * (2 if i % 2 else 0), q * 3, q, 0, (0.3, 0.75, 0.3))
        l.rect(mx0, suelo_juego + q, mw, mh - (suelo_juego - my0) - q, 0, (0.55, 0.35, 0.2))
        salto = abs(math.sin(t * 3)) * q * 3
        l.rect(mx0 + q * 6, suelo_juego - q * 2.5 - salto, q * 1.6, q * 2.5, 0, (0.9, 0.25, 0.25))
        l.rect(mx0 + q * 6.3, suelo_juego - q * 3.2 - salto, q, q, 0, (1.0, 0.85, 0.7))
        l.rect(mx0 + q * 9.5, my0 + mh - q * 0.5, q * 3, q * 3.5, 0, (0.15, 0.15, 0.18))  # el pie
        # Teclado RGB y ratón
        tx = x + w * 0.12
        for i in range(12):
            l.rect(tx + i * q * 1.2, y + mesa - q * 1.6, q, q, 0, colorsys.hsv_to_rgb((i / 12 + t * 0.4) % 1, 0.7, 1.0))
        l.rect(tx - q * 0.5, y + mesa - q * 0.7, q * 15.4, q * 0.7, 0, (0.15, 0.15, 0.18))
        l.rect(tx + q * 17, y + mesa - q * 1.6, q * 1.6, q * 1.6, q * 0.6, (0.2, 0.2, 0.25))
        l.rect(tx + q * 17.5, y + mesa - q * 1.4, q * 0.6, q * 0.6, 0, colorsys.hsv_to_rgb((t * 0.4) % 1, 0.7, 1.0))
        suelo_y = hasta(0.74)
        suelo(suelo_y, (0.16, 0.12, 0.24))
        bloque(0, suelo_y, w, q * 0.6, (0.22, 0.17, 0.32))
        return y + suelo_y + (h - suelo_y) * 0.55
    if clave == "concierto":
        base((0.05, 0.03, 0.09))
        escenario = hasta(0.7)
        ritmo = 2.5 if musica else 0.6  # con música, los focos se mueven al ritmo
        for i, color in enumerate(((1.0, 0.3, 0.6), (0.3, 0.7, 1.0), (1.0, 0.85, 0.3), (0.5, 1.0, 0.5))):
            ox = w * (0.12 + 0.25 * i)
            ang = math.sin(t * ritmo + i * 2.1) * 0.5
            dx = math.tan(ang) * escenario
            l.poligono([(x + ox - q, y), (x + ox + q, y), (x + ox + dx + q * 9, y + escenario),
                        (x + ox + dx - q * 9, y + escenario)], (*color, 0.2 if musica else 0.1))
            l.rect(x + ox - q * 1.5, y, q * 3, q * 2, q * 0.5, (0.25, 0.25, 0.3))
            l.rect(x + ox - q, y + q * 2, q * 2, q, 0, color)
        # Batería al fondo del escenario
        bx = x + w * 0.5
        l.circulo(bx, y + escenario - q * 4, q * 4, (0.85, 0.2, 0.3))
        l.circulo(bx, y + escenario - q * 4, q * 2.8, (0.95, 0.92, 0.88))
        for dx in (-q * 7, q * 7):
            l.rect(bx + dx - q * 2, y + escenario - q * 8, q * 4, q * 1.2, q * 0.5, (1.0, 0.82, 0.3))
            l.rect(bx + dx - q * 0.2, y + escenario - q * 7, q * 0.4, q * 7, 0, (0.6, 0.6, 0.65))
        pulso = 0.5 + 0.5 * abs(math.sin(t * 6)) if musica else 0.4
        for fx in (0.02, 0.86):  # altavoces que laten
            ax, ay = x + w * fx, y + escenario - q * 13
            l.rect(ax, ay, q * 7, q * 13, q * 0.8, (0.13, 0.13, 0.16))
            for cy_, r in ((q * 3.5, q * 2.2), (q * 9, q * 2.8)):
                l.circulo(ax + q * 3.5, ay + cy_, r * (1 + 0.15 * pulso), (0.3, 0.3, 0.36))
                l.circulo(ax + q * 3.5, ay + cy_, r * 0.4, (0.5, 0.5, 0.56))
        suelo(escenario, (0.22, 0.15, 0.12))
        bloque(0, escenario, w, q, (0.45, 0.32, 0.22))
        for c in range(0, int(w / q), 10):
            bloque(c * q, escenario + q, q * 0.5, h, (0.17, 0.11, 0.09))
        # El público, delante: con música, manos arriba
        for i in range(9):
            cx = x + w * (i + 0.5) / 9
            cabeza = y + h - q * (4 + (i % 3))
            l.circulo(cx, cabeza, q * 2.2, (0.08, 0.06, 0.1))
            l.rect(cx - q * 3, cabeza + q, q * 6, h, q * 2, (0.08, 0.06, 0.1))
            if musica and math.sin(t * 5 + i) > 0:
                l.rect(cx + q * 2, cabeza - q * 4, q * 0.9, q * 4, 0, (0.08, 0.06, 0.1))
        return y + escenario + (h - escenario) * 0.4
    if clave == "mar":
        arriba_c, abajo_c = (0.25, 0.62, 0.88), (0.04, 0.2, 0.42)
        bandas = 8
        for i in range(bandas):
            bloque(0, h * i / bandas, w, h / bandas + 1, mezcla(arriba_c, abajo_c, i / (bandas - 1)))
        for i in range(4):  # rayos de luz que bajan desde la superficie
            rx_ = w * (0.15 + 0.25 * i) + math.sin(t * 0.4 + i) * q * 3
            l.poligono([(x + rx_, y), (x + rx_ + q * 4, y), (x + rx_ + q * 10, y + h * 0.8), (x + rx_ + q * 3, y + h * 0.8)],
                       (0.8, 0.95, 1.0, 0.08))
        arena = hasta(0.76)
        for i in range(3):  # peces: cuerpo, cola, aleta y ojo
            color = ((1.0, 0.55, 0.15), (1.0, 0.85, 0.25), (0.4, 0.75, 1.0))[i]
            fx = (azar.uniform(0, w) + t * q * (3 + i)) % (w + q * 16) - q * 8
            fy = h * (0.18 + 0.17 * i) + math.sin(t * 2 + i) * q
            l.rect(x + fx, y + fy, q * 6, q * 3.2, q * 1.6, color)
            l.poligono([(x + fx + q * 0.5, y + fy + q * 1.6), (x + fx - q * 2.5, y + fy - q * 0.4),
                        (x + fx - q * 2.5, y + fy + q * 3.6)], _sombra(color, 0.15))
            l.rect(x + fx + q * 2.5, y + fy - q * 0.6, q * 1.6, q, q * 0.5, _sombra(color, 0.15))
            if i == 0:  # el payaso, con sus rayas
                for dx in (q * 1.5, q * 3.5):
                    l.rect(x + fx + dx, y + fy, q * 0.7, q * 3.2, 0, (1, 1, 1))
            l.rect(x + fx + q * 4.4, y + fy + q * 0.8, q, q, 0, (1, 1, 1))
            l.rect(x + fx + q * 4.8, y + fy + q * 1.1, q * 0.5, q * 0.5, 0, (0.05, 0.05, 0.1))
        suelo_degradado(arena, (0.92, 0.82, 0.58), (0.8, 0.68, 0.45))
        for fx, color in ((0.06, (1.0, 0.45, 0.5)), (0.9, (1.0, 0.6, 0.3))):  # corales
            cx = x + w * fx
            for rama in (-2.5, 0, 2.5):
                l.linea(cx, y + arena + q, cx + rama * q, y + arena - q * (7 - abs(rama)), q * 1.4, color)
                l.circulo(cx + rama * q, y + arena - q * (7 - abs(rama)), q * 1.1, _brillo(color, 0.3))
        for fx in (0.18, 0.26, 0.78):  # algas que se mecen
            cx = x + w * fx
            for f in range(10):
                l.rect(cx + math.sin(t * 1.5 + f * 0.6 + fx * 9) * q * 1.2, y + arena - f * q * 1.2, q * 1.3, q * 1.3, 0,
                       (0.2, 0.6, 0.32) if f % 2 else (0.28, 0.72, 0.4))
        for dx, dy in ((1, 0), (0, 1), (1, 1), (2, 1), (1, 2), (0, 3), (2, 3)):  # estrella de mar
            l.rect(x + w * 0.62 + dx * q, y + arena + q * 3 + dy * q, q + 0.5, q + 0.5, 0, (1.0, 0.45, 0.35))
        l.rect(x + w * 0.38, y + arena + q * 4, q * 3, q * 2, q, (1.0, 0.85, 0.8))  # concha
        for i in range(10):  # burbujas
            bx = azar.uniform(0, w)
            by = (azar.uniform(0, h) - t * q * (3 + i % 3)) % arena
            l.circulo(x + bx + math.sin(t * 2 + i) * q, y + by, q * (0.6 + 0.3 * (i % 3)), (0.85, 0.95, 1.0, 0.45))
            l.rect(x + bx + math.sin(t * 2 + i) * q - q * 0.3, y + by - q * 0.3, q * 0.4, q * 0.4, 0, (1, 1, 1, 0.8))
        return y + arena + (h - arena) * 0.55
    if clave == "espacio":
        base((0.03, 0.02, 0.09))
        l.circulo(x + w * 0.3, y + h * 0.3, w * 0.35, (0.35, 0.15, 0.5, 0.18))  # una nebulosa
        l.circulo(x + w * 0.45, y + h * 0.2, w * 0.22, (0.15, 0.3, 0.6, 0.15))
        for i in range(int(w * h / (q * q * 40))):
            sx, sy = azar.uniform(0, w), azar.uniform(0, h * 0.8)
            a = 0.4 + 0.6 * abs(math.sin(t * (0.8 + i % 3) + i))
            l.rect(x + sx, y + sy, q * (1 if i % 5 else 1.5), q * (1 if i % 5 else 1.5), 0, (1, 1, 0.95, a))
        if (t % 6) < 0.8:  # una estrella fugaz de vez en cuando
            k = (t % 6) / 0.8
            ex, ey = x + w * (0.1 + 0.5 * k), y + h * (0.1 + 0.15 * k)
            l.linea(ex - q * 8, ey - q * 2.5, ex, ey, q * 0.6, (1, 1, 1, 0.6 * (1 - k)))
        # Planeta con bandas y anillos
        pcx, pcy, pr = x + w * 0.78, y + h * 0.26, q * 7
        l.linea(pcx - pr * 1.9, pcy + pr * 0.45, pcx + pr * 1.9, pcy - pr * 0.45, q * 1.3, (0.85, 0.75, 0.55, 0.9))
        l.circulo(pcx, pcy, pr, (0.95, 0.6, 0.3))
        for k, color in ((-0.4, (0.85, 0.45, 0.2)), (0.1, (1.0, 0.75, 0.45)), (0.5, (0.8, 0.4, 0.2))):
            l.rect(pcx - pr * math.sqrt(1 - k * k) * 0.95, pcy + pr * k, pr * 2 * math.sqrt(1 - k * k) * 0.95, q * 1.2,
                   q * 0.6, color)
        l.circulo(pcx - pr * 0.4, pcy - pr * 0.4, pr * 0.25, (1, 1, 1, 0.3))
        l.linea(pcx - pr * 0.2, pcy + pr * 0.98, pcx + pr * 1.9, pcy - pr * 0.45, q * 1.3, (0.85, 0.75, 0.55, 0.9))
        # La Tierra a lo lejos
        l.circulo(x + w * 0.15, y + h * 0.18, q * 3, (0.25, 0.5, 0.95))
        l.rect(x + w * 0.15 - q * 1.5, y + h * 0.18 - q, q * 2, q * 1.5, q * 0.6, (0.35, 0.75, 0.35))
        l.rect(x + w * 0.15, y + h * 0.18 + q * 0.8, q * 1.5, q, q * 0.4, (0.35, 0.75, 0.35))
        luna = hasta(0.74)
        suelo_degradado(luna, (0.62, 0.62, 0.68), (0.45, 0.45, 0.52))
        for i in range(6):  # cráteres con su borde iluminado
            cx, cy = x + azar.uniform(0, w), y + azar.uniform(luna + q * 2, h - q * 3)
            r = q * azar.uniform(1.5, 3)
            l.rect(cx - r, cy - r * 0.45, r * 2, r * 0.9, r * 0.45, (0.42, 0.42, 0.48))
            l.rect(cx - r, cy - r * 0.45, r * 2, q * 0.6, 0, (0.75, 0.75, 0.8))
        return y + luna + (h - luna) * 0.55
    if clave == "dulces":
        bandas = 6
        for i in range(bandas):
            bloque(0, h * 0.7 * i / bandas, w, h * 0.7 / bandas + 1, mezcla((1.0, 0.78, 0.9), (1.0, 0.9, 0.8), i / (bandas - 1)))
        for i in range(3):  # nubes de algodón de azúcar
            nx = (azar.uniform(0, w) + t * q * 0.4) % (w + q * 16) - q * 8
            ny = h * (0.08 + 0.12 * i)
            for dx, r in ((0, 2.2), (2.5, 3), (5.2, 2.4)):
                l.circulo(x + nx + dx * q, y + ny, q * r, (1.0, 0.85, 0.95) if i % 2 else (0.85, 0.92, 1.0))
        colinas(hasta(0.66), h * 0.12, (0.55, 0.32, 0.2), 0.11, 0.7)  # de chocolate
        caramelo = hasta(0.68)
        suelo_degradado(caramelo, (1.0, 0.62, 0.78), (0.95, 0.5, 0.68))
        for c in range(0, int(w / q), 6):  # chispitas de colores
            for f in range(int(caramelo / q) + 2, int(h / q), 5):
                color = ((1, 1, 1), (0.5, 0.85, 1.0), (1.0, 0.9, 0.3), (0.6, 1.0, 0.6))[(c + f) % 4]
                l.rect(x + c * q + (f % 2) * q * 2, y + f * q, q * 1.5, q * 0.6, 0, color)
        for fx, color in ((0.1, (0.55, 0.85, 1.0)), (0.9, (1.0, 0.85, 0.3))):  # piruletas en espiral
            cx, cy = x + w * fx, y + caramelo - q * 12
            l.rect(cx - q * 0.5, cy, q, q * 12, 0, (1, 1, 1))
            l.circulo(cx, cy, q * 4.5, color)
            for k in range(14):
                a, r = k * 0.9 + t, q * (0.6 + k * 0.28)
                l.rect(cx + math.cos(a) * r - q / 2, cy + math.sin(a) * r - q / 2, q, q, 0, (1, 1, 1))
        for fx in (0.25, 0.75):  # bastones de caramelo
            cx = x + w * fx
            for f in range(9):
                l.rect(cx, y + caramelo - q * (f + 1), q * 1.5, q, 0, (0.9, 0.15, 0.25) if f % 2 else (1, 1, 1))
            l.rect(cx, y + caramelo - q * 10, q * 3.5, q * 1.5, q * 0.7, (0.9, 0.15, 0.25))
        return y + caramelo + (h - caramelo) * 0.55
    return None


# ---------------------------------------------------------------------------
# La mascota: necesidades, acciones, tienda y su dibujo dentro del widget
# ---------------------------------------------------------------------------

class Mascota:
    def __init__(self, datos, al_guardar):
        """datos: el dict de la configuración (se modifica aquí); al_guardar: guarda la config."""
        self.d = datos
        self.al_guardar = al_guardar
        self.botones = []          # (x, y, w, h, accion) del último dibujo
        self.burbuja = ("", 0.0)   # (texto, hasta cuándo)
        self.animacion = ("", 0.0)
        self._guardado = time.monotonic()
        self._parpadeo = time.monotonic() + 3

    @property
    def adoptada(self):
        return bool(self.d.get("especie"))

    def adoptar(self, nombre, especie, colores):
        ahora = time.time()
        self.d.clear()
        self.d.update({"nombre": nombre or _("Pixel"), "especie": especie, "colores": list(colores),
                       "complementos": [], "puestos": [], "monedas": MONEDAS_INICIALES,
                       "necesidades": {k: 80.0 for k, _n in NECESIDADES}, "nacida": ahora, "ultimo": ahora,
                       "cuidado": 0.0, "durmiendo": False, "avisos": {}, "fondo": "jardin",
                       "dia_premio": time.strftime("%Y-%m-%d"), "racha": 1})
        self.decir(_("¡Hola! Soy {nombre}.").format(nombre=self.d["nombre"]))
        self.al_guardar()

    def personalizar(self, nombre, especie, colores, puestos, fondo=None):
        self.d.update({"nombre": nombre or self.d["nombre"], "especie": especie, "colores": list(colores),
                       "puestos": [p for p in puestos if p in self.d["complementos"]]})
        if fondo in self.fondos():
            self.d["fondo"] = fondo
        self.al_guardar()

    def fondos(self):
        """Los fondos que tiene: los gratis y los comprados."""
        return [k for k, _n, precio in FONDOS if precio == 0 or k in self.d.get("fondos", [])]

    # --- estado ------------------------------------------------------------------

    def n(self, clave):
        return self.d["necesidades"][clave]

    def etapa(self):
        """(nombre, escala) según las horas bien cuidada."""
        nombre, escala = ETAPAS[0][1:]
        for horas, n, e in ETAPAS:
            if self.d.get("cuidado", 0) >= horas:
                nombre, escala = n, e
        return nombre, escala

    def dias(self):
        return int((time.time() - self.d.get("nacida", time.time())) // 86400)

    def humor(self):
        if self.d.get("durmiendo"):
            return "dormido"
        valores = list(self.d["necesidades"].values())
        if min(valores) < 25:
            return "triste"
        if self.n("felicidad") > 70 and min(valores) >= 50:
            return "feliz"
        return "normal"

    def _cambiar(self, clave, delta):
        self.d["necesidades"][clave] = max(0.0, min(100.0, self.d["necesidades"][clave] + delta))

    def avanzar(self, contexto):
        """Aplica el tiempo pasado desde la última vez. Devuelve los avisos que toca dar."""
        if not self.adoptada:
            return []
        ahora = time.time()
        dt = ahora - self.d.get("ultimo", ahora)
        self.d["ultimo"] = ahora
        if dt <= 0:
            return []
        ausente = dt > AUSENTE
        horas = min(dt, MAX_HORAS * 3600) / 3600
        hora = time.localtime().tm_hour
        # De madrugada se duerme sola; por la mañana, descansada, se despierta
        if hora < 7 and not self.d.get("durmiendo") and not self.d.get("desvelada"):
            self.d["durmiendo"] = True
        if hora >= 7:
            self.d["desvelada"] = False
            if self.d.get("durmiendo") and self.n("energia") >= 95 and not self.d.get("siesta"):
                self.d["durmiendo"] = False
        if self.d.get("siesta") and self.n("energia") >= 99:
            self.d["durmiendo"] = self.d["siesta"] = False
        dormida = self.d.get("durmiendo")
        for clave, (despierta, dormida_r) in RITMO.items():
            ritmo = dormida_r if dormida else despierta
            if dormida and clave == "energia" and self.tiene("camita"):
                ritmo -= 10     # en su camita descansa más rápido
            if dormida and clave == "felicidad" and self.tiene("peluche"):
                ritmo -= 3      # abrazada al peluche, se despierta más contenta
            if not dormida and not ausente:
                if clave == "felicidad" and contexto.get("musica"):
                    ritmo -= 3      # bailar la anima
                if clave == "felicidad" and contexto.get("video"):
                    ritmo -= 1.5    # ver algo con palomitas, un poco
                if clave == "energia" and contexto.get("musica"):
                    ritmo += 2
                if clave == "limpieza" and contexto.get("calor"):
                    ritmo += 3      # sudar ensucia
            delta = -ritmo * horas * (0.5 if ausente else 1)
            antes = self.n(clave)
            self._cambiar(clave, delta)
            if ausente and delta < 0:
                self.d["necesidades"][clave] = max(min(antes, MINIMO_AUSENTE), self.n(clave))
        if self.n("energia") <= 3 and not dormida:
            self.d["durmiendo"] = self.d["siesta"] = True  # rendida: se queda dormida
        if min(self.d["necesidades"].values()) >= 50:
            self.d["cuidado"] = self.d.get("cuidado", 0) + horas
        if time.monotonic() - self._guardado > 300 or ausente:
            self._guardado = time.monotonic()
            self.al_guardar()
        avisos = self._avisos(ahora)
        premio = self._premio_del_dia()
        return avisos + ([premio] if premio else [])

    def _premio_del_dia(self):
        """La primera vez de cada día: monedas por un día más juntos, más con días seguidos."""
        hoy = time.strftime("%Y-%m-%d")
        ultimo = self.d.get("dia_premio")
        if ultimo == hoy:
            return None
        ayer = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
        racha = self.d.get("racha", 0) + 1 if ultimo == ayer else 1
        self.d["dia_premio"], self.d["racha"] = hoy, racha
        base, extra, tope = PREMIO_DIA
        ganadas = self.anadir_monedas(min(tope, base + extra * (racha - 1)), avisar=False)
        nombre = self.d["nombre"]
        if not ganadas:
            texto = _("{nombre} quería darte monedas, pero la hucha está llena.").format(nombre=nombre)
        elif racha > 1:
            texto = _("{nombre} te da {n} monedas: {d} días seguidos juntos.").format(nombre=nombre, n=ganadas, d=racha)
        else:
            texto = _("{nombre} te da {n} monedas por un día más juntos.").format(nombre=nombre, n=ganadas)
        self.decir(texto, 5)
        return texto

    def _avisos(self, ahora):
        if self.d.get("durmiendo"):
            return []
        textos = {"hambre": _("{nombre} tiene hambre."), "felicidad": _("{nombre} se aburre: juega un rato."),
                  "energia": _("{nombre} no puede más: necesita dormir."), "limpieza": _("{nombre} necesita un baño.")}
        salida = []
        avisos = self.d.setdefault("avisos", {})
        for clave, texto in textos.items():
            if self.n(clave) < 20 and ahora - avisos.get(clave, 0) > AVISO_CADA:
                avisos[clave] = ahora
                salida.append(texto.format(nombre=self.d["nombre"]))
        return salida

    # --- acciones ----------------------------------------------------------------

    def decir(self, texto, segundos=2.6):
        self.burbuja = (texto, time.monotonic() + segundos)

    def _animar(self, nombre, segundos):
        self.animacion = (nombre, time.monotonic() + segundos)

    def animando(self):
        nombre, hasta = self.animacion
        return nombre if time.monotonic() < hasta else ""

    def accion(self, clave):
        nombre = self.d["nombre"]
        if clave == "dormir":
            despierta = self.d.get("durmiendo")
            self.d["durmiendo"] = not despierta
            self.d["siesta"] = False
            if despierta:
                self.d["desvelada"] = time.localtime().tm_hour < 7
                self.decir(_("¡Buenos días!"))
            else:
                self.d["siesta"] = time.localtime().tm_hour >= 7
        elif self.d.get("durmiendo"):
            self.decir(_("Shh… {nombre} está durmiendo.").format(nombre=nombre))
            return
        elif clave == "comer":
            if self.n("hambre") >= 95:
                self.decir(_("No tengo hambre."))
                return
            self._cambiar("hambre", 30)
            self._cambiar("limpieza", -3)
            self._animar("comer", 1.6)
            self.decir(_("¡Ñam!"))
        elif clave == "jugar":
            if self.n("energia") < 15:
                self.decir(_("Necesito descansar…"))
                return
            animo = 30 if self.tiene("pelota") else 20  # con su pelota se lo pasa mejor
            for k, v in (("felicidad", animo), ("energia", -10), ("limpieza", -6), ("hambre", -4)):
                self._cambiar(k, v)
            self._animar("jugar", 2.2)
            self.decir(_("¡Otra vez!"))
        elif clave == "limpiar":
            self.d["necesidades"]["limpieza"] = 100.0
            self._cambiar("felicidad", 3)
            self._animar("limpiar", 1.8)
            self.decir(_("¡Qué gusto!"))
        self.al_guardar()

    def usar(self, clave, poner=True):
        """Desde la tienda: ponerse o quitarse un complemento, o usar un fondo o un pelaje que ya tiene."""
        d = self.d
        if clave in d.get("complementos", []):
            puestos = d.setdefault("puestos", [])
            if poner and clave not in puestos:
                puestos.append(clave)
            elif not poner and clave in puestos:
                puestos.remove(clave)
        elif clave in self.fondos():
            d["fondo"] = clave
        elif clave in PELAJES and self.tiene(clave):
            d["pelaje"] = clave if poner else None
        self.al_guardar()

    def tiene(self, clave):
        """Si tiene ese objeto o pelaje especial (los compra en la tienda)."""
        return clave in self.d.get("objetos", [])

    def _comprar_especial(self, clave, precio):
        if self.tiene(clave):
            return None
        if self.d["monedas"] < precio:
            return _("No tienes monedas suficientes.")
        if clave == "caja":
            # Un complemento al azar de los que aún no tiene (la caja no se guarda: se abre)
            quedan = [k for k, _n, p in COMPLEMENTOS if k not in self.d["complementos"] and p <= 45]
            if not quedan:
                return _("Ya tienes todos los complementos de la caja.")
            self.d["monedas"] -= precio
            premio = random.choice(quedan)
            self.d["complementos"].append(premio)
            self.d["puestos"].append(premio)
            nombre = next(_(n) for k, n, _p in COMPLEMENTOS if k == premio)
            self.decir(_("¡Sorpresa! {cosa}").format(cosa=nombre), 4)
            self.al_guardar()
            return None
        self.d["monedas"] -= precio
        self.d.setdefault("objetos", []).append(clave)
        if clave in PELAJES:
            self.d["pelaje"] = clave
        self.decir(_("¡Me encanta!"))
        self.al_guardar()
        return None

    def anadir_monedas(self, n, avisar=True):
        """Suma monedas sin pasar del máximo de la hucha. Devuelve las que han cabido."""
        if not self.adoptada:
            return 0
        ganadas = max(0, min(n, MAX_MONEDAS - self.d.get("monedas", 0)))
        self.d["monedas"] = self.d.get("monedas", 0) + ganadas
        if avisar:
            self.decir(_("+{n} monedas").format(n=ganadas) if ganadas else
                       _("La hucha está llena: ¡gasta algo en la tienda!"))
        self.al_guardar()
        return ganadas

    def comprar(self, clave):
        """Compra comida (se la come) o un complemento (se lo pone). Devuelve un texto de error o None."""
        for k, nombre, precio, efecto in COMIDAS:
            if k == clave:
                if self.d.get("durmiendo"):
                    return _("Está durmiendo.")
                if self.d["monedas"] < precio:
                    return _("No tienes monedas suficientes.")
                self.d["monedas"] -= precio
                for n, v in efecto.items():
                    self._cambiar(n, v)
                self._animar("comer", 1.6)
                self.decir(_("¡Mmm, {comida}!").format(comida=_(nombre).lower()))
                self.al_guardar()
                return None
        for k, nombre, precio, _para in ESPECIALES:
            if k == clave:
                return self._comprar_especial(k, precio)
        for k, nombre, precio in FONDOS:
            if k == clave:
                if k in self.fondos():
                    return None
                if self.d["monedas"] < precio:
                    return _("No tienes monedas suficientes.")
                self.d["monedas"] -= precio
                self.d.setdefault("fondos", []).append(k)
                self.d["fondo"] = k
                self.decir(_("¡Qué sitio tan bonito!"))
                self.al_guardar()
                return None
        for k, nombre, precio in COMPLEMENTOS:
            if k == clave:
                if k in self.d["complementos"]:
                    return None
                if self.d["monedas"] < precio:
                    return _("No tienes monedas suficientes.")
                self.d["monedas"] -= precio
                self.d["complementos"].append(k)
                self.d["puestos"].append(k)
                self.decir(_("¡Me encanta!"))
                self.al_guardar()
                return None
        return None

    # --- dibujo --------------------------------------------------------------------

    def dibujar(self, l, pal, w, h, contexto, t):
        self.botones = []
        texto, gris, tenue = pal["texto"], pal["gris"], pal["tenue"]
        if not self.adoptada:
            px = max(2, int(min(w, h - 40) / 22))
            dibujar_huevo(l, (w - 16 * px) / 2, (h - 40 - 16 * px) / 2, px, t)
            l.texto(_("Toca para adoptar tu mascota"), 0, h - 34, w, 20, max(10.0, min(13.0, w / 22)), gris)
            self.botones = [(0, 0, w, h, "adoptar")]
            return
        k = max(0.8, min(1.3, min(w / 300, h / 260)))
        # Arriba: nombre, etapa y monedas
        alto_cab = 18 * k
        etapa, escala = self.etapa()
        l.texto(self.d["nombre"], 4, 0, w, alto_cab, 13 * k, texto, "negrita", h_al=0)
        nw, _nh = l.medir(self.d["nombre"], 13 * k, "negrita")
        dias = self.dias()
        sub = f"{_(etapa)} · " + (_("1 día") if dias == 1 else _("{n} días").format(n=dias))
        l.texto(sub, 12 + nw, 0, w, alto_cab, 10 * k, gris, h_al=0)
        monedas = str(self.d.get("monedas", 0))
        mw, _mh = l.medir(monedas, 12 * k, "negrita")
        l.circulo(w - mw - 14 * k, alto_cab / 2, 5.5 * k, (1.0, 0.78, 0.2))
        l.circulo(w - mw - 14 * k, alto_cab / 2, 3 * k, (0.95, 0.62, 0.1))
        llena = self.d.get("monedas", 0) >= MAX_MONEDAS  # hucha llena: en amarillo
        l.texto(monedas, w - mw - 4, 0, mw, alto_cab, 12 * k, pal["amarillo"] if llena else texto, "negrita")
        self.botones.append((w - mw - 22 * k, 0, mw + 22 * k, alto_cab, "tienda"))  # las monedas abren la tienda
        # Abajo: botones y necesidades
        alto_bot = max(22.0, min(30.0, h * 0.12))
        y_bot = h - alto_bot
        acciones = (("comer", _("Comer")), ("jugar", _("Jugar")), ("limpiar", _("Limpiar")),
                    ("dormir", _("Despertar") if self.d.get("durmiendo") else _("Dormir")))
        hueco = 6
        ancho_b = (w - hueco * 3) / 4
        for i, (clave, nombre) in enumerate(acciones):
            bx = i * (ancho_b + hueco)
            l.rect(bx, y_bot, ancho_b, alto_bot, 7, con_alfa(tenue, 0.12))
            l.texto(nombre, bx, y_bot, ancho_b, alto_bot, px_que_quepa(l, nombre, ancho_b - 8, 11.5 * k, "normal"),
                    texto)
            self.botones.append((bx, y_bot, ancho_b, alto_bot, clave))
        y_fin = y_bot - 6
        if h >= 190:
            fila_h = 15 * k
            y_nec = y_fin - fila_h * 2
            col_w = (w - 12) / 2
            for i, (clave, nombre) in enumerate(NECESIDADES):
                cx, cy = (i % 2) * (col_w + 12), y_nec + (i // 2) * fila_h
                valor = self.n(clave) / 100
                lw = 52 * k
                l.texto(_(nombre), cx, cy, lw, fila_h, 10 * k, gris, h_al=0)
                bw = col_w - lw
                color = pal["verde"] if valor > 0.5 else pal["amarillo"] if valor > 0.25 else pal["rojo"]
                l.rect(cx + lw, cy + fila_h / 2 - 3 * k, bw, 6 * k, 3 * k, con_alfa(tenue, 0.15))
                if valor > 0.01:
                    l.rect(cx + lw, cy + fila_h / 2 - 3 * k, max(6 * k, bw * valor), 6 * k, 3 * k, color)
            y_fin = y_nec - 4
        # La mascota, en el hueco que queda
        zona_y, zona_h = alto_cab + 2, y_fin - alto_cab - 2
        self._escena(l, pal, 0, zona_y, w, zona_h, escala, contexto, t)

    def _escena(self, l, pal, x, y, w, h, escala, contexto, t):
        if h < 30:
            return
        suelo_fondo = dibujar_fondo(l, x, y, w, h, self.d.get("fondo", "ninguno"), t,
                                    musica=bool(contexto.get("musica")), clima=contexto.get("clima"))
        tam = min(w * 0.62, h * (0.8 if suelo_fondo else 0.98)) * escala
        px = 2 * max(1, math.floor(tam / 32))  # la mascota va a 32 x 32: píxeles enteros, nítidos
        lado = 16 * px
        cx, suelo = x + w / 2, (suelo_fondo + px * 1.5 if suelo_fondo else y + h - 2)
        humor = self.humor()
        anim = self.animando()
        dormida = humor == "dormido"
        baila = contexto.get("musica") and not dormida and not anim
        # Un vídeo: lo mira comiendo palomitas (si no está jugando, que entonces saca el mando)
        ve_video = (contexto.get("video") and not baila and not dormida and not anim
                    and not contexto.get("jugando"))
        picotea = ve_video and (t % 3.2) < 0.7   # cada poco, se lleva una palomita a la boca
        dx = dy = 0.0
        if baila:
            dx = math.sin(t * 6) * px * 0.8
            dy = -abs(math.sin(t * 6)) * px * 1.5
        elif anim == "jugar":
            dy = -abs(math.sin(t * 9)) * px * 3
        elif not dormida:
            dy = -px * 0.5 if int(t * 1.6) % 2 else 0  # respira
        # Sombra
        sombra = (0, 0, 0, 0.18) if suelo_fondo else con_alfa(pal["tenue"], 0.12)
        l.rect(cx - lado * 0.36, suelo - px * 1.1, lado * 0.72, px * 1.6, px, sombra)
        mx, my = cx - lado / 2 + dx, suelo - lado + dy
        expresion = humor
        if anim == "comer":
            expresion = "comiendo" if int(t * 5) % 2 else "normal"
        elif anim in ("jugar", "limpiar") or baila:
            expresion = "feliz"
        elif picotea:
            expresion = "comiendo" if (t % 3.2) > 0.35 else "normal"
        elif not dormida and time.monotonic() > self._parpadeo:
            expresion = "parpadeo"
            if time.monotonic() > self._parpadeo + 0.15:
                self._parpadeo = time.monotonic() + random.uniform(2.5, 5.5)
        complementos = list(self.d.get("puestos", []))
        if contexto.get("discord") and "auriculares" not in complementos:
            complementos.append("auriculares")
        if contexto.get("jugando") and not dormida and not anim:
            complementos.append("mando")
        en_cama = dormida and self.tiene("camita")
        if en_cama:
            dibujar_objeto(l, mx, suelo, px, "camita_detras")
        dibujar_mascota(l, mx, my, px, self.d["especie"], self.d["colores"], expresion, complementos,
                        sucia=self.n("limpieza") < 30, t=t, pelaje=self.d.get("pelaje"))
        if en_cama:
            dibujar_objeto(l, mx, suelo, px, "camita_manta")
        if dormida and self.tiene("peluche"):  # abrazada al peluche: a su lado, encima de la manta
            dibujar_objeto(l, mx + px * 10.5, suelo - px * (12 if en_cama else 8), px * 0.75, "peluche")
        if ve_video:
            self._palomitas(l, mx, suelo, px, t)
        # Efectos alrededor, con colores que se lean sobre el fondo que haya
        fondo = color_de_fondo(self.d.get("fondo", "ninguno"), None, pal, contexto.get("clima"))
        legibles = [c for c in _COLORES_NOTAS if se_distingue(c, fondo)] or [(0.15, 0.15, 0.2)]

        def con_sombra(texto, tx, ty, tam, color, alfa):
            l.texto(texto, tx + max(1.0, tam * 0.06), ty + max(1.0, tam * 0.06), 14, 14, tam, (0, 0, 0, 0.35 * alfa))
            l.texto(texto, tx, ty, 14, 14, tam, con_alfa(color, alfa))

        if dormida:
            gris = pal["gris"] if se_distingue(pal["gris"], fondo) else (1, 1, 1) if _luz(fondo) < 0.5 else (0.2, 0.2, 0.25)
            for i in range(3):
                fase = (t * 0.6 + i / 3) % 1
                con_sombra("z" if i % 2 else "Z", mx + lado * (0.85 + fase * 0.25), my - fase * lado * 0.5,
                           px * (2.2 + i * 0.6), gris, 1 - fase)
        if baila:
            for i in range(2):
                fase = (t * 0.7 + i / 2) % 1
                vuelta = int(t * 0.7 + i / 2)  # cada nota que sale cambia de color
                color = legibles[(vuelta * 3 + i * 2) % len(legibles)]
                lado_x = mx - px * 3 if i else mx + lado + px
                con_sombra("♪" if i else "♫", lado_x - px * 0.5, my + lado * 0.3 - fase * lado * 0.5, px * 4.2, color,
                           1 - fase ** 3)  # se ve entera casi todo el camino y se desvanece al final
        if contexto.get("calor") and not dormida:
            gota = (0.45, 0.75, 1.0) if se_distingue((0.45, 0.75, 1.0), fondo) else (1, 1, 1)
            for dx, desfase in ((13.2, 0), (2, 0.5)):
                fase = (t * 1.2 + desfase) % 1
                l.rect(mx + px * dx, my + px * (5 + desfase * 2 + fase * 4), px * 0.9, px * 1.4, px * 0.45,
                       con_alfa(gota, 1 - fase))
        if self.n("limpieza") < 30 and not anim:
            for i in range(3):
                a = t * (2 + i * 0.7) + i * 2.1
                l.circulo(mx + lado / 2 + math.cos(a) * lado * 0.6, my + lado * 0.35 + math.sin(a * 1.3) * lado * 0.25,
                          max(1.2, px * 0.45), (0.15, 0.15, 0.15))
        if anim == "comer":
            fin = self.animacion[1]
            queda = max(0.0, (fin - time.monotonic()) / 1.6)
            r = px * 1.6 * (0.3 + queda * 0.7)
            l.circulo(mx + lado * 0.5, my + px * 12.4, r, (0.9, 0.2, 0.25))
            l.rect(mx + lado * 0.5 - px * 0.2, my + px * 12.4 - r - px, px * 0.5, px, 0, (0.4, 0.25, 0.1))
        if anim == "jugar":
            bx = mx + lado + px * 2 + math.cos(t * 5) * px * 2
            by = suelo - px * 2 - abs(math.sin(t * 6)) * lado * 0.45
            l.circulo(bx, by, px * 1.4, (1.0, 0.55, 0.2))
        if anim == "limpiar":
            for i in range(6):
                fase = (t * 0.9 + i / 6) % 1
                l.circulo(mx + lado * (0.15 + (i * 0.37) % 0.7), my + lado * (0.9 - fase * 0.9),
                          px * (0.6 + (i % 3) * 0.3), con_alfa((0.8, 0.9, 1.0), 0.8 * (1 - fase)))
        # Bocadillo
        texto, hasta = self.burbuja
        if texto and time.monotonic() < hasta:
            tpx = max(10.0, min(13.0, w / 26))
            tw, th = l.medir(texto, tpx)
            bw, bh = min(w - 8, tw + 14), th + 8
            bx = max(x + 4, min(x + w - bw - 4, cx - bw / 2))
            by = max(y, my - bh - px)
            claro = sum(pal["texto"][:3]) > 1.5  # tema oscuro: bocadillo claro, y al revés
            l.rect(bx, by, bw, bh, 8, con_alfa(pal["texto"], 0.92))
            l.texto(texto, bx, by, bw, bh, px_que_quepa(l, texto, bw - 10, tpx),
                    (0.1, 0.1, 0.12) if claro else (1.0, 1.0, 1.0))

    def _palomitas(self, l, mx, suelo, px, t):
        """El cubo de palomitas a su lado y, al picotear, una palomita que va del cubo a la boca."""
        colores = {"W": (1.0, 0.97, 0.88)}
        x0, y0 = mx + px * 14.5, suelo - px * 5.5
        dibujar_objeto(l, x0, y0, px, "palomitas")
        fase = (t % 3.2) / 0.35
        if fase < 1:  # sube del cubo a la boca
            bx = x0 + px * 2 + (mx + px * 8 - x0 - px * 2) * fase
            by = y0 - math.sin(fase * math.pi) * px * 3 + (suelo - px * 6.5 - y0) * fase
            l.rect(bx, by, px * 0.9, px * 0.9, px * 0.3, colores["W"])

    def pulsar(self, x, y):
        """Devuelve la acción del botón pulsado ("adoptar", "comer"...) o None."""
        for bx, by, bw, bh, accion in self.botones:
            if bx <= x <= bx + bw and by <= y <= by + bh:
                if accion not in ("adoptar", "tienda"):
                    self.accion(accion)
                return accion
        return None
