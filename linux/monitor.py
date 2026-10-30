#!/usr/bin/env python3
"""MoonDeck: widgets de cristal para el escritorio de Linux (COSMIC)."""

import calendar
import datetime
import faulthandler
import json
import math
import os
import re
import sys
import threading
import time
import traceback
import types
from collections import deque
from zoneinfo import ZoneInfo

# Ejecutando desde el repositorio, los módulos compartidos están en ../comun
# (en lo instalado van todos juntos en la misma carpeta).
_COMUN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "comun")
if os.path.isdir(_COMUN):
    sys.path.insert(1, _COMUN)

# ---------------------------------------------------------------------------
# Registro de errores: todo va a ~/.config/MoonDeck/error.log
# ---------------------------------------------------------------------------
CARPETA = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "MoonDeck")

# Antes se llamaba "Monitor de Hardware": la primera vez se trae su configuración.
_VIEJA = os.path.join(os.path.dirname(CARPETA), "MonitorHardware")
if not os.path.exists(CARPETA) and os.path.isdir(_VIEJA):
    import shutil
    shutil.copytree(_VIEJA, CARPETA, ignore=shutil.ignore_patterns("error.log"))
LOG = os.path.join(CARPETA, "error.log")
os.makedirs(CARPETA, exist_ok=True)
import instancia  # noqa: E402
if not instancia.unica(CARPETA):
    sys.exit(0)  # ya hay un MoonDeck abierto: se le ha pedido que se muestre
instancia.quieren_verme(CARPETA)  # un aviso viejo, de antes de abrir esta
_log = open(LOG, "w", encoding="utf-8", buffering=1)
faulthandler.enable(_log)  # también registra cierres bruscos


def log(*partes):
    texto = time.strftime("%H:%M:%S ") + " ".join(str(p) for p in partes)
    _log.write(texto + "\n")
    if sys.stderr:
        print(texto, file=sys.stderr)


_error_mostrado = False


def aviso_error(titulo, texto):
    try:
        d = Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE,
                              text=titulo, secondary_text=texto)
        d.run()
        d.destroy()
    except Exception:  # noqa: BLE001 - sin GTK no hay ventana que mostrar
        pass


def _excepthook(tipo, valor, tb):
    global _error_mostrado
    detalle = "".join(traceback.format_exception(tipo, valor, tb))
    log("ERROR NO CONTROLADO\n" + detalle)
    if not _error_mostrado and getattr(sys, "_arrancando", True):
        _error_mostrado = True
        aviso_error("MoonDeck - error", f"{tipo.__name__}: {valor}\n\nDetalle guardado en:\n{LOG}")


sys.excepthook = _excepthook
log("Iniciando. Python", sys.version.split()[0], "|", os.environ.get("XDG_CURRENT_DESKTOP", "?"),
    "|", os.environ.get("XDG_SESSION_TYPE", "?"))

try:
    import cairo
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("GdkPixbuf", "2.0")
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    gi.require_version("Gio", "2.0")
    from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango, PangoCairo

    try:
        gi.require_version("GtkLayerShell", "0.1")
        from gi.repository import GtkLayerShell
        CAPAS = GtkLayerShell.is_supported()
    except (ValueError, ImportError):
        GtkLayerShell, CAPAS = None, False
    try:
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as AppIndicator
    except (ValueError, ImportError):
        AppIndicator = None

    from glass import Blur, rounded_rects, superficie
    from escritorios import Escritorios, vista_general
    from multimedia import Dispositivos, Mezclador, Reproductores
    from tiempo import CIUDAD_POR_DEFECTO, Tiempo, buscar_ciudades, describir
    import tema as temas
    import idioma
    from idioma import _
    from actualizar import Actualizador
    from version import REPO, VERSION
    from sensores import Sampler
    import velocimetro
    import esferas
    import packs
except Exception:
    _excepthook(*sys.exc_info())
    sys.exit(1)

# ---------------------------------------------------------------------------
# Ajustes
# ---------------------------------------------------------------------------
EFECTO = "cristal"     # "cristal" (desenfoque de COSMIC) o "ninguno" (fondo oscuro translúcido)
INTERVALO = 1.0        # segundos entre lecturas
HISTORIAL = 120        # muestras en las gráficas
ANCHO = 340            # ancho de cada widget
SEPARACION = 14        # espacio entre widgets al colocarlos
COLUMNAS = 4
RECOLOCAR_AL_ABRIR = False  # True: al abrir siempre en cuadrícula; False: donde los dejaste
MAX_REPRODUCTORES = 3      # cuántas apps con música se muestran a la vez
MAX_APPS_VOLUMEN = 8       # cuántas apps se muestran en el mezclador
OPACIDADES = (100, 90, 80, 70, 60, 50, 40)
RADIO = 12
NEON_MARGEN = 10  # sitio para el halo del neón alrededor de la tarjeta


def hex_rgba(h):
    r, g, b, a = bytes.fromhex(h)
    return r / 255, g / 255, b / 255, a / 255


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


COLORES = {
    "azul": hex_rgb("4d8dff"), "naranja": hex_rgb("ff9e43"), "verde": hex_rgb("2ecc71"),
    "morado": hex_rgb("a873ff"), "rojo": hex_rgb("ff5c5c"), "amarillo": hex_rgb("f1c40f"),
}

# Colores del tema en uso; los cambia aplicar_colores() (ventana de Configuración).
BLANCO = GRIS = GRIS_CLARO = NORMAL = CLARO = TITULO = TENUE = (1, 1, 1)
SOMBRA = 0.22   # fondo de las gráficas
ESCALA = 1.0    # tamaño de letra


def aplicar_colores(t):
    global BLANCO, GRIS, GRIS_CLARO, NORMAL, CLARO, TITULO, TENUE, SOMBRA, ESCALA
    g = t["global"]
    COLORES["azul"] = hex_rgb(g["acento"])
    BLANCO, GRIS = hex_rgb(g["texto"]), hex_rgb(g["texto_sec"])
    CLARO = temas.mezcla(BLANCO, GRIS, 0.1)
    NORMAL = temas.mezcla(BLANCO, GRIS, 0.25)
    GRIS_CLARO = temas.mezcla(BLANCO, GRIS, 0.45)
    TITULO = temas.mezcla(BLANCO, GRIS, 0.7)
    TENUE = BLANCO  # líneas y fondos finos: el color del texto con poca opacidad
    SOMBRA = 0.22 if temas.luminancia(BLANCO) > 0.5 else 0.07
    ESCALA = max(0.6, min(1.8, float(g["escala"])))


aplicar_colores(temas.completo(None))

CONFIG = os.path.join(CARPETA, "config.json")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def fmt_bytes(n, rate=False):
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    i = 0
    n = float(n)
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    s = f"{n:.0f} {units[i]}" if i == 0 else f"{n:.1f} {units[i]}"
    return s + "/s" if rate else s


def tema_claro():
    return SOMBRA < 0.2  # texto oscuro: fondo claro


def color_temp(t):
    """Verde, amarillo o rojo según la temperatura (más oscuros en los temas claros)."""
    claro = tema_claro()
    if t is None:
        return "#6b7484" if claro else "#8b94a4"
    if t < 60:
        return "#178a4a" if claro else "#2ecc71"
    if t < 80:
        return "#a87a00" if claro else "#f1c40f"
    return "#d33a3a" if claro else "#ff5c5c"


def etiqueta(texto="", estilo="sub", envolver=False):
    """Etiqueta con estilo (el texto se traduce). El ancho lo decide la tarjeta: los textos
    largos se cortan con "…"."""
    lb = Gtk.Label(label=_(texto), xalign=0)
    lb.get_style_context().add_class(estilo)
    if envolver:
        lb.set_line_wrap(True)
        lb.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    else:
        lb.set_ellipsize(Pango.EllipsizeMode.END)
    lb.set_max_width_chars(1)  # que el texto no ensanche la tarjeta
    lb.set_hexpand(True)
    return lb


def poner_texto(label, texto):
    """Cambia el texto solo si cambia (evita redibujos y recalcular tamaños)."""
    if label.get_text() != texto:
        label.set_text(texto)

def poner_visible(w, ver):
    """Muestra u oculta, pero sin volver a enseñar lo que la tarjeta quitó por falta de sitio:
    se vería un instante antes de que lo quite otra vez (parpadeo). Ya lo devuelve ella si cabe."""
    if getattr(w, "_quitado", False):
        if ver:
            return
        w._quitado = False
    w.set_visible(ver)



def poner_marcado(label, marcado):
    if getattr(label, "_marcado", None) != marcado:
        label._marcado = marcado
        label.set_markup(marcado)


def caja(vertical=True, espacio=0):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL,
                   spacing=espacio)


def boton_icono(icono, tam=Gtk.IconSize.BUTTON):
    b = Gtk.Button()
    b.set_relief(Gtk.ReliefStyle.NONE)
    b.get_style_context().add_class("plano")
    b.set_image(Gtk.Image.new_from_icon_name(icono, tam))
    b.set_can_focus(False)
    return b


def poner_icono(boton, icono, tam=Gtk.IconSize.BUTTON):
    if getattr(boton, "_icono", None) != icono:
        boton._icono = icono
        boton.set_image(Gtk.Image.new_from_icon_name(icono, tam))


def boton_texto(texto, estilo="normal"):
    b = Gtk.Button(label=_(texto))
    b.get_style_context().add_class(estilo)
    b.set_can_focus(False)
    return b


def clases(widget, **activas):
    ctx = widget.get_style_context()
    for nombre, si in activas.items():
        (ctx.add_class if si else ctx.remove_class)(nombre)


# --- texto en los dibujos (Pango) ---

def capa_texto(widget, cr, texto, px, peso=Pango.Weight.NORMAL):
    lay = PangoCairo.create_layout(cr)
    fd = widget.get_pango_context().get_font_description().copy()
    fd.set_absolute_size(max(6, px * ESCALA) * Pango.SCALE)
    fd.set_weight(peso)
    lay.set_font_description(fd)
    attrs = Pango.AttrList()
    attrs.insert(Pango.attr_font_features_new("tnum"))  # cifras de ancho fijo: no bailan al cambiar
    lay.set_attributes(attrs)
    lay.set_text(texto, -1)
    return lay


def pintar_texto(cr, lay, x, y, w, h, color, h_al=0.0, v_al=0.5, recortar=False):
    if recortar:
        lay.set_width(int(max(1, w) * Pango.SCALE))
        lay.set_ellipsize(Pango.EllipsizeMode.MIDDLE if recortar == "medio" else Pango.EllipsizeMode.END)
    lw, lh = lay.get_pixel_size()
    if len(color) == 4:
        cr.set_source_rgba(*color)
    else:
        cr.set_source_rgb(*color)
    dx = (w - lw) * h_al
    cr.move_to(x + (max(0, dx) if recortar else dx), y + (h - lh) * v_al)
    PangoCairo.show_layout(cr, lay)
    return lw


def px_que_quepa(widget, cr, texto, ancho, alto, peso=Pango.Weight.LIGHT):
    """El tamaño de letra más grande con el que `texto` cabe en ancho x alto (alto = altura de las cifras)."""
    px = max(8, alto / 0.72)  # las cifras miden ~0.72 del tamaño de la fuente
    lay = capa_texto(widget, cr, texto, px, peso)
    w = lay.get_pixel_size()[0]
    if w > ancho:
        px = max(8, px * ancho / w)
    return px


class LienzoCairo:
    """Las operaciones de dibujo que usan los relojes y velocímetros comunes (esferas.py)."""

    PESOS = {"fino": Pango.Weight.LIGHT, "normal": Pango.Weight.NORMAL, "negrita": Pango.Weight.BOLD}

    def __init__(self, widget, cr):
        self.widget, self.cr = widget, cr

    def _color(self, c):
        (self.cr.set_source_rgba if len(c) == 4 else self.cr.set_source_rgb)(*c)

    def rect(self, x, y, w, h, radio, color):
        if radio:
            rect_redondeado(self.cr, x, y, w, h, radio)
        else:
            self.cr.rectangle(x, y, w, h)
        self._color(color)
        self.cr.fill()

    def circulo(self, cx, cy, r, color):
        self.cr.new_path()
        self.cr.arc(cx, cy, r, 0, 2 * math.pi)
        self._color(color)
        self.cr.fill()

    def arco(self, cx, cy, r, a0, a1, grosor, color, redondo=False):
        cr = self.cr
        cr.new_path()
        cr.arc(cx, cy, r, a0, a1)
        cr.set_line_width(grosor)
        cr.set_line_cap(cairo.LINE_CAP_ROUND if redondo else cairo.LINE_CAP_BUTT)
        self._color(color)
        cr.stroke()

    def linea(self, x0, y0, x1, y1, grosor, color, redondo=False):
        cr = self.cr
        cr.new_path()
        cr.move_to(x0, y0)
        cr.line_to(x1, y1)
        cr.set_line_width(grosor)
        cr.set_line_cap(cairo.LINE_CAP_ROUND if redondo else cairo.LINE_CAP_BUTT)
        self._color(color)
        cr.stroke()

    def poligono(self, puntos, color):
        cr = self.cr
        cr.new_path()
        cr.move_to(*puntos[0])
        for p in puntos[1:]:
            cr.line_to(*p)
        cr.close_path()
        self._color(color)
        cr.fill()

    def recortar(self, x, y, w, h, radio):
        """Lo que se dibuje hasta sin_recorte() no sale de este rectángulo redondeado."""
        self.cr.save()
        self.cr.new_path()
        if radio:
            rect_redondeado(self.cr, x, y, w, h, radio)
        else:
            self.cr.rectangle(x, y, w, h)
        self.cr.clip()

    def sin_recorte(self):
        self.cr.restore()

    _hojas = {}  # la hoja del dinosaurio ya teñida, por color

    def sprite(self, sx, sy, sw, sh, dx, dy, dw, dh, tinta=None):
        """Un trozo de la hoja del dinosaurio, escalado sin suavizar (pixel art)."""
        clave = tuple(round(c, 3) for c in tinta[:3]) if tinta else None
        if clave not in self._hojas:
            import dino_sprite
            import juegos
            cargador = GdkPixbuf.PixbufLoader()
            cargador.write(dino_sprite.PNG)
            cargador.close()
            pb = cargador.get_pixbuf()
            w, h, fila = pb.get_width(), pb.get_height(), pb.get_rowstride()
            crudo = pb.get_pixels()
            rgba = b"".join(crudo[y * fila:y * fila + w * 4] for y in range(h))
            datos = juegos.tinta_sprite(rgba, tinta)
            pb = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(datos), GdkPixbuf.Colorspace.RGB, True, 8, w, h, w * 4)
            self._hojas[clave] = Gdk.cairo_surface_create_from_pixbuf(pb, 1, None)
        cr = self.cr
        cr.save()
        cr.rectangle(dx, dy, dw, dh)
        cr.clip()
        ex, ey = dw / sw, dh / sh
        cr.translate(dx - sx * ex, dy - sy * ey)
        cr.scale(ex, ey)
        cr.set_source_surface(self._hojas[clave], 0, 0)
        cr.get_source().set_filter(cairo.FILTER_NEAREST)
        cr.paint()
        cr.restore()

    def medir(self, texto, px, peso="normal"):
        return capa_texto(self.widget, self.cr, texto, px / ESCALA, self.PESOS[peso]).get_pixel_size()

    def texto(self, texto, x, y, w, h, px, color, peso="normal", h_al=0.5, v_al=0.5):
        lay = capa_texto(self.widget, self.cr, texto, px / ESCALA, self.PESOS[peso])
        lw, lh = lay.get_pixel_size()
        self._color(color)
        self.cr.move_to(x + (w - lw) * h_al, y + (h - lh) * v_al)
        PangoCairo.show_layout(self.cr, lay)


def paleta():
    """Colores del tema en uso para los dibujos comunes."""
    return {"texto": BLANCO, "gris": GRIS, "tenue": TENUE, **COLORES}


# Las áreas de dibujo tienen su propia ventana de GDK: sin estos eventos, los clics
# sobre ellas no llegarían a la tarjeta (menú, arrastrar).
EVENTOS = Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.POINTER_MOTION_MASK


class Dibujo(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.add_events(EVENTOS)
        self.altos = None

    def poner_alto(self, minimo, natural=None):
        """Alto mínimo y natural: si la tarjeta va justa, encoge hasta el mínimo
        (antes que cortar los textos de debajo)."""
        self.altos = (minimo, max(minimo, natural or minimo))
        self.queue_resize()

    def do_get_preferred_height(self):
        return self.altos or Gtk.DrawingArea.do_get_preferred_height(self)


def fundido_al_desplazar(scroll, borde=22):
    """Lista desplazable sin barra: el contenido se funde arriba o abajo cuando queda
    más por ese lado (se pinta en un grupo y se aplica una máscara degradada)."""
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.EXTERNAL)
    adj = scroll.get_vadjustment()

    def antes(_w, cr):
        cr.push_group()
        return False

    def despues(w, cr):
        cr.set_source(cr.pop_group())
        h = w.get_allocated_height()
        arriba = adj.get_value() > 0.5
        abajo = adj.get_value() < adj.get_upper() - adj.get_page_size() - 0.5
        if not (arriba or abajo):
            cr.paint()
            return False
        f = min(0.45, borde / max(1, h))
        mascara = cairo.LinearGradient(0, 0, 0, h)
        for pos, alfa in ((0, 0 if arriba else 1), (f, 1), (1 - f, 1), (1, 0 if abajo else 1)):
            mascara.add_color_stop_rgba(pos, 0, 0, 0, alfa)
        cr.mask(mascara)
        return False
    scroll.connect("draw", antes)
    scroll.connect_after("draw", despues)
    adj.connect("value-changed", lambda _a: scroll.queue_draw())


def rect_redondeado(cr, x, y, w, h, r):
    r = max(0, min(r, w / 2, h / 2))
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


# ---------------------------------------------------------------------------
# Widgets de dibujo
# ---------------------------------------------------------------------------

class Grafica(Dibujo):
    """Gráfica de líneas con historial; escala fija (0-100) o automática."""

    def __init__(self, series, maximo=100.0, alto=80):
        super().__init__()
        self.poner_alto(28, alto)
        self.maximo = maximo
        self.series = [(COLORES[c], deque([0.0] * HISTORIAL, maxlen=HISTORIAL)) for c in series]
        self.connect("draw", self.dibujar)

    def push(self, *valores):
        for (_, datos), v in zip(self.series, valores):
            datos.append(v if v is not None else 0.0)
        self.queue_draw()

    def dibujar(self, _w, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        rect_redondeado(cr, 0, 0, w, h, 6)
        cr.set_source_rgba(0, 0, 0, SOMBRA)
        cr.fill()
        cr.set_source_rgba(*TENUE, 0.07)
        cr.set_line_width(1)
        for i in range(1, 4):
            y = int(h * i / 4) + 0.5
            cr.move_to(0, y)
            cr.line_to(w, y)
        cr.stroke()
        tope = self.maximo
        if tope is None:
            tope = max((max(d) for _, d in self.series), default=1.0)
            tope = max(tope * 1.15, 1.0)
        paso = w / (HISTORIAL - 1)
        for (r, g, b), datos in self.series:
            puntos = [(i * paso, h - min(v / tope, 1.0) * (h - 2) - 1) for i, v in enumerate(datos)]
            cr.move_to(*puntos[0])
            for p in puntos[1:]:
                cr.line_to(*p)
            camino = cr.copy_path()
            cr.line_to(w, h)
            cr.line_to(0, h)
            cr.close_path()
            cr.set_source_rgba(r, g, b, 0.16)
            cr.fill()
            cr.append_path(camino)
            cr.set_source_rgb(r, g, b)
            cr.set_line_width(1.6)
            cr.stroke()


class Barra(Dibujo):
    """Barra de progreso fina; sin color fijo, cambia de color al llenarse."""

    def __init__(self, alto=8, color=None):
        super().__init__()
        self.alto = alto
        self.color = color
        self.set_size_request(-1, alto)
        self.valor = 0.0
        self.connect("draw", self.dibujar)

    def set(self, v):
        if v != self.valor:
            self.valor = v
            self.queue_draw()

    def dibujar(self, _w, cr):
        w = self.get_allocated_width()
        r = self.alto / 2
        rect_redondeado(cr, 0, 0, w, self.alto, r)
        cr.set_source_rgba(*TENUE, 0.11)
        cr.fill()
        color = COLORES["azul"] if self.color == "acento" else self.color or (COLORES["azul"] if self.valor < 70 else
                               COLORES["amarillo"] if self.valor < 90 else COLORES["rojo"])
        ancho = w * min(max(self.valor, 0), 100) / 100
        if ancho > 0.5:
            rect_redondeado(cr, 0, 0, max(ancho, self.alto), self.alto, r)
            cr.set_source_rgb(*color)
            cr.fill()


class BarrasNucleos(Dibujo):
    """Barras verticales de uso por núcleo."""

    def __init__(self, n):
        super().__init__()
        self.valores = [0.0] * n
        self.poner_alto(16, 42)
        self.connect("draw", self.dibujar)

    def set(self, valores):
        self.valores = valores
        self.queue_draw()

    def dibujar(self, _w, cr):
        n = len(self.valores)
        gap = 3
        w, h = self.get_allocated_width(), self.get_allocated_height()
        bw = (w - gap * (n - 1)) / n
        for i, v in enumerate(self.valores):
            x = i * (bw + gap)
            cr.set_source_rgba(*TENUE, 0.085)
            cr.rectangle(x, 0, bw, h)
            cr.fill()
            cr.set_source_rgb(*(COLORES["azul"] if v < 60 else COLORES["naranja"] if v < 85 else COLORES["rojo"]))
            frac = min(v / 100, 1.0)
            cr.rectangle(x, h - frac * h, bw, frac * h)
            cr.fill()


def leyenda(*items):
    fila = caja(False, 12)
    for texto, color in items:
        r, g, b = COLORES[color]
        lb = Gtk.Label(xalign=0)
        lb.set_markup(f'<span foreground="#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}">●</span> '
                      + GLib.markup_escape_text(_(texto)))
        lb.get_style_context().add_class("dim")
        fila.pack_start(lb, False, False, 0)
    return fila


# ---------------------------------------------------------------------------
# Multimedia: reproductores y mezclador
# ---------------------------------------------------------------------------

def fmt_tiempo(seg):
    seg = int(seg)
    return f"{seg // 3600}:{seg % 3600 // 60:02d}:{seg % 60:02d}" if seg >= 3600 else f"{seg // 60}:{seg % 60:02d}"


class Portada(Dibujo):
    """Portada recortada en cuadrado con esquinas redondeadas (o una nota si no hay)."""

    TAM = 52

    def __init__(self):
        super().__init__()
        self.set_size_request(self.TAM, self.TAM)
        self.set_valign(Gtk.Align.START)
        self.pixbuf = None
        self.connect("draw", self.dibujar)

    def poner(self, datos):
        self.pixbuf = None
        if datos:
            try:
                cargador = GdkPixbuf.PixbufLoader()
                cargador.write(datos)
                cargador.close()
                img = cargador.get_pixbuf()
                pw, ph = img.get_width(), img.get_height()
                lado = min(pw, ph)
                tam = self.TAM * max(1, self.get_scale_factor())
                self.pixbuf = img.new_subpixbuf((pw - lado) // 2, (ph - lado) // 2, lado, lado).scale_simple(
                    tam, tam, GdkPixbuf.InterpType.BILINEAR)
            except GLib.Error:
                self.pixbuf = None
        self.queue_draw()

    def dibujar(self, _w, cr):
        tam = self.TAM
        rect_redondeado(cr, 0, 0, tam, tam, 6)
        cr.clip()
        if self.pixbuf:
            escala = self.pixbuf.get_width() / tam
            cr.save()
            cr.scale(1 / escala, 1 / escala)
            Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 0, 0)
            cr.paint()
            cr.restore()
        else:
            cr.set_source_rgba(*TENUE, 0.1)
            cr.paint()
            lay = capa_texto(self, cr, "♪", 22)
            pintar_texto(cr, lay, 0, 0, tam, tam, (*TENUE, 0.35), 0.5)


class BarraProgreso(Dibujo):
    """Progreso de la canción o el vídeo: clic o arrastrar para ir a otro punto."""

    ALTO = 14

    def __init__(self, al_mover, al_soltar):
        super().__init__()
        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.set_size_request(-1, self.ALTO)
        self.al_mover, self.al_soltar = al_mover, al_soltar
        self.valor = 0.0          # 0-1
        self.puede = False        # la app deja saltar
        self.encima = False
        self.arrastre = None      # fracción mientras se arrastra
        self.connect("draw", self.dibujar)
        self.connect("button-press-event", self._pulsar)
        self.connect("motion-notify-event", self._mover)
        self.connect("button-release-event", self._soltar)
        self.connect("enter-notify-event", lambda *_a: self._encima(True))
        self.connect("leave-notify-event", lambda *_a: self._encima(False))

    def set(self, valor, puede):
        if self.arrastre is None and (valor, puede) != (self.valor, self.puede):
            self.valor, self.puede = valor, puede
            self.queue_draw()

    def _frac(self, x):
        return min(max(x / max(1, self.get_allocated_width()), 0.0), 1.0)

    def _encima(self, si):
        self.encima = si
        ventana = self.get_window()
        if ventana:
            ventana.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), "pointer")
                               if si and self.puede else None)
        self.queue_draw()

    def _pulsar(self, _w, ev):
        tarjeta = self.get_ancestor(Tarjeta)
        if ev.button != 1 or not self.puede or (tarjeta and tarjeta.en_edicion()):
            return False  # el clic derecho (menú) y la edición del panel siguen a la tarjeta
        self.arrastre = self._frac(ev.x)
        self.al_mover(self.arrastre)
        self.queue_draw()
        return True

    def _mover(self, _w, ev):
        if self.arrastre is None:
            return False
        self.arrastre = self._frac(ev.x)
        self.al_mover(self.arrastre)
        self.queue_draw()
        return True

    def _soltar(self, _w, ev):
        if self.arrastre is None or ev.button != 1:
            return False
        self.valor = self._frac(ev.x)
        self.arrastre = None
        self.al_soltar(self.valor)
        self.queue_draw()
        return True

    def dibujar(self, _w, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        activo = self.puede and (self.encima or self.arrastre is not None)
        grosor = 6 if activo else 4
        y = (h - grosor) / 2
        rect_redondeado(cr, 0, y, w, grosor, grosor / 2)
        cr.set_source_rgba(*TENUE, 0.11)
        cr.fill()
        frac = self.valor if self.arrastre is None else self.arrastre
        if frac * w > 0.5:
            rect_redondeado(cr, 0, y, max(frac * w, grosor), grosor, grosor / 2)
            cr.set_source_rgb(*COLORES["verde"])
            cr.fill()
        if activo:
            x = min(max(frac * w, 6), w - 6)
            cr.arc(x, h / 2, 6, 0, 2 * math.pi)
            cr.set_source_rgb(*BLANCO)
            cr.fill()


class FilaReproductor(Gtk.Box):
    """Una app con música: portada, título, artista, progreso y controles."""

    def __init__(self, reproductores):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.rep = reproductores
        self.ident = None
        self.clave_portada = None
        self.pista_portada = None
        arriba = caja(False, 10)
        self.portada = Portada()
        arriba.pack_start(self.portada, False, False, 0)
        textos = caja(True, 1)
        self.titulo = etiqueta("", "sub")
        self.titulo.get_style_context().add_class("negrita")
        self.artista = etiqueta("", "dim")
        self.app = etiqueta("", "dim")
        for w in (self.titulo, self.artista, self.app):
            textos.pack_start(w, False, False, 0)
        arriba.pack_start(textos, True, True, 0)
        self.pack_start(arriba, False, False, 0)

        abajo = caja(False, 2)
        self.tiempo = etiqueta("", "dim")
        abajo.pack_start(self.tiempo, True, True, 0)
        self.b_anterior = boton_icono("media-skip-backward-symbolic")
        self.b_play = boton_icono("media-playback-start-symbolic")
        self.b_siguiente = boton_icono("media-skip-forward-symbolic")
        for b, accion in ((self.b_anterior, "anterior"), (self.b_play, "play_pausa"),
                          (self.b_siguiente, "siguiente")):
            b.connect("clicked", lambda _b, a=accion: self.rep.orden(self.ident, a))
            abajo.pack_start(b, False, False, 0)
        self.pack_start(abajo, False, False, 0)
        self.progreso = BarraProgreso(self._previsualizar, self._buscar)
        self.pack_start(self.progreso, False, False, 0)
        self.dur = 0
        self.buscado = None  # (segundo, cuándo): hasta que la app informe de la posición nueva
        self.show_all()

    def _previsualizar(self, frac):
        poner_texto(self.tiempo, f"{fmt_tiempo(frac * self.dur)} / {fmt_tiempo(self.dur)}")

    def _buscar(self, frac):
        self.buscado = (frac * self.dur, time.monotonic())
        self.rep.buscar(self.ident, frac * self.dur)

    def actualizar(self, d):
        self.ident = d["id"]
        self.dur = d["dur"]
        pos = d["pos"]
        if self.buscado:
            seg, cuando = self.buscado
            pasado = time.monotonic() - cuando
            if abs(pos - seg) < 2.5 or pasado > 3:
                self.buscado = None
            else:  # la app aún no ha dicho la posición nueva: no volver atrás un momento
                pos = min(seg + (pasado if d["reproduciendo"] else 0), d["dur"])
        poner_texto(self.titulo, d["titulo"])
        self.titulo.set_tooltip_text(d["titulo"] if len(d["titulo"]) > 30 else None)
        poner_texto(self.artista, d["artista"] or "—")
        poner_texto(self.app, d["app"])
        if self.progreso.arrastre is None:
            poner_texto(self.tiempo, f"{fmt_tiempo(pos)} / {fmt_tiempo(d['dur'])}" if d["dur"] > 0 else "")
        self.progreso.set(pos / d["dur"] if d["dur"] > 0 else 0, d.get("buscar", False))
        self.progreso.set_tooltip_text(None if d.get("buscar") else _("Esta app no deja saltar a otro punto"))
        self.progreso.set_visible(d["dur"] > 0)
        poner_icono(self.b_play, "media-playback-pause-symbolic" if d["reproduciendo"]
                    else "media-playback-start-symbolic")
        self.b_anterior.set_sensitive(d["anterior"])
        self.b_siguiente.set_sensitive(d["siguiente"])
        self.b_play.set_sensitive(d["play_pausa"])
        # Firefox quita la portada de los metadatos al poco de ponerla: mientras siga la misma
        # canción, se queda la que había.
        pista = (d["id"], d["titulo"], d["artista"])
        if not d["portada"] and self.clave_portada and pista == self.pista_portada:
            return
        if d["portada"] != self.clave_portada:
            datos = self.rep.portada(d["portada"])
            if datos or not d["portada"]:
                self.clave_portada = d["portada"]
                self.pista_portada = pista
            self.portada.poner(datos)


class FilaVolumen(Gtk.Box):
    """Nombre, deslizador de volumen, porcentaje y botón de silencio."""

    def __init__(self, mezclador, nombre, texto):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.mez = mezclador
        self.nombre = nombre  # None = volumen general
        self.silenciado = False
        self._tocado = 0.0
        self._actualizando = False
        self._pulsado = False
        self.etiqueta = etiqueta(texto, "sub")
        self.etiqueta.set_size_request(92, -1)
        self.etiqueta.set_hexpand(False)
        self.etiqueta.set_tooltip_text(texto)
        self.pack_start(self.etiqueta, False, False, 0)
        self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.slider.set_draw_value(False)
        self.slider.set_can_focus(False)
        self.slider.set_hexpand(True)
        self.slider.connect("value-changed", self._cambio)
        self.slider.connect("button-press-event", lambda *_: setattr(self, "_pulsado", True))
        self.slider.connect("button-release-event", lambda *_: setattr(self, "_pulsado", False))
        self.pack_start(self.slider, True, True, 0)
        self.valor = Gtk.Label(xalign=1)
        self.valor.get_style_context().add_class("dim")
        self.valor.set_size_request(30, -1)
        self.pack_start(self.valor, False, False, 0)
        self.b_mute = boton_icono("audio-volume-high-symbolic", Gtk.IconSize.MENU)
        self.b_mute.connect("clicked", self._mute)
        self.pack_start(self.b_mute, False, False, 0)
        self.show_all()

    def _cambio(self, s):
        v = round(s.get_value())
        poner_texto(self.valor, f"{v}")
        if not self._actualizando:
            self._tocado = time.monotonic()
            self.mez.volumen(self.nombre, v / 100)

    def _mute(self, _b):
        self._tocado = time.monotonic()
        self.silenciado = not self.silenciado
        self.mez.silencio(self.nombre, self.silenciado)
        self._icono()

    def _icono(self):
        poner_icono(self.b_mute, "audio-volume-muted-symbolic" if self.silenciado
                    else "audio-volume-high-symbolic", Gtk.IconSize.MENU)

    def actualizar(self, volumen, silenciado):
        # No pisar lo que el usuario está moviendo (el audio tarda en reflejarlo).
        if self._pulsado or time.monotonic() - self._tocado < 1.5:
            return
        self._actualizando = True
        self.slider.set_value(min(round(volumen * 100), 100))
        self._actualizando = False
        poner_texto(self.valor, f"{round(volumen * 100)}")
        if silenciado != self.silenciado:
            self.silenciado = silenciado
            self._icono()


def abrir_web(url):
    try:
        Gio.AppInfo.launch_default_for_uri(url, None)
    except GLib.Error as e:
        log("No se pudo abrir", url, e)


# ---------------------------------------------------------------------------
# Tiempo
# ---------------------------------------------------------------------------

_iconos = {}


def icono_pixbuf(widget, nombre, tam):
    """Icono del tema (los del tiempo, en color) a tamaño fijo, con caché."""
    escala = max(1, widget.get_scale_factor())
    clave = (nombre, tam, escala)
    if clave not in _iconos:
        try:
            _iconos[clave] = Gtk.IconTheme.get_default().load_icon_for_scale(
                nombre, tam, escala, Gtk.IconLookupFlags.FORCE_SIZE)
        except GLib.Error:
            _iconos[clave] = None
    return _iconos[clave]


def pintar_icono(cr, widget, nombre, x, y, tam):
    pb = icono_pixbuf(widget, nombre, tam)
    if pb:
        escala = pb.get_width() / tam
        cr.save()
        cr.translate(x, y)
        cr.scale(1 / escala, 1 / escala)
        Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
        cr.paint()
        cr.restore()


class PronosticoHoras(Dibujo):
    """Las próximas horas: tantas como quepan a lo ancho."""

    COLUMNA = 50

    def __init__(self):
        super().__init__()
        self.horas = []
        self.set_size_request(-1, 78)
        self.connect("draw", self.dibujar)

    def poner(self, horas):
        self.horas = horas
        self.queue_draw()

    def dibujar(self, _w, cr):
        w = self.get_allocated_width()
        n = max(1, min(len(self.horas), w // self.COLUMNA))
        ancho = w / n if self.horas else w
        for i, h in enumerate(self.horas[:n]):
            x = i * ancho
            lay = capa_texto(self, cr, f"{h['hora']}h", 11)
            pintar_texto(cr, lay, x, 0, ancho, 16, GRIS, 0.5)
            pintar_icono(cr, self, describir(h["codigo"], h["dia"])[1], x + (ancho - 26) / 2, 18, 26)
            lay = capa_texto(self, cr, f"{h['temp']:.0f}°", 13, Pango.Weight.BOLD)
            pintar_texto(cr, lay, x, 46, ancho, 16, BLANCO, 0.5)
            if h["lluvia"]:
                lay = capa_texto(self, cr, f"{h['lluvia']:.0f} %", 10)
                pintar_texto(cr, lay, x, 62, ancho, 14, COLORES["azul"], 0.5)


class PronosticoDias(Dibujo):
    """Los próximos días: icono, lluvia y una barra de mínima a máxima."""

    FILA = 26

    def __init__(self):
        super().__init__()
        self.dias = []
        self.set_vexpand(True)
        self.connect("draw", self.dibujar)

    def poner(self, dias):
        cambia = len(dias) != len(self.dias)
        self.dias = dias
        if cambia:
            self.queue_resize()
        self.queue_draw()

    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_get_preferred_width(self):
        return 100, ANCHO - 32

    def do_get_preferred_height_for_width(self, _ancho):
        return self.FILA * 2, self.FILA * max(2, len(self.dias))

    def do_get_preferred_height(self):
        return self.do_get_preferred_height_for_width(ANCHO - 32)

    def dibujar(self, _w, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        dias = self.dias[:max(1, h // self.FILA)]
        if not dias:
            return
        minimo = min(d["min"] for d in dias)
        maximo = max(d["max"] for d in dias)
        hoy = datetime.date.today()
        estrecho = w < 230   # en una celda estrecha del panel, sin barra
        nombres = [_("Hoy") if datetime.date.fromisoformat(d["fecha"]) == hoy
                   else idioma.dia_corto(datetime.date.fromisoformat(d["fecha"]).weekday()) for d in dias]
        # La columna del día, tan ancha como el nombre más largo ("Hoy", "Сегодня"…).
        col = max(40, max(capa_texto(self, cr, n, 12.5, Pango.Weight.BOLD).get_pixel_size()[0] for n in nombres) + 6)
        for i, d in enumerate(dias):
            y = i * self.FILA
            fecha = datetime.date.fromisoformat(d["fecha"])
            nombre = nombres[i]
            lay = capa_texto(self, cr, nombre, 12.5, Pango.Weight.BOLD if fecha == hoy else Pango.Weight.NORMAL)
            pintar_texto(cr, lay, 0, y, col, self.FILA, NORMAL)
            pintar_icono(cr, self, describir(d["codigo"])[1], col, y + (self.FILA - 20) / 2, 20)
            x = col + 26
            if d["lluvia"] and not estrecho:
                lay = capa_texto(self, cr, f"{d['lluvia']:.0f} %", 10.5)
                pintar_texto(cr, lay, x, y, 40, self.FILA, COLORES["azul"])
            x = x if estrecho else x + 40
            lay_min = capa_texto(self, cr, f"{d['min']:.0f}°", 12.5)
            lay_max = capa_texto(self, cr, f"{d['max']:.0f}°", 12.5, Pango.Weight.BOLD)
            if estrecho:
                pintar_texto(cr, lay_max, x, y, w - x, self.FILA, BLANCO, 1.0)
                pintar_texto(cr, lay_min, x, y, w - x - 34, self.FILA, GRIS, 1.0)
                continue
            pintar_texto(cr, lay_min, x, y, 30, self.FILA, GRIS, 1.0)
            pintar_texto(cr, lay_max, w - 30, y, 30, self.FILA, BLANCO, 1.0)
            # Barra: todo el rango de la semana, y en color el de ese día.
            bx, bw = x + 38, max(10, w - 30 - 8 - (x + 38))
            by = y + self.FILA / 2 - 2
            rect_redondeado(cr, bx, by, bw, 4, 2)
            cr.set_source_rgba(*TENUE, 0.1)
            cr.fill()
            rango = max(maximo - minimo, 1)
            x1 = bx + bw * (d["min"] - minimo) / rango
            x2 = bx + bw * (d["max"] - minimo) / rango
            degradado = cairo.LinearGradient(bx, 0, bx + bw, 0)
            degradado.add_color_stop_rgb(0, *COLORES["azul"])
            degradado.add_color_stop_rgb(0.5, *COLORES["amarillo"])
            degradado.add_color_stop_rgb(1, *COLORES["naranja"])
            rect_redondeado(cr, x1, by, max(x2 - x1, 4), 4, 2)
            cr.set_source(degradado)
            cr.fill()


class DialogoCiudad(Gtk.Dialog):
    """Buscar y elegir la ciudad del widget del tiempo."""

    def __init__(self):
        super().__init__(title=_("Ciudad del tiempo"))
        self.set_default_size(440, 380)
        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        self.elegida = None
        area = self.get_content_area()
        area.set_spacing(8)
        area.set_border_width(12)
        self.buscar = Gtk.SearchEntry()
        self.buscar.set_placeholder_text(_("Escribe una ciudad y pulsa Enter"))
        self.buscar.connect("activate", lambda e: self.lanzar(e.get_text()))
        area.pack_start(self.buscar, False, False, 0)
        self.estado = Gtk.Label(xalign=0)
        area.pack_start(self.estado, False, False, 0)
        self.lista = Gtk.ListBox()
        self.lista.connect("row-activated", self.elegir)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.add(self.lista)
        area.pack_start(scroll, True, True, 0)
        self.show_all()

    def lanzar(self, texto):
        if not texto.strip():
            return
        self.estado.set_text(_("Buscando…"))

        def trabajo():
            try:
                res, err = buscar_ciudades(texto.strip()), None
            except (OSError, ValueError) as e:
                res, err = [], str(e)
            GLib.idle_add(self.mostrar, res, err)
        threading.Thread(target=trabajo, daemon=True).start()

    def mostrar(self, resultados, error):
        for fila in self.lista.get_children():
            self.lista.remove(fila)
        self.estado.set_text(_("Error: {error}").format(error=error) if error else
                             "" if resultados else _("No se ha encontrado ninguna ciudad con ese nombre."))
        for r in resultados:
            fila = Gtk.ListBoxRow()
            fila.ciudad = r
            lb = Gtk.Label(xalign=0)
            lb.set_markup(f"<b>{GLib.markup_escape_text(r['nombre'])}</b>  "
                          f"<span alpha='60%'>{GLib.markup_escape_text(r['region'])}</span>")
            lb.set_margin_top(6)
            lb.set_margin_bottom(6)
            lb.set_margin_start(6)
            fila.add(lb)
            self.lista.add(fila)
        self.lista.show_all()
        return False

    def elegir(self, _lista, fila):
        self.elegida = fila.ciudad
        self.response(Gtk.ResponseType.OK)


# ---------------------------------------------------------------------------
# Reloj y calendario
# ---------------------------------------------------------------------------

def fecha_larga(d):
    return idioma.fecha_larga(d)


CIUDADES = (  # reloj mundial: (nombre, zona horaria)
    ("Madrid", "Europe/Madrid"), ("Canarias", "Atlantic/Canary"), ("Londres", "Europe/London"),
    ("Moscú", "Europe/Moscow"), ("Nueva York", "America/New_York"),
    ("Los Ángeles", "America/Los_Angeles"), ("Ciudad de México", "America/Mexico_City"),
    ("Bogotá", "America/Bogota"), ("Lima", "America/Lima"), ("Caracas", "America/Caracas"),
    ("Santiago", "America/Santiago"), ("Buenos Aires", "America/Argentina/Buenos_Aires"),
    ("São Paulo", "America/Sao_Paulo"), ("Dubái", "Asia/Dubai"), ("Shanghái", "Asia/Shanghai"),
    ("Seúl", "Asia/Seoul"), ("Tokio", "Asia/Tokyo"), ("Sídney", "Australia/Sydney"), ("UTC", "UTC"),
)
ESTILOS_RELOJ = (("digital", "Digital"), ("analogico", "Analógico"),
                 ("minimal", "Minimalista"), ("mundial", "Reloj mundial")) + esferas.ESTILOS_NUEVOS
# al_abrir: qué hacer al abrir Discord desde el widget ("nada", "ultimo" o "gente").
# servidores: ids de los servidores cuyos canales de voz se muestran en el widget.
DISCORD_POR_DEFECTO = {"al_abrir": "nada", "servidores": []}

RELOJ_POR_DEFECTO = {"estilo": "digital", "h24": True, "segundos": True, "fecha": True,
                     "zonas": ["Europe/Madrid", "America/New_York", "America/Mexico_City", "Asia/Tokyo"]}


class RelojVista(Dibujo):
    """Reloj dibujado que se escala al tamaño que tenga (celda del panel o widget).

    Estilos: digital, analógico, minimalista y mundial (varias ciudades), y los de
    esferas.py (anillos, binario, Nixie, flip y LED).
    """

    def __init__(self, opciones):
        super().__init__()
        self.opciones = opciones
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.ajustar_minimo()
        self.connect("draw", self.dibujar)
        GLib.timeout_add(33, self._fluido)

    def _fluido(self):
        """Con agujas o anillos y segundero, se redibuja ~30 veces por segundo para que
        se muevan suaves (el resto de estilos cambia solo cada segundo)."""
        o = self.opciones
        if o["segundos"] and o["estilo"] in ("analogico", "anillos") and self.get_mapped():
            self.queue_draw()
        return True

    def ajustar_minimo(self):
        o = self.opciones
        minimos = {"digital": 130, "analogico": 210, "minimal": 110,
                   "mundial": 44 * max(1, len(o["zonas"])), **esferas.ALTOS}
        alto = minimos.get(o["estilo"], 96)
        self.poner_alto(int(alto * 0.55), alto)
        self.queue_draw()

    def hora(self, t):
        return t.strftime("%H:%M") if self.opciones["h24"] else t.strftime("%I:%M").lstrip("0")

    def dibujar(self, _w, cr):
        ahora = datetime.datetime.now()
        if self.opciones["estilo"] in esferas.ALTOS:
            esferas.reloj(LienzoCairo(self, cr), paleta(), self.get_allocated_width(), self.get_allocated_height(),
                          ahora, self.opciones, fecha_larga(ahora.date()), self.opciones["estilo"])
            return
        {"analogico": self.analogico, "minimal": self.minimal,
         "mundial": self.mundial}.get(self.opciones["estilo"], self.digital)(cr, ahora)

    def digital(self, cr, ahora, minimal=False):
        o = self.opciones
        w, h = self.get_allocated_width(), self.get_allocated_height()
        alto_fecha = 0 if not o["fecha"] or (minimal and h < 140) else max(14, h * 0.16)
        hora = self.hora(ahora)
        extra = ahora.strftime("%S") if o["segundos"] and not minimal else ""
        ampm = "" if o["h24"] else ("AM" if ahora.hour < 12 else "PM")
        peso = Pango.Weight.ULTRALIGHT if minimal else Pango.Weight.LIGHT
        alto_cifras = (h - 2 * alto_fecha) * (0.80 if minimal else 0.72)
        px = px_que_quepa(self, cr, hora + (" 00" if extra or ampm else ""), w * 0.98, alto_cifras, peso)
        lay = capa_texto(self, cr, hora, px, peso)
        tinta, logico = lay.get_pixel_extents()
        ancho_hora = logico.width
        lay2 = capa_texto(self, cr, extra or ampm, px / 3, peso)
        ancho_extra = lay2.get_pixel_size()[0] + px * 0.12 if (extra or ampm) else 0
        # La hora, centrada en el widget (la fecha va debajo, sin moverla).
        hueco = tinta.height * 0.35
        arriba = max(0, (h - tinta.height) / 2)
        x0 = (w - ancho_hora - ancho_extra) / 2
        y_lay = arriba - tinta.y
        cr.set_source_rgb(*BLANCO)
        cr.move_to(x0, y_lay)
        PangoCairo.show_layout(cr, lay)
        base = y_lay + lay.get_baseline() / Pango.SCALE
        if extra or ampm:
            cr.set_source_rgb(*GRIS)
            xe = x0 + ancho_hora + px * 0.12
            cr.move_to(xe, base - lay2.get_baseline() / Pango.SCALE)
            PangoCairo.show_layout(cr, lay2)
            if extra and ampm:
                lay3 = capa_texto(self, cr, ampm, px / 3, peso)
                cr.move_to(xe, base - px * 0.42 - lay3.get_baseline() / Pango.SCALE)
                PangoCairo.show_layout(cr, lay3)
        if alto_fecha:
            texto = fecha_larga(ahora.date())
            pxf = min(18, alto_fecha * 0.62)
            layf = capa_texto(self, cr, texto, pxf)
            if layf.get_pixel_size()[0] > w:
                layf = capa_texto(self, cr, texto, pxf * w / layf.get_pixel_size()[0] * 0.96)
            y = min(arriba + tinta.height + hueco, h - alto_fecha)
            pintar_texto(cr, layf, 0, y, w, alto_fecha, GRIS_CLARO, 0.5)

    def minimal(self, cr, ahora):
        self.digital(cr, ahora, minimal=True)

    def analogico(self, cr, ahora):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        alto_fecha = 20 if self.opciones["fecha"] and h > 180 else 0
        r = min(w, h - 2 * alto_fecha) / 2 - 4
        cx, cy = w / 2, h / 2
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.set_source_rgba(*TENUE, 0.04)
        cr.fill_preserve()
        cr.set_source_rgba(*TENUE, 0.2)
        cr.set_line_width(max(1.0, r * 0.02))
        cr.stroke()
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        for i in range(60):
            ang = math.radians(i * 6)
            largo, grosor, alfa = (0.12, 0.035, 0.86) if i % 5 == 0 else (0.05, 0.012, 0.43)
            dx, dy = math.sin(ang), -math.cos(ang)
            cr.set_source_rgba(*TENUE, alfa)
            cr.set_line_width(max(1.0, r * grosor))
            cr.move_to(cx + dx * r * (0.92 - largo), cy + dy * r * (0.92 - largo))
            cr.line_to(cx + dx * r * 0.92, cy + dy * r * 0.92)
            cr.stroke()
        seg = ahora.second + ahora.microsecond / 1e6
        minuto = ahora.minute + seg / 60
        horas = (ahora.hour % 12) + minuto / 60

        def aguja(fraccion, largo, grosor, color):
            ang = math.radians(fraccion * 360)
            cr.set_source_rgb(*color)
            cr.set_line_width(max(1.5, r * grosor))
            cr.move_to(cx - math.sin(ang) * r * 0.12, cy + math.cos(ang) * r * 0.12)
            cr.line_to(cx + math.sin(ang) * r * largo, cy - math.cos(ang) * r * largo)
            cr.stroke()

        aguja(horas / 12, 0.5, 0.055, BLANCO)
        aguja(minuto / 60, 0.75, 0.035, BLANCO)
        if self.opciones["segundos"]:
            aguja(seg / 60, 0.82, 0.012, COLORES["naranja"])
        cr.set_source_rgb(*(COLORES["naranja"] if self.opciones["segundos"] else BLANCO))
        cr.arc(cx, cy, r * 0.045, 0, 2 * math.pi)
        cr.fill()
        if alto_fecha:
            lay = capa_texto(self, cr, fecha_larga(ahora.date()), 13)
            pintar_texto(cr, lay, 0, h - alto_fecha, w, alto_fecha, GRIS_CLARO, 0.5)

    def mundial(self, cr, ahora):
        zonas = self.opciones["zonas"] or ["UTC"]
        nombres = {z: n for n, z in CIUDADES}
        w, h = self.get_allocated_width(), self.get_allocated_height()
        fila = h / len(zonas)
        hoy_local = ahora.date()
        px_hora = px_que_quepa(self, cr, "00:00", w * 0.4, min(fila * 0.45, 32), Pango.Weight.LIGHT)
        px_nombre = max(11, min(fila * 0.3, 18))
        px_extra = max(9, px_nombre * 0.75)
        offset_local = ahora.astimezone().utcoffset()
        for i, zona in enumerate(zonas):
            y0 = i * fila
            try:
                t = datetime.datetime.now(ZoneInfo(zona))
            except Exception:  # noqa: BLE001 - zona desconocida
                lay = capa_texto(self, cr, _("{ciudad}: zona no disponible").format(ciudad=_(nombres.get(zona, zona))), px_extra)
                pintar_texto(cr, lay, 0, y0, w, fila, COLORES["rojo"], recortar=True)
                continue
            dias = (t.date() - hoy_local).days
            extra = {1: _("mañana"), -1: _("ayer")}.get(dias, _("hoy"))
            difer = (t.utcoffset() - offset_local).total_seconds() / 3600
            if difer:
                extra += f" · {difer:+g} h"
            if i:
                cr.set_source_rgba(*TENUE, 0.1)
                cr.set_line_width(1)
                cr.move_to(0, int(y0) + 0.5)
                cr.line_to(w, int(y0) + 0.5)
                cr.stroke()
            texto = self.hora(t) + ("" if self.opciones["h24"] else (" AM" if t.hour < 12 else " PM"))
            lay_h = capa_texto(self, cr, texto, px_hora, Pango.Weight.LIGHT)
            ancho_h = pintar_texto(cr, lay_h, 0, y0, w, fila, BLANCO, 1.0)
            libre = w - ancho_h - 12
            lay_n = capa_texto(self, cr, _(nombres.get(zona, zona)), px_nombre)
            lay_e = capa_texto(self, cr, extra, px_extra)
            hn = lay_n.get_pixel_size()[1]
            he = lay_e.get_pixel_size()[1]
            arriba = y0 + (fila - hn - he) / 2
            pintar_texto(cr, lay_n, 0, arriba, libre, hn, CLARO, recortar=True)
            pintar_texto(cr, lay_e, 0, arriba + hn, libre, he, GRIS, recortar=True)


class CalendarioMes(Dibujo):
    """Un mes en cuadrícula con el día de hoy marcado; la semana empieza en lunes o domingo."""

    def __init__(self, primer_dia=0):
        super().__init__()
        self.primer_dia = primer_dia  # 0 = lunes, 6 = domingo
        self.ir_a_hoy()
        self.poner_alto(84, 165)
        self.set_vexpand(True)
        self.connect("draw", self.dibujar)

    def ir_a_hoy(self):
        hoy = datetime.date.today()
        self.anio, self.mes = hoy.year, hoy.month
        self.queue_draw()

    def cambiar(self, meses):
        m = self.mes - 1 + meses
        self.anio, self.mes = self.anio + m // 12, m % 12 + 1
        self.queue_draw()

    def titulo(self):
        return idioma.titulo_mes(self.anio, self.mes)

    def dibujar(self, _w, cr):
        hoy = datetime.date.today()
        semanas = calendar.Calendar(firstweekday=self.primer_dia).monthdatescalendar(self.anio, self.mes)
        w, h = self.get_allocated_width(), self.get_allocated_height()
        cw = w / 7
        ch = h / (len(semanas) + 1)
        px = min(15.0, max(10.5, ch * 0.55))
        for i in range(7):
            dia = (self.primer_dia + i) % 7  # 0 = lunes
            lay = capa_texto(self, cr, idioma.inicial_dia(dia), px * 0.8, Pango.Weight.BOLD)
            pintar_texto(cr, lay, i * cw, 0, cw, ch, GRIS if dia < 5 else
                         hex_rgb("c4561a") if tema_claro() else COLORES["naranja"], 0.5)
        for f, semana in enumerate(semanas, 1):
            for c, dia in enumerate(semana):
                x, y = c * cw, f * ch
                if dia == hoy:
                    cr.set_source_rgb(*COLORES["azul"])
                    cr.arc(x + cw / 2, y + ch / 2, min(cw, ch) * 0.44, 0, 2 * math.pi)
                    cr.fill()
                    color, peso = (1, 1, 1), Pango.Weight.BOLD
                else:
                    color = CLARO if dia.weekday() < 5 else hex_rgb("c4561a" if tema_claro() else "ffb877")
                    if dia.month != self.mes:
                        color = (*color, 0.27)
                    peso = Pango.Weight.NORMAL
                lay = capa_texto(self, cr, str(dia.day), px, peso)
                pintar_texto(cr, lay, x, y, cw, ch, color, 0.5)


# ---------------------------------------------------------------------------
# Sensores: formato, selección por defecto y selector
# ---------------------------------------------------------------------------

TIPOS_SENSOR = {
    "Temperature": ("Temperaturas", "{:.1f} °C"), "Fan": ("Ventiladores", "rpm"),
    "Control": ("Control de ventiladores", "{:.0f} %"), "Load": ("Cargas", "{:.0f} %"),
    "Clock": ("Relojes", "{:.0f} MHz"), "Power": ("Consumos", "{:.1f} W"),
    "Voltage": ("Voltajes", "{:.3f} V"), "Current": ("Corrientes", "{:.2f} A"),
    "Data": ("Datos", "{:.1f} GB"), "SmallData": ("Datos", "{:.0f} MB"),
    "Throughput": ("Transferencia", "bytes/s"), "Frequency": ("Frecuencias", "{:.0f} Hz"),
    "Level": ("Niveles", "{:.0f} %"), "Factor": ("Factores", "{:.2f}"),
    "Energy": ("Energía", "{:.0f} mWh"), "Flow": ("Caudal", "{:.0f} L/h"),
    "Noise": ("Ruido", "{:.0f} dBA"), "Humidity": ("Humedad", "{:.0f} %"),
    "TimeSpan": ("Tiempos", "{:.0f} s"),
}
MAX_SENSORES = 40


# ---------------------------------------------------------------------------
# Estilo (CSS de GTK)
# ---------------------------------------------------------------------------

CSS = """
.hw { font-feature-settings: "tnum"; }
window.hw, window.hw.background { background-color: transparent; background-image: none; }
.hw scrolledwindow, .hw viewport { background-color: transparent; border: none; }
.hw .titulo { color: #aab3c2; font-weight: bold; font-size: 10pt; letter-spacing: 1px; }
.hw .grande { color: #f2f4f8; font-size: 22pt; font-weight: 600; }
.hw .sub { color: #d0d6e0; font-size: 10pt; }
.hw .dim { color: #9aa3b2; font-size: 9pt; }
.hw .negrita { font-weight: 600; }
.hw .verde { color: #2ecc71; }
.hw .rojo { color: #ff5c5c; }
.hw .seccion { color: #aab3c2; font-weight: bold; font-size: 8pt; letter-spacing: 1px; }
.hw button {
    background-image: none; box-shadow: none; text-shadow: none; border: none;
    min-height: 0; min-width: 0; outline: none; -gtk-outline-radius: 0;
}
.hw button.plano { background-color: transparent; color: #e6e9ef; padding: 3px; border-radius: 5px; }
.hw button.plano:hover { background-color: rgba(255, 255, 255, 0.12); }
.hw button.plano:disabled { opacity: 0.3; }
.hw button.normal { background-color: rgba(255, 255, 255, 0.09); color: #e6e9ef; border-radius: 6px; padding: 7px 12px; }
.hw button.normal:hover { background-color: rgba(255, 255, 255, 0.15); }
.hw button.normal:disabled { color: rgba(255, 255, 255, 0.35); }
.hw button.principal { background-color: #4d8dff; color: white; font-weight: 600; border-radius: 6px; padding: 7px 12px; }
.hw button.principal:hover { background-color: #6a9fff; }
.hw button.principal:disabled { background-color: rgba(77, 141, 255, 0.45); color: rgba(255, 255, 255, 0.7); }
.hw button.marcado { background-color: rgba(255, 92, 92, 0.27); color: white; }
.hw button.marcado:hover { background-color: rgba(255, 92, 92, 0.38); }
.hw button label { font-weight: normal; }
.hw button.principal label, .hw button.mes label { font-weight: 600; }
.hw button.dispositivo { background-color: transparent; color: #d0d6e0; padding: 3px 8px; border-radius: 6px; }
.hw button.dispositivo:hover { background-color: rgba(255, 255, 255, 0.09); }
.hw button.dispositivo.activo { background-color: rgba(77, 141, 255, 0.22); color: white; }
.hw button.dispositivo.activo label { font-weight: 600; }
.hw button.dispositivo:disabled { color: rgba(255, 255, 255, 0.4); }
.hw button.calendario { font-size: 15pt; padding: 0 8px; }
.hw button.mes { font-weight: 600; font-size: 11pt; }
.hw scale { padding: 6px 0; }
.hw scale trough { min-height: 4px; background-color: rgba(255, 255, 255, 0.16); background-image: none; border: none; border-radius: 2px; }
.hw scale highlight { background-color: #4d8dff; background-image: none; border: none; border-radius: 2px; min-height: 4px; }
.hw scale slider {
    min-width: 12px; min-height: 12px; margin: -4px 0; background-color: #f2f4f8; background-image: none;
    border: none; border-radius: 6px; box-shadow: none;
}
.hw .barra-edicion { background-color: rgba(22, 24, 30, 0.92); border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.16); padding: 6px 8px 6px 14px; }
.hw .barra-edicion button.plano { font-size: 11pt; padding: 3px 9px; }
.hw .barra-edicion button.principal { padding: 4px 12px; }
"""


def css_tema(t):
    """El CSS de arriba con los colores, la fuente y el tamaño de letra del tema."""
    g = t["global"]
    acento = hex_rgb(g["acento"])

    def rgba(rgb, a):
        return f"rgba({round(rgb[0] * 255)}, {round(rgb[1] * 255)}, {round(rgb[2] * 255)}, {a})"
    css = CSS
    for viejo, nuevo in (("#aab3c2", TITULO), ("#f2f4f8", BLANCO), ("#d0d6e0", NORMAL), ("#9aa3b2", GRIS),
                         ("#e6e9ef", CLARO), ("#6a9fff", temas.mezcla(acento, (1, 1, 1), 0.2)),
                         ("#4d8dff", acento)):
        css = css.replace(viejo, temas.a_hex(nuevo))
    css = re.sub(r"rgba\(255, 255, 255, ([\d.]+)\)", lambda m: rgba(TENUE, m.group(1)), css)
    css = re.sub(r"rgba\(77, 141, 255, ([\d.]+)\)", lambda m: rgba(acento, m.group(1)), css)
    fondo = hex_rgb(t["widgets"]["fondo"])
    css = css.replace("rgba(22, 24, 30, 0.92)", rgba(fondo, 0.94))
    css = re.sub(r"([\d.]+)pt", lambda m: f"{float(m.group(1)) * ESCALA:.1f}pt", css)
    if g["fuente"]:
        css = f'.hw {{ font-family: "{g["fuente"]}"; }}\n' + css
    return css


def pintar_fondo(cr, p, w, h, opacidad, prefijo=""):
    """Fondo según el tema: el color o el degradado.
    `prefijo` = "panel_" para el fondo del panel entero."""
    alfa = p[prefijo + "opacidad"] * opacidad
    color = hex_rgb(p[prefijo + "fondo"])
    if not prefijo and p["degradado"]:
        ang = math.radians(p["angulo"])
        dx, dy = math.cos(ang), math.sin(ang)
        medio = (abs(w * dx) + abs(h * dy)) / 2
        deg = cairo.LinearGradient(w / 2 - dx * medio, h / 2 - dy * medio, w / 2 + dx * medio, h / 2 + dy * medio)
        deg.add_color_stop_rgba(0, *color, alfa)
        deg.add_color_stop_rgba(1, *hex_rgb(p["fondo2"]), alfa)
        cr.set_source(deg)
    else:
        cr.set_source_rgba(*color, alfa)
    cr.paint()


# ---------------------------------------------------------------------------
# Tarjeta: el contenido de un widget. Vive en su ventana o en el panel.
# ---------------------------------------------------------------------------

class Tarjeta(Gtk.EventBox):
    ASA = 26  # píxeles de la esquina que sirven para cambiar el tamaño en el panel

    def __init__(self, clave, titulo, app):
        super().__init__()
        self.set_visible_window(False)
        self.clave = clave
        self.titulo = titulo
        self.nombre_menu = titulo  # cómo aparece en "Widgets visibles"
        self.app = app
        self.opacidad = 1.0
        self.relleno = "cristal"   # "cristal" (ventana propia) o "claro" (dentro del panel)
        self.radio = RADIO
        self.ventana = None        # VentanaWidget cuando está suelta en el escritorio
        self._estira = False       # ya hay un elemento que absorbe la altura sobrante
        self.prescindibles = []    # lo que se quita si la tarjeta es muy baja (ver add_w)
        self._ajuste = None
        self.brillo = 1.0          # del neón (baja cuando parpadea)
        self._secuencia = []
        self._siguiente = time.monotonic() + __import__("random").uniform(1, 8)
        self._pulsado_titulo = None  # dónde se pulsó el título (clic = opciones, arrastre = mover)
        self.titulo_con_opciones = False  # lo pone marcar_titulos: el título se puede pulsar
        self._mano = False
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        # Si el contenido no cabe (celda pequeña del panel), se recorta al dibujar.
        self.contenido = caja(True, 6)
        self._margen = None
        self.ajustar_margenes()
        self.add(self.contenido)
        self.lb_titulo = etiqueta(titulo.upper(), "titulo")
        self.lb_titulo.set_no_show_all(True)  # se ve u oculta según "Mostrar título"
        self.lb_titulo.show()
        self.contenido.pack_start(self.lb_titulo, False, False, 0)
        self.connect("draw", self.dibujar_fondo)
        self.connect_after("draw", self.dibujar_edicion)
        self.connect("button-press-event", self.pulsar)
        self.connect("button-release-event", self.soltar)
        self.connect("motion-notify-event", self.mover_raton)
        self.connect("leave-notify-event", lambda _w, _ev: self.poner_mano(False))

    def add_w(self, w, expand=None, prescindible=0):
        """prescindible: si la tarjeta es tan baja que no cabe todo (celda pequeña del
        panel), se quita (1 = lo primero que se quita, 2 = después...) en vez de cortar
        el texto de abajo. Las gráficas encogen antes de quitar nada."""
        # La primera gráfica crece si la tarjeta es más alta que su contenido
        # (filas de la misma altura en modo widgets, cuadrícula en modo panel).
        if expand is None:
            expand = isinstance(w, Grafica) and not self._estira
        self._estira = self._estira or expand
        self.contenido.pack_start(w, expand, expand, 0)
        if prescindible:
            w._prescindible, w._quitado = prescindible, False
            self.prescindibles.append(w)
        return w

    def do_size_allocate(self, a):
        Gtk.EventBox.do_size_allocate(self, a)
        if self.prescindibles:
            self.ajustar_prescindibles(a.width, a.height)

    def ajustar_prescindibles(self, ancho, alto):
        """Quita lo prescindible que haga falta para que el resto quepa en `alto`."""
        interior = ancho - self.contenido.get_margin_start() - self.contenido.get_margin_end()

        def alto_de(w):
            # Oculto, GTK lo mide como 0: se usa lo que medía la última vez que se vio.
            if w.get_visible():
                padre = w.get_parent()
                w._alto = (w.get_preferred_height_for_width(max(1, interior))[0]
                           + (padre.get_spacing() if isinstance(padre, Gtk.Box) else 0))
            return getattr(w, "_alto", 0)

        for w in self.prescindibles:
            if w._quitado and w.get_visible():
                w._quitado = False  # alguien lo ha vuelto a mostrar (show_all)
        candidatos = [w for w in self.prescindibles if w.get_visible() or w._quitado]
        necesario = self.contenido.get_preferred_height_for_width(ancho)[0]
        necesario += sum(alto_de(w) for w in candidatos if w._quitado)
        quitar = set()
        for w in sorted(candidatos, key=lambda x: x._prescindible):
            if necesario <= alto:
                break
            necesario -= alto_de(w)
            quitar.add(w)
        cambios = [(w, w not in quitar) for w in candidatos if w.get_visible() != (w not in quitar)]
        if cambios and not self._ajuste:
            # No se cambia nada en mitad de la asignación de tamaños: justo después.
            def aplicar():
                self._ajuste = None
                for w, ver in cambios:
                    w._quitado = not ver
                    w.set_visible(ver)
                return False
            self._ajuste = GLib.idle_add(aplicar)

    def poner_esquina(self, w):
        """Un botón pequeño a la derecha del título (p. ej. silenciar si el volumen no cabe).
        Se ve solo cuando quien lo pone lo muestra."""
        cab = caja(False, 6)
        self.contenido.remove(self.lb_titulo)
        cab.pack_start(self.lb_titulo, True, True, 0)
        w.set_no_show_all(True)
        w.set_valign(Gtk.Align.CENTER)
        cab.pack_end(w, False, False, 0)
        cab.show()
        self.contenido.pack_start(cab, False, False, 0)
        self.contenido.reorder_child(cab, 0)
        return w

    def prescindibles_grupo(self, grupo, widgets, base):
        """Filas que se crean sobre la marcha (p. ej. una por app): se quitan en el orden de
        `widgets` con prioridad desde `base`. Sustituye a las del mismo grupo de antes."""
        self.prescindibles = [w for w in self.prescindibles if getattr(w, "_grupo", None) != grupo]
        for i, w in enumerate(widgets):
            w._grupo, w._prescindible, w._quitado = grupo, base + i / 100, False
            self.prescindibles.append(w)

    def ajustar_margenes(self):
        """Margen interior del contenido. Con neón, la tarjeta se dibuja NEON_MARGEN px hacia
        dentro (el halo va por fuera), y el contenido se aparta lo mismo: así la tarjeta
        visible y su margen interior no cambian."""
        m = self.margen_neon() if hasattr(self, "app") and self.app else 0
        if m == self._margen:
            return
        self._margen = m
        for lado, base in (("top", 14), ("bottom", 16), ("start", 16), ("end", 16)):
            getattr(self.contenido, f"set_margin_{lado}")(base + m)

    def alto_natural(self, ancho):
        """Alto de la tarjeta visible (sin el sitio del halo del neón) para un ancho visible."""
        m = self.margen_neon()
        alto = self.contenido.get_preferred_height_for_width(ancho + 2 * m)[1] - 2 * m
        # Lo quitado por falta de sitio también cuenta: en su ventana cabe todo y vuelve a verse.
        return alto + sum(getattr(w, "_alto", 0) for w in self.prescindibles if w._quitado)

    def set_opacidad(self, valor):
        """Atenúa el contenido y el fondo (1.0 = normal)."""
        self.opacidad = valor
        self.contenido.set_opacity(valor)
        self.queue_draw()

    def perfil(self):
        """Ajustes del tema que le tocan: los del panel si está dentro de él."""
        return self.app.tema["panel" if self.relleno == "claro" else "widgets"]

    def margen_neon(self):
        """Con neón, la tarjeta se dibuja un poco hacia dentro para que quepa el halo."""
        return NEON_MARGEN if self.perfil()["neon"] else 0

    def sin_fondo(self):
        """El usuario puede quitar el fondo y el borde de cada widget (solo queda el contenido)."""
        app = getattr(self, "app", None)
        return bool(app) and self.clave in app.config.get("sin_fondo", [])

    def dibujar_fondo(self, _w, cr):
        p = self.perfil()
        self.radio = p["radio"]
        w, h = self.get_allocated_width(), self.get_allocated_height()
        m = self.margen_neon()
        x, y, cw, ch = m + 0.5, m + 0.5, w - 2 * m - 1, h - 2 * m - 1
        if self.sin_fondo():
            return False
        cr.save()
        rect_redondeado(cr, x, y, cw, ch, self.radio)
        cr.clip()
        cr.translate(m, m)
        pintar_fondo(cr, p, w - 2 * m, h - 2 * m, self.opacidad)
        cr.restore()
        if p["neon"]:
            self.pintar_neon(cr, p, x, y, cw, ch)
        elif p["borde_grosor"] > 0:
            g = p["borde_grosor"]
            rect_redondeado(cr, m + g / 2, m + g / 2, w - 2 * m - g, h - 2 * m - g, self.radio)
            cr.set_source_rgba(*hex_rgb(p["borde"]), p["borde_opacidad"] * self.opacidad)
            cr.set_line_width(g)
            cr.stroke()
        rect_redondeado(cr, x, y, cw, ch, self.radio)
        cr.clip()  # el contenido no se sale de la tarjeta redondeada
        return False

    def pintar_neon(self, cr, p, x, y, w, h):
        """Tubo de neón: halo suave (caída gaussiana, sin escalones) del color del
        borde, el tubo de color y un núcleo casi blanco."""
        color = hex_rgb(p["borde"])
        brillo = self.brillo * self.opacidad * max(0.35, p["borde_opacidad"])
        g = max(1.0, p["borde_grosor"])
        alcance = int(round(NEON_MARGEN + 4 + 2 * g))
        for ancho, alfa in temas.capas_neon(alcance, round(min(0.9, 0.62 * brillo), 2)):
            rect_redondeado(cr, x, y, w, h, self.radio)
            cr.set_source_rgba(*color, alfa)
            cr.set_line_width(ancho)
            cr.stroke()
        for ancho, alfa, mezcla in ((1.8 * g, 0.9, 0.25), (0.8 * g, 0.95, 0.75)):
            rect_redondeado(cr, x, y, w, h, self.radio)
            cr.set_source_rgba(*temas.mezcla(color, (1, 1, 1), mezcla), alfa * brillo)
            cr.set_line_width(ancho)
            cr.stroke()

    # Parpadeo: de vez en cuando, una serie corta de apagones como un tubo que falla.
    def tic_parpadeo(self, ahora):
        if ahora < self._siguiente:
            return
        if not self._secuencia:
            import random
            r = random.random()
            if r < 0.5:      # un titileo rápido
                self._secuencia = [(0.25, 0.05), (1, 0.06), (0.35, 0.04)]
            elif r < 0.85:   # varios fallos seguidos
                self._secuencia = [(0.15, 0.07), (1, 0.05), (0.1, 0.09), (0.8, 0.05), (0.2, 0.12)]
            else:            # se apaga un momento y vuelve con dudas
                self._secuencia = [(0.05, 0.35), (0.6, 0.06), (0.1, 0.08), (1, 0.05), (0.3, 0.06)]
            self._secuencia.append((1, random.uniform(2.5, 11)))  # y aguanta encendido un rato
        brillo, dura = self._secuencia.pop(0)
        self._siguiente = ahora + dura
        if brillo != self.brillo:
            self.brillo = brillo
            self.queue_draw()

    def dibujar_edicion(self, _w, cr):
        if not self.en_edicion():
            return False
        cr.reset_clip()
        w, h = self.get_allocated_width(), self.get_allocated_height()
        rect_redondeado(cr, 1.5, 1.5, w - 3, h - 3, self.radio)
        cr.set_source_rgba(*COLORES["azul"], 0.67)
        cr.set_line_width(1.5)
        cr.set_dash([5, 4])
        cr.stroke()
        cr.set_dash([])
        cr.set_source_rgba(*TENUE, 0.8)
        cr.set_line_width(2)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        for d in (6, 11, 16):
            cr.move_to(w - 5, h - 5 - d)
            cr.line_to(w - 5 - d, h - 5)
        cr.stroke()
        return False

    # --- ratón -------------------------------------------------------------

    def en_edicion(self):
        panel = self.app.panel if self.app.modo == "panel" else None
        return bool(panel and panel.editando and not self.ventana)

    def en_asa(self, x, y):
        return x > self.get_allocated_width() - self.ASA and y > self.get_allocated_height() - self.ASA

    def pulsar(self, _w, ev):
        if ev.type != Gdk.EventType.BUTTON_PRESS:
            return False
        if ev.button == 1 and self.en_edicion():
            self.app.panel.empezar_arrastre(self, ev, "tam" if self.en_asa(ev.x, ev.y) else "mover")
            return True
        if ev.button == 1 and self.titulo_con_opciones and self.en_titulo(ev):
            self._pulsado_titulo = (ev.x_root, ev.y_root)  # clic (opciones) o arrastre (mover): se ve después
            return True
        if ev.button == 1 and self.ventana:
            self.mover_ventana(ev)
            return True
        if ev.button == 3:
            self.app.menu_tarjeta(self).popup_at_pointer(ev)
            return True
        return False

    def mover_ventana(self, ev):
        if self.app.modo == "widgets":
            # Ya no se recolocan solos (tampoco al reiniciar) hasta "Recolocar widgets".
            self.app.manual = True
            self.app.config["manual"] = True
        self.ventana.empezar_arrastre(ev)

    def en_titulo(self, ev):
        t = self.lb_titulo
        ventana = t.get_window()
        if not t.get_visible() or ventana is None:
            return False
        # La etiqueta no tiene ventana propia: su sitio va en las coordenadas de la del padre
        _v, x, y, _m = ventana.get_device_position(ev.device)
        a = t.get_allocation()
        return a.x <= x < a.x + a.width and a.y <= y < a.y + a.height

    def poner_mano(self, mano):
        """La manita sobre los títulos que se pueden pulsar."""
        if mano != self._mano and not self.en_edicion():
            self._mano = mano
            ventana = self.get_toplevel().get_window()
            if ventana:
                ventana.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), "pointer") if mano else None)
        return False

    def soltar(self, _w, ev):
        if self._pulsado_titulo is None or ev.button != 1:
            return False
        self._pulsado_titulo = None  # un clic en el título: las opciones del widget
        self.app.pulsar_titulo(self, ev)
        return True

    def mover_raton(self, _w, ev):
        if self._pulsado_titulo is not None:
            # Se arrastra desde el título: ya no es un clic, se mueve la ventana como siempre
            x0, y0 = self._pulsado_titulo
            umbral = Gtk.Settings.get_default().props.gtk_dnd_drag_threshold
            if abs(ev.x_root - x0) + abs(ev.y_root - y0) > umbral:
                self._pulsado_titulo = None
                if self.ventana:
                    self.mover_ventana(types.SimpleNamespace(button=1, x_root=x0, y_root=y0, time=ev.time))
            return False
        if self.titulo_con_opciones:
            self.poner_mano(self.en_titulo(ev))
        if self.en_edicion() and not self.app.panel.arrastre:
            ventana = self.get_toplevel().get_window()
            nombre = "nwse-resize" if self.en_asa(ev.x, ev.y) else "move"
            if ventana:
                ventana.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), nombre))
        return False


# ---------------------------------------------------------------------------
# Ventanas: base de cristal, widget suelto y panel
# ---------------------------------------------------------------------------

class VentanaCristal(Gtk.Window):
    """Ventana transparente sin marco, como capa de COSMIC (layer-shell), con desenfoque."""

    def __init__(self, titulo, capa, monitor, anclas, teclado=True):
        super().__init__(title=titulo)
        self.get_style_context().add_class("hw")
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)
        self.blur = None
        self._rects = None
        # La rueda sobre lo que no la usa (todo menos las barras deslizantes) cambia de escritorio.
        self.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.connect("scroll-event", lambda _w, ev: bool(getattr(self, "app", None)) and self.app.rueda(ev))
        self.con_capas = CAPAS
        if CAPAS:
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_namespace(self, "moondeck")
            self.poner_capa(capa)
            if monitor:
                GtkLayerShell.set_monitor(self, monitor)
            for borde in anclas:
                GtkLayerShell.set_anchor(self, borde, True)
            GtkLayerShell.set_exclusive_zone(self, 0)
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND if teclado
                                            else GtkLayerShell.KeyboardMode.NONE)
        else:
            # Sin layer-shell: ventana normal sin barra (COSMIC decide dónde va).
            barra = Gtk.Box(visible=True)
            self.set_titlebar(barra)
            self.set_skip_taskbar_hint(True)
        self.connect("draw", self._limpiar)
        self.connect("map-event", self._mapeada)
        self.connect("size-allocate", lambda *_: self.actualizar_blur())

    def poner_capa(self, capa):
        if CAPAS:
            GtkLayerShell.set_layer(self, {"fondo": GtkLayerShell.Layer.BOTTOM, "encima": GtkLayerShell.Layer.OVERLAY,
                                           "escritorio": GtkLayerShell.Layer.BACKGROUND}[capa])
        else:
            self.set_keep_above(capa == "encima")

    @staticmethod
    def _limpiar(_w, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        return False

    def _mapeada(self, *_):
        if EFECTO != "cristal":
            return False
        # GTK rehace la superficie de Wayland cada vez que la ventana se oculta y se muestra.
        sup = superficie(self)
        if self.blur is None or self.blur.surface != sup:
            self.blur = Blur(self)
            self._rects = None
        self.actualizar_blur()
        return False

    def rects_blur(self):
        tarjeta = getattr(self, "tarjeta", None)
        if tarjeta and tarjeta.sin_fondo():
            return []
        a = self.get_allocation()
        p = self.app.tema["widgets"]
        m = NEON_MARGEN if p["neon"] else 0
        return rounded_rects(m, m, a.width - 2 * m, a.height - 2 * m, int(p["radio"])) if p["cristal"] else []

    def actualizar_blur(self):
        if not self.blur or not self.blur.ok:
            return
        rects = self.rects_blur()
        if rects != self._rects:
            self._rects = rects
            self.blur.set_region(rects)
            self.queue_draw()


class VentanaWidget(VentanaCristal):
    """Ventana de cristal suelta en el escritorio que aloja una Tarjeta."""

    def __init__(self, tarjeta, app, encima=False, monitor=None):
        super().__init__(f"MoonDeck · {tarjeta.titulo}",
                         "encima" if encima or os.environ.get("MOONDECK_ENCIMA") else "fondo",
                         monitor, (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.LEFT) if CAPAS else ())
        self.app = app
        self.tarjeta = tarjeta
        self.encima = encima
        self.monitor = monitor
        self.pos = [0, 0]
        self._agarre = None
        self._esperando = False
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)
        tarjeta.relleno = "cristal"
        tarjeta.ventana = self
        tarjeta.ajustar_margenes()
        self.add(tarjeta)
        self.tamano(ANCHO, tarjeta.alto_natural(ANCHO))
        self.connect("motion-notify-event", self._arrastrar)
        self.connect("button-release-event", self._soltar_arrastre)
        self.connect("key-press-event", self._tecla)

    def tamano(self, ancho, alto):
        """Tamaño de la tarjeta visible; con neón, la ventana es algo mayor para el halo."""
        self.alto = alto
        m = self.tarjeta.margen_neon()
        self.tarjeta.set_size_request(ancho + 2 * m, alto + 2 * m)
        self.resize(ancho + 2 * m, alto + 2 * m)
        self.mover(*self.pos)

    def mover(self, x, y):
        """Posición de la tarjeta visible (la ventana empieza antes si hay halo de neón)."""
        self.pos = [max(0, int(x)), max(0, int(y))]
        m = self.tarjeta.margen_neon() if self.tarjeta else 0
        if CAPAS:
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, self.pos[0] - m)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, self.pos[1] - m)

    # Arrastre: la capa no se puede mover con el gestor de ventanas, así que se
    # cambian sus márgenes según lo que se desplaza el ratón dentro de ella.
    def empezar_arrastre(self, ev):
        if not CAPAS:
            self.begin_move_drag(ev.button, int(ev.x_root), int(ev.y_root), ev.time)
            return
        self._agarre = (ev.x_root, ev.y_root)

    def _arrastrar(self, _w, ev):
        if not self._agarre or self._esperando:
            return False
        dx, dy = ev.x_root - self._agarre[0], ev.y_root - self._agarre[1]
        if abs(dx) < 1 and abs(dy) < 1:
            return True
        self.mover(self.pos[0] + dx, self.pos[1] + dy)
        # Un movimiento por fotograma: los eventos que lleguen mientras COSMIC
        # aplica el anterior aún vienen con la posición vieja.
        self._esperando = True
        GLib.timeout_add(16, lambda: setattr(self, "_esperando", False))
        return True

    def _soltar_arrastre(self, _w, _ev):
        if self._agarre:
            self._agarre = None
            self.app.guardar_config()
        return False

    def soltar(self):
        """Devuelve la tarjeta (para llevarla al panel o a otra ventana) y cierra la ventana."""
        t = self.tarjeta
        self.remove(t)
        t.ventana = None
        t.set_size_request(-1, -1)
        self.tarjeta = None
        self.destroy()
        return t

    def _tecla(self, _w, ev):
        if ev.keyval in (Gdk.KEY_q, Gdk.KEY_Q) and ev.state & Gdk.ModifierType.CONTROL_MASK:
            self.app.salir()
        return False


class Lienzo(Gtk.Fixed):
    """Contenedor del panel: coloca cada tarjeta exactamente en su rectángulo."""

    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.rects = {}   # tarjeta -> (x, y, ancho, alto)

    def do_get_preferred_width(self):
        return 1, 1   # el tamaño lo pone COSMIC (pantalla completa)

    def do_get_preferred_height(self):
        return 1, 1

    def do_size_allocate(self, a):
        self.set_allocation(a)
        if a.width < 200 or a.height < 200:
            return  # tamaño provisional antes de que COSMIC dé el de la pantalla
        if (a.width, a.height) != self.panel.tam:
            self.panel.tam = (a.width, a.height)
            self.panel.recalcular(asignar=False)
        for t in self.get_children():
            r = self.rects.get(t)
            if not r:
                continue
            t.get_preferred_size()  # GTK pide medir antes de asignar
            m = t.margen_neon()  # el halo del neón ocupa parte del hueco entre tarjetas
            rect = Gdk.Rectangle()
            rect.x, rect.y = a.x + r[0] - m, a.y + r[1] - m
            rect.width, rect.height = max(1, r[2] + 2 * m), max(1, r[3] + 2 * m)
            t.size_allocate(rect)


# Disposición por defecto del modo panel: (fila, columna, alto, ancho) en una
# cuadrícula de PANEL_COLUMNAS columnas. "gpu1"/"gpu2" son la primera y la segunda GPU que haya.
PANEL_COLUMNAS = 11
PANEL_POR_DEFECTO = {
    "cpu": (0, 0, 3, 2), "gpu1": (0, 2, 2, 3), "memoria": (0, 5, 2, 2), "discos": (0, 7, 2, 2),
    "gpu2": (0, 9, 2, 2), "multimedia": (2, 2, 2, 3), "reloj": (2, 5, 2, 2), "discord": (2, 7, 2, 2),
    "red": (2, 9, 2, 2), "calendario": (3, 0, 2, 2), "audio": (4, 2, 2, 2), "temperaturas": (4, 4, 2, 4),
    "velocidad": (4, 8, 2, 2), "tiempo": (4, 10, 2, 1),
}


def empaquetar(items, columnas):
    """Coloca (clave, ancho, alto) en orden en la primera posición libre de la cuadrícula.

    Devuelve ({clave: (fila, col, alto, ancho)}, filas usadas).
    """
    ocupado = set()
    celdas = {}
    filas = 0
    for clave, ancho, alto in items:
        ancho = max(1, min(ancho, columnas))
        alto = max(1, alto)
        fila = 0
        while clave not in celdas:
            for col in range(columnas - ancho + 1):
                bloque = {(fila + i, col + j) for i in range(alto) for j in range(ancho)}
                if not bloque & ocupado:
                    ocupado |= bloque
                    celdas[clave] = (fila, col, alto, ancho)
                    filas = max(filas, fila + alto)
                    break
            fila += 1
    return celdas, filas


class BarraEdicion(Gtk.Box):
    """Barra flotante del modo "Editar disposición": columnas, filas, restablecer, listo."""

    def __init__(self, panel):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.panel = panel
        self.get_style_context().add_class("barra-edicion")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.START)
        self.set_margin_top(14)

        def boton(texto, fn, estilo="plano"):
            b = boton_texto(texto, estilo)
            b.connect("clicked", lambda _b: fn())
            self.pack_start(b, False, False, 0)
            return b

        def texto(t, estilo="sub"):
            lb = Gtk.Label(label=t)
            lb.get_style_context().add_class(estilo)
            self.pack_start(lb, False, False, 0)
            return lb

        texto(_("Columnas"))
        boton("−", lambda: panel.cambiar_columnas(-1))
        self.columnas = texto("")
        boton("+", lambda: panel.cambiar_columnas(1))
        self.pack_start(Gtk.Box(width_request=14), False, False, 0)
        texto(_("Filas"))
        boton("−", lambda: panel.cambiar_filas(-1))
        self.filas = texto("")
        boton("+", lambda: panel.cambiar_filas(1))
        self.pack_start(Gtk.Box(width_request=14), False, False, 0)
        texto(_("Arrastra un widget a cualquier celda · su esquina ◢ cambia el tamaño"), "dim")
        self.pack_start(Gtk.Box(width_request=10), False, False, 0)
        boton(_("Restablecer"), panel.restablecer)
        boton(_("Listo"), lambda: panel.set_edicion(False), "principal")

    def actualizar(self):
        g = self.panel.config_grid()
        self.columnas.set_text(str(self.panel.cols))
        self.filas.set_text(str(g["filas"]) if g["filas"] else _("auto ({n})").format(n=self.panel.filas))


class VentanaPanel(VentanaCristal):
    """Modo panel: una ventana de cristal a pantalla completa con las tarjetas en cuadrícula.

    Colocación libre: cada widget tiene su fila, columna, alto y ancho en celdas
    (config["panel_grid"]["pos"]) y puede haber huecos. Si no hay nada guardado,
    se calcula una disposición según la pantalla.
    """

    MARGEN = 24
    MARGEN_EDICION = 70   # arriba, sitio para la barra de edición
    HUECO = 16
    MAX_COLUMNAS = 12
    MAX_ALTO = 6
    ANCHO_MIN = 290

    def __init__(self, app, monitor):
        E = GtkLayerShell.Edge if CAPAS else None
        super().__init__("MoonDeck", "encima" if os.environ.get("MOONDECK_ENCIMA") else "fondo", monitor,
                         (E.TOP, E.BOTTOM, E.LEFT, E.RIGHT) if CAPAS else ())
        self.app = app
        self.monitor = monitor
        self.tarjetas = []
        self.celdas = {}      # clave -> (fila, col, alto, ancho)
        self.cols = 1
        self.filas = 1
        self.editando = False
        self.previa = None    # (fila, col, alto, ancho) donde caería el widget arrastrado
        self.arrastre = None  # (tarjeta, "mover"/"tam", agarre)
        g = monitor.get_geometry() if monitor else None
        self.tam = (g.width, g.height - 40) if g else (1920, 1040)  # hasta que COSMIC diga el real
        if not CAPAS and monitor:
            self.set_default_size(g.width, g.height)
        superposicion = Gtk.Overlay()
        self.lienzo = Lienzo(self)
        self.lienzo.connect("draw", self.dibujar)
        superposicion.add(self.lienzo)
        self.barra = BarraEdicion(self)
        self.barra.show_all()  # sus botones; la barra en sí solo se ve al editar
        self.barra.hide()
        self.barra.set_no_show_all(True)
        superposicion.add_overlay(self.barra)
        self.add(superposicion)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK)
        self.connect("button-press-event", self._pulsar)
        self.connect("motion-notify-event", self._mover)
        self.connect("button-release-event", self._soltar)
        self.connect("key-press-event", self._tecla)
        superposicion.show_all()
        if not CAPAS and monitor:
            self.fullscreen_on_monitor(self.get_screen(), app.indice_monitor(monitor))

    def rects_blur(self):
        a = self.get_allocation()
        return [(0, 0, a.width, a.height)] if self.app.tema["panel"]["cristal"] else []

    # --- modelo de la cuadrícula ----------------------------------------------

    def repartir(self, tarjetas):
        for t in list(self.lienzo.get_children()):
            if t not in tarjetas:
                self.lienzo.remove(t)
                self.lienzo.rects.pop(t, None)
        self.tarjetas = tarjetas
        for t in tarjetas:
            if t.get_parent() is not self.lienzo:
                self.lienzo.put(t, 0, 0)
            t.relleno = "claro"
            t.ajustar_margenes()
            t.set_above_child(self.editando)
            t.show()
        self.recalcular()

    def config_grid(self):
        g = self.app.config.get("panel_grid")
        if g and "orden" in g:   # formato antiguo: orden + tamaños -> posiciones
            items = [(c, *g["tam"].get(c, [1, 1])) for c in g["orden"]]
            g = {"columnas": g["columnas"], "filas": g["filas"], "pos": empaquetar(items, g["columnas"])[0]}
            self.app.config["panel_grid"] = g
        return g or self.grid_por_defecto()

    def grid_editable(self):
        """La cuadrícula guardada; la primera vez que se edita, se guarda la actual."""
        if not self.app.config.get("panel_grid"):
            g = self.grid_por_defecto()
            g["pos"] = {c: list(v) for c, v in self.celdas.items()}
            self.app.config["panel_grid"] = g
        return self.app.config["panel_grid"]

    def grid_por_defecto(self):
        """Las menos columnas con las que todo cabe en alto, con filas equilibradas
        (7 widgets -> 3 + 2 + 2). Las columnas de la cuadrícula son el mínimo común
        múltiplo de los widgets por fila, para que cada fila llene el ancho."""
        n = len(self.tarjetas)
        if not n:
            return {"columnas": 1, "filas": 0, "pos": {}}
        if self.app.config.get("panel_predeterminado"):  # la que guardó el usuario en Configuración
            return json.loads(json.dumps(self.app.config["panel_predeterminado"]))
        # La disposición de serie; lo que no esté en ella (una tercera GPU...) va a un hueco libre.
        gpus = [t.clave for t in self.app.tarjetas if t.clave.startswith("gpu-")]
        nombres = {f"gpu{i}": clave for i, clave in enumerate(gpus, 1)}
        pos = {nombres.get(k, k): list(v) for k, v in PANEL_POR_DEFECTO.items()}
        if any(t.clave in pos for t in self.tarjetas):
            return {"columnas": PANEL_COLUMNAS, "filas": 0, "pos": pos}
        ancho = self.tam[0] - 2 * self.MARGEN
        alto = self.tam[1] - 2 * self.MARGEN
        max_cols = max(1, min(n, (ancho + self.HUECO) // (self.ANCHO_MIN + self.HUECO)))
        for cols in range(1, max_cols + 1):
            por_fila = -(-n // cols)
            base, resto = divmod(n, por_fila)
            tamanos = [base + 1] * resto + [base] * (por_fila - resto)
            tamanos = [k for k in tamanos if k]
            filas, i = [], 0
            for k in tamanos:
                filas.append(self.tarjetas[i:i + k])
                i += k
            necesario = sum(max(t.alto_natural(ANCHO) for t in f) for f in filas) + self.HUECO * (len(filas) - 1)
            if necesario <= alto:
                break
        columnas = math.lcm(*tamanos)
        items = [(t.clave, columnas // len(f), 1) for f in filas for t in f]
        return {"columnas": columnas, "filas": 0, "pos": empaquetar(items, columnas)[0]}

    def normalizar(self, pos, primero=None, hueco=None):
        """Quita solapes: se respeta la posición de `primero` y luego la de los demás
        por orden de lectura; el que choca va a `hueco` (p. ej. el sitio que dejó el
        widget arrastrado) o, si no cabe, al primer hueco libre."""
        ocupado = set()

        def libre(f, c, h, w):
            return c >= 0 and c + w <= self.cols and f >= 0 and not (
                {(f + i, c + j) for i in range(h) for j in range(w)} & ocupado)

        resultado = {}
        # Los que no tienen sitio (None) van los últimos, al primer hueco libre.
        orden = sorted(pos, key=lambda k: (pos[k] is None, k != primero, *(pos[k] or (0, 0))[:2]))
        for k in orden:
            if pos[k] is None:
                tam = next(((h, w) for h, w in ((2, 2), (1, 2), (1, 1)) if w <= self.cols and any(
                    libre(fi, ci, h, w) for fi in range(self.filas or 1) for ci in range(self.cols - w + 1))), (1, 1))
                f, c = next((fi, ci) for fi in range(10000) for ci in range(self.cols - tam[1] + 1)
                            if libre(fi, ci, *tam))
                ocupado |= {(f + i, c + j) for i in range(tam[0]) for j in range(tam[1])}
                resultado[k] = (f, c, *tam)
                continue
            f, c, h, w = pos[k]
            w = max(1, min(w, self.cols))
            h = max(1, min(h, self.MAX_ALTO))
            c = max(0, min(c, self.cols - w))
            if not libre(f, c, h, w):
                if hueco and libre(hueco[0], min(hueco[1], self.cols - w), h, w):
                    f, c = hueco[0], min(hueco[1], self.cols - w)
                    hueco = None
                else:
                    f, c = next((fi, ci) for fi in range(10000) for ci in range(self.cols - w + 1)
                                if libre(fi, ci, h, w))
            ocupado |= {(f + i, c + j) for i in range(h) for j in range(w)}
            resultado[k] = (f, c, h, w)
        return resultado

    def recalcular(self, asignar=True):
        g = self.config_grid()
        self.cols = max(1, min(g["columnas"], self.MAX_COLUMNAS))
        guardadas = g["pos"]
        # Los que no tienen sitio guardado (una GPU nueva, un widget que se vuelve a
        # mostrar) van al final, al primer hueco libre.
        pos = {t.clave: tuple(guardadas[t.clave]) if t.clave in guardadas else None for t in self.tarjetas}
        self.celdas = self.normalizar(pos)
        usadas = max((f + h for f, _, h, _ in self.celdas.values()), default=1)
        self.filas = max(usadas, g["filas"] or 0, 1)
        self.colocar_tarjetas(asignar)

    def guardar_posiciones(self, pos):
        g = self.grid_editable()
        g["pos"].update({c: list(v) for c, v in pos.items()})  # se conservan las de los sacados del panel
        self.recalcular()
        self.app.guardar_config()

    def area(self):
        arriba = self.MARGEN_EDICION if self.editando else self.MARGEN
        return self.MARGEN, arriba, self.tam[0] - 2 * self.MARGEN, self.tam[1] - arriba - self.MARGEN

    def tam_celda(self):
        _, _, aw, ah = self.area()
        return ((aw - self.HUECO * (self.cols - 1)) / self.cols,
                (ah - self.HUECO * (self.filas - 1)) / self.filas)

    def rect_celda(self, fila, col, alto=1, ancho=1):
        ax, ay, _, _ = self.area()
        cw, ch = self.tam_celda()
        return (round(ax + col * (cw + self.HUECO)), round(ay + fila * (ch + self.HUECO)),
                round(ancho * cw + (ancho - 1) * self.HUECO), round(alto * ch + (alto - 1) * self.HUECO))

    def colocar_tarjetas(self, asignar=True):
        for t in self.tarjetas:
            if t.clave in self.celdas:
                self.lienzo.rects[t] = self.rect_celda(*self.celdas[t.clave])
        if self.editando:
            self.barra.actualizar()
        if asignar:
            self.lienzo.queue_resize()
        self.lienzo.queue_draw()

    # --- edición -------------------------------------------------------------

    def set_edicion(self, activo):
        self.editando = activo
        for t in self.tarjetas:
            # En edición, los clics van a la tarjeta (para arrastrarla), no a sus botones.
            t.set_above_child(activo)
            t.queue_draw()
        self.barra.set_visible(activo)
        if not activo:
            self.previa = None
            self.arrastre = None
            if self.get_window():
                self.get_window().set_cursor(None)
        self.colocar_tarjetas()

    def cambiar_columnas(self, delta):
        g = self.grid_editable()
        g["columnas"] = max(1, min(self.cols + delta, self.MAX_COLUMNAS))
        self.cols = g["columnas"]
        self.guardar_posiciones(self.normalizar(dict(self.celdas)))

    def cambiar_filas(self, delta):
        g = self.grid_editable()
        filas = (g["filas"] or self.filas) + delta
        usadas = max((f + h for f, _, h, _ in self.celdas.values()), default=1)
        g["filas"] = 0 if filas < usadas else filas  # por debajo de las ocupadas, automático
        self.guardar_posiciones({})

    def cambiar_tam(self, tarjeta, ancho=None, alto=None):
        f, c, h, w = self.celdas[tarjeta.clave]
        pos = dict(self.celdas)
        pos[tarjeta.clave] = (f, c, alto or h, ancho or w)
        self.guardar_posiciones(self.normalizar(pos, primero=tarjeta.clave))

    def restablecer(self):
        self.app.config.pop("panel_grid", None)
        self.recalcular()
        self.app.guardar_config()

    def celda_en(self, x, y):
        ax, ay, _, _ = self.area()
        cw, ch = self.tam_celda()
        return (max(0, round((y - ay) / (ch + self.HUECO))), max(0, round((x - ax) / (cw + self.HUECO))))

    def empezar_arrastre(self, tarjeta, ev, tipo):
        x, y, _, _ = self.lienzo.rects[tarjeta]
        self.arrastre = (tarjeta, tipo, (ev.x_root - x, ev.y_root - y))
        if tipo == "mover":
            # Encima de las demás mientras se arrastra.
            self.lienzo.remove(tarjeta)
            self.lienzo.put(tarjeta, 0, 0)

    def _mover(self, _w, ev):
        if not self.arrastre:
            return False
        tarjeta, tipo, agarre = self.arrastre
        if tipo == "mover":
            x, y, w, h = self.lienzo.rects[tarjeta]
            nx, ny = ev.x_root - agarre[0], ev.y_root - agarre[1]
            self.lienzo.rects[tarjeta] = (round(nx), round(ny), w, h)
            _, _, ha, wa = self.celdas[tarjeta.clave]
            fila, col = self.celda_en(nx, ny)
            self.previa = (min(fila, self.filas - 1), min(col, self.cols - wa), ha, wa)
            self.lienzo.queue_resize()
        else:
            fila, col, _, _ = self.celdas[tarjeta.clave]
            ox, oy, _, _ = self.rect_celda(fila, col)
            cw, ch = self.tam_celda()
            ancho = max(1, min(round((ev.x_root - ox) / (cw + self.HUECO)), self.cols - col))
            alto = max(1, min(round((ev.y_root - oy) / (ch + self.HUECO)), self.MAX_ALTO))
            self.previa = (fila, col, alto, ancho)
        self.lienzo.queue_draw()
        return True

    def _soltar(self, _w, _ev):
        if not self.arrastre:
            return False
        tarjeta, tipo, _ = self.arrastre
        self.arrastre = None
        previa, self.previa = self.previa, None
        if previa and tipo == "mover":
            origen = self.celdas[tarjeta.clave]
            pos = dict(self.celdas)
            pos[tarjeta.clave] = previa
            # El que estorbe se va al sitio que deja el arrastrado (como un intercambio).
            self.guardar_posiciones(self.normalizar(pos, primero=tarjeta.clave, hueco=origen[:2]))
        elif previa:
            self.cambiar_tam(tarjeta, previa[3], previa[2])
        else:
            self.colocar_tarjetas()
        return True

    def dibujar(self, _w, cr):
        w, h = self.lienzo.get_allocated_width(), self.lienzo.get_allocated_height()
        pintar_fondo(cr, self.app.tema["panel"], w, h, 1.0, "panel_")
        if self.editando:
            cr.set_line_width(1)
            cr.set_dash([4, 4])
            for f in range(self.filas):
                for c in range(self.cols):
                    x, y, cw, ch = self.rect_celda(f, c)
                    rect_redondeado(cr, x + 0.5, y + 0.5, cw - 1, ch - 1, 8)
                    cr.set_source_rgba(*TENUE, 0.03)
                    cr.fill_preserve()
                    cr.set_source_rgba(*TENUE, 0.18)
                    cr.stroke()
            cr.set_dash([])
        if self.previa:
            x, y, cw, ch = self.rect_celda(*self.previa)
            rect_redondeado(cr, x + 1, y + 1, cw - 2, ch - 2, 10)
            cr.set_source_rgba(*COLORES["azul"], 0.2)
            cr.fill_preserve()
            cr.set_source_rgba(*COLORES["azul"], 0.86)
            cr.set_line_width(2)
            cr.stroke()
        return False

    def _tecla(self, _w, ev):
        if ev.keyval in (Gdk.KEY_q, Gdk.KEY_Q) and ev.state & Gdk.ModifierType.CONTROL_MASK:
            self.app.salir()
        elif ev.keyval == Gdk.KEY_Escape and self.editando:
            self.set_edicion(False)
        return False

    def _pulsar(self, _w, ev):
        if ev.button == 3 and ev.type == Gdk.EventType.BUTTON_PRESS:
            menu = Gtk.Menu()
            self.app.acciones_comunes(menu)
            menu.show_all()
            self._menu = menu
            menu.popup_at_pointer(ev)
            return True
        return False


class Sonda(Gtk.Window):
    """Capa invisible a pantalla completa para saber el área libre de un monitor
    (la pantalla menos el panel y el dock de COSMIC)."""

    def __init__(self, monitor, listo):
        super().__init__()
        self.listo = listo
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "moondeck-sonda")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.BACKGROUND)
        GtkLayerShell.set_monitor(self, monitor)
        for borde in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                      GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self, borde, True)
        GtkLayerShell.set_exclusive_zone(self, 0)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.NONE)
        self.connect("draw", VentanaCristal._limpiar)
        self.connect("realize", lambda w: w.get_window().input_shape_combine_region(cairo.Region(), 0, 0))
        self.connect("map-event", lambda *_: GLib.timeout_add(250, self._medir))
        self.show()

    def _medir(self):
        a = self.get_allocation()
        self.destroy()
        self.listo(a.width, a.height)
        return False


# ---------------------------------------------------------------------------
# Ventana de configuración
# ---------------------------------------------------------------------------

AUTOARRANQUE = os.path.expanduser("~/.config/autostart/moondeck.desktop")

def texto_actualizacion(a):
    """Qué decir del actualizador `a` y qué hace el botón: (texto, botón, acción o None)."""
    if a.desde_codigo:
        return (_("Estás ejecutando MoonDeck desde el código fuente: actualízalo con git pull."),
                _("Buscar actualizaciones"), None)
    v = a.version_nueva
    if a.ocupado:
        if a.estado == "descargando":
            return _("Descargando la versión {v}… {p}").format(v=v, p=f"{a.progreso:.0%}"), _("Descargando…"), None
        return {"buscando": _("Buscando…"), "instalando": _("Instalando…")}.get(a.estado, "…"), _("Espera…"), None
    if a.estado == "al_dia":
        return _("Tienes la última versión ({v}).").format(v=a.version), _("Buscar actualizaciones"), "buscar"
    if a.estado == "nueva":
        return _("Hay una versión nueva: {v}.").format(v=v), _("Actualizar a la {v}").format(v=v), "actualizar"
    if a.estado == "listo":
        return _("Listo. Reinicia MoonDeck para usar la versión nueva."), _("Reiniciar MoonDeck"), "reiniciar"
    if a.estado == "error":
        return _("No se ha podido: {error}").format(error=a.error), _("Buscar actualizaciones"), "buscar"
    return "", _("Buscar actualizaciones"), "buscar"


class VentanaConfig(Gtk.Window):
    """Temas, colores, fuentes, fondos, disposición por defecto y ajustes generales.
    Todo se aplica al momento."""

    # (clave, título en la barra lateral, una frase arriba de la página)
    PAGINAS = (("tema", "Tema", "Colores y letra de todo MoonDeck. Los cambios se aplican al momento."),
               ("ajustes", "Opciones de widgets", "Lo que muestra y hace cada widget. Cuáles se ven se elige "
                                                  "con el clic derecho › Widgets visibles."),
               ("titulos", "Títulos y fondos", "Quita el título o el fondo a los widgets que quieras."),
               ("widgets", "Estilo · modo widgets", "Cómo se ven los widgets sueltos por el escritorio."),
               ("panel", "Estilo · modo panel", "Cómo se ve el modo panel: el velo que cubre la pantalla y "
                                                "sus tarjetas."),
               ("disposicion", "Disposición y tamaño", "Dónde se colocan los widgets y de qué tamaño."),
               ("packs", "Tienda", None),
               ("general", "General", "Idioma, arranque, lecturas y actualizaciones."))

    def __init__(self, app):
        super().__init__(title=_("Configuración · MoonDeck"))
        self.app = app
        self.set_default_size(820, 660)
        self._guardar = None
        raiz = caja(False, 0)
        self.pila = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, hexpand=True)
        lateral = Gtk.StackSidebar(stack=self.pila)
        lateral.set_size_request(210, -1)
        raiz.pack_start(lateral, False, False, 0)
        raiz.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)
        raiz.pack_start(self.pila, True, True, 0)
        self.add(raiz)
        self.construir()
        self.show_all()

    # --- piezas -----------------------------------------------------------------

    def construir(self, pagina=None):
        """(Re)hace todas las páginas con los valores actuales (p. ej. tras elegir un tema)."""
        pagina = pagina or self.pila.get_visible_child_name()
        for hijo in self.pila.get_children():
            self.pila.remove(hijo)
        for clave, titulo, intro in self.PAGINAS:
            scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
            cont = caja(True, 18)
            for lado in ("top", "bottom", "start", "end"):
                getattr(cont, f"set_margin_{lado}")(22)
            if intro:
                lb = Gtk.Label(label=_(intro), xalign=0, wrap=True, max_width_chars=70)
                lb.get_style_context().add_class("dim-label")
                cont.pack_start(lb, False, False, 0)
            getattr(self, f"pagina_{clave}")(cont)
            scroll.add(cont)
            self.pila.add_titled(scroll, clave, _(titulo))
        self.pila.show_all()
        if pagina:
            self.pila.set_visible_child_name(pagina)

    def grupo(self, cont, titulo, texto=None):
        lb = Gtk.Label(xalign=0)
        lb.set_markup(f"<b>{GLib.markup_escape_text(_(titulo))}</b>")
        cont.pack_start(lb, False, False, 0)
        if texto:
            ayuda = Gtk.Label(label=_(texto), xalign=0, wrap=True, max_width_chars=70)
            ayuda.get_style_context().add_class("dim-label")
            cont.pack_start(ayuda, False, False, 0)
        marco = Gtk.Frame()
        lista = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        marco.add(lista)
        cont.pack_start(marco, False, False, 0)
        return lista

    @staticmethod
    def fila(lista, titulo, control, subtitulo=None):
        f = caja(False, 12)
        for lado in ("top", "bottom"):
            getattr(f, f"set_margin_{lado}")(8)
        f.set_margin_start(12)
        f.set_margin_end(12)
        textos = caja(True, 2)
        textos.pack_start(Gtk.Label(label=_(titulo), xalign=0), False, False, 0)
        if subtitulo:
            sub = Gtk.Label(label=_(subtitulo), xalign=0, wrap=True, max_width_chars=50)
            sub.get_style_context().add_class("dim-label")
            textos.pack_start(sub, False, False, 0)
        f.pack_start(textos, True, True, 0)
        control.set_valign(Gtk.Align.CENTER)
        f.pack_start(control, False, False, 0)
        fila = Gtk.ListBoxRow(activatable=False)
        fila.add(f)
        lista.add(fila)
        return control

    def cambiar(self, seccion, clave, valor):
        t = self.app.tema
        t[seccion][clave] = valor
        self.app.config["tema"] = t
        self.app.aplicar_tema()

    def color(self, seccion, clave):
        b = Gtk.ColorButton(rgba=Gdk.RGBA(*hex_rgb(self.app.tema[seccion][clave]), 1))
        b.connect("color-set", lambda b: self.cambiar(seccion, clave, temas.a_hex(
            (b.get_rgba().red, b.get_rgba().green, b.get_rgba().blue))))
        return b

    def deslizador(self, seccion, clave, minimo, maximo, factor=1.0, sufijo=" %"):
        """Deslizador para un número del tema; `factor` pasa del valor guardado al mostrado."""
        sl = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, minimo, maximo, 1)
        sl.set_size_request(240, -1)
        sl.set_value(self.app.tema[seccion][clave] * factor)
        sl.connect("format-value", lambda _s, v: f"{v:.0f}{sufijo}")
        sl.set_value_pos(Gtk.PositionType.RIGHT)
        sl.connect("value-changed", lambda s: self.cambiar(seccion, clave, s.get_value() / factor))
        return sl

    def interruptor(self, seccion, clave):
        sw = Gtk.Switch(active=bool(self.app.tema[seccion][clave]))
        sw.connect("notify::active", lambda w, _p: self.cambiar(seccion, clave, w.get_active()))
        return sw

    # --- páginas -------------------------------------------------------------------

    def pagina_tema(self, cont):
        lista = self.grupo(cont, "Temas de serie", "Un clic y se aplica a todo. Después puedes retocar lo que quieras.")
        flujo = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4, row_spacing=10,
                            column_spacing=10, homogeneous=True)
        for lado in ("top", "bottom", "start", "end"):
            getattr(flujo, f"set_margin_{lado}")(12)
        for nombre, t in temas.PREDEFINIDOS.items():
            b = Gtk.Button()
            b.set_relief(Gtk.ReliefStyle.NONE)
            caj = caja(True, 6)
            muestra = Gtk.DrawingArea()
            muestra.set_size_request(130, 64)
            muestra.connect("draw", lambda w, cr, t=t: self.pintar_muestra(w, cr, t))
            caj.pack_start(muestra, False, False, 0)
            caj.pack_start(Gtk.Label(label=_(nombre)), False, False, 0)
            b.add(caj)
            b.connect("clicked", lambda _b, t=t: self.elegir_tema(t))
            flujo.add(b)
        fila = Gtk.ListBoxRow(activatable=False)
        fila.add(flujo)
        lista.add(fila)

        g = "global"
        lista = self.grupo(cont, "Colores")
        self.fila(lista, "Color de acento", self.color(g, "acento"), "Barras, botones, el día de hoy, deslizadores…")
        self.fila(lista, "Texto principal", self.color(g, "texto"), "Cifras grandes, horas, nombres")
        self.fila(lista, "Texto secundario", self.color(g, "texto_sec"), "Detalles y leyendas")

        lista = self.grupo(cont, "Letra")
        fuente = Gtk.FontButton(show_size=False, use_font=True)
        if self.app.tema[g]["fuente"]:
            fuente.set_font(f"{self.app.tema[g]['fuente']} 11")
        fuente.connect("font-set", lambda b: self.cambiar(g, "fuente", b.get_font_family().get_name()))
        sistema = Gtk.Button(label=_("La del sistema"))
        sistema.connect("clicked", lambda _b: (self.cambiar(g, "fuente", ""), self.construir()))
        fila = caja(False, 6)
        fila.pack_start(fuente, False, False, 0)
        fila.pack_start(sistema, False, False, 0)
        self.fila(lista, "Fuente", fila)
        self.fila(lista, "Tamaño de letra", self.deslizador(g, "escala", 70, 150, 100))

        lista = self.grupo(cont, "Compartir el tema", "Guarda tu tema en un archivo para pasárselo a quien quieras, "
                                                      "o carga uno. Las imágenes de fondo van por su ruta: quien lo "
                                                      "cargue tiene que tener esas imágenes en su equipo.")
        botones = caja(False, 6)
        for texto, fn in ((_("Exportar…"), self.exportar), (_("Importar…"), self.importar),
                          (_("Volver al tema de serie"), lambda: self.elegir_tema(temas.POR_DEFECTO))):
            b = Gtk.Button(label=texto)
            b.connect("clicked", lambda _b, fn=fn: fn())
            botones.pack_start(b, False, False, 0)
        self.fila(lista, "Archivo de tema", botones)

    def pintar_muestra(self, w, cr, t):
        """Miniatura de un tema: fondo del panel, una tarjeta y el acento."""
        t = temas.completo(t)
        ancho, alto = w.get_allocated_width(), w.get_allocated_height()
        rect_redondeado(cr, 0, 0, ancho, alto, 8)
        cr.clip()
        cr.set_source_rgb(0.35, 0.25, 0.4)  # algo detrás, como el fondo de pantalla
        cr.paint()
        pintar_fondo(cr, t["panel"], ancho, alto, 1.0, "panel_")
        p = t["widgets"]
        cr.save()
        cr.translate(10, 10)
        rect_redondeado(cr, 0, 0, ancho - 20, alto - 20, min(p["radio"], 10))
        cr.clip()
        pintar_fondo(cr, p, ancho - 20, alto - 20, 1.0)
        cr.restore()
        rect_redondeado(cr, 10.5, 10.5, ancho - 21, alto - 21, min(p["radio"], 10))
        cr.set_source_rgba(*hex_rgb(p["borde"]), max(p["borde_opacidad"], 0.15))
        cr.set_line_width(1)
        cr.stroke()
        cr.set_source_rgb(*hex_rgb(t["global"]["texto"]))
        cr.rectangle(20, 20, 40, 7)
        cr.fill()
        cr.set_source_rgb(*hex_rgb(t["global"]["texto_sec"]))
        cr.rectangle(20, 32, 60, 4)
        cr.fill()
        cr.set_source_rgb(*hex_rgb(t["global"]["acento"]))
        rect_redondeado(cr, 20, 42, ancho - 40, 5, 2.5)
        cr.fill()

    def elegir_tema(self, t):
        nuevo = temas.completo(t)
        # La letra es cosa de cada uno: un tema no la cambia.
        for clave in ("fuente", "escala"):
            nuevo["global"][clave] = self.app.tema["global"][clave]
        self.app.config["tema"] = nuevo
        self.app.aplicar_tema()
        self.construir()

    def pagina_ajustes(self, cont):
        """Ajustes de cada widget: el tiempo, el calendario, el reloj y los títulos."""
        app = self.app
        lista = self.grupo(cont, "Tiempo")
        fila = caja(False, 8)
        c = app.tiempo.ciudad
        lugar = Gtk.Label(label=f"{c['nombre']}" + (f" · {c['region']}" if c.get("region") else ""), xalign=1)
        lugar.get_style_context().add_class("dim-label")
        cambiar = Gtk.Button(label=_("Cambiar…"))
        cambiar.connect("clicked", lambda _b: (app.elegir_ciudad(), self.construir()))
        fila.pack_start(lugar, False, False, 0)
        fila.pack_start(cambiar, False, False, 0)
        self.fila(lista, "Ciudad", fila, "Busca tu ciudad para ver su tiempo")

        lista = self.grupo(cont, "Calendario")
        semana = Gtk.ComboBoxText()
        for dia in (0, 6):
            semana.append(str(dia), idioma.dia_semana(dia).capitalize())
        semana.set_active_id(str(app.primer_dia()))
        semana.connect("changed", lambda w: app.cambiar_semana(int(w.get_active_id())))
        self.fila(lista, "La semana empieza en", semana)

        lista = self.grupo(cont, "Reloj")
        o = app.config["reloj"]
        tipo = Gtk.ComboBoxText()
        for clave, nombre in ESTILOS_RELOJ:
            tipo.append(clave, _(nombre))
        tipo.set_active_id(o["estilo"])
        tipo.connect("changed", lambda w: app.cambiar_reloj(estilo=w.get_active_id()))
        self.fila(lista, "Tipo de reloj", tipo, "Las ciudades del reloj mundial, con clic derecho en el reloj")
        for texto, clave in (("Formato 24 horas", "h24"), ("Mostrar segundos", "segundos"), ("Mostrar la fecha", "fecha")):
            sw = Gtk.Switch(active=bool(o[clave]))
            sw.connect("notify::active", lambda w, _p, c=clave: app.cambiar_reloj(**{c: w.get_active()}))
            self.fila(lista, texto, sw)
        nixie = Gtk.ColorButton(rgba=Gdk.RGBA(*hex_rgb(o.get("nixie", esferas.NIXIE_POR_DEFECTO)), 1))
        nixie.connect("color-set", lambda b: app.cambiar_reloj(nixie=temas.a_hex(
            (b.get_rgba().red, b.get_rgba().green, b.get_rgba().blue))))
        self.fila(lista, "Color de los tubos Nixie", nixie)

        packs.llamar(app.packs, "ajustes", self, cont)

    def pagina_titulos(self, cont):
        """Título (CPU, RELOJ…) y fondo con borde de cada widget, en una sola lista."""
        app = self.app
        lista = self.grupo(cont, "Cada widget", "Sin título se gana espacio; sin fondo ni borde, del widget "
                                                "solo se ve su contenido.")
        sin = app.config.get("sin_titulo", [])
        for t in app.tarjetas:
            botones = caja(False, 14)
            titulo = Gtk.CheckButton(label=_("Título"), active=t.clave not in sin)
            titulo.connect("toggled", lambda w, t=t: app.alternar_titulo(t, w.get_active()))
            fondo = Gtk.CheckButton(label=_("Fondo"), active=not t.sin_fondo())
            fondo.connect("toggled", lambda w, t=t: app.alternar_fondo(t, w.get_active()))
            botones.pack_start(titulo, False, False, 0)
            botones.pack_start(fondo, False, False, 0)
            self.fila(lista, t.nombre_menu, botones)

    def pagina_tarjetas(self, cont, seccion):
        lista = self.grupo(cont, "Fondo")
        self.fila(lista, "Color", self.color(seccion, "fondo"))
        self.fila(lista, "Opacidad", self.deslizador(seccion, "opacidad", 0, 100, 100), "0 % = solo cristal")
        self.fila(lista, "Degradado", self.interruptor(seccion, "degradado"), "Del color de fondo a un segundo color")
        self.fila(lista, "Segundo color", self.color(seccion, "fondo2"))
        self.fila(lista, "Dirección del degradado", self.deslizador(seccion, "angulo", 0, 360, 1, "°"))
        self.fila(lista, "Desenfoque (cristal)", self.interruptor(seccion, "cristal"),
                  _("Desenfoca lo que hay detrás") + (_(" de las tarjetas") if seccion == "widgets" else _(" del panel")))
        lista = self.grupo(cont, "Borde y esquinas")
        self.fila(lista, "Color del borde", self.color(seccion, "borde"))
        self.fila(lista, "Opacidad del borde", self.deslizador(seccion, "borde_opacidad", 0, 100, 100))
        self.fila(lista, "Grosor del borde", self.deslizador(seccion, "borde_grosor", 0, 4, 1, " px"))
        self.fila(lista, "Esquinas redondeadas", self.deslizador(seccion, "radio", 0, 30, 1, " px"))
        lista = self.grupo(cont, "Neón", "El borde se convierte en un tubo de luz de su color (sube la opacidad "
                                         "del borde para que brille más).")
        self.fila(lista, "Modo neón", self.interruptor(seccion, "neon"))
        self.fila(lista, "Parpadeo", self.interruptor(seccion, "parpadeo"),
                  "De vez en cuando el neón falla, como un tubo viejo")

    def pagina_widgets(self, cont):
        self.pagina_tarjetas(cont, "widgets")

    def pagina_panel(self, cont):
        s = "panel"
        lista = self.grupo(cont, "Fondo del panel", "El velo que cubre toda la pantalla en el modo panel.")
        self.fila(lista, "Color", self.color(s, "panel_fondo"))
        self.fila(lista, "Opacidad", self.deslizador(s, "panel_opacidad", 0, 100, 100), "0 % = solo cristal")
        self.pagina_tarjetas(cont, s)

    def numero(self, clave, minimo, maximo, paso, digitos, fn):
        b = Gtk.SpinButton.new_with_range(minimo, maximo, paso)
        b.set_digits(digitos)
        b.set_value(self.app.config.get(clave, {"ancho": ANCHO, "columnas": COLUMNAS, "intervalo": INTERVALO}[clave]))
        b.connect("value-changed", lambda b: fn(b.get_value()))
        return b

    def pagina_disposicion(self, cont):
        cfg = self.app.config
        lista = self.grupo(cont, "Modo panel", "«Restablecer disposición» vuelve a la que guardes aquí.")
        guardar = Gtk.Button(label=_("Guardar la actual"))
        guardar.connect("clicked", lambda _b: self.guardar_panel())
        self.fila(lista, "Disposición predeterminada", guardar,
                  _("Personalizada") if cfg.get("panel_predeterminado") else _("La de fábrica"))
        fabrica = Gtk.Button(label=_("Volver a la de fábrica"))
        fabrica.set_sensitive(bool(cfg.get("panel_predeterminado")))
        fabrica.connect("clicked", lambda _b: (cfg.pop("panel_predeterminado", None), self.app.guardar_config(),
                                                self.construir()))
        self.fila(lista, "Disposición de fábrica", fabrica)

        lista = self.grupo(cont, "Modo widgets", "«Recolocar widgets» los pondrá donde estén ahora.")
        guardar = Gtk.Button(label=_("Guardar las actuales"))
        guardar.set_sensitive(self.app.modo == "widgets")
        guardar.connect("clicked", lambda _b: self.guardar_widgets())
        self.fila(lista, "Posiciones predeterminadas", guardar,
                  _("Personalizadas") if cfg.get("posiciones_predeterminadas") else _("Automáticas (por columnas)")
                  + ("" if self.app.modo == "widgets" else _(" · cambia a modo widgets para guardarlas")))
        auto = Gtk.Button(label=_("Volver a automáticas"))
        auto.set_sensitive(bool(cfg.get("posiciones_predeterminadas")))
        auto.connect("clicked", lambda _b: (cfg.pop("posiciones_predeterminadas", None), self.app.guardar_config(),
                                             self.construir()))
        self.fila(lista, "Colocación automática", auto)

        lista = self.grupo(cont, "Tamaño", "En el modo widgets.")
        self.fila(lista, "Ancho de cada widget", self.numero("ancho", 260, 560, 10, 0, self.app.cambiar_ancho),
                  "En píxeles")
        self.fila(lista, "Columnas al colocarlos", self.numero("columnas", 1, 8, 1, 0, self.app.cambiar_columnas),
                  "Las mínimas: si no caben en alto, se usan más")

    def guardar_panel(self):
        p = self.app.panel
        grid = self.app.config.get("panel_grid")
        if not grid and p:
            grid = {"columnas": p.cols, "filas": 0, "pos": {c: list(v) for c, v in p.celdas.items()}}
        if grid:
            self.app.config["panel_predeterminado"] = json.loads(json.dumps(grid))
            self.app.guardar_config()
        self.construir()

    def guardar_widgets(self):
        self.app.config["posiciones_predeterminadas"] = {
            t.clave: list(t.ventana.pos) for t in self.app.tarjetas if t.ventana}
        self.app.guardar_config()
        self.construir()

    def pagina_packs(self, cont):
        """La tienda: borrar los widgets que no se usan y volver a descargarlos de GitHub."""
        app = self.app
        g = app.gestor_packs
        lista = self.grupo(cont, "Widgets", "Instala solo los que uses: bórralos cuando quieras y vuelve a "
                                             "descargarlos de GitHub. Se aplica al reiniciar MoonDeck.")
        for ident, nombre, texto, widgets, _x in packs.CATALOGO:
            if not packs.borrable(ident):
                control = Gtk.Label(label=_("Incluido"))
                control.get_style_context().add_class("dim-label")
            elif g.ocupado_con == ident:
                control = Gtk.Button(label=_("Descargando…"), sensitive=False)
            elif g.instalado(ident):
                control = Gtk.Button(label=_("Borrar"), sensitive=not g.ocupado and not g.desde_codigo)
                control.get_style_context().add_class("destructive-action")
                if g.desde_codigo:
                    control.set_tooltip_text(_("Ejecutando desde el código: aquí no se borra nada."))
                control.connect("clicked", lambda _b, i=ident: (g.borrar(i), self.construir("packs")))
            else:
                control = Gtk.Button(label=_("Descargar"), sensitive=not g.ocupado)
                control.get_style_context().add_class("suggested-action")
                control.connect("clicked", lambda _b, i=ident: self.descargar_pack(i))
            self.fila(lista, nombre, control, _(texto) + ("" if widgets == (nombre,) else
                                                      "\n" + " · ".join(_(w) for w in widgets)))
        aviso = (_("No se pudo descargar: {error}").format(error=g.error) if g.estado == "error" else
                 _("Reinicia MoonDeck para ver los cambios.") if g.cambiado else "")
        if aviso:
            fila = caja(False, 8)
            lb = Gtk.Label(label=aviso, xalign=0, wrap=True, max_width_chars=60)
            fila.pack_start(lb, True, True, 0)
            if g.cambiado and g.estado != "error":
                reiniciar = Gtk.Button(label=_("Reiniciar ahora"))
                reiniciar.get_style_context().add_class("suggested-action")
                reiniciar.connect("clicked", lambda _b: app.actualizador.reiniciar(app.salir))
                fila.pack_start(reiniciar, False, False, 0)
            cont.pack_start(fila, False, False, 0)

    def descargar_pack(self, ident):
        self.app.gestor_packs.descargar(ident)
        self.construir("packs")

        def mirar():
            if self.app.gestor_packs.ocupado:
                return True
            if self.get_visible():
                self.construir("packs")
            return False
        GLib.timeout_add(300, mirar)

    def pagina_general(self, cont):
        app = self.app
        lista = self.grupo(cont, "Idioma")
        fila = caja(False, 8)
        elegir = Gtk.ComboBoxText()
        for codigo, nombre in idioma.IDIOMAS:
            elegir.append(codigo, nombre)
        elegir.set_active_id(idioma.actual())
        reiniciar = Gtk.Button(label=_("Reiniciar ahora"))
        reiniciar.set_no_show_all(True)
        reiniciar.connect("clicked", lambda _b: app.actualizador.reiniciar(app.salir))

        def cambio(w):
            app.config["idioma"] = w.get_active_id()
            app.guardar_config()
            reiniciar.set_visible(w.get_active_id() != idioma.actual())
        elegir.connect("changed", cambio)
        fila.pack_start(elegir, False, False, 0)
        fila.pack_start(reiniciar, False, False, 0)
        self.fila(lista, "Idioma", fila, "Se aplica al reiniciar MoonDeck")

        lista = self.grupo(cont, "Arranque")
        sw = Gtk.Switch(active=os.path.exists(AUTOARRANQUE))
        sw.connect("notify::active", lambda w, _p: app.autoarranque(w.get_active()))
        self.fila(lista, "Abrir al iniciar sesión", sw)

        lista = self.grupo(cont, "Escritorios virtuales")
        sw = Gtk.Switch(active=app.config.get("rueda_escritorios", True))
        sw.connect("notify::active", lambda w, _p: (app.config.__setitem__("rueda_escritorios", w.get_active()),
                                                     app.guardar_config()))
        self.fila(lista, "Cambiar de escritorio con la rueda del ratón", sw,
                  "Girando la rueda sobre un widget (menos en las barras de volumen y similares). "
                  "Con Ctrl + rueda abajo, se ven todos los escritorios.")

        lista = self.grupo(cont, "Sensores")
        self.fila(lista, "Actualizar cada", self.numero("intervalo", 0.5, 5, 0.5, 1, app.cambiar_intervalo),
                  "Segundos entre lecturas de los sensores")

        lista = self.grupo(cont, "Actualizaciones", _("Busca la última versión estable en github.com/{repo}. "
                                                      "Tu configuración se conserva.").format(repo=REPO))
        botones = caja(False, 6)
        self.upd_boton = Gtk.Button(label=_("Buscar actualizaciones"))
        self.upd_boton.get_style_context().add_class("suggested-action")
        self.upd_boton.connect("clicked", lambda _b: self.pulsar_actualizar())
        self.upd_atras = Gtk.Button(label=_("Volver a la anterior"))
        self.upd_atras.set_tooltip_text(_("Deshace la última actualización"))
        self.upd_atras.connect("clicked", lambda _b: app.actualizador.volver_atras())
        botones.pack_start(self.upd_boton, False, False, 0)
        botones.pack_start(self.upd_atras, False, False, 0)
        self.fila(lista, f"MoonDeck {VERSION}", botones)
        self.upd_estado = Gtk.Label(xalign=0, wrap=True, max_width_chars=70, selectable=True)
        self.upd_notas = Gtk.Label(xalign=0, wrap=True, max_width_chars=70, selectable=True)
        self.upd_notas.get_style_context().add_class("dim-label")
        for lb in (self.upd_estado, self.upd_notas):
            lb.set_margin_start(12)
            lb.set_margin_end(12)
            lb.set_margin_bottom(8)
            fila = Gtk.ListBoxRow(activatable=False)
            fila.add(lb)
            lista.add(fila)
        self._accion_actualizar = "buscar"
        self.refrescar_actualizacion()
        GLib.timeout_add(300, self.refrescar_actualizacion)

    def pulsar_actualizar(self):
        a = self.app.actualizador
        {"buscar": a.buscar, "actualizar": a.actualizar,
         "reiniciar": lambda: a.reiniciar(self.app.salir)}.get(self._accion_actualizar, lambda: None)()
        self.refrescar_actualizacion()

    def refrescar_actualizacion(self):
        if not self.upd_estado.get_mapped() and self.upd_estado.get_toplevel() is not self:
            return False  # se rehízo la página o se cerró la ventana
        a = self.app.actualizador
        texto, boton, accion = texto_actualizacion(a)
        self._accion_actualizar = accion
        poner_texto(self.upd_estado, texto)
        self.upd_estado.set_visible(bool(texto))
        notas = a.notas if a.estado == "nueva" else ""
        poner_texto(self.upd_notas, notas[:800])
        self.upd_notas.set_visible(bool(notas))
        self.upd_boton.set_label(boton)
        self.upd_boton.set_sensitive(accion is not None)
        self.upd_atras.set_sensitive(a.hay_anterior() and not a.ocupado and not a.desde_codigo)
        return True

    # --- archivos de tema -------------------------------------------------------

    def exportar(self):
        d = Gtk.FileChooserDialog(title=_("Exportar tema"), transient_for=self, action=Gtk.FileChooserAction.SAVE)
        d.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL, _("Guardar"), Gtk.ResponseType.OK)
        d.set_current_name("mi-tema.json")
        d.set_do_overwrite_confirmation(True)
        if d.run() == Gtk.ResponseType.OK:
            try:
                with open(d.get_filename(), "w") as f:
                    json.dump({"tema_moondeck": 1, **self.app.tema}, f, indent=1, ensure_ascii=False)
            except OSError as e:
                self.aviso(_("No se pudo guardar: {error}").format(error=e))
        d.destroy()

    def importar(self):
        d = Gtk.FileChooserDialog(title=_("Importar tema"), transient_for=self, action=Gtk.FileChooserAction.OPEN)
        d.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL, _("Abrir"), Gtk.ResponseType.OK)
        filtro = Gtk.FileFilter()
        filtro.set_name(_("Temas (.json)"))
        filtro.add_pattern("*.json")
        d.add_filter(filtro)
        if d.run() == Gtk.ResponseType.OK:
            try:
                with open(d.get_filename()) as f:
                    datos = json.load(f)
                if not isinstance(datos, dict) or not any(k in datos for k in ("global", "widgets", "panel")):
                    raise ValueError(_("no es un archivo de tema"))
                self.elegir_tema(datos)
            except (OSError, ValueError) as e:
                self.aviso(_("No se pudo cargar el tema: {error}").format(error=e))
        d.destroy()

    def aviso(self, texto):
        m = Gtk.MessageDialog(transient_for=self, message_type=Gtk.MessageType.WARNING,
                              buttons=Gtk.ButtonsType.CLOSE, text=texto)
        m.run()
        m.destroy()


# ---------------------------------------------------------------------------
# Aplicación
# ---------------------------------------------------------------------------

# Los packs de widgets (pack_*.py): sus métodos se añaden a Monitor.
PACKS = packs.cargar(os.path.dirname(os.path.abspath(__file__)), log, CONFIG)


class Monitor(*[p.Metodos for p in PACKS if hasattr(p, "Metodos")]):
    def __init__(self):
        self.colocado = False
        log("Capas (gtk-layer-shell):", CAPAS, "| bandeja:", bool(AppIndicator), "| efecto:", EFECTO)
        idioma.poner(self.cargar_config().get("idioma") or idioma.detectar())
        log("Abriendo sensores...")
        self.sampler = Sampler()
        log("nvidia-smi:", "sí" if self.sampler.has_nvidia_smi else "no")
        first = self.sampler.sample()
        log("GPUs:", [g["name"] for g in first["gpus"]], "| temperaturas:", len(first["temps"]),
            "| ventiladores:", len(first["fans"]))
        self.config = self.cargar_config()
        if not self.config.get("juegos_visto"):
            # El widget de juegos llega oculto (también al actualizar): se activa en "Widgets visibles".
            self.config.setdefault("ocultos", []).append("juegos")
            self.config["juegos_visto"] = True
        if not self.config.get("apps_visto"):
            # El lanzador llega oculto (vacío no aporta nada): se activa en "Widgets visibles".
            self.config.setdefault("ocultos", []).append("apps")
            self.config["apps_visto"] = True
        for clave in ("immich", "docker"):
            if not self.config.get(f"{clave}_visto"):  # widgets nuevos: llegan ocultos
                self.config.setdefault("ocultos", []).append(clave)
                self.config[f"{clave}_visto"] = True
        idioma.poner(self.config.get("idioma") or idioma.detectar())
        global ANCHO, COLUMNAS, INTERVALO
        ANCHO = int(self.config.get("ancho", ANCHO))
        COLUMNAS = int(self.config.get("columnas", COLUMNAS))
        INTERVALO = float(self.config.get("intervalo", INTERVALO))
        self.ventana_config = None
        self._guardar_tema = None
        self.aplicar_tema(guardar=False)
        self.manual = False  # True cuando el usuario arrastra un widget
        self.areas = {}      # monitor -> (ancho, alto) del área libre
        self.reproductores = Reproductores()
        self.mezclador = Mezclador()
        self.dispositivos = Dispositivos()
        self.escritorios = Escritorios()
        self._rueda, self._rueda_t, self._rueda_ult = 0.0, 0.0, 0.0
        self.actualizador = Actualizador(os.path.dirname(os.path.abspath(__file__)))
        self.tiempo = Tiempo(self.config.get("tiempo_ciudad") or CIUDAD_POR_DEFECTO)
        self.actualizador.omitir = packs.omitidos(self.config.get("packs_borrados", []))
        self.gestor_packs = packs.Gestor(self.actualizador.carpeta, self.config, self.guardar_config)
        self.packs = PACKS
        packs.llamar(self.packs, "iniciar", self)
        log("Audio:", "OK" if self.mezclador.ok else self.mezclador.error,
            "| reproductores:", "OK" if self.reproductores.ok else self.reproductores.error)

        self.modo = self.config.get("modo", "widgets")
        self.panel = None
        self.tarjetas = []
        self.construir(first)
        for t in self.tarjetas:
            t.show_all()
            t.set_opacidad(self.config["opacidad"].get(t.clave, 1.0))
        self.poner_titulos()
        self.aplicar(first)
        self.actualizar_multimedia()
        self.actualizar_reloj()
        self.actualizar_audio()
        packs.llamar(self.packs, "arrancar", self)
        self.marcar_titulos()

        self.bandeja = None
        if AppIndicator:
            self.bandeja = AppIndicator.Indicator.new(
                "moondeck", "utilities-system-monitor-symbolic",
                AppIndicator.IndicatorCategory.HARDWARE)
            self.bandeja.set_title("MoonDeck")
            self.bandeja.set_status(AppIndicator.IndicatorStatus.ACTIVE)
            self.menu_bandeja = Gtk.Menu()
            self.bandeja.set_menu(self.menu_bandeja)
            self.rehacer_bandeja()

        self.aplicar_modo(inicio=True)
        self.colocado = True

        GLib.timeout_add(1000, self.actualizar_multimedia)
        GLib.timeout_add(1000, self.actualizar_reloj)
        GLib.timeout_add(1000, self.mirar_aperturas)
        # Un fondo animado que arranca después (linux-wallpaperengine va a la misma capa) la taparía.
        GLib.timeout_add_seconds(10, lambda: self.traer_delante() and False)
        GLib.timeout_add(2000, self.actualizar_audio)
        GLib.timeout_add(1000, self.actualizar_tiempo)
        GLib.timeout_add(40, self.parpadear)
        self._activo = True
        threading.Thread(target=self.bucle, daemon=True).start()

    def tarjeta(self, clave, titulo):
        t = Tarjeta(clave, _(titulo), self)
        self.tarjetas.append(t)
        return t

    def construir(self, s):
        # CPU
        c = self.tarjeta("cpu", "CPU")
        c.add_w(etiqueta(self.sampler.cpu, "dim"))
        self.cpu_big = c.add_w(etiqueta("", "grande"))
        self.cpu_sub = c.add_w(etiqueta())
        self.cpu_temp = c.add_w(etiqueta())
        self.cpu_graf = c.add_w(Grafica(["azul", "naranja"]), prescindible=9)
        c.add_w(leyenda(("Uso %", "azul"), ("Temp °C", "naranja")), prescindible=2)
        self.cpu_nucleos = c.add_w(BarrasNucleos(len(s["cores"])), prescindible=3)
        self.uptime = c.add_w(etiqueta("", "dim"), prescindible=1)

        # Memoria
        c = self.tarjeta("memoria", "Memoria")
        self.mem_big = c.add_w(etiqueta("", "grande"))
        self.mem_sub = c.add_w(etiqueta())
        self.mem_barra = c.add_w(Barra())
        self.swap_sub = c.add_w(etiqueta(), prescindible=2)
        self.swap_barra = c.add_w(Barra(), prescindible=2)
        self.mem_graf = c.add_w(Grafica(["morado", "naranja"]), prescindible=9)
        c.add_w(leyenda(("RAM %", "morado"), ("Swap %", "naranja")), prescindible=1)

        # Una tarjeta por GPU
        self.gpus = {}
        for g in s["gpus"]:
            c = self.tarjeta(f"gpu-{g['id']}", "GPU")
            c.nombre_menu = f"GPU · {g['name']}"
            c.add_w(etiqueta(g["name"], "dim"))
            w = {"big": c.add_w(etiqueta("", "grande")), "temp": c.add_w(etiqueta()),
                 "sub": c.add_w(etiqueta(), prescindible=3), "sub2": c.add_w(etiqueta(), prescindible=2),
                 "graf": c.add_w(Grafica(["verde", "azul"]), prescindible=9)}
            c.add_w(leyenda(("Uso %", "verde"), ("VRAM %", "azul")), prescindible=1)
            self.gpus[g["id"]] = w

        # Red
        c = self.tarjeta("red", "Red")
        self.red_big = c.add_w(etiqueta("", "grande"))
        self.red_sub = c.add_w(etiqueta())
        self.red_graf = c.add_w(Grafica(["verde", "morado"], maximo=None), prescindible=9)
        c.add_w(leyenda(("Bajada", "verde"), ("Subida", "morado")), prescindible=1)

        # Discos
        c = self.tarjeta("discos", "Almacenamiento")
        self.disco_big = c.add_w(etiqueta("", "grande"))
        self.disco_sub = c.add_w(etiqueta())
        self.disco_graf = c.add_w(Grafica(["azul", "naranja"], maximo=None), prescindible=9)
        c.add_w(leyenda(("Lectura", "azul"), ("Escritura", "naranja")), prescindible=7)
        self.particiones = {}
        partes = s["parts"][:6]
        for i, (mount, *_x) in enumerate(partes):
            # Si no caben, se van quitando las últimas particiones.
            n = len(partes) - i
            self.particiones[mount] = (c.add_w(etiqueta(), prescindible=n), c.add_w(Barra(), prescindible=n))

        # Multimedia: lo que suena y volumen por app
        c = self.tarjeta("multimedia", "Multimedia")
        m = {"reproductores": caja(True, 10), "filas_rep": [], "claves_rep": None,
             "volumen": caja(True, 4), "filas_vol": [], "claves_vol": None}
        c.add_w(m["reproductores"])
        m["nada"] = c.add_w(etiqueta("No está sonando nada.", "dim"))
        m["seccion_vol"] = c.add_w(etiqueta("VOLUMEN", "seccion"))
        m["seccion_vol"].set_margin_top(8)
        # El volumen por app se desplaza con la rueda si no cabe (en vez de quitar filas).
        m["scroll_vol"] = Gtk.ScrolledWindow()
        fundido_al_desplazar(m["scroll_vol"])
        m["scroll_vol"].set_propagate_natural_height(True)
        m["scroll_vol"].set_min_content_height(30)
        m["scroll_vol"].add(m["volumen"])
        m["scroll_vol"].get_child().set_shadow_type(Gtk.ShadowType.NONE)
        c.add_w(m["scroll_vol"], expand=True)
        m["aviso"] = c.add_w(etiqueta("", "dim", envolver=True))
        m["tarjeta"] = c
        self.multimedia = m

        # Reloj (tipo y opciones en el clic derecho)
        c = self.tarjeta("reloj", "Reloj")
        opciones = dict(RELOJ_POR_DEFECTO, **self.config.get("reloj", {}))
        self.config["reloj"] = opciones
        self.reloj = c.add_w(RelojVista(opciones), expand=True)

        # Calendario
        c = self.tarjeta("calendario", "Calendario")
        cab = caja(False, 0)
        anterior, siguiente = boton_texto("‹", "plano"), boton_texto("›", "plano")
        for b in (anterior, siguiente):
            b.get_style_context().add_class("calendario")
        self.cal_titulo = boton_texto("", "plano")
        self.cal_titulo.get_style_context().add_class("mes")
        self.cal_titulo.set_tooltip_text(_("Volver a hoy"))
        cab.pack_start(anterior, False, False, 0)
        cab.set_center_widget(self.cal_titulo)
        cab.pack_end(siguiente, False, False, 0)
        c.add_w(cab)
        self.calendario = c.add_w(CalendarioMes(self.primer_dia()), expand=True)
        anterior.connect("clicked", lambda _b: self.mover_calendario(-1))
        siguiente.connect("clicked", lambda _b: self.mover_calendario(1))
        self.cal_titulo.connect("clicked", lambda _b: self.mover_calendario(0))
        self.cal_titulo.set_label(self.calendario.titulo())

        # Tiempo
        c = self.tarjeta("tiempo", "Tiempo")
        t = {"version": None}
        arriba = caja(False, 12)
        t["icono"] = Gtk.Image()
        arriba.pack_start(t["icono"], False, False, 0)
        textos = caja(True, 0)
        t["temp"] = etiqueta("—", "grande")
        t["desc"] = etiqueta("", "sub")
        textos.pack_start(t["temp"], False, False, 0)
        textos.pack_start(t["desc"], False, False, 0)
        textos.set_valign(Gtk.Align.CENTER)
        arriba.pack_start(textos, True, True, 0)
        c.add_w(arriba)
        # En una celda estrecha del panel, sin el icono grande (si no, no caben los grados).
        arriba.connect("size-allocate", lambda _w, a: GLib.idle_add(
            lambda: t["icono"].set_visible(a.width >= 220 and bool(t["icono"].get_pixbuf())) or False))
        t["detalle"] = c.add_w(etiqueta("", "dim", envolver=True), prescindible=3)
        t["horas"] = c.add_w(PronosticoHoras(), prescindible=2)
        t["horas"].set_margin_top(4)
        t["dias"] = c.add_w(PronosticoDias(), expand=True)
        t["ciudad"] = c.add_w(etiqueta("", "dim"), prescindible=1)
        self.tm = t

        # Dispositivos de audio
        c = self.tarjeta("audio", "Dispositivos de audio")
        a = {"claves": None, "filas": {}}
        # Se ve el dispositivo en uso; "Cambiar" despliega los demás.
        for clave, titulo in (("salida", "SALIDA"), ("entrada", "ENTRADA")):
            cab = caja(False, 0)
            cab.pack_start(etiqueta(titulo, "seccion"), True, True, 0)
            b = boton_texto("Cambiar ▾", "plano")
            b.get_style_context().add_class("dim")
            b.connect("clicked", lambda _b, k=clave: self.desplegar_audio(k))
            cab.pack_start(b, False, False, 0)
            a[clave + "_tit"] = c.add_w(cab)
            a[clave + "_boton"] = b
            a[clave + "_abierto"] = False
            a[clave] = c.add_w(caja(True, 2))
        a["entrada_tit"].set_margin_top(4)
        # Silenciar el micro: arriba a la derecha, siempre a mano (antes era lo primero que se quitaba).
        a["mic"] = c.poner_esquina(boton_icono("microphone-sensitivity-high-symbolic", Gtk.IconSize.MENU))
        a["mic"].connect("clicked", lambda _b: self.silenciar_mic(not a.get("mic_estado")))
        a["aviso"] = c.add_w(etiqueta("", "dim", envolver=True))
        self.audio = a

        # Lo de los packs (pack_*.py)
        packs.llamar(self.packs, "construir", self, s)

    # --- escritorios virtuales -------------------------------------------------------

    def rueda(self, ev):
        """Rueda abajo: escritorio siguiente; arriba: el anterior; Ctrl + rueda abajo: todos
        los escritorios. En los touchpads (scroll
        suave) se acumula el giro, y como mucho cambia uno cada 0,3 s."""
        if not self.config.get("rueda_escritorios", True) or not self.escritorios.disponible:
            return False
        if ev.direction == Gdk.ScrollDirection.SMOOTH:
            delta = ev.get_scroll_deltas()[2]
        elif ev.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.DOWN):
            delta = 1.0 if ev.direction == Gdk.ScrollDirection.DOWN else -1.0
        else:
            return False
        ahora = time.monotonic()
        if ahora - self._rueda_ult > 0.6:  # un giro nuevo: lo de antes no cuenta
            self._rueda = 0.0
        self._rueda_ult = ahora
        self._rueda += delta
        if abs(self._rueda) >= 1 and ahora - self._rueda_t > 0.3:
            if ev.get_state() & Gdk.ModifierType.CONTROL_MASK:
                if self._rueda > 0:  # Ctrl + rueda abajo: la vista con todos los escritorios
                    vista_general()
            else:
                self.escritorios.cambiar(1 if self._rueda > 0 else -1)
            self._rueda, self._rueda_t = 0.0, ahora
        return True

    # --- aplicaciones ---------------------------------------------------------------

    # --- títulos de los widgets ---------------------------------------------------

    def alternar_titulo(self, tarjeta, mostrar=None):
        sin = self.config.setdefault("sin_titulo", [])
        if mostrar is None:
            mostrar = tarjeta.clave in sin
        if mostrar and tarjeta.clave in sin:
            sin.remove(tarjeta.clave)
        elif not mostrar and tarjeta.clave not in sin:
            sin.append(tarjeta.clave)
        self.poner_titulos()
        self.ajustar_alturas()
        self.guardar_config()

    def alternar_fondo(self, tarjeta, mostrar=None):
        sin = self.config.setdefault("sin_fondo", [])
        if mostrar is None:
            mostrar = tarjeta.clave in sin
        if mostrar and tarjeta.clave in sin:
            sin.remove(tarjeta.clave)
        elif not mostrar and tarjeta.clave not in sin:
            sin.append(tarjeta.clave)
        tarjeta.queue_draw()
        if tarjeta.ventana:
            tarjeta.ventana.actualizar_blur()
        self.guardar_config()

    def poner_titulos(self):
        sin = self.config.get("sin_titulo", [])
        for t in self.tarjetas:
            t.lb_titulo.set_visible(t.clave not in sin)

    # --- calendario --------------------------------------------------------------

    def cambiar_semana(self, primer_dia):
        self.config.setdefault("calendario", {})["semana"] = "domingo" if primer_dia == 6 else "lunes"
        self.calendario.primer_dia = primer_dia
        self.calendario.queue_draw()
        self.guardar_config()

    def primer_dia(self):
        return 6 if self.config.get("calendario", {}).get("semana") == "domingo" else 0

    # --- widgets visibles -----------------------------------------------------

    def visibles(self):
        ocultos = self.config.get("ocultos", [])
        return [t for t in self.tarjetas if t.clave not in ocultos]

    def alternar_widget(self, tarjeta):
        ocultos = self.config.setdefault("ocultos", [])
        if tarjeta.clave in ocultos:
            ocultos.remove(tarjeta.clave)
        elif len(self.visibles()) > 1:  # al menos uno visible
            ocultos.append(tarjeta.clave)
        self.aplicar_modo()
        self.guardar_config()

    # --- configuración --------------------------------------------------------

    @staticmethod
    def cargar_config():
        try:
            with open(CONFIG) as f:
                config = json.load(f)
        except (OSError, ValueError):
            config = {}
        for clave in ("posiciones", "posiciones_sueltas", "opacidad"):
            config.setdefault(clave, {})
        config.setdefault("sueltas", [])
        return config

    def guardar_config(self):
        # Las posiciones del modo widgets y las de los widgets sacados del panel
        # se guardan aparte: son colocaciones distintas.
        if self.colocado:
            destino = self.config["posiciones" if self.modo == "widgets" else "posiciones_sueltas"]
            for t in self.tarjetas:
                if t.ventana:
                    destino[t.clave] = list(t.ventana.pos)
        self.config["modo"] = self.modo
        try:
            with open(CONFIG + ".tmp", "w") as f:
                json.dump(self.config, f, indent=1)
            os.replace(CONFIG + ".tmp", CONFIG)
        except OSError:
            pass
        self.rehacer_bandeja()

    # --- pantallas -----------------------------------------------------------

    @staticmethod
    def monitores():
        d = Gdk.Display.get_default()
        return [d.get_monitor(i) for i in range(d.get_n_monitors())]

    def indice_monitor(self, monitor):
        return next((i for i, m in enumerate(self.monitores()) if m == monitor), 0)

    @staticmethod
    def nombre_monitor(m):
        g = m.get_geometry()
        return f"{m.get_manufacturer() or ''}|{m.get_model() or ''}|{g.x},{g.y}"

    def pantalla_guardada(self):
        nombre = self.config.get("pantalla")
        mons = self.monitores()
        return (next((m for m in mons if self.nombre_monitor(m) == nombre), None)
                or Gdk.Display.get_default().get_primary_monitor() or (mons[0] if mons else None))

    def area_libre(self, monitor):
        """(ancho, alto) del monitor sin el panel y el dock (medido con una Sonda)."""
        if monitor in self.areas:
            return self.areas[monitor]
        g = monitor.get_workarea() if monitor else None
        return (g.width, g.height - 40) if g else (1920, 1040)

    def medir_area(self, monitor, luego):
        if not CAPAS or not monitor or monitor in self.areas:
            luego()
            return

        def medido(ancho, alto):
            if ancho > 100 and alto > 100:
                self.areas[monitor] = (ancho, alto)
            luego()
        Sonda(monitor, medido)

    def en_area(self, pos, monitor):
        if not pos:
            return False
        ancho, alto = self.area_libre(monitor)
        return 0 <= pos[0] < ancho - 20 and 0 <= pos[1] < alto - 20

    # --- modos ---------------------------------------------------------------

    def aplicar_modo(self, inicio=False):
        """Pone cada tarjeta donde le toca según el modo actual."""
        monitor = self.pantalla_guardada()
        if self.modo == "panel":
            if self.panel and self.panel.monitor != monitor:
                self.panel.repartir([])
                self.panel.destroy()
                self.panel = None
            if self.panel is None:
                self.panel = VentanaPanel(self, monitor)
            en_panel = []
            visibles = self.visibles()
            for t in self.tarjetas:
                if t not in visibles:
                    if t.ventana:
                        t.ventana.soltar()
                elif t.clave in self.config["sueltas"]:
                    if t.ventana and (not t.ventana.encima or t.ventana.monitor != monitor):
                        t.ventana.soltar()
                    if not t.ventana:
                        self.ventana_para(t, encima=True, monitor=monitor,
                                          pos=self.config["posiciones_sueltas"].get(t.clave))
                else:
                    if t.ventana:
                        t.ventana.soltar()
                    en_panel.append(t)
            for t in self.tarjetas:  # las que salen del panel (o se ocultan) se quitan antes de repartir
                if t not in en_panel and t.get_parent() is self.panel.lienzo:
                    self.panel.lienzo.remove(t)
                    self.panel.lienzo.rects.pop(t, None)
            self.panel.repartir(en_panel)
            self.panel.show()
            for t in self.tarjetas:
                if t.ventana:
                    t.ventana.show()
        else:
            visibles = self.visibles()
            if self.panel:
                self.panel.set_edicion(False)
                self.panel.repartir([])
                self.panel.destroy()
                self.panel = None
            for t in self.tarjetas:
                if t.ventana and (t.ventana.encima or t not in visibles or t.ventana.monitor != monitor):
                    t.ventana.soltar()  # se rehace sin "siempre encima", o se oculta
                if t in visibles and not t.ventana:
                    self.ventana_para(t, encima=False, monitor=monitor)
            self.manual = bool(self.config.get("manual")) and not RECOLOCAR_AL_ABRIR

            def colocar():
                self.colocar(ignorar_guardadas=not self.manual, monitor=monitor)
                for t in self.visibles():
                    if t.ventana:
                        t.ventana.show()
            self.medir_area(monitor, colocar)
        packs.llamar(self.packs, "visibles", self, {t.clave for t in self.visibles()})
        self.rehacer_bandeja()

    def ventana_para(self, tarjeta, encima, monitor, pos=None):
        if tarjeta.get_parent():
            tarjeta.get_parent().remove(tarjeta)
        v = VentanaWidget(tarjeta, self, encima, monitor)
        if self.en_area(pos, monitor):
            v.mover(*pos)
        return v

    def cambiar_modo(self, modo, monitor=None):
        if monitor:
            self.config["pantalla"] = self.nombre_monitor(monitor)
        self.guardar_config()  # guarda las posiciones del modo que se deja
        self.modo = modo
        self.aplicar_modo()
        self.guardar_config()
        log("Modo:", modo)

    def sacar_del_panel(self, tarjeta):
        """Saca una tarjeta del panel a su propia ventana, en el mismo sitio."""
        x, y, _, _ = self.panel.lienzo.rects.get(tarjeta, (40, 40, 0, 0))
        self.config["sueltas"].append(tarjeta.clave)
        self.config["posiciones_sueltas"][tarjeta.clave] = [x, y]
        self.aplicar_modo()
        self.guardar_config()

    def devolver_al_panel(self, tarjeta):
        self.config["sueltas"] = [c for c in self.config["sueltas"] if c != tarjeta.clave]
        self.guardar_config()
        self.aplicar_modo()
        self.guardar_config()

    # --- modo widgets: cuadrícula --------------------------------------------

    def colocar(self, ignorar_guardadas=False, monitor=None):
        """Reparte las ventanas por columnas, cada widget con su altura natural y justo
        debajo del anterior de su columna (sin estirarlos ni dejar huecos). Los que
        tienen una posición guardada (los que moviste a mano) se quedan en ella."""
        monitor = monitor or self.pantalla_guardada()
        guardadas = {} if ignorar_guardadas else self.config["posiciones"]
        ancho_area, alto_area = self.area_libre(monitor)
        tarjetas = [t for t in self.visibles() if t.ventana]
        if not tarjetas:
            return
        altos = [t.alto_natural(ANCHO) for t in tarjetas]

        def repartir(cols):
            columnas, sitios = [0] * cols, []
            for alto in altos:
                i = columnas.index(min(columnas))
                sitios.append((i, columnas[i]))
                columnas[i] += alto + SEPARACION
            return sitios, max(columnas) - SEPARACION

        # Las menos columnas (desde COLUMNAS) con las que todo cabe en alto.
        max_cols = max(1, min(len(tarjetas), (ancho_area + SEPARACION) // (ANCHO + SEPARACION)))
        cols = min(COLUMNAS, max_cols)
        sitios, alto_total = repartir(cols)
        while alto_total > alto_area and cols < max_cols:
            cols += 1
            sitios, alto_total = repartir(cols)
        ancho_total = cols * ANCHO + SEPARACION * (cols - 1)
        x0 = max((ancho_area - ancho_total) // 2, 0)
        y0 = max((alto_area - alto_total) // 2, 0)
        for t, alto, (col, y) in zip(tarjetas, altos, sitios):
            t.ventana.tamano(ANCHO, alto)
            pos = guardadas.get(t.clave)
            if self.en_area(pos, monitor):
                t.ventana.mover(*pos)
            else:
                t.ventana.mover(x0 + col * (ANCHO + SEPARACION), y0 + y)
        self._altos = altos

    def recolocar(self, monitor=None):
        """Coloca en cuadrícula y recuerda la pantalla para las próximas veces."""
        if monitor:
            self.config["pantalla"] = self.nombre_monitor(monitor)
        predeterminadas = self.config.get("posiciones_predeterminadas")
        self.manual = bool(predeterminadas)
        self.config["manual"] = self.manual
        self.config["posiciones"] = dict(predeterminadas or {})
        if monitor and any(t.ventana and t.ventana.monitor != monitor for t in self.tarjetas):
            self.aplicar_modo()  # rehace las ventanas en el otro monitor
            self.guardar_config()
            return
        self.medir_area(self.pantalla_guardada(), lambda: (
            self.colocar(ignorar_guardadas=not self.manual, monitor=self.pantalla_guardada()),
            self.guardar_config()))

    def ajustar_alturas(self):
        """Adapta las ventanas al contenido (p. ej. empieza a sonar música)."""
        if not self.colocado:
            return
        if self.modo == "widgets" and not self.manual:
            # Sin colocar a mano: si uno crece o encoge, se reparten otra vez.
            altos = [t.alto_natural(ANCHO) for t in self.visibles() if t.ventana]
            if altos != getattr(self, "_altos", None):
                self.colocar(ignorar_guardadas=True, monitor=self.pantalla_guardada())
            return
        # Ventanas sueltas o movidas a mano: cada una a su altura.
        for t in self.tarjetas:
            if t.ventana:
                alto = t.alto_natural(ANCHO)
                if alto != getattr(t.ventana, "alto", None) or t._margen != t.margen_neon():
                    t.ventana.tamano(ANCHO, alto)

    # --- menús ---------------------------------------------------------------

    @staticmethod
    def item(menu, texto, fn=None, marcado=None):
        texto = _(texto)  # los nombres que no son textos de la app (pantallas, GPU…) se quedan igual
        if marcado is None:
            it = Gtk.MenuItem(label=texto)
        else:
            it = Gtk.CheckMenuItem(label=texto)
            it.set_active(marcado)
        if fn:
            it.connect("activate", lambda _i: fn())
        menu.append(it)
        return it

    def submenu(self, menu, texto):
        it = self.item(menu, texto)
        sub = Gtk.Menu()
        it.set_submenu(sub)
        return sub

    def acciones_comunes(self, menu):
        self.item(menu, "Configuración…", self.abrir_configuracion)
        self.item(menu, "Mostrar / ocultar", self.alternar)
        sub = self.submenu(menu, "Widgets visibles")
        visibles = self.visibles()
        for t in self.tarjetas:
            self.item(sub, t.nombre_menu, lambda t=t: self.alternar_widget(t), t in visibles)
        packs.llamar(self.packs, "acciones", self, menu)
        if self.modo == "widgets":
            self.listar_pantallas(self.submenu(menu, "Recolocar widgets en..."), self.recolocar)
            self.listar_pantallas(self.submenu(menu, "Modo panel (pantalla completa) en..."),
                                  lambda m: self.cambiar_modo("panel", m), marcar=False)
        else:
            editando = bool(self.panel and self.panel.editando)
            self.item(menu, "Editar disposición (mover y redimensionar)",
                      lambda: self.panel.set_edicion(not self.panel.editando), editando)
            self.item(menu, "Restablecer disposición", lambda: self.panel.restablecer())
            self.listar_pantallas(self.submenu(menu, "Mover el panel a..."),
                                  lambda m: self.cambiar_modo("panel", m))
            self.item(menu, "Volver a modo widgets", lambda: self.cambiar_modo("widgets"))
        menu.append(Gtk.SeparatorMenuItem())
        self.item(menu, _("Salir"), self.salir)

    def listar_pantallas(self, menu, accion, marcar=True):
        principal = Gdk.Display.get_default().get_primary_monitor()
        elegida = self.pantalla_guardada()
        for i, m in enumerate(self.monitores(), 1):
            g = m.get_geometry()
            modelo = f" {m.get_model()}" if m.get_model() else ""
            texto = (_("Pantalla {n}").format(n=i) + f"{modelo}{_(' (principal)') if m == principal else ''}"
                     f" · {g.width}×{g.height}")
            self.item(menu, texto, lambda m=m: accion(m), (m == elegida) if marcar else None)

    def menu_tarjeta(self, tarjeta):
        """Menú del clic derecho: opacidad de ese widget, sacar/devolver y lo general."""
        menu = Gtk.Menu()
        sub = self.submenu(menu, "Opacidad de este widget")
        for nivel in OPACIDADES:
            self.item(sub, f"{nivel} %", lambda v=nivel / 100: self.cambiar_opacidad([tarjeta], v),
                      round(tarjeta.opacidad * 100) == nivel)
        sub.append(Gtk.SeparatorMenuItem())
        self.item(sub, "Aplicar a todos los widgets", lambda: self.cambiar_opacidad(self.tarjetas, tarjeta.opacidad))
        self.opciones_tarjeta(tarjeta, menu)
        if self.modo == "panel" and not tarjeta.ventana and tarjeta.clave in self.panel.celdas:
            _x, _x, alto, ancho = self.panel.celdas[tarjeta.clave]
            sub = self.submenu(menu, "Tamaño en la cuadrícula")
            for titulo, actual, maximo, campo in (("Ancho", ancho, self.panel.cols, "ancho"),
                                                  ("Alto", alto, VentanaPanel.MAX_ALTO, "alto")):
                s2 = self.submenu(sub, f"{_(titulo)}: {actual}")
                for v in range(1, maximo + 1):
                    self.item(s2, str(v), lambda v=v, campo=campo: self.panel.cambiar_tam(tarjeta, **{campo: v}),
                              v == actual)
        if self.modo == "panel":
            if tarjeta.ventana:
                self.item(menu, "Devolver al panel", lambda: self.devolver_al_panel(tarjeta))
            else:
                self.item(menu, "Sacar del panel (ventana aparte, siempre encima)",
                          lambda: self.sacar_del_panel(tarjeta))
        self.item(menu, "Mostrar título", lambda: self.alternar_titulo(tarjeta),
                  tarjeta.clave not in self.config.get("sin_titulo", []))
        self.item(menu, "Mostrar fondo y borde", lambda: self.alternar_fondo(tarjeta), not tarjeta.sin_fondo())
        self.item(menu, "Ocultar este widget", lambda: self.alternar_widget(tarjeta))
        menu.append(Gtk.SeparatorMenuItem())
        self.acciones_comunes(menu)
        menu.show_all()
        self._menu_tarjeta = menu  # que no lo borre el recolector mientras se muestra
        return menu

    def opciones_tarjeta(self, tarjeta, menu):
        """Lo que es solo de ese widget (tipo de reloj, juego, ciudad...): va en su clic derecho y
        es lo que sale al pulsar su título."""
        if tarjeta.clave == "reloj":
            self.menu_reloj(menu)
        if tarjeta.clave == "calendario":
            sub = self.submenu(menu, "La semana empieza en")
            for dia, nombre in ((0, idioma.dia_semana(0)), (6, idioma.dia_semana(6))):
                self.item(sub, nombre.capitalize(), lambda d=dia: self.cambiar_semana(d), self.primer_dia() == dia)
            menu.append(Gtk.SeparatorMenuItem())
        packs.llamar(self.packs_de(tarjeta), "menu", self, tarjeta, menu)
        if tarjeta.clave == "tiempo":
            self.item(menu, "Cambiar ciudad…", self.elegir_ciudad)
            self.item(menu, "Actualizar ahora", self.tiempo._despertar.set)
            menu.append(Gtk.SeparatorMenuItem())

    def packs_de(self, tarjeta):
        return [p for p in self.packs if tarjeta.clave in getattr(p, "WIDGETS", ())]

    def pulsar_titulo(self, tarjeta, ev):
        """Clic en el título: lo que enseñe su pack (gancho `titulo`) o el menú de opciones."""
        if any(packs.llamar(self.packs_de(tarjeta), "titulo", self, tarjeta, ev)):
            return
        menu = self.menu_titulo(tarjeta)
        if menu:
            menu.show_all()
            self._menu_tarjeta = menu  # que no lo borre el recolector mientras se muestra
            menu.popup_at_widget(tarjeta.lb_titulo, Gdk.Gravity.SOUTH_WEST, Gdk.Gravity.NORTH_WEST, ev)

    def menu_titulo(self, tarjeta):
        """El menú del título: solo las opciones de ese widget, o None si no tiene."""
        menu = Gtk.Menu()
        self.opciones_tarjeta(tarjeta, menu)
        while menu.get_children() and isinstance(menu.get_children()[-1], Gtk.SeparatorMenuItem):
            menu.remove(menu.get_children()[-1])
        return menu if menu.get_children() else None

    def marcar_titulos(self):
        """En los widgets con opciones, el título se puede pulsar: manita y una pista al pasar."""
        for t in self.tarjetas:
            if any(hasattr(p, "titulo") for p in self.packs_de(t)) or self.menu_titulo(t):
                t.titulo_con_opciones = True
                t.lb_titulo.set_tooltip_text(_("Clic para ver las opciones de este widget"))

    def rehacer_bandeja(self):
        """El menú del icono de la bandeja depende del modo: se rehace con cada cambio."""
        if not self.bandeja:
            return
        for hijo in self.menu_bandeja.get_children():
            self.menu_bandeja.remove(hijo)
        self.acciones_comunes(self.menu_bandeja)
        self.menu_bandeja.show_all()
        self.bandeja.set_secondary_activate_target(self.menu_bandeja.get_children()[0])

    def cambiar_opacidad(self, tarjetas, valor):
        for t in tarjetas:
            t.set_opacidad(valor)
            self.config["opacidad"][t.clave] = valor
        self.guardar_config()

    def ventanas(self):
        return [t.ventana for t in self.tarjetas if t.ventana] + ([self.panel] if self.panel else [])

    def traer_delante(self):
        """Vuelve a abrir las ventanas: el compositor las pone encima de lo que haya en su capa."""
        for v in self.ventanas():
            if v.get_visible():
                v.hide()
            v.show()
            v.present()

    def mirar_aperturas(self):
        if instancia.quieren_verme(CARPETA):  # la han vuelto a abrir: se muestra la que ya estaba
            self.traer_delante()
        return True

    def alternar(self):
        ventanas = self.ventanas()
        visible = any(v.get_visible() for v in ventanas)
        for v in ventanas:
            v.set_visible(not visible)

    def salir(self):
        self._activo = False
        self.reproductores.close()
        self.guardar_config()
        self.sampler.close()
        Gtk.main_quit()

    # --- datos -------------------------------------------------------------

    def bucle(self):
        while self._activo:
            time.sleep(INTERVALO)
            try:
                GLib.idle_add(self.aplicar, self.sampler.sample())
            except Exception as e:  # noqa: BLE001 - seguir aunque falle una lectura
                log("Error leyendo sensores:", e)

    def aplicar(self, s):
        # CPU
        poner_texto(self.cpu_big, f"{s['cpu']:.0f} %")
        freq = f"{s['freq'] / 1000:.2f} GHz" if s["freq"] else "—"
        extra = f" · {s['cpu_power']:.0f} W" if s.get("cpu_power") is not None else ""
        poner_texto(self.cpu_sub, f"{freq} · " + _("{n} procesos").format(n=s["procs"]) + extra)
        t = s["cpu_temp"]
        temp = f"{t:.1f} °C" if t is not None else "—"
        poner_marcado(self.cpu_temp, f'<span foreground="{color_temp(t)}">' + _("Temperatura {t}").format(t=temp) + "</span>")
        self.cpu_graf.push(s["cpu"], t)
        self.cpu_nucleos.set(s["cores"])
        up = int(s["uptime"])
        poner_texto(self.uptime, _("{n} hilos · Encendido {tiempo}").format(
            n=len(s["cores"]), tiempo=f"{up // 86400}d {up % 86400 // 3600}h {up % 3600 // 60}m"))

        # Memoria
        used, total, pct = s["mem"]
        poner_texto(self.mem_big, f"{pct:.0f} %")
        poner_texto(self.mem_sub, f"RAM {fmt_bytes(used)} / {fmt_bytes(total)}")
        self.mem_barra.set(pct)
        su, st, sp = s["swap"]
        poner_texto(self.swap_sub, f"Swap {fmt_bytes(su)} / {fmt_bytes(st)}" if st else _("Sin swap"))
        self.swap_barra.set(sp if st else 0)
        self.mem_graf.push(pct, sp if st else 0)

        # GPUs
        for g in s["gpus"]:
            w = self.gpus.get(g["id"])
            if not w:
                continue
            poner_texto(w["big"], f"{g['util']:.0f} %" if g["util"] is not None else "—")
            temp = f"{g['temp']:.0f} °C" if g["temp"] is not None else "—"
            poner_marcado(w["temp"], f'<span foreground="{color_temp(g["temp"])}">' + _("Temperatura {t}").format(t=temp) + "</span>")
            vram_pct = 0
            if g["vram"]:
                vram_pct = 100 * g["vram"][0] / g["vram"][1]
                poner_texto(w["sub"], f"VRAM {fmt_bytes(g['vram'][0])} / {fmt_bytes(g['vram'][1])} ({vram_pct:.0f} %)")
            else:
                poner_texto(w["sub"], _("VRAM —"))
            partes = []
            if g["power"] is not None:
                partes.append(f"{g['power']:.0f} W" + (f" / {g['power_limit']:.0f} W" if g["power_limit"] else ""))
            if g["clock"] is not None:
                partes.append(f"{g['clock']:.0f} MHz")
            if g["fan"] is not None:
                partes.append(_("Ventilador {n} %").format(n=f"{g['fan']:.0f}"))
            poner_texto(w["sub2"], " · ".join(partes))
            w["graf"].push(g["util"], vram_pct)

        # Red
        rx, tx = s["net"]
        poner_texto(self.red_big, f"↓ {fmt_bytes(rx, True)}")
        poner_texto(self.red_sub, f"↑ {fmt_bytes(tx, True)}")
        self.red_graf.push(rx, tx)

        # Discos
        r, w_ = s["disk_io"]
        poner_texto(self.disco_big, _("L {v}").format(v=fmt_bytes(r, True)))
        poner_texto(self.disco_sub, _("E {v}").format(v=fmt_bytes(w_, True)))
        self.disco_graf.push(r, w_)
        for mount, used, total, pct in s["parts"]:
            if mount in self.particiones:
                lb, barra = self.particiones[mount]
                poner_texto(lb, f"{mount}  {fmt_bytes(used)} / {fmt_bytes(total)} · {pct:.0f} %")
                barra.set(pct)

        self.ultimo = s
        packs.llamar(self.packs, "aplicar", self, s)
        self.ajustar_alturas()
        return False

    # --- reloj y calendario ----------------------------------------------------

    def actualizar_reloj(self):
        ahora = datetime.datetime.now()
        self.reloj.queue_draw()
        # A medianoche cambia el día marcado en el calendario.
        if ahora.date() != getattr(self, "_hoy", None):
            self._hoy = ahora.date()
            self.calendario.queue_draw()
        return True

    def cambiar_reloj(self, **cambios):
        o = self.config["reloj"]
        if "zona" in cambios:  # marcar o desmarcar una ciudad del reloj mundial
            zona = cambios.pop("zona")
            if zona in o["zonas"]:
                if len(o["zonas"]) > 1:
                    o["zonas"].remove(zona)
            elif len(o["zonas"]) < 8:
                o["zonas"].append(zona)
        o.update(cambios)
        self.reloj.ajustar_minimo()
        self.ajustar_alturas()
        self.guardar_config()

    def menu_reloj(self, menu):
        o = self.config["reloj"]
        tipos = self.submenu(menu, "Tipo de reloj")
        for clave, nombre in ESTILOS_RELOJ:
            self.item(tipos, nombre, lambda c=clave: self.cambiar_reloj(estilo=c), o["estilo"] == clave)
        for texto, clave in (("Formato 24 horas", "h24"), ("Mostrar segundos", "segundos"), ("Mostrar la fecha", "fecha")):
            self.item(menu, texto, lambda c=clave: self.cambiar_reloj(**{c: not o[c]}), o[clave])
        ciudades = self.submenu(menu, "Ciudades (reloj mundial, hasta 8)")
        for nombre, zona in CIUDADES:
            self.item(ciudades, nombre, lambda z=zona: self.cambiar_reloj(zona=z), zona in o["zonas"])
        if o["estilo"] == "nixie":
            actual = o.get("nixie", esferas.NIXIE_POR_DEFECTO)
            sub = self.submenu(menu, "Color de los tubos")
            for color, nombre in esferas.COLORES_NIXIE:
                self.item(sub, nombre, lambda c=color: self.cambiar_reloj(nixie=c), actual == color)
            self.item(sub, "Otro color…", self.elegir_color_nixie)
        menu.append(Gtk.SeparatorMenuItem())

    def elegir_color_nixie(self):
        d = Gtk.ColorChooserDialog(title=_("Color de los tubos"))
        d.set_use_alpha(False)
        d.set_rgba(Gdk.RGBA(*hex_rgb(self.config["reloj"].get("nixie", esferas.NIXIE_POR_DEFECTO)), 1))
        if d.run() == Gtk.ResponseType.OK:
            c = d.get_rgba()
            self.cambiar_reloj(nixie=temas.a_hex((c.red, c.green, c.blue)))
        d.destroy()

    def mover_calendario(self, meses):
        if meses:
            self.calendario.cambiar(meses)
        else:
            self.calendario.ir_a_hoy()
        self.cal_titulo.set_label(self.calendario.titulo())

    # --- dispositivos de audio -------------------------------------------------

    def actualizar_audio(self):
        a = self.audio
        datos = self.dispositivos.leer()
        if datos:
            claves = tuple((k, tuple((i, n) for i, n, _x in datos[k])) for k in ("salida", "entrada"))
            if claves != a["claves"]:
                a["claves"] = claves
                for b in a["filas"].values():
                    b.destroy()
                a["filas"] = {}
                for k in ("salida", "entrada"):
                    for ident, nombre, _x in datos[k]:
                        b = Gtk.Button()
                        b.get_style_context().add_class("dispositivo")
                        b.set_can_focus(False)
                        lb = etiqueta(nombre, "")
                        b.add(lb)
                        b.etiqueta = lb
                        b.set_tooltip_text(nombre)
                        b.connect("clicked", lambda _b, i=ident: self.elegir_dispositivo(i))
                        a[k].pack_start(b, False, False, 0)
                        a["filas"][ident] = b
                    if not datos[k]:
                        b = Gtk.Button(label=_("Ninguno conectado"))
                        b.get_style_context().add_class("dispositivo")
                        b.set_sensitive(False)
                        a[k].pack_start(b, False, False, 0)
                        a["filas"][f"ninguno-{k}"] = b
                    a[k].show_all()
            for k in ("salida", "entrada"):
                for ident, nombre, pred in datos[k]:
                    b = a["filas"][ident]
                    clases(b, activo=pred)
                    poner_texto(b.etiqueta, f"{'◉' if pred else '○'}  {nombre}")
                    b.set_visible(pred or a[k + "_abierto"] or not any(p for *_x, p in datos[k]))
                a[k + "_boton"].set_visible(len(datos[k]) > 1)
                a[k + "_boton"].set_label(_("Cerrar ▴") if a[k + "_abierto"] else _("Cambiar ▾"))
            mic = datos["mic_silenciado"]
            a["mic_estado"] = bool(mic)
            a["mic"].set_visible(mic is not None)
            clases(a["mic"], marcado=bool(mic))
            poner_icono(a["mic"], "microphone-sensitivity-muted-symbolic" if mic
                        else "microphone-sensitivity-high-symbolic", Gtk.IconSize.MENU)
            a["mic"].set_tooltip_text(_("Micrófono silenciado · clic para activar") if mic else _("Silenciar micrófono"))
        error = self.dispositivos.error or ""
        poner_texto(a["aviso"], error)
        a["aviso"].set_visible(bool(error))
        self.ajustar_alturas()
        return True

    def silenciar_mic(self, activo):
        log("Micrófono:", self.dispositivos.silenciar_mic(activo))
        GLib.timeout_add(400, lambda: self.actualizar_audio() and False)  # refleja el estado real

    def desplegar_audio(self, clave):
        self.audio[clave + "_abierto"] = not self.audio[clave + "_abierto"]
        self.actualizar_audio()

    def elegir_dispositivo(self, ident):
        for k in ("salida", "entrada"):
            self.audio[k + "_abierto"] = False  # elegido: se pliega la lista
        self.dispositivos.predeterminar(ident)
        GLib.timeout_add(400, lambda: self.actualizar_audio() and False)

    # --- tema y ajustes ----------------------------------------------------------

    def aplicar_tema(self, guardar=True):
        self.tema = temas.completo(self.config.get("tema"))
        aplicar_colores(self.tema)
        if PROVEEDOR:
            PROVEEDOR.load_from_data(css_tema(self.tema).encode())
        for t in getattr(self, "tarjetas", []):
            if t._margen != t.margen_neon():  # se ha activado o quitado el neón
                t.ajustar_margenes()
                if t.ventana:
                    t.ventana.tamano(ANCHO, t.alto_natural(ANCHO))
                elif t.get_parent():
                    t.get_parent().queue_resize()
        for v in self.ventanas() if hasattr(self, "tarjetas") else []:
            v._rects = None
            v.actualizar_blur()
            v.queue_draw()
        if guardar:
            self.ajustar_alturas()
            # Al arrastrar un deslizador llegan muchos cambios: se guarda al parar.
            if self._guardar_tema:
                GLib.source_remove(self._guardar_tema)
            self._guardar_tema = GLib.timeout_add(500, lambda: (setattr(self, "_guardar_tema", None),
                                                                self.guardar_config()) and False)

    def parpadear(self):
        """Avanza el parpadeo de los neones (solo si está activado en algún modo)."""
        activo = {k: self.tema[k]["neon"] and self.tema[k]["parpadeo"] for k in ("widgets", "panel")}
        if any(activo.values()):
            ahora = time.monotonic()
            for t in self.tarjetas:
                if t.get_mapped() and activo["panel" if t.relleno == "claro" else "widgets"]:
                    t.tic_parpadeo(ahora)
                elif t.brillo != 1.0:
                    t.brillo = 1.0
                    t.queue_draw()
        return True

    def abrir_configuracion(self):
        if self.ventana_config:
            self.ventana_config.present()
            return
        self.ventana_config = VentanaConfig(self)
        self.ventana_config.connect("destroy", lambda *_: setattr(self, "ventana_config", None))

    def autoarranque(self, activo):
        if activo:
            os.makedirs(os.path.dirname(AUTOARRANQUE), exist_ok=True)
            with open(AUTOARRANQUE, "w") as f:
                f.write("[Desktop Entry]\nType=Application\nName=MoonDeck\n"
                        f"Exec=python3 {os.path.abspath(__file__)}\nIcon=utilities-system-monitor\n"
                        "Terminal=false\nX-GNOME-Autostart-Delay=3\n")
        elif os.path.exists(AUTOARRANQUE):
            os.remove(AUTOARRANQUE)

    def cambiar_ancho(self, valor):
        global ANCHO
        ANCHO = int(valor)
        self.config["ancho"] = ANCHO
        if self.modo == "widgets":
            if self.manual:
                self.ajustar_alturas()
            else:
                self.colocar(ignorar_guardadas=True)
        for t in self.tarjetas:
            if t.ventana:
                t.ventana.tamano(ANCHO, t.alto_natural(ANCHO))
        self.guardar_config()

    def cambiar_columnas(self, valor):
        global COLUMNAS
        COLUMNAS = int(valor)
        self.config["columnas"] = COLUMNAS
        if self.modo == "widgets" and not self.manual:
            self.colocar(ignorar_guardadas=True)
        self.guardar_config()

    def cambiar_intervalo(self, valor):
        global INTERVALO
        INTERVALO = float(valor)
        self.config["intervalo"] = INTERVALO
        self.guardar_config()

    # --- tiempo ------------------------------------------------------------------

    def elegir_ciudad(self):
        dlg = DialogoCiudad()
        if dlg.run() == Gtk.ResponseType.OK and dlg.elegida:
            self.config["tiempo_ciudad"] = dlg.elegida
            self.tiempo.cambiar_ciudad(dlg.elegida)
            self.guardar_config()
        dlg.destroy()

    def actualizar_tiempo(self):
        t = self.tm
        if self.tiempo.version == t["version"]:
            return True
        t["version"] = self.tiempo.version
        d, c = self.tiempo.datos, self.tiempo.ciudad
        if d:
            texto, icono = describir(d["codigo"], d["dia"])
            texto = _(texto)
            t["icono"].set_from_pixbuf(icono_pixbuf(t["icono"], icono, 56))
            poner_texto(t["temp"], f"{d['temp']:.0f} °C")
            poner_texto(t["desc"], texto)
            poner_texto(t["detalle"], _("Sensación {s}° · Humedad {h} % · Viento {v} km/h · Sol {a}–{b}").format(
                s=f"{d['sensacion']:.0f}", h=f"{d['humedad']:.0f}", v=f"{d['viento']:.0f}", a=d["salida"], b=d["puesta"]))
            t["horas"].poner(d["horas"])
            t["dias"].poner(d["dias"])
        else:
            poner_texto(t["temp"], "—")
            poner_texto(t["desc"], _("Cargando…") if not self.tiempo.error else "")
            poner_texto(t["detalle"], self.tiempo.error or "")
        lugar = f"{c['nombre']}" + (f" · {d['leido']}" if d else "")
        poner_texto(t["ciudad"], lugar + (_(" · sin conexión") if self.tiempo.error and d else ""))
        self.ajustar_alturas()
        return True

    # --- multimedia ---------------------------------------------------------

    def actualizar_multimedia(self):
        m = self.multimedia
        # Reproductores: se rehacen las filas solo si cambian las apps.
        lista = self.reproductores.leer()[:MAX_REPRODUCTORES]
        claves = [d["id"] for d in lista]
        if claves != m["claves_rep"]:
            m["claves_rep"] = claves
            for f in m["filas_rep"]:
                f.destroy()
            m["filas_rep"] = [FilaReproductor(self.reproductores) for _x in lista]
            for f in m["filas_rep"]:
                m["reproductores"].pack_start(f, False, False, 0)
            # Si no cabe todo, lo que suena (el primero) es lo último que se quita.
            m["tarjeta"].prescindibles_grupo("reproductores", m["filas_rep"][:0:-1], 2)
        for f, d in zip(m["filas_rep"], lista):
            f.actualizar(d)
        m["reproductores"].set_visible(bool(lista))
        m["nada"].set_visible(not lista)

        # Mezclador: volumen general + una fila por app con sonido.
        datos = self.mezclador.leer()
        if datos:
            apps = datos["apps"][:MAX_APPS_VOLUMEN]
            claves = [datos["dispositivo"]] + [a[0] for a in apps]
            if claves != m["claves_vol"]:
                m["claves_vol"] = claves
                for f in m["filas_vol"]:
                    f.destroy()
                m["filas_vol"] = [FilaVolumen(self.mezclador, None, _("General"))]
                m["filas_vol"] += [FilaVolumen(self.mezclador, nombre, nombre) for nombre, _x, _x in apps]
                for f in m["filas_vol"]:
                    m["volumen"].pack_start(f, False, False, 0)
            m["filas_vol"][0].actualizar(*datos["general"])
            for f, (_x, vol, mute) in zip(m["filas_vol"][1:], apps):
                f.actualizar(vol, mute)
            poner_texto(m["seccion_vol"], _("VOLUMEN") + f" · {datos['dispositivo'].upper()}")
        m["scroll_vol"].set_visible(bool(datos))
        m["seccion_vol"].set_visible(bool(datos))
        errores = [e for e in (self.reproductores.error, self.mezclador.error) if e]
        poner_texto(m["aviso"], "\n".join(errores))
        m["aviso"].set_visible(bool(errores))
        self.ajustar_alturas()
        return True


PROVEEDOR = None  # CSS de la app; se recarga al cambiar el tema


def main():
    global PROVEEDOR
    Gtk.Window.set_default_icon_name("utilities-system-monitor")
    GLib.set_prgname("moondeck")
    PROVEEDOR = Gtk.CssProvider()
    PROVEEDOR.load_from_data(CSS.encode())
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), PROVEEDOR,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    if not CAPAS:
        log("AVISO: sin gtk-layer-shell (instala gir1.2-gtklayershell-0.1): los widgets no se podrán colocar.")
    try:
        app = Monitor()
    except Exception:
        _excepthook(*sys.exc_info())
        sys.exit(1)
    sys._arrancando = False
    log("En marcha.")
    app.keep = app  # noqa: B018 - mantener la referencia viva
    Gtk.main()


if __name__ == "__main__":
    main()
