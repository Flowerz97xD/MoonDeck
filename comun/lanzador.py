"""Widget de aplicaciones (lanzador): lo que comparten Linux y Windows.

Cada app guardada es {"id", "nombre"}: en Linux el id es el del .desktop; en Windows,
la ruta del acceso directo (.lnk) o del .exe. Los iconos se dibujan con sus colores o
teñidos con un color del tema (manteniendo sus luces y sombras).
"""

import os

TAM = 40     # lado del icono
HUECO = 12   # separación entre iconos

COLORES_ICONOS = (("original", "Colores originales"), ("acento", "Color de acento"), ("texto", "Color del texto"))


def rejilla(n, ancho, alto=0):
    """Posición (x, y) de cada uno de los n iconos y el alto que ocupan. Cada fila va
    centrada (también la última, aunque esté a medias) y, si sobra alto, el bloque
    entero queda centrado en vertical."""
    cols = max(1, (int(ancho) + HUECO) // (TAM + HUECO))
    filas = -(-n // cols) if n else 0
    ocupado = max(0, filas * (TAM + HUECO) - HUECO)
    y0 = max(0, (alto - ocupado) / 2)
    pos = []
    for i in range(n):
        fila, col = divmod(i, cols)
        en_fila = min(cols, n - fila * cols)
        x0 = (ancho - (en_fila * TAM + (en_fila - 1) * HUECO)) / 2
        pos.append((x0 + col * (TAM + HUECO), y0 + fila * (TAM + HUECO)))
    return pos, ocupado


def tenir_icono(rgba, color):
    """Tiñe un icono (bytes RGBA sin premultiplicar) con un color: las zonas oscuras
    quedan en el color apagado y las claras en el color aclarado. Devuelve bytes nuevos."""
    cr, cg, cb = (c * 255 for c in color[:3])
    tabla = []
    for lum in range(256):
        t = lum / 255
        if t < 0.6:
            f = 0.35 + t / 0.6 * 0.65
            tabla.append((round(cr * f), round(cg * f), round(cb * f)))
        else:
            m = (t - 0.6) / 0.4 * 0.55  # hacia el blanco
            tabla.append(tuple(round(c + (255 - c) * m) for c in (cr, cg, cb)))
    salida = bytearray(rgba)
    for i in range(0, len(salida), 4):
        if salida[i + 3]:
            lum = (salida[i] * 77 + salida[i + 1] * 150 + salida[i + 2] * 29) >> 8
            salida[i], salida[i + 1], salida[i + 2] = tabla[lum]
    return bytes(salida)


def apps_windows():
    """Los accesos directos del menú Inicio (del usuario y de todos): [{"id", "nombre"}]."""
    carpetas = [os.path.join(os.environ.get(v, ""), "Microsoft", "Windows", "Start Menu", "Programs")
                for v in ("APPDATA", "PROGRAMDATA")]
    apps = {}
    for carpeta in carpetas:
        for raiz, _dirs, archivos in os.walk(carpeta):
            for a in archivos:
                nombre, ext = os.path.splitext(a)
                if ext.lower() != ".lnk" or "uninstall" in nombre.lower() or "desinstalar" in nombre.lower():
                    continue
                apps.setdefault(nombre.lower(), {"id": os.path.join(raiz, a), "nombre": nombre})
    return sorted(apps.values(), key=lambda a: a["nombre"].lower())
