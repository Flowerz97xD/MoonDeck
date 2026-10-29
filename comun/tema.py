"""Temas: aspecto general (acento, texto, fuente) y de las tarjetas de cada modo.

config["tema"] = {"global": {...}, "widgets": {...}, "panel": {...}}; lo que falte
se completa con los valores de POR_DEFECTO, así un tema viejo sigue sirviendo.
"""

import copy
import functools
import math

POR_DEFECTO = {
    "global": {
        "acento": "#4d8dff",
        "texto": "#f2f4f8",        # cifras grandes, horas...
        "texto_sec": "#9aa3b2",    # textos secundarios
        "fuente": "",              # "" = la del sistema
        "escala": 1.0,             # tamaño de letra
    },
    "widgets": {                   # tarjetas sueltas por el escritorio (y las sacadas del panel)
        "fondo": "#14161c", "opacidad": 0.45,
        "degradado": False, "fondo2": "#2a2140", "angulo": 135,
        "borde": "#ffffff", "borde_opacidad": 0.12, "borde_grosor": 1.0,
        "radio": 12, "cristal": True,
        "neon": False, "parpadeo": False,  # borde como un tubo de neón, y que falle a ratos
    },
    "panel": {                     # tarjetas dentro del panel y el fondo del panel
        "fondo": "#ffffff", "opacidad": 0.055,
        "degradado": False, "fondo2": "#4d8dff", "angulo": 135,
        "borde": "#ffffff", "borde_opacidad": 0.12, "borde_grosor": 1.0,
        "radio": 10, "cristal": True,
        "neon": False, "parpadeo": False,
        "panel_fondo": "#0c0e12", "panel_opacidad": 0.47,
    },
}


PREDEFINIDOS = {
    "Cristal oscuro": copy.deepcopy(POR_DEFECTO),
    "Cristal claro": {
        "global": dict(POR_DEFECTO["global"], acento="#2f6fe0", texto="#15181e", texto_sec="#4f5866"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#ffffff", opacidad=0.55, borde="#000000",
                        borde_opacidad=0.10),
        "panel": dict(POR_DEFECTO["panel"], fondo="#ffffff", opacidad=0.38, borde="#000000", borde_opacidad=0.08,
                      panel_fondo="#eef0f4", panel_opacidad=0.40),
    },
    "Negro sólido": {
        "global": dict(POR_DEFECTO["global"]),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#0b0c0f", opacidad=0.96, cristal=False, borde_opacidad=0.07),
        "panel": dict(POR_DEFECTO["panel"], fondo="#16181d", opacidad=1.0, cristal=False, borde_opacidad=0.06,
                      panel_fondo="#050506", panel_opacidad=1.0),
    },
    "Neón morado": {
        "global": dict(POR_DEFECTO["global"], acento="#b57bff"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#1c1036", fondo2="#0b1838", degradado=True, opacidad=0.6,
                        borde="#b57bff", borde_opacidad=0.38),
        "panel": dict(POR_DEFECTO["panel"], fondo="#2a1655", fondo2="#0e2150", degradado=True, opacidad=0.35,
                      borde="#b57bff", borde_opacidad=0.3, panel_fondo="#0a0618", panel_opacidad=0.55),
    },
    "Océano": {
        "global": dict(POR_DEFECTO["global"], acento="#2ec4d6"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#0b2a3a", fondo2="#06121c", degradado=True, opacidad=0.58,
                        borde="#2ec4d6", borde_opacidad=0.25),
        "panel": dict(POR_DEFECTO["panel"], fondo="#0f3a4f", fondo2="#071822", degradado=True, opacidad=0.4,
                      borde="#2ec4d6", borde_opacidad=0.2, panel_fondo="#03121a", panel_opacidad=0.55),
    },
    "Atardecer": {
        "global": dict(POR_DEFECTO["global"], acento="#ff8a4c"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#3a1426", fondo2="#1b0f2e", degradado=True, opacidad=0.58,
                        borde="#ff8a4c", borde_opacidad=0.3),
        "panel": dict(POR_DEFECTO["panel"], fondo="#4a1a30", fondo2="#22123a", degradado=True, opacidad=0.38,
                      borde="#ff8a4c", borde_opacidad=0.25, panel_fondo="#12070f", panel_opacidad=0.55),
    },
    "Cyberpunk": {
        "global": dict(POR_DEFECTO["global"], acento="#ff2bd6", texto="#f4f0ff", texto_sec="#9d93c0"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#0d0716", opacidad=0.72, borde="#ff2bd6",
                        borde_opacidad=0.9, borde_grosor=1.5, neon=True, parpadeo=True),
        "panel": dict(POR_DEFECTO["panel"], fondo="#120a1f", opacidad=0.6, borde="#22e6ff", borde_opacidad=0.9,
                      borde_grosor=1.5, neon=True, parpadeo=True, panel_fondo="#05020a", panel_opacidad=0.7),
    },
    "Synthwave": {
        "global": dict(POR_DEFECTO["global"], acento="#ff7edb", texto="#fdf1ff", texto_sec="#b49ad8"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#2b1055", fondo2="#7a1f5c", degradado=True, angulo=90,
                        opacidad=0.62, borde="#ff7edb", borde_opacidad=0.85, borde_grosor=1.5, neon=True),
        "panel": dict(POR_DEFECTO["panel"], fondo="#3a1466", fondo2="#8f2a52", degradado=True, angulo=90,
                      opacidad=0.42, borde="#ffb86c", borde_opacidad=0.8, borde_grosor=1.5, neon=True,
                      panel_fondo="#12051f", panel_opacidad=0.6),
    },
    "Ciberseguridad": {
        "global": dict(POR_DEFECTO["global"], acento="#00ff88", texto="#c8ffe0", texto_sec="#4fa873"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#010a05", opacidad=0.86, borde="#00ff88", borde_opacidad=0.8,
                        borde_grosor=1.0, radio=4, neon=True),
        "panel": dict(POR_DEFECTO["panel"], fondo="#021208", opacidad=0.75, borde="#00ff88", borde_opacidad=0.7,
                      borde_grosor=1.0, radio=4, neon=True, panel_fondo="#000302", panel_opacidad=0.82),
    },
    "Alerta roja": {
        "global": dict(POR_DEFECTO["global"], acento="#ff3b3b", texto="#ffeaea", texto_sec="#b07a7a"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#140404", opacidad=0.8, borde="#ff3b3b", borde_opacidad=0.85,
                        borde_grosor=1.5, radio=6, neon=True, parpadeo=True),
        "panel": dict(POR_DEFECTO["panel"], fondo="#1c0505", opacidad=0.65, borde="#ff3b3b", borde_opacidad=0.8,
                      borde_grosor=1.5, radio=6, neon=True, parpadeo=True, panel_fondo="#070101", panel_opacidad=0.75),
    },
    "Tron": {
        "global": dict(POR_DEFECTO["global"], acento="#4df3ff", texto="#e8fdff", texto_sec="#6fa9b3"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#00080c", opacidad=0.88, borde="#4df3ff", borde_opacidad=0.9,
                        borde_grosor=1.0, radio=2, neon=True),
        "panel": dict(POR_DEFECTO["panel"], fondo="#00121a", opacidad=0.7, borde="#4df3ff", borde_opacidad=0.85,
                      borde_grosor=1.0, radio=2, neon=True, panel_fondo="#000204", panel_opacidad=0.85),
    },
    "Vaporwave": {
        "global": dict(POR_DEFECTO["global"], acento="#01cdfe", texto="#fff6fd", texto_sec="#d6a7e6"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#ff71ce", fondo2="#01cdfe", degradado=True, angulo=160,
                        opacidad=0.38, borde="#fffb96", borde_opacidad=0.55, radio=16),
        "panel": dict(POR_DEFECTO["panel"], fondo="#b967ff", fondo2="#05ffa1", degradado=True, angulo=160,
                      opacidad=0.22, borde="#fffb96", borde_opacidad=0.45, radio=16,
                      panel_fondo="#2d1b45", panel_opacidad=0.5),
    },
    "Pastel lavanda": {
        "global": dict(POR_DEFECTO["global"], acento="#8b6cf0", texto="#2f2748", texto_sec="#7a6e9c"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#f4efff", fondo2="#ffe8f3", degradado=True, opacidad=0.7,
                        borde="#c9b8ff", borde_opacidad=0.6, radio=18),
        "panel": dict(POR_DEFECTO["panel"], fondo="#ffffff", fondo2="#f7e9ff", degradado=True, opacidad=0.6,
                      borde="#c9b8ff", borde_opacidad=0.5, radio=18, panel_fondo="#ece6fb", panel_opacidad=0.55),
    },
    "Pastel melocotón": {
        "global": dict(POR_DEFECTO["global"], acento="#ff8a6b", texto="#4a2f26", texto_sec="#9a7466"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#fff1e8", fondo2="#ffe3ec", degradado=True, opacidad=0.72,
                        borde="#ffc2a8", borde_opacidad=0.65, radio=18),
        "panel": dict(POR_DEFECTO["panel"], fondo="#fffaf6", fondo2="#ffeef0", degradado=True, opacidad=0.6,
                      borde="#ffc2a8", borde_opacidad=0.5, radio=18, panel_fondo="#fbe9e1", panel_opacidad=0.55),
    },
    "Pastel menta": {
        "global": dict(POR_DEFECTO["global"], acento="#2fbf8f", texto="#1f3f35", texto_sec="#5f8a7c"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#eafbf4", fondo2="#e7f3ff", degradado=True, opacidad=0.72,
                        borde="#a8e6cf", borde_opacidad=0.7, radio=18),
        "panel": dict(POR_DEFECTO["panel"], fondo="#f7fffb", fondo2="#eef6ff", degradado=True, opacidad=0.6,
                      borde="#a8e6cf", borde_opacidad=0.55, radio=18, panel_fondo="#e3f5ee", panel_opacidad=0.55),
    },
    "Nord": {
        "global": dict(POR_DEFECTO["global"], acento="#88c0d0", texto="#eceff4", texto_sec="#9aa5b8"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#2e3440", opacidad=0.8, borde="#4c566a", borde_opacidad=0.8,
                        radio=10),
        "panel": dict(POR_DEFECTO["panel"], fondo="#3b4252", opacidad=0.75, borde="#4c566a", borde_opacidad=0.6,
                      radio=10, panel_fondo="#242933", panel_opacidad=0.75),
    },
    "Drácula": {
        "global": dict(POR_DEFECTO["global"], acento="#bd93f9", texto="#f8f8f2", texto_sec="#8f94b8"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#282a36", opacidad=0.85, borde="#ff79c6", borde_opacidad=0.45,
                        radio=10),
        "panel": dict(POR_DEFECTO["panel"], fondo="#343746", opacidad=0.75, borde="#bd93f9", borde_opacidad=0.4,
                      radio=10, panel_fondo="#1e1f29", panel_opacidad=0.78),
    },
    "Bosque": {
        "global": dict(POR_DEFECTO["global"], acento="#9ccc65", texto="#eef5e6", texto_sec="#9fb38f"),
        "widgets": dict(POR_DEFECTO["widgets"], fondo="#1b2a1c", fondo2="#2e2418", degradado=True, opacidad=0.65,
                        borde="#9ccc65", borde_opacidad=0.25, radio=14),
        "panel": dict(POR_DEFECTO["panel"], fondo="#22351f", fondo2="#3a2c1c", degradado=True, opacidad=0.45,
                      borde="#9ccc65", borde_opacidad=0.2, radio=14, panel_fondo="#0c140b", panel_opacidad=0.6),
    },
    "Minimal": {
        "global": dict(POR_DEFECTO["global"]),
        "widgets": dict(POR_DEFECTO["widgets"], opacidad=0.18, borde_opacidad=0.28, radio=4),
        "panel": dict(POR_DEFECTO["panel"], opacidad=0.0, borde_opacidad=0.2, radio=4, panel_opacidad=0.3),
    },
}


def completo(tema):
    """El tema con todas las claves (las que falten, de POR_DEFECTO)."""
    t = copy.deepcopy(POR_DEFECTO)
    for seccion in t:
        t[seccion].update((tema or {}).get(seccion, {}))
    return t


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def a_hex(rgb):
    return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in rgb[:3])


def mezcla(a, b, t):
    """Color entre a (t=0) y b (t=1)."""
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def luminancia(rgb):
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


@functools.lru_cache(maxsize=64)
def capas_neon(alcance, pico):
    """Trazos (ancho, alfa) que, pintados uno encima de otro, dan un halo con caída
    gaussiana sin escalones: cada trazo es 2 px más ancho que el anterior y su alfa
    se calcula para que la mezcla acumulada siga la curva."""
    sigma = alcance / 2.3
    capas, resto_fuera = [], 1.0
    for k in range(alcance, 0, -1):
        resto = 1 - pico * math.exp(-((k - 0.5) / sigma) ** 2)  # transparencia buscada en ese anillo
        capas.append((2.0 * k, max(0.0, 1 - resto / resto_fuera)))
        resto_fuera = resto
    return tuple(capas)
