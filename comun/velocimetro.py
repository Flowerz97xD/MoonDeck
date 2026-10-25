"""Cálculos del velocímetro del test de velocidad (los comparten Linux y Windows;
cada versión lo dibuja con lo suyo).

El arco va de abajo a la izquierda a abajo a la derecha pasando por arriba, como
el cuentakilómetros de un coche. La escala es de raíz cuadrada: las velocidades
bajas no se quedan apelotonadas al principio.
"""

import math

INICIO = 150.0   # grados (0 = a la derecha, en el sentido de las agujas del reloj)
ARCO = 240.0
SEGMENTOS = 44

TOPES = (10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)


def tope(*valores):
    """El fondo de escala más pequeño en el que caben los valores (Mbps)."""
    v = max((x for x in valores if x), default=0)
    return next((t for t in TOPES if t >= v * 1.04), TOPES[-1])


def fraccion(valor, maximo):
    """0-1: dónde cae el valor en el arco."""
    if not valor or maximo <= 0:
        return 0.0
    return math.sqrt(min(max(valor, 0) / maximo, 1.0))


def marcas(maximo):
    """Valores que se rotulan en la escala."""
    return (0, maximo / 10, maximo / 4, maximo / 2, maximo)


def fmt_marca(v):
    if v >= 1000:
        return f"{v / 1000:g}k"
    return f"{v:g}"


def angulo(frac):
    """Ángulo en radianes (eje y hacia abajo, como en Cairo y Qt) para una fracción del arco."""
    return math.radians(INICIO + ARCO * frac)


def geometria(ancho, alto):
    """Centro y radio exterior del arco para que quepa en ancho x alto.

    El arco ocupa 2r de ancho y r + r·sin(30°) = 1.5r de alto."""
    margen = 6
    r = max(10.0, min((ancho - 2 * margen) / 2, (alto - 2 * margen) / 1.5))
    alto_arco = 1.5 * r
    return ancho / 2, (alto - alto_arco) / 2 + r, r


def mezcla(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))
