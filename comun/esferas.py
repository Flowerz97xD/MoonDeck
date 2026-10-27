"""Relojes y velocímetros dibujados una sola vez para Linux (Cairo) y Windows (Qt).

Cada versión pasa un "lienzo" con estas operaciones (colores en tuplas 0-1, con o
sin alfa; ángulos en radianes en el sentido de las agujas del reloj, eje y hacia abajo):

    rect(x, y, w, h, radio, color)                      rectángulo relleno
    circulo(cx, cy, r, color)                           círculo relleno
    arco(cx, cy, r, a0, a1, grosor, color, redondo)     arco de a0 a a1
    linea(x0, y0, x1, y1, grosor, color, redondo)
    poligono(puntos, color)                             polígono relleno
    medir(texto, px, peso) -> (ancho, alto)             peso: "fino", "normal" o "negrita"
    texto(texto, x, y, w, h, px, color, peso, h_al, v_al)   texto alineado en la caja

y una paleta: "texto", "gris", "tenue" y los colores "azul" (el acento), "verde",
"morado", "naranja", "rojo" y "amarillo".
"""

import math

import velocimetro as vm

# --- utilidades ---------------------------------------------------------------


def con_alfa(color, alfa):
    return (*color[:3], alfa)


def mezcla(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a[:3], b[:3]))


def px_que_quepa(l, texto, ancho, alto, peso="fino"):
    """El tamaño de letra más grande con el que `texto` cabe en ancho x alto."""
    px = max(6.0, alto)
    w, h = l.medir(texto, px, peso)
    if w > ancho:
        px *= ancho / w
    if h > alto * 1.25:
        px *= alto * 1.25 / h
    return max(6.0, px)


# --- velocímetros ---------------------------------------------------------------

ESTILOS_VELOCIMETRO = (("deportivo", "Deportivo"), ("aguja", "Aguja"), ("anillo", "Anillo"))


def velocimetro(l, pal, w, h, e, estilo="deportivo"):
    """e: valor, tope, texto, fase, color (nombre de la paleta), progreso (o None) y unidad."""
    {"aguja": _vel_aguja, "anillo": _vel_anillo}.get(estilo, _vel_deportivo)(l, pal, w, h, e)


def _cifras(l, pal, cx, cy, r, hueco, e, color, alto_cifra=0.3):
    """Cifra grande en el centro, la unidad debajo y la fase encima."""
    px = px_que_quepa(l, e["texto"], hueco, r * alto_cifra)
    _, ch = l.medir(e["texto"], px, "fino")
    l.texto(e["texto"], cx - hueco, cy - ch / 2, 2 * hueco, ch, px, pal["texto"], "fino")
    chico = max(9.0, r * 0.13)
    _, uh = l.medir(e["unidad"], chico, "normal")
    l.texto(e["unidad"], cx - r, cy + ch * 0.42, 2 * r, uh, chico, pal["gris"], "normal", 0.5, 0.0)
    if e["fase"] and r >= 60:  # en pequeño no cabe sin pisar el arco
        _, fh = l.medir(e["fase"], chico, "negrita")
        l.texto(e["fase"], cx - r, cy - ch * 0.45 - fh, 2 * r, fh, chico, color, "negrita", 0.5, 1.0)


def _marcas(l, pal, cx, cy, r_txt, r, tope):
    if r < 70:
        return
    px = max(8.0, min(12.0, r * 0.1))
    for v in vm.marcas(tope):
        a = vm.angulo(vm.fraccion(v, tope))
        x, y = cx + math.cos(a) * r_txt, cy + math.sin(a) * r_txt
        l.texto(vm.fmt_marca(v), x - 20, y - 10, 40, 20, px, pal["gris"], "normal")


def _progreso_fase(l, pal, cx, cy, r, e, color):
    """Arco fino por fuera con lo que lleva la fase en marcha."""
    if e["progreso"] is None:
        return
    l.arco(cx, cy, r, vm.angulo(0), vm.angulo(1), 2, con_alfa(pal["tenue"], 0.1), True)
    if e["progreso"] > 0:
        l.arco(cx, cy, r, vm.angulo(0), vm.angulo(min(1, e["progreso"])), 2, con_alfa(color, 0.8), True)


def _vel_deportivo(l, pal, w, h, e):
    """Arco de segmentos que se encienden, como un cuentakilómetros digital."""
    cx, cy, r = vm.geometria(w, h)
    grueso = max(6.0, r * 0.13)
    r_med = r - grueso / 2 - 4
    frac = vm.fraccion(e["valor"], e["tope"])
    color = pal.get(e["color"], pal["azul"])
    oscuro = mezcla(color, (0, 0, 0), 0.35)
    n = vm.SEGMENTOS
    paso = math.radians(vm.ARCO) / n
    for i in range(n):
        if (i + 0.5) / n <= frac:
            c = mezcla(oscuro, color, min(1, i / max(1, n - 1) * 1.6))
        else:
            c = con_alfa(pal["tenue"], 0.08)
        l.arco(cx, cy, r_med, vm.angulo(i / n) + paso * 0.14, vm.angulo((i + 1) / n) - paso * 0.14, grueso, c, False)
    if frac > 0:  # brillo en la punta, como la aguja encendida
        a = vm.angulo(frac)
        l.arco(cx, cy, r_med, a - paso * 0.9, a, grueso * 1.9, con_alfa(color, 0.35), False)
    _progreso_fase(l, pal, cx, cy, r - 1, e, color)
    r_txt = r_med - grueso / 2 - max(9, r * 0.1)
    _marcas(l, pal, cx, cy, r_txt, r, e["tope"])
    _cifras(l, pal, cx, cy, r, r_txt * 1.25 if r >= 70 else r_med * 1.3, e, color)


def _vel_aguja(l, pal, w, h, e):
    """Esfera clásica: rayas, números y una aguja; la cifra abajo, en el hueco del arco."""
    cx, cy, r = vm.geometria(w, h)
    frac = vm.fraccion(e["valor"], e["tope"])
    color = pal.get(e["color"], pal["azul"])
    r_ext = r - 4
    l.arco(cx, cy, r_ext, vm.angulo(0), vm.angulo(1), max(2.0, r * 0.025), con_alfa(pal["tenue"], 0.25), False)
    if frac > 0:
        l.arco(cx, cy, r_ext, vm.angulo(0), vm.angulo(frac), max(3.0, r * 0.05), color, False)
    # Zona roja al final de la escala.
    l.arco(cx, cy, r_ext - r * 0.07, vm.angulo(0.88), vm.angulo(1), max(2.0, r * 0.04), con_alfa(pal["rojo"], 0.7), False)
    for i in range(41):
        f = i / 40
        a = vm.angulo(f)
        largo, grosor, alfa = (0.13, 0.025, 0.85) if i % 5 == 0 else (0.06, 0.012, 0.45)
        x0, y0 = cx + math.cos(a) * r_ext * (1 - largo - 0.04), cy + math.sin(a) * r_ext * (1 - largo - 0.04)
        x1, y1 = cx + math.cos(a) * r_ext * 0.96, cy + math.sin(a) * r_ext * 0.96
        l.linea(x0, y0, x1, y1, max(1.0, r * grosor), con_alfa(pal["tenue"], alfa), False)
    _progreso_fase(l, pal, cx, cy, r - 1, e, color)
    _marcas(l, pal, cx, cy, r_ext * 0.68, r, e["tope"])
    # Aguja con un poco de cola y el eje.
    a = vm.angulo(frac)
    largo = r_ext * 0.86
    l.linea(cx - math.cos(a) * r * 0.12, cy - math.sin(a) * r * 0.12,
            cx + math.cos(a) * largo, cy + math.sin(a) * largo, max(2.0, r * 0.03), color, True)
    l.circulo(cx, cy, max(4.0, r * 0.07), color)
    l.circulo(cx, cy, max(2.0, r * 0.035), pal["texto"])
    # Cifra y unidad en el hueco de abajo; la fase sobre el eje.
    alto = r * 0.24
    px = px_que_quepa(l, e["texto"], r * 0.9, alto)
    _, ch = l.medir(e["texto"], px, "fino")
    y = cy + r * 0.2
    l.texto(e["texto"], cx - r, y, 2 * r, ch, px, pal["texto"], "fino", 0.5, 0.0)
    chico = max(9.0, r * 0.11)
    _, uh = l.medir(e["unidad"], chico, "normal")
    if y + ch + uh <= h:
        l.texto(e["unidad"], cx - r, y + ch, 2 * r, uh, chico, pal["gris"], "normal", 0.5, 0.0)
    if e["fase"] and r >= 60:
        _, fh = l.medir(e["fase"], chico, "negrita")
        l.texto(e["fase"], cx - r, cy - r * 0.32 - fh, 2 * r, fh, chico, color, "negrita", 0.5, 1.0)


def _vel_anillo(l, pal, w, h, e):
    """Anillo grueso de extremos redondos: moderno y limpio."""
    cx, cy, r = vm.geometria(w, h)
    grueso = max(7.0, r * 0.16)
    r_med = r - grueso / 2 - 3
    frac = vm.fraccion(e["valor"], e["tope"])
    color = pal.get(e["color"], pal["azul"])
    l.arco(cx, cy, r_med, vm.angulo(0), vm.angulo(1), grueso, con_alfa(pal["tenue"], 0.09), True)
    if frac > 0.002:
        # Degradado a trozos: de más oscuro a su color.
        trozos = max(2, int(48 * frac))
        oscuro = mezcla(color, (0, 0, 0), 0.4)
        for i in range(trozos):
            f0, f1 = frac * i / trozos, frac * (i + 1) / trozos
            c = mezcla(oscuro, color, (i + 1) / trozos)
            l.arco(cx, cy, r_med, vm.angulo(f0), vm.angulo(f1) + 0.01, grueso, c, i in (0, trozos - 1))
    if e["progreso"] is not None:
        r_in = r_med - grueso / 2 - 5
        l.arco(cx, cy, r_in, vm.angulo(0), vm.angulo(1), 2, con_alfa(pal["tenue"], 0.1), True)
        if e["progreso"] > 0:
            l.arco(cx, cy, r_in, vm.angulo(0), vm.angulo(min(1, e["progreso"])), 2, con_alfa(color, 0.8), True)
    _cifras(l, pal, cx, cy, r, r_med * 1.2, e, color, 0.34)


# --- relojes ----------------------------------------------------------------------

ESTILOS_NUEVOS = (("anillos", "Anillos"), ("binario", "Binario"), ("nixie", "Tubos Nixie"),
                  ("flip", "Tarjetas (flip)"), ("led", "LED de 7 segmentos"))

# Alto natural de cada uno (el mínimo es algo más de la mitad).
ALTOS = {"anillos": 200, "binario": 150, "nixie": 120, "flip": 120, "led": 110}


def reloj(l, pal, w, h, ahora, o, fecha, estilo):
    """o: opciones del reloj (h24, segundos); fecha: el texto de la fecha ya traducido."""
    {"anillos": _anillos, "binario": _binario, "nixie": _nixie, "flip": _flip,
     "led": _led}[estilo](l, pal, w, h, ahora, o, fecha)


def _hora12(ahora, o):
    return ahora.hour if o["h24"] else (ahora.hour % 12 or 12)


def _digitos(ahora, o):
    """["HH", "MM"] y "SS" si se muestran los segundos."""
    partes = [f"{_hora12(ahora, o):02d}", f"{ahora.minute:02d}"]
    if o["segundos"]:
        partes.append(f"{ahora.second:02d}")
    return partes


def _alto_fecha(o, h, umbral, alto):
    """Alto de la franja de la fecha: 0 si está oculta o no cabe. La hora va siempre
    centrada en el widget: se le deja el mismo margen arriba que la fecha ocupa abajo."""
    return alto if o.get("fecha", True) and h > umbral else 0


def _pie(l, pal, w, h, alto, fecha, ahora, o):
    """La fecha (y AM/PM) en una franja de abajo si hay sitio."""
    if alto <= 0:
        return
    texto = fecha + ("" if o["h24"] else (" · AM" if ahora.hour < 12 else " · PM"))
    px = min(16.0, alto * 0.6)
    tw, _ = l.medir(texto, px, "normal")
    if tw > w:
        px *= w / tw * 0.96
    l.texto(texto, 0, h - alto, w, alto, px, pal["gris"], "normal")


def _anillos(l, pal, w, h, ahora, o, fecha):
    """Tres anillos que se llenan: horas (fuera), minutos y segundos; la hora en medio."""
    alto_fecha = _alto_fecha(o, h, 170, 20)
    r = min(w, h - 2 * alto_fecha) / 2 - 4
    cx, cy = w / 2, h / 2
    grueso = max(4.0, r * 0.11)
    hueco = grueso * 0.45
    minuto = ahora.minute + (ahora.second + ahora.microsecond / 1e6) / 60
    anillos = [((ahora.hour % 12 + minuto / 60) / 12, pal["azul"]), (minuto / 60, pal["morado"])]
    if o["segundos"]:
        anillos.append(((ahora.second + ahora.microsecond / 1e6) / 60, pal["verde"]))
    arriba = -math.pi / 2
    for i, (frac, color) in enumerate(anillos):
        ri = r - grueso / 2 - i * (grueso + hueco)
        l.arco(cx, cy, ri, 0, 2 * math.pi, grueso, con_alfa(color, 0.14), False)
        if frac > 0.003:
            l.arco(cx, cy, ri, arriba, arriba + 2 * math.pi * frac, grueso, color, True)
    r_libre = r - len(anillos) * (grueso + hueco)
    texto = f"{_hora12(ahora, o)}:{ahora.minute:02d}" if not o["h24"] else f"{ahora.hour:02d}:{ahora.minute:02d}"
    px = px_que_quepa(l, texto, r_libre * 1.6, r_libre * 0.6)
    _, th = l.medir(texto, px, "fino")
    l.texto(texto, cx - r_libre, cy - th / 2, 2 * r_libre, th, px, pal["texto"], "fino")
    _pie(l, pal, w, h, alto_fecha, fecha, ahora, o)


def _binario(l, pal, w, h, ahora, o, fecha):
    """Reloj binario (BCD): una columna por cifra; cada punto encendido suma 8, 4, 2 o 1."""
    cifras = "".join(_digitos(ahora, o))
    bits = [2, 4, 3, 4, 3, 4][:len(cifras)]  # cuántos puntos necesita cada columna
    alto_etiq = 16 if h > 110 else 0
    alto_fecha = _alto_fecha(o, h, 170, 18)
    zona = h - alto_etiq - 2 * alto_fecha
    grupos = len(cifras) // 2
    sep = 0.6  # hueco extra entre horas, minutos y segundos (en columnas)
    col = min(w / (len(cifras) + sep * (grupos - 1)), zona / 4)
    rad = col * 0.32
    total = col * (len(cifras) + sep * (grupos - 1))
    x0 = (w - total) / 2
    y0 = (h - 4 * col - alto_etiq) / 2
    for i, (c, n) in enumerate(zip(cifras, bits)):
        x = x0 + col * (i + sep * (i // 2)) + col / 2
        valor = int(c)
        for fila in range(4):
            peso = 8 >> fila
            if 4 - fila > n:
                continue  # ese bit no hace falta en esta columna
            y = y0 + col * fila + col / 2
            encendido = valor & peso
            color = pal["azul"] if encendido else con_alfa(pal["tenue"], 0.1)
            if encendido:
                l.circulo(x, y, rad * 1.45, con_alfa(pal["azul"], 0.18))
            l.circulo(x, y, rad, color)
        if alto_etiq:
            l.texto(c, x - col / 2, y0 + 4 * col + 2, col, alto_etiq, min(13.0, alto_etiq * 0.8), pal["gris"], "normal")
    _pie(l, pal, w, h, alto_fecha, fecha, ahora, o)


NIXIE_POR_DEFECTO = "#ff8529"  # el naranja del neón de verdad
# Colores para elegir rápido (clic derecho en el reloj); en Configuración, cualquiera.
COLORES_NIXIE = (("#ff8529", "Naranja"), ("#5ad1ff", "Azul hielo"), ("#4dff88", "Verde"),
                 ("#ff4fa3", "Rosa"), ("#b77bff", "Violeta"), ("#ff4040", "Rojo"))


def _rgb(hexa):
    hexa = (hexa or NIXIE_POR_DEFECTO).lstrip("#")
    try:
        return tuple(int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return _rgb(NIXIE_POR_DEFECTO)


def _nixie(l, pal, w, h, ahora, o, fecha):
    """Tubos Nixie: cristal oscuro, la cifra "fantasma" y la de verdad brillando (naranja,
    o el color que se elija en o["nixie"])."""
    color = _rgb(o.get("nixie"))
    nucleo = mezcla(color, (1, 1, 1), 0.4)  # el centro de la cifra, casi blanco
    partes = _digitos(ahora, o)
    alto_fecha = _alto_fecha(o, h, 150, 18)
    zona = h - 2 * alto_fecha - 4
    n = len(partes) * 2
    puntos = len(partes) - 1
    ancho_tubo = min((w - 8) / (n + puntos * 0.45 + (n - 1) * 0.12), zona * 0.62)
    alto_tubo = min(zona, ancho_tubo / 0.62)
    gap = ancho_tubo * 0.12
    total = n * ancho_tubo + (n - 1) * gap + puntos * ancho_tubo * 0.45
    x = (w - total) / 2
    y = (h - alto_tubo) / 2
    px = alto_tubo * 0.78
    for k, parte in enumerate(partes):
        for c in parte:
            r = ancho_tubo * 0.42
            l.rect(x, y, ancho_tubo, alto_tubo, r, (0.10, 0.07, 0.06, 0.75))
            l.rect(x + 1, y + 1, ancho_tubo - 2, alto_tubo * 0.35, r, (1, 1, 1, 0.05))  # reflejo del cristal
            l.texto("8", x, y, ancho_tubo, alto_tubo, px, con_alfa(mezcla(color, (1, 1, 1), 0.15), 0.08), "normal")
            # Brillo: la cifra repetida alrededor con poca opacidad.
            halo = max(1.0, px * 0.035)
            for dx, dy in ((halo, 0), (-halo, 0), (0, halo), (0, -halo),
                           (halo * 0.7, halo * 0.7), (-halo * 0.7, -halo * 0.7)):
                l.texto(c, x + dx, y + dy, ancho_tubo, alto_tubo, px, con_alfa(color, 0.18), "normal")
            l.texto(c, x, y, ancho_tubo, alto_tubo, px, nucleo, "normal")
            x += ancho_tubo + gap
        if k < len(partes) - 1:
            sep = ancho_tubo * 0.45
            for f in (0.36, 0.64):
                l.circulo(x - gap / 2 + sep / 2, y + alto_tubo * f, max(1.5, ancho_tubo * 0.06), color)
            x += sep
    _pie(l, pal, w, h, alto_fecha, fecha, ahora, o)


def _flip(l, pal, w, h, ahora, o, fecha):
    """Reloj de tarjetas abatibles: una tarjeta por par de cifras, partida por la mitad."""
    partes = _digitos(ahora, o)[:2]
    seg = f"{ahora.second:02d}" if o["segundos"] else ""
    alto_fecha = _alto_fecha(o, h, 150, 18)
    zona = h - 2 * alto_fecha - 6
    gap = max(6.0, w * 0.03)
    extra = 0.42 if seg else 0  # los segundos, en una tarjeta pequeña
    ancho = min((w - 8 - gap * (1 + (1 if seg else 0))) / (2 + extra), zona * 1.05)
    alto = min(zona, ancho * 0.95)
    total = ancho * (2 + extra) + gap * (1 + (1 if seg else 0))
    x = (w - total) / 2
    y = (h - alto) / 2
    fondo = mezcla(pal["tenue"], (0, 0, 0), 0.82)
    for texto, ancho_t, alto_t in [(p, ancho, alto) for p in partes] + ([(seg, ancho * extra, alto * 0.5)] if seg else []):
        yt = y + (alto - alto_t)
        r = max(4.0, ancho_t * 0.07)
        l.rect(x, yt, ancho_t, alto_t, r, (*fondo, 0.92))
        l.rect(x, yt, ancho_t, alto_t / 2, r, (1, 1, 1, 0.045))  # mitad de arriba algo más clara
        px = px_que_quepa(l, texto, ancho_t * 0.86, alto_t * 0.72, "negrita")
        l.texto(texto, x, yt, ancho_t, alto_t, px, pal["texto"], "negrita")
        # La raja del medio y las bisagras.
        l.rect(x, yt + alto_t / 2 - max(1.0, alto_t * 0.012), ancho_t, max(2.0, alto_t * 0.024), 0, (0, 0, 0, 0.55))
        for bx in (x + ancho_t * 0.04, x + ancho_t * 0.96 - max(2.0, ancho_t * 0.025)):
            l.rect(bx, yt + alto_t * 0.44, max(2.0, ancho_t * 0.025), alto_t * 0.12, 1, (0, 0, 0, 0.6))
        x += ancho_t + gap
    _pie(l, pal, w, h, alto_fecha, fecha, ahora, o)


# Segmentos encendidos de cada cifra (a b c d e f g, como en los displays de siempre).
SEGMENTOS = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd",
             "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg"}


def _segmento(l, nombre, x, y, cw, ch, t, color):
    """Un segmento hexagonal de una cifra de cw x ch con grosor t."""
    m = t / 2
    horizontal = {"a": y, "g": y + ch / 2, "d": y + ch}
    if nombre in horizontal:
        yy = horizontal[nombre]
        x0, x1 = x + m + 1, x + cw - m - 1
        l.poligono([(x0, yy), (x0 + m, yy - m), (x1 - m, yy - m), (x1, yy), (x1 - m, yy + m), (x0 + m, yy + m)], color)
        return
    xx = x + cw if nombre in "bc" else x
    arriba = nombre in "bf"
    y0 = (y if arriba else y + ch / 2) + m + 1
    y1 = (y + ch / 2 if arriba else y + ch) - m - 1
    l.poligono([(xx, y0), (xx + m, y0 + m), (xx + m, y1 - m), (xx, y1), (xx - m, y1 - m), (xx - m, y0 + m)], color)


def _led(l, pal, w, h, ahora, o, fecha):
    """Display LED de 7 segmentos con los segmentos apagados en sombra."""
    partes = _digitos(ahora, o)
    principal = "".join(partes[:2])
    seg = partes[2] if len(partes) > 2 else ""
    alto_fecha = _alto_fecha(o, h, 140, 18)
    zona = h - 2 * alto_fecha - 8

    # Piezas en unidades del alto de una cifra: (tipo, x, ancho, alto, texto).
    piezas, x = [], 0.0
    for i, c in enumerate(principal):
        piezas.append(("cifra", x, 0.55, 1.0, c))
        x += 0.55
        if i == 1:
            piezas.append(("puntos", x + 0.15, 0, 1.0, ""))
            x += 0.3
        elif i < 3:
            x += 0.18
    if seg:
        x += 0.22
        for i, c in enumerate(seg):
            piezas.append(("cifra", x, 0.55 * 0.5, 0.5, c))
            x += 0.55 * 0.5 + (0.09 if i == 0 else 0)
    margen = 0.12  # los segmentos sobresalen medio grosor por los lados
    ch = min(zona, w / (x + 2 * margen))
    t = max(2.0, ch * 0.11)
    x0 = (w - x * ch) / 2
    y = (h - ch) / 2
    color = pal["azul"]
    sombra = con_alfa(pal["tenue"], 0.06)
    for tipo, px, pw, ph, c in piezas:
        if tipo == "puntos":  # los dos puntos, que parpadean con los segundos
            encendidos = ahora.second % 2 == 0
            for f in (0.32, 0.68):
                l.circulo(x0 + px * ch, y + ch * f, t * 0.6, color if encendidos else sombra)
            continue
        alto = ph * ch
        grosor = t if ph == 1.0 else max(1.5, t * 0.6)
        for s_ in "abcdefg":
            _segmento(l, s_, x0 + px * ch, y + ch - alto, pw * ch, alto, grosor,
                      color if s_ in SEGMENTOS[c] else sombra)
    _pie(l, pal, w, h, alto_fecha, fecha, ahora, o)
