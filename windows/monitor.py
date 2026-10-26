"""MoonDeck: widgets de cristal para el escritorio de Windows 11."""

import calendar
import ctypes
import datetime
import faulthandler
import json
import math
import os
import random
import re
import sys
import threading
import time
import traceback
from collections import deque
from zoneinfo import ZoneInfo

# Ejecutando desde el repositorio, los módulos compartidos están en ../comun
# (en lo instalado van todos juntos en la misma carpeta).
_COMUN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "comun")
if os.path.isdir(_COMUN):
    sys.path.insert(1, _COMUN)

# ---------------------------------------------------------------------------
# Registro de errores. Con pythonw.exe no hay consola y cualquier fallo
# cerraría la app sin avisar: todo se guarda en %APPDATA%\MoonDeck\error.log
# y los errores graves se muestran en una ventana.
# ---------------------------------------------------------------------------
CARPETA = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~/.config"), "MoonDeck")

# Antes se llamaba "Monitor de Hardware": la primera vez se trae su configuración.
_VIEJA = os.path.join(os.path.dirname(CARPETA), "MonitorHardware")
if not os.path.exists(CARPETA) and os.path.isdir(_VIEJA):
    import shutil
    shutil.copytree(_VIEJA, CARPETA, ignore=shutil.ignore_patterns("error.log"))
LOG = os.path.join(CARPETA, "error.log")
os.makedirs(CARPETA, exist_ok=True)
_log = open(LOG, "w", encoding="utf-8", buffering=1)
if sys.stderr is None:
    sys.stderr = _log
if sys.stdout is None:
    sys.stdout = _log
faulthandler.enable(_log)  # también registra cierres bruscos (fallos de C/.NET)


def log(*partes):
    texto = time.strftime("%H:%M:%S ") + " ".join(str(p) for p in partes)
    _log.write(texto + "\n")
    if sys.stderr is not _log:
        print(texto, file=sys.stderr)


def aviso_error(titulo, texto):
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(None, texto, titulo, 0x10)  # MB_ICONERROR


_error_mostrado = False


def _excepthook(tipo, valor, tb):
    global _error_mostrado
    detalle = "".join(traceback.format_exception(tipo, valor, tb))
    log("ERROR NO CONTROLADO\n" + detalle)
    if not _error_mostrado:
        _error_mostrado = True
        aviso_error("MoonDeck - error",
                    f"{tipo.__name__}: {valor}\n\nDetalle guardado en:\n{LOG}")


sys.excepthook = _excepthook
log("Iniciando. Python", sys.version.split()[0], "en", sys.platform, "| admin:",
    bool(ctypes.windll.shell32.IsUserAnAdmin()) if sys.platform == "win32" else os.geteuid() == 0)

try:
    from PySide6.QtCore import QEvent, QFileInfo, QObject, QPointF, QRectF, QSize, Qt, QTimer, QUrl, Signal
    from PySide6.QtGui import (QColor, QDesktopServices, QFont, QFontDatabase, QFontMetricsF, QGuiApplication,
                               QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF)
    from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDoubleSpinBox,
                                   QFileDialog, QFileIconProvider, QFontComboBox, QFrame, QGraphicsOpacityEffect, QGridLayout,
                                   QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
                                   QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox,
                                   QStackedWidget, QStyle, QSystemTrayIcon, QToolButton, QTreeWidget,
                                   QTreeWidgetItem, QVBoxLayout, QWidget)

    from multimedia import Dispositivos, Mezclador, Reproductores
    from velocidad import TestVelocidad
    import velocimetro
    import esferas
    import juegos
    import lanzador
    import dino_sprite
    from sensores import ES_WINDOWS, Sampler
    from discord_voz import CLIENT_ID_POR_DEFECTO, CLIENT_SECRET_POR_DEFECTO, Discord, abrir_discord
    from tiempo import CIUDAD_POR_DEFECTO, Tiempo, buscar_ciudades, describir
    import tema as temas
    import idioma
    from idioma import _
    from actualizar import Actualizador
    from version import REPO, VERSION
except Exception:
    _excepthook(*sys.exc_info())
    sys.exit(1)

# ---------------------------------------------------------------------------
# Ajustes
# ---------------------------------------------------------------------------
EFECTO = "acrilico"   # "acrilico" (cristal de Windows 11) o "ninguno" (fondo oscuro translúcido)
# Colores, fondos, bordes...: en el menú > "Configuración…" (se guardan en config.json).
INTERVALO = 1.0       # segundos entre lecturas
HISTORIAL = 120       # muestras en las gráficas
ANCHO = 340           # ancho de cada widget
SEPARACION = 14       # espacio entre widgets al colocarlos
COLUMNAS = 4
RECOLOCAR_AL_ABRIR = False  # True: al abrir siempre en cuadrícula; False: donde los dejaste
MAX_REPRODUCTORES = 3      # cuántas apps con música se muestran a la vez
MAX_APPS_VOLUMEN = 8       # cuántas apps se muestran en el mezclador
OPACIDADES = (100, 90, 80, 70, 60, 50, 40)
QWIDGETSIZE_MAX = 16777215

COLORES = {
    "azul": QColor(77, 141, 255), "naranja": QColor(255, 158, 67),
    "verde": QColor(46, 204, 113), "morado": QColor(168, 115, 255),
    "rojo": QColor(255, 92, 92), "amarillo": QColor(241, 196, 15),
}

BaseVentana = QWidget
USA_ACRILICO = False
if ES_WINDOWS and EFECTO == "acrilico":
    try:
        from qframelesswindow import AcrylicWindow as BaseVentana
        USA_ACRILICO = True
    except Exception:  # noqa: BLE001 - sin la librería se usa el fondo simple
        log("No se pudo cargar el efecto acrílico:\n" + traceback.format_exc())

CONFIG = os.path.join(CARPETA, "config.json")

# En Windows el acrílico ya aclara mucho: los widgets necesitan algo más de tinte.
temas.POR_DEFECTO["widgets"]["opacidad"] = 0.63
temas.PREDEFINIDOS["Cristal oscuro"] = temas.completo(None)

# --- colores del tema en uso (los cambia aplicar_colores) ---
C_TEXTO = "#f2f4f8"       # cifras grandes
C_CLARO = "#e6e9ef"
C_NORMAL = "#d0d6e0"
C_GRIS_CLARO = "#c3cad6"
C_TITULO = "#aab3c2"
C_SEC = "#9aa3b2"         # textos secundarios
TENUE = (255, 255, 255)   # líneas y fondos finos: el color del texto con poca opacidad
SOMBRA = 55               # fondo de las gráficas
ESCALA = 1.0              # tamaño de letra
NEON_MARGEN = 0 if ES_WINDOWS else 6  # con acrílico, el halo va hacia dentro (el cristal cubre la ventana)


def tenue(alfa):
    return QColor(TENUE[0], TENUE[1], TENUE[2], max(0, min(255, round(alfa))))


def acento(alfa=255):
    c = QColor(COLORES["azul"])
    c.setAlpha(max(0, min(255, round(alfa))))
    return c


def aplicar_colores(t):
    global C_TEXTO, C_CLARO, C_NORMAL, C_GRIS_CLARO, C_TITULO, C_SEC, TENUE, SOMBRA, ESCALA
    g = t["global"]
    COLORES["azul"] = QColor(g["acento"])
    texto, sec = temas.hex_rgb(g["texto"]), temas.hex_rgb(g["texto_sec"])
    C_TEXTO, C_SEC = temas.a_hex(texto), temas.a_hex(sec)
    C_CLARO = temas.a_hex(temas.mezcla(texto, sec, 0.1))
    C_NORMAL = temas.a_hex(temas.mezcla(texto, sec, 0.25))
    C_GRIS_CLARO = temas.a_hex(temas.mezcla(texto, sec, 0.45))
    C_TITULO = temas.a_hex(temas.mezcla(texto, sec, 0.7))
    TENUE = tuple(round(c * 255) for c in texto)
    SOMBRA = 55 if temas.luminancia(texto) > 0.5 else 18
    ESCALA = max(0.6, min(1.8, float(g["escala"])))


def tema_claro():
    return SOMBRA < 40  # texto oscuro: fondo claro


_imagenes = {}


def imagen_cubriendo(ruta, ancho, alto):
    """La imagen escalada para cubrir ancho x alto (recortando lo que sobre), con caché."""
    clave = (ruta, ancho, alto)
    if clave not in _imagenes:
        if len(_imagenes) > 40:
            _imagenes.clear()
        img = QPixmap(ruta)
        if img.isNull() or ancho < 1 or alto < 1:
            _imagenes[clave] = None
        else:
            img = img.scaled(ancho, alto, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            _imagenes[clave] = img.copy((img.width() - ancho) // 2, (img.height() - alto) // 2, ancho, alto)
    return _imagenes[clave]


def pintar_fondo(p, perfil, rect, opacidad, prefijo="", solo_extras=False):
    """Fondo según el tema: imagen (si hay) y encima el color o el degradado.
    `prefijo` = "panel_" para el fondo del panel entero. Con `solo_extras` (el
    acrílico ya pone el color) solo se pinta la imagen y el degradado."""
    imagen = perfil.get(prefijo + "imagen")
    if imagen:
        img = imagen_cubriendo(imagen, int(rect.width()), int(rect.height()))
        if img:
            p.save()
            p.setOpacity(perfil[prefijo + "imagen_opacidad"] * opacidad)
            p.drawPixmap(rect.topLeft(), img)
            p.restore()
    alfa = round(perfil[prefijo + "opacidad"] * opacidad * 255)
    color = QColor(perfil[prefijo + "fondo"])
    if not prefijo and perfil["degradado"]:
        ang = math.radians(perfil["angulo"])
        dx, dy = math.cos(ang), math.sin(ang)
        c = rect.center()
        medio = (abs(rect.width() * dx) + abs(rect.height() * dy)) / 2
        deg = QLinearGradient(c.x() - dx * medio, c.y() - dy * medio, c.x() + dx * medio, c.y() + dy * medio)
        c1, c2 = QColor(color), QColor(perfil["fondo2"])
        c1.setAlpha(alfa)
        c2.setAlpha(alfa)
        deg.setColorAt(0, c1)
        deg.setColorAt(1, c2)
        p.fillRect(rect, deg)
    elif not solo_extras:
        color.setAlpha(alfa)
        p.fillRect(rect, color)


def pintar_neon(p, perfil, rect, radio, brillo):
    """Tubo de neón: halo suave (caída gaussiana, sin escalones) del color del borde,
    el tubo de color y un núcleo casi blanco."""
    rgb = temas.hex_rgb(perfil["borde"])
    brillo *= max(0.35, perfil["borde_opacidad"])
    g = max(1.0, perfil["borde_grosor"])
    alcance = int(round(NEON_MARGEN + 6 + 2 * g))
    p.setBrush(Qt.NoBrush)
    for ancho, alfa in temas.capas_neon(alcance, round(min(0.9, 0.62 * brillo), 2)):
        c = QColor(perfil["borde"])
        c.setAlphaF(min(1.0, alfa))
        p.setPen(QPen(c, ancho))
        p.drawRoundedRect(rect, radio, radio)
    for ancho, alfa, mezcla in ((1.8 * g, 0.9, 0.25), (0.8 * g, 0.95, 0.75)):
        c = QColor(*(round(v * 255) for v in temas.mezcla(rgb, (1, 1, 1), mezcla)))
        c.setAlphaF(min(1.0, alfa * brillo))
        p.setPen(QPen(c, ancho))
        p.drawRoundedRect(rect, radio, radio)

def fmt_bytes(n, rate=False):
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    i = 0
    n = float(n)
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    s = f"{n:.0f} {units[i]}" if i == 0 else f"{n:.1f} {units[i]}"
    return s + "/s" if rate else s


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


def ajustes_ventana_windows(hwnd):
    """Quita el widget de la barra de tareas y le pone esquinas redondeadas."""
    if not ES_WINDOWS:
        return
    user32 = ctypes.windll.user32
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    GWL_EXSTYLE, WS_EX_TOOLWINDOW, WS_EX_APPWINDOW = -20, 0x80, 0x40000
    ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, (ex | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)
    try:
        DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND = 33, 2
        pref = ctypes.c_int(DWMWCP_ROUND)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(pref), 4)
    except OSError:
        pass


def etiqueta(texto="", estilo="sub"):
    """Etiqueta con estilo (el texto se traduce)."""
    lb = QLabel(_(texto))
    lb.setProperty("estilo", estilo)
    return lb


# ---------------------------------------------------------------------------
# Widgets de dibujo
# ---------------------------------------------------------------------------

class Grafica(QWidget):
    """Gráfica de líneas con historial; escala fija (0-100) o automática."""

    def __init__(self, series, maximo=100.0, alto=80):
        super().__init__()
        # Si la tarjeta va justa, encoge hasta 28 px antes que cortar los textos de debajo.
        self.alto = alto
        self.setMinimumHeight(28)
        self.maximo = maximo
        self.series = [(COLORES[c], deque([0.0] * HISTORIAL, maxlen=HISTORIAL)) for c in series]

    def push(self, *valores):
        for (_, datos), v in zip(self.series, valores):
            datos.append(v if v is not None else 0.0)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, SOMBRA))
        p.drawRoundedRect(QRectF(0, 0, w, h), 6, 6)

        p.setPen(QPen(tenue(18), 1))
        for i in range(1, 4):
            y = int(h * i / 4) + 0.5
            p.drawLine(QPointF(0, y), QPointF(w, y))

        tope = self.maximo
        if tope is None:
            tope = max((max(d) for _, d in self.series), default=1.0)
            tope = max(tope * 1.15, 1.0)

        paso = w / (HISTORIAL - 1)
        for color, datos in self.series:
            puntos = [QPointF(i * paso, h - min(v / tope, 1.0) * (h - 2) - 1) for i, v in enumerate(datos)]
            linea = QPainterPath(puntos[0])
            for pt in puntos[1:]:
                linea.lineTo(pt)
            relleno = QPainterPath(linea)
            relleno.lineTo(w, h)
            relleno.lineTo(0, h)
            relleno.closeSubpath()
            c = QColor(color)
            c.setAlpha(40)
            p.fillPath(relleno, c)
            p.setPen(QPen(color, 1.6))
            p.setBrush(Qt.NoBrush)
            p.drawPath(linea)

    def sizeHint(self):
        return QSize(ANCHO - 32, self.alto)


class Barra(QWidget):
    """Barra de progreso fina; sin color fijo, cambia de color al llenarse."""

    def __init__(self, alto=8, color=None):
        super().__init__()
        self.alto = alto
        self.color = color
        self.setFixedHeight(alto)
        self.valor = 0.0

    def set(self, v):
        self.valor = v
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        r = self.alto / 2
        p.setBrush(tenue(28))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.alto), r, r)
        color = COLORES["azul"] if self.color == "acento" else self.color or (COLORES["azul"] if self.valor < 70 else
                               COLORES["amarillo"] if self.valor < 90 else COLORES["rojo"])
        p.setBrush(color)
        p.drawRoundedRect(QRectF(0, 0, self.width() * min(self.valor, 100) / 100, self.alto), r, r)


class BarrasNucleos(QWidget):
    """Barras verticales de uso por núcleo."""

    def __init__(self, n):
        super().__init__()
        self.valores = [0.0] * n
        self.setMinimumHeight(16)

    def sizeHint(self):
        return QSize(ANCHO - 32, 42)

    def set(self, valores):
        self.valores = valores
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setPen(Qt.NoPen)
        n = len(self.valores)
        gap = 3
        bw = (self.width() - gap * (n - 1)) / n
        h = self.height()
        for i, v in enumerate(self.valores):
            x = i * (bw + gap)
            p.setBrush(tenue(22))
            p.drawRect(QRectF(x, 0, bw, h))
            p.setBrush(COLORES["azul"] if v < 60 else COLORES["naranja"] if v < 85 else COLORES["rojo"])
            frac = min(v / 100, 1.0)
            p.drawRect(QRectF(x, h - frac * h, bw, frac * h))


def leyenda(*items):
    caja = QWidget()
    fila = QHBoxLayout(caja)
    fila.setContentsMargins(0, 0, 0, 0)
    fila.setSpacing(12)
    for texto, color in items:
        lb = etiqueta(f'<span style="color:{COLORES[color].name()}">●</span> {_(texto)}', "dim")
        fila.addWidget(lb)
    fila.addStretch()
    return caja


# ---------------------------------------------------------------------------
# Multimedia: reproductores y mezclador
# ---------------------------------------------------------------------------

# Iconos de Windows 11 (Segoe Fluent Icons) o de Windows 10 (Segoe MDL2 Assets);
# en otros sistemas, símbolos Unicode.
ICONOS = {"anterior": "\uE892", "play": "\uE768", "pausa": "\uE769", "siguiente": "\uE893",
          "volumen": "\uE767", "silencio": "\uE74F"}
ICONOS_UNICODE = {"anterior": "⏮", "play": "▶", "pausa": "⏸", "siguiente": "⏭",
                  "volumen": "🔊", "silencio": "🔇"}
_fuente_iconos = None


def fuente_iconos():
    global _fuente_iconos
    if _fuente_iconos is None:
        familias = set(QFontDatabase.families())
        _fuente_iconos = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in familias), "")
    return _fuente_iconos


def boton_icono(nombre, tam=12):
    b = QToolButton()
    b.setCursor(Qt.PointingHandCursor)
    poner_icono(b, nombre, tam)
    return b


def poner_icono(boton, nombre, tam=12):
    familia = fuente_iconos()
    if familia:
        boton.setFont(QFont(familia, tam))
        boton.setText(ICONOS[nombre])
    else:
        boton.setText(ICONOS_UNICODE[nombre])


def fmt_tiempo(seg):
    seg = int(seg)
    return f"{seg // 3600}:{seg % 3600 // 60:02d}:{seg % 60:02d}" if seg >= 3600 else f"{seg // 60}:{seg % 60:02d}"


def recortar(label, texto, ancho):
    """Pone el texto en la etiqueta con "…" si no cabe: en su ancho real si ya se
    ve (tarjetas anchas o estrechas del panel) o, si no, en `ancho` píxeles."""
    # El ancho lo decide la tarjeta, no el texto: si no, un texto largo de una
    # tarjeta ancha del panel la ensancharía al pasarla a una ventana.
    if label.minimumWidth() != label.maximumWidth():  # las de ancho fijo ya están acotadas
        label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    if label.isVisible() and label.width() > 20:
        ancho = label.width()
    label.setText(label.fontMetrics().elidedText(texto, Qt.ElideRight, ancho))
    label.setToolTip(texto if label.text() != texto else "")


def color_qt(c):
    return QColor.fromRgbF(*c[:3], c[3] if len(c) == 4 else 1.0)


def rgb(c):
    return (c.redF(), c.greenF(), c.blueF())


def paleta():
    """Colores del tema en uso para los dibujos comunes (esferas.py)."""
    return {"texto": rgb(QColor(C_TEXTO)), "gris": rgb(QColor(C_SEC)), "tenue": tuple(v / 255 for v in TENUE),
            **{k: rgb(v) for k, v in COLORES.items()}}


class LienzoQt:
    """Las operaciones de dibujo que usan los relojes y velocímetros comunes (esferas.py)."""

    PESOS = {"fino": QFont.Light, "normal": QFont.Normal, "negrita": QFont.Bold}

    def __init__(self, widget, p):
        self.widget, self.p = widget, p
        self.fuentes = {}

    def rect(self, x, y, w, h, radio, color):
        self.p.setPen(Qt.NoPen)
        self.p.setBrush(color_qt(color))
        self.p.drawRoundedRect(QRectF(x, y, w, h), radio, radio)

    def circulo(self, cx, cy, r, color):
        self.p.setPen(Qt.NoPen)
        self.p.setBrush(color_qt(color))
        self.p.drawEllipse(QPointF(cx, cy), r, r)

    def arco(self, cx, cy, r, a0, a1, grosor, color, redondo=False):
        self.p.setBrush(Qt.NoBrush)
        self.p.setPen(QPen(color_qt(color), grosor, Qt.SolidLine, Qt.RoundCap if redondo else Qt.FlatCap))
        # Qt cuenta los ángulos en 1/16 de grado y al revés (contra las agujas del reloj).
        self.p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), round(-math.degrees(a0) * 16),
                       round(-math.degrees(a1 - a0) * 16))

    def linea(self, x0, y0, x1, y1, grosor, color, redondo=False):
        self.p.setPen(QPen(color_qt(color), grosor, Qt.SolidLine, Qt.RoundCap if redondo else Qt.FlatCap))
        self.p.drawLine(QPointF(x0, y0), QPointF(x1, y1))

    def poligono(self, puntos, color):
        self.p.setPen(Qt.NoPen)
        self.p.setBrush(color_qt(color))
        self.p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in puntos]))

    _hojas = {}  # la hoja del dinosaurio ya teñida, por color

    def sprite(self, sx, sy, sw, sh, dx, dy, dw, dh, tinta=None):
        """Un trozo de la hoja del dinosaurio, escalado sin suavizar (pixel art)."""
        clave = tuple(round(c, 3) for c in tinta[:3]) if tinta else None
        if clave not in self._hojas:
            img = QImage.fromData(dino_sprite.PNG).convertToFormat(QImage.Format_RGBA8888)
            w, h, fila = img.width(), img.height(), img.bytesPerLine()
            crudo = bytes(img.constBits())
            rgba = b"".join(crudo[y * fila:y * fila + w * 4] for y in range(h))
            datos = juegos.tinta_sprite(rgba, tinta)
            self._hojas[clave] = QPixmap.fromImage(QImage(datos, w, h, w * 4, QImage.Format_RGBA8888).copy())
        self.p.save()
        self.p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        self.p.drawPixmap(QRectF(dx, dy, dw, dh), self._hojas[clave], QRectF(sx, sy, sw, sh))
        self.p.restore()

    def _fuente(self, px, peso):
        clave = (round(px), peso)
        if clave not in self.fuentes:
            f = QFont(self.widget.font())
            f.setPixelSize(max(1, round(px)))
            f.setWeight(self.PESOS[peso])
            self.fuentes[clave] = (f, QFontMetricsF(f))
        return self.fuentes[clave]

    def medir(self, texto, px, peso="normal"):
        _f, fm = self._fuente(px, peso)
        return fm.horizontalAdvance(texto), fm.height()

    def texto(self, texto, x, y, w, h, px, color, peso="normal", h_al=0.5, v_al=0.5):
        f, fm = self._fuente(px, peso)
        tw, th = fm.horizontalAdvance(texto), fm.height()
        self.p.setFont(f)
        self.p.setPen(color_qt(color))
        self.p.drawText(QRectF(x + (w - tw) * h_al, y + (h - th) * v_al, tw, th), Qt.AlignCenter, texto)


class VistaJuego(QWidget):
    """El minijuego en marcha (juegos.py): le pasa el ratón y el teclado y lo redibuja
    cuando lo pide (cada frame mientras se mueve algo, cada segundo con el cronómetro)."""

    TECLAS = {Qt.Key_Left: "izquierda", Qt.Key_A: "izquierda", Qt.Key_Right: "derecha", Qt.Key_D: "derecha",
              Qt.Key_Up: "arriba", Qt.Key_W: "arriba", Qt.Key_Down: "abajo", Qt.Key_S: "abajo",
              Qt.Key_Space: "espacio", Qt.Key_N: "n"}
    BOTONES = {Qt.LeftButton: 1, Qt.MiddleButton: 2, Qt.RightButton: 3}

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setMinimumHeight(80)  # en una celda pequeña se dibuja en pequeño, sin cortar
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.ClickFocus)  # para las flechas y el espacio
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._frame)
        cfg = app.config.setdefault("juegos", {})
        self.poner(cfg.get("actual", "buscaminas"))

    def sizeHint(self):
        return QSize(ANCHO - 32, 280)

    def poner(self, nombre):
        cfg = self.app.config.setdefault("juegos", {})
        cfg["actual"] = nombre
        self.juego = juegos.crear(nombre, cfg.setdefault(nombre, {}), self.app.guardar_config)
        self.update()
        self._programar()

    def nueva(self):
        self.juego.nueva()
        self.update()
        self._programar()

    def _programar(self):
        ms = self.juego.siguiente_frame()
        if ms and not self.timer.isActive() and self.isVisible():
            self.timer.start(ms)

    def _frame(self):
        self.update()
        self._programar()

    def showEvent(self, e):
        super().showEvent(e)
        self._programar()

    def _tarjeta(self):
        w = self.parentWidget()
        while w and not isinstance(w, Tarjeta):
            w = w.parentWidget()
        return w

    def mousePressEvent(self, e):
        tarjeta = self._tarjeta()
        boton = self.BOTONES.get(e.button())
        if not boton or (tarjeta and tarjeta.en_edicion()):
            e.ignore()
            return
        pos = e.position()
        usado = self.juego.pulsar(pos.x(), pos.y(), boton)
        self.update()
        self._programar()
        if not (usado or boton == 1):
            e.ignore()  # el clic derecho que no usa el juego abre el menú de la tarjeta

    def mouseDoubleClickEvent(self, e):
        self.mousePressEvent(e)  # en Qt el segundo clic rápido llega como doble clic

    def mouseReleaseEvent(self, e):
        boton = self.BOTONES.get(e.button())
        pos = e.position()
        if not boton or not self.juego.soltar(pos.x(), pos.y(), boton):
            e.ignore()
        self.update()
        self._programar()

    def _tecla(self, e, pulsada):
        nombre = self.TECLAS.get(e.key())
        if e.isAutoRepeat() and nombre in ("espacio", "arriba", "abajo"):
            return  # mantener pulsado no repite el salto
        if nombre and self.juego.tecla(nombre, pulsada):
            self.update()
            self._programar()
        else:
            e.ignore()

    def keyPressEvent(self, e):
        self._tecla(e, True)

    def keyReleaseEvent(self, e):
        self._tecla(e, False)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self.juego.dibujar(LienzoQt(self, p), paleta(), self.width(), self.height())


class BarraProgreso(QWidget):
    """Progreso de la canción o el vídeo: clic o arrastrar para ir a otro punto."""

    ALTO = 14

    def __init__(self, al_mover, al_soltar):
        super().__init__()
        self.setFixedHeight(self.ALTO)
        self.al_mover, self.al_soltar = al_mover, al_soltar
        self.valor = 0.0          # 0-1
        self.puede = False        # la app deja saltar
        self.encima = False
        self.arrastre = None      # fracción mientras se arrastra

    def set(self, valor, puede):
        if self.arrastre is None and (valor, puede) != (self.valor, self.puede):
            self.valor, self.puede = valor, puede
            self.setCursor(Qt.PointingHandCursor if puede else Qt.ArrowCursor)
            self.update()

    def _frac(self, e):
        return min(max(e.position().x() / max(1, self.width()), 0.0), 1.0)

    def _tarjeta(self):
        w = self.parentWidget()
        while w and not isinstance(w, Tarjeta):
            w = w.parentWidget()
        return w

    def enterEvent(self, _e):
        self.encima = True
        self.update()

    def leaveEvent(self, _e):
        self.encima = False
        self.update()

    def mousePressEvent(self, e):
        tarjeta = self._tarjeta()
        if e.button() != Qt.LeftButton or not self.puede or (tarjeta and tarjeta.en_edicion()):
            e.ignore()  # el clic derecho (menú) y la edición del panel siguen a la tarjeta
            return
        self.arrastre = self._frac(e)
        self.al_mover(self.arrastre)
        self.update()

    def mouseMoveEvent(self, e):
        if self.arrastre is None:
            e.ignore()
            return
        self.arrastre = self._frac(e)
        self.al_mover(self.arrastre)
        self.update()

    def mouseReleaseEvent(self, e):
        if self.arrastre is None or e.button() != Qt.LeftButton:
            e.ignore()
            return
        self.valor = self._frac(e)
        self.arrastre = None
        self.al_soltar(self.valor)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        w, h = self.width(), self.height()
        activo = self.puede and (self.encima or self.arrastre is not None)
        grosor = 6 if activo else 4
        y = (h - grosor) / 2
        p.setBrush(tenue(28))
        p.drawRoundedRect(QRectF(0, y, w, grosor), grosor / 2, grosor / 2)
        frac = self.valor if self.arrastre is None else self.arrastre
        if frac * w > 0.5:
            p.setBrush(COLORES["verde"])
            p.drawRoundedRect(QRectF(0, y, max(frac * w, grosor), grosor), grosor / 2, grosor / 2)
        if activo:
            p.setBrush(QColor(C_TEXTO))
            p.drawEllipse(QPointF(min(max(frac * w, 6), w - 6), h / 2), 6, 6)


def shiboken_vivo(w):
    """False si Qt ya ha borrado el widget (filas rehechas con deleteLater)."""
    try:
        import shiboken6
    except ImportError:
        return True
    return shiboken6.isValid(w)


def mezclar(a, b, t):
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


class Velocimetro(QWidget):
    """Test de velocidad como el velocímetro digital de un deportivo: arco de segmentos
    que se encienden, la cifra en el centro y la fase encima."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.valor = 0.0        # lo que marca ahora (se anima hacia el objetivo)
        self.objetivo = 0.0
        self.tope = 100
        self.texto = "—"        # la cifra del centro
        self.unidad = "Mbps"
        self.fase = ""          # rótulo de encima
        self.color = "azul"
        self.progreso = None    # 0-1 mientras mide (arco fino exterior)
        self.estilo = "deportivo"
        self.animacion = QTimer(self)
        self.animacion.setInterval(16)
        self.animacion.timeout.connect(self._animar)

    def sizeHint(self):
        return QSize(ANCHO - 32, 190)

    def poner(self, valor, tope, texto, fase, color="azul", progreso=None, unidad="Mbps"):
        self.objetivo = valor or 0.0
        self.tope, self.texto, self.fase, self.color, self.progreso, self.unidad = (
            tope, texto, fase, color, progreso, unidad)
        if abs(self.objetivo - self.valor) > self.tope * 1e-4:
            if not self.animacion.isActive():
                self.animacion.start()
        self.update()

    def _animar(self):
        self.valor += (self.objetivo - self.valor) * 0.14
        if abs(self.objetivo - self.valor) <= self.tope * 1e-4:
            self.valor = self.objetivo
            self.animacion.stop()
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        e = {"valor": self.valor, "tope": self.tope, "texto": self.texto, "fase": self.fase,
             "color": self.color, "progreso": self.progreso, "unidad": self.unidad}
        esferas.velocimetro(LienzoQt(self, p), paleta(), self.width(), self.height(), e, self.estilo)


class FilaReproductor(QWidget):
    """Una app con música: portada, título, artista, progreso y controles."""

    PORTADA = 52

    def __init__(self, reproductores):
        super().__init__()
        self.rep = reproductores
        self.ident = None
        self.clave_portada = None
        caja = QVBoxLayout(self)
        caja.setContentsMargins(0, 2, 0, 2)
        caja.setSpacing(4)

        arriba = QHBoxLayout()
        arriba.setSpacing(10)
        self.portada = QLabel()
        self.portada.setFixedSize(self.PORTADA, self.PORTADA)
        arriba.addWidget(self.portada)
        textos = QVBoxLayout()
        textos.setSpacing(1)
        self.titulo = etiqueta()
        self.titulo.setStyleSheet("font-weight: 600;")
        self.artista = etiqueta("", "dim")
        self.app = etiqueta("", "dim")
        for w in (self.titulo, self.artista, self.app):
            textos.addWidget(w)
        textos.addStretch()
        arriba.addLayout(textos, 1)
        caja.addLayout(arriba)

        abajo = QHBoxLayout()
        abajo.setSpacing(2)
        self.tiempo = etiqueta("", "dim")
        abajo.addWidget(self.tiempo)
        abajo.addStretch()
        self.b_anterior = boton_icono("anterior")
        self.b_play = boton_icono("play", 14)
        self.b_siguiente = boton_icono("siguiente")
        for b, accion in ((self.b_anterior, "anterior"), (self.b_play, "play_pausa"),
                          (self.b_siguiente, "siguiente")):
            b.clicked.connect(lambda _=False, a=accion: self.rep.orden(self.ident, a))
            abajo.addWidget(b)
        caja.addLayout(abajo)
        self.progreso = BarraProgreso(self._previsualizar, self._buscar)
        caja.addWidget(self.progreso)
        self.dur = 0
        self.buscado = None  # (segundo, cuándo): hasta que la app informe de la posición nueva

    def _previsualizar(self, frac):
        self.tiempo.setText(f"{fmt_tiempo(frac * self.dur)} / {fmt_tiempo(self.dur)}")

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
        ancho = ANCHO - 32 - self.PORTADA - 10
        recortar(self.titulo, d["titulo"], ancho)
        recortar(self.artista, d["artista"] or "—", ancho)
        recortar(self.app, d["app"], ancho)
        if self.progreso.arrastre is None:
            self.tiempo.setText(f"{fmt_tiempo(pos)} / {fmt_tiempo(d['dur'])}" if d["dur"] > 0 else "")
        self.progreso.set(pos / d["dur"] if d["dur"] > 0 else 0, d.get("buscar", False))
        self.progreso.setToolTip("" if d.get("buscar") else _("Esta app no deja saltar a otro punto"))
        self.progreso.setVisible(d["dur"] > 0)
        poner_icono(self.b_play, "pausa" if d["reproduciendo"] else "play", 14)
        self.b_anterior.setEnabled(d["anterior"])
        self.b_siguiente.setEnabled(d["siguiente"])
        self.b_play.setEnabled(d["play_pausa"])
        if d["portada"] != self.clave_portada:
            self.clave_portada = d["portada"]
            self.portada.setPixmap(self.pixmap_portada(self.rep.portada(d["portada"])))

    def pixmap_portada(self, datos):
        """Portada recortada en cuadrado con esquinas redondeadas (o un hueco)."""
        tam = self.PORTADA
        dpr = self.devicePixelRatioF()
        final = QPixmap(int(tam * dpr), int(tam * dpr))
        final.setDevicePixelRatio(dpr)
        final.fill(Qt.transparent)
        p = QPainter(final)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        ruta = QPainterPath()
        ruta.addRoundedRect(QRectF(0, 0, tam, tam), 6, 6)
        p.setClipPath(ruta)
        img = QPixmap()
        if datos and img.loadFromData(datos):
            img = img.scaled(int(tam * dpr), int(tam * dpr), Qt.KeepAspectRatioByExpanding,
                             Qt.SmoothTransformation)
            img.setDevicePixelRatio(dpr)
            x = (img.width() / dpr - tam) / 2
            y = (img.height() / dpr - tam) / 2
            p.drawPixmap(QPointF(-x, -y), img)
        else:
            p.fillPath(ruta, tenue(25))
            p.setPen(tenue(90))
            p.setFont(QFont(self.font().family(), 20))
            p.drawText(QRectF(0, 0, tam, tam), Qt.AlignCenter, "♪")
        p.end()
        return final


class FilaVolumen(QWidget):
    """Nombre, deslizador de volumen, porcentaje y botón de silencio."""

    def __init__(self, mezclador, nombre, texto):
        super().__init__()
        self.mez = mezclador
        self.nombre = nombre  # None = volumen general
        self.silenciado = False
        self._tocado = 0.0
        self._actualizando = False
        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(6)
        self.etiqueta = etiqueta("", "sub")
        self.etiqueta.setFixedWidth(92)
        recortar(self.etiqueta, texto, 92)
        fila.addWidget(self.etiqueta)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setCursor(Qt.PointingHandCursor)
        self.slider.valueChanged.connect(self._cambio)
        fila.addWidget(self.slider, 1)
        self.valor = etiqueta("", "dim")
        self.valor.setFixedWidth(30)
        self.valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        fila.addWidget(self.valor)
        self.b_mute = boton_icono("volumen", 10)
        self.b_mute.clicked.connect(self._mute)
        fila.addWidget(self.b_mute)

    def _cambio(self, v):
        self.valor.setText(f"{v}")
        if not self._actualizando:
            self._tocado = time.monotonic()
            self.mez.volumen(self.nombre, v / 100)

    def _mute(self):
        self._tocado = time.monotonic()
        self.silenciado = not self.silenciado
        self.mez.silencio(self.nombre, self.silenciado)
        poner_icono(self.b_mute, "silencio" if self.silenciado else "volumen", 10)

    def actualizar(self, volumen, silenciado):
        # No pisar lo que el usuario está moviendo (Windows tarda en reflejarlo).
        if self.slider.isSliderDown() or time.monotonic() - self._tocado < 1.5:
            return
        self._actualizando = True
        self.slider.setValue(round(volumen * 100))
        self._actualizando = False
        self.valor.setText(f"{round(volumen * 100)}")
        if silenciado != self.silenciado:
            self.silenciado = silenciado
            poner_icono(self.b_mute, "silencio" if silenciado else "volumen", 10)


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

RELOJ_POR_DEFECTO = {"estilo": "digital", "h24": True, "segundos": True,
                     "zonas": ["Europe/Madrid", "America/New_York", "America/Mexico_City", "Asia/Tokyo"]}


def fuente_que_quepa(texto, ancho, alto, peso=QFont.Light, base=None):
    """La fuente más grande con la que `texto` cabe en ancho x alto píxeles."""
    f = QFont(base) if base else QFont()
    f.setWeight(peso)
    f.setPixelSize(max(8, int(alto)))
    w = QFontMetricsF(f).horizontalAdvance(texto)
    if w > ancho:
        f.setPixelSize(max(8, int(alto * ancho / w)))
    return f


class RelojVista(QWidget):
    """Reloj dibujado que se escala al tamaño que tenga (celda del panel o widget).

    Estilos: digital, analógico, minimalista y mundial (varias ciudades).
    """

    def __init__(self, opciones):
        super().__init__()
        self.opciones = opciones
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ajustar_minimo()

    def ajustar_minimo(self):
        o = self.opciones
        minimos = {"digital": 96, "analogico": 210, "minimal": 104,
                   "mundial": 44 * max(1, len(o["zonas"])), **esferas.ALTOS}
        self._alto = minimos.get(o["estilo"], 96)
        self.setMinimumHeight(int(self._alto * 0.55))
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        return QSize(ANCHO - 32, self._alto)

    def hora(self, t):
        o = self.opciones
        formato = ("%H:%M" if o["h24"] else "%I:%M").replace("%I", "%-I" if sys.platform != "win32" else "%#I")
        return t.strftime(formato)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        ahora = datetime.datetime.now()
        if self.opciones["estilo"] in esferas.ALTOS:
            esferas.reloj(LienzoQt(self, p), paleta(), self.width(), self.height(), ahora, self.opciones,
                          fecha_larga(ahora.date()), self.opciones["estilo"])
            return
        dibujar = {"analogico": self.analogico, "minimal": self.minimal,
                   "mundial": self.mundial}.get(self.opciones["estilo"], self.digital)
        dibujar(p, ahora)

    def digital(self, p, ahora, minimal=False):
        o = self.opciones
        w, h = self.width(), self.height()
        alto_fecha = 0 if minimal and h < 140 else max(14, h * 0.16)
        hora = self.hora(ahora)
        extra = ahora.strftime("%S") if o["segundos"] and not minimal else ""
        ampm = "" if o["h24"] else ("AM" if ahora.hour < 12 else "PM")
        zona = QRectF(0, 0, w, h - alto_fecha)
        f = fuente_que_quepa(hora + (" 00" if extra or ampm else ""), w * 0.98, zona.height() * 0.92,
                             QFont.ExtraLight if minimal else QFont.Light, self.font())
        p.setFont(f)
        metr = p.fontMetrics()
        ancho_hora = metr.horizontalAdvance(hora)
        f2 = QFont(f)
        f2.setPixelSize(max(8, f.pixelSize() // 3))
        p.setPen(QColor(C_TEXTO))
        x0 = 0 if not minimal else (w - ancho_hora - (metr.horizontalAdvance(" 00") if ampm else 0)) / 2
        # Hora y fecha centradas juntas en vertical (sin hueco entre ellas en celdas altas).
        hueco = metr.capHeight() * 0.35
        bloque = metr.capHeight() + (hueco + alto_fecha if alto_fecha else 0)
        arriba = max(0, (h - bloque) / 2)
        base = arriba + metr.capHeight()
        p.drawText(QPointF(x0, base), hora)
        if extra or ampm:
            p.setFont(f2)
            p.setPen(QColor(C_SEC))
            p.drawText(QPointF(x0 + ancho_hora + f.pixelSize() * 0.12, base), extra or ampm)
            if extra and ampm:
                p.drawText(QPointF(x0 + ancho_hora + f.pixelSize() * 0.12, base - f.pixelSize() * 0.42), ampm)
        if alto_fecha:
            ff = fuente_que_quepa(fecha_larga(ahora.date()), w, alto_fecha * 0.8, QFont.Normal, self.font())
            ff.setPixelSize(min(ff.pixelSize(), 18))
            p.setFont(ff)
            p.setPen(QColor(C_GRIS_CLARO))
            p.drawText(QRectF(0, min(base + hueco, h - alto_fecha), w, alto_fecha),
                       (Qt.AlignHCenter if minimal else Qt.AlignLeft) | Qt.AlignVCenter, fecha_larga(ahora.date()))

    def minimal(self, p, ahora):
        self.digital(p, ahora, minimal=True)

    def analogico(self, p, ahora):
        w, h = self.width(), self.height()
        alto_fecha = 20 if h > 180 else 0
        r = min(w, h - alto_fecha) / 2 - 4
        c = QPointF(w / 2, (h - alto_fecha) / 2)
        p.setPen(QPen(tenue(50), max(1.0, r * 0.02)))
        p.setBrush(tenue(10))
        p.drawEllipse(c, r, r)
        # Marcas: horas gruesas, minutos finas.
        for i in range(60):
            ang = math.radians(i * 6)
            largo, grosor, alfa = (0.12, 0.035, 220) if i % 5 == 0 else (0.05, 0.012, 110)
            p.setPen(QPen(tenue(alfa), max(1.0, r * grosor), Qt.SolidLine, Qt.RoundCap))
            dx, dy = math.sin(ang), -math.cos(ang)
            p.drawLine(QPointF(c.x() + dx * r * (0.92 - largo), c.y() + dy * r * (0.92 - largo)),
                       QPointF(c.x() + dx * r * 0.92, c.y() + dy * r * 0.92))
        seg = ahora.second
        minuto = ahora.minute + seg / 60
        horas = (ahora.hour % 12) + minuto / 60

        def aguja(fraccion, largo, grosor, color):
            ang = math.radians(fraccion * 360)
            p.setPen(QPen(color, max(1.5, r * grosor), Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(c.x() - math.sin(ang) * r * 0.12, c.y() + math.cos(ang) * r * 0.12),
                       QPointF(c.x() + math.sin(ang) * r * largo, c.y() - math.cos(ang) * r * largo))

        aguja(horas / 12, 0.5, 0.055, QColor(C_TEXTO))
        aguja(minuto / 60, 0.75, 0.035, QColor(C_TEXTO))
        if self.opciones["segundos"]:
            aguja(seg / 60, 0.82, 0.012, QColor("#ff9e43"))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ff9e43") if self.opciones["segundos"] else QColor(C_TEXTO))
        p.drawEllipse(c, r * 0.045, r * 0.045)
        if alto_fecha:
            ff = QFont(self.font())
            ff.setPixelSize(13)
            p.setFont(ff)
            p.setPen(QColor(C_GRIS_CLARO))
            p.drawText(QRectF(0, h - alto_fecha, w, alto_fecha), Qt.AlignCenter, fecha_larga(ahora.date()))

    def mundial(self, p, ahora):
        zonas = self.opciones["zonas"] or ["UTC"]
        nombres = dict((z, n) for n, z in CIUDADES)
        w, h = self.width(), self.height()
        fila = h / len(zonas)
        hoy_local = ahora.date()
        fuente_hora = fuente_que_quepa("00:00", w * 0.4, min(fila * 0.62, 44), QFont.Light, self.font())
        fuente_nombre = QFont(self.font())
        fuente_nombre.setPixelSize(max(11, min(int(fila * 0.36), 20)))
        fuente_extra = QFont(fuente_nombre)
        fuente_extra.setPixelSize(max(9, int(fuente_nombre.pixelSize() * 0.75)))
        for i, zona in enumerate(zonas):
            caja = QRectF(0, i * fila, w, fila)
            try:
                t = datetime.datetime.now(ZoneInfo(zona))
            except Exception:  # noqa: BLE001 - p. ej. falta tzdata en Windows
                p.setFont(fuente_extra)
                p.setPen(QColor("#ff5c5c"))
                p.drawText(caja, Qt.AlignLeft | Qt.AlignVCenter,
                           _("{ciudad}: zona no disponible (vuelve a ejecutar instalar.bat)").format(ciudad=_(nombres.get(zona, zona))))
                continue
            dias = (t.date() - hoy_local).days
            extra = {1: _("mañana"), -1: _("ayer")}.get(dias, _("hoy"))
            difer = (t.utcoffset() - ahora.astimezone().utcoffset()).total_seconds() / 3600
            if difer:
                extra += f" · {difer:+g} h"
            if i:
                p.setPen(QPen(tenue(25), 1))
                p.drawLine(QPointF(0, caja.top()), QPointF(w, caja.top()))
            texto = self.hora(t) + ("" if self.opciones["h24"] else (" AM" if t.hour < 12 else " PM"))
            libre = w - QFontMetricsF(fuente_hora).horizontalAdvance(texto) - 12  # lo que deja la hora
            p.setFont(fuente_nombre)
            p.setPen(QColor(C_CLARO))
            p.drawText(caja.adjusted(0, 0, 0, -fila * 0.42), Qt.AlignLeft | Qt.AlignBottom,
                       p.fontMetrics().elidedText(_(nombres.get(zona, zona)), Qt.ElideRight, int(libre)))
            p.setFont(fuente_extra)
            p.setPen(QColor(C_SEC))
            p.drawText(caja.adjusted(0, fila * 0.56, 0, 0), Qt.AlignLeft | Qt.AlignTop,
                       p.fontMetrics().elidedText(extra, Qt.ElideRight, int(libre)))
            p.setFont(fuente_hora)
            p.setPen(QColor(C_TEXTO))
            p.drawText(caja, Qt.AlignRight | Qt.AlignVCenter, texto)


class CalendarioMes(QWidget):
    """Un mes en cuadrícula con el día de hoy marcado; la semana empieza en lunes o domingo."""

    def __init__(self, primer_dia=0):
        super().__init__()
        self.primer_dia = primer_dia  # 0 = lunes, 6 = domingo
        self.ir_a_hoy()
        self.setMinimumHeight(84)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def sizeHint(self):
        return QSize(ANCHO - 32, 165)

    def ir_a_hoy(self):
        hoy = datetime.date.today()
        self.anio, self.mes = hoy.year, hoy.month
        self.update()

    def cambiar(self, meses):
        m = self.mes - 1 + meses
        self.anio, self.mes = self.anio + m // 12, m % 12 + 1
        self.update()

    def titulo(self):
        return idioma.titulo_mes(self.anio, self.mes)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        hoy = datetime.date.today()
        semanas = calendar.Calendar(firstweekday=self.primer_dia).monthdatescalendar(self.anio, self.mes)
        cw = self.width() / 7
        ch = self.height() / (len(semanas) + 1)
        fuente = QFont(self.font())
        fuente.setPointSizeF(min(11.0, max(8.0, ch * 0.42)))
        pequena = QFont(fuente)
        pequena.setPointSizeF(fuente.pointSizeF() * 0.8)
        pequena.setBold(True)
        p.setFont(pequena)
        for i in range(7):
            dia = (self.primer_dia + i) % 7  # 0 = lunes
            p.setPen(QColor(C_SEC) if dia < 5 else QColor("#c4561a" if tema_claro() else "#ff9e43"))
            p.drawText(QRectF(i * cw, 0, cw, ch), Qt.AlignCenter, idioma.inicial_dia(dia))
        for f, semana in enumerate(semanas, 1):
            for c, dia in enumerate(semana):
                caja = QRectF(c * cw, f * ch, cw, ch)
                if dia == hoy:
                    r = min(cw, ch) * 0.44
                    p.setPen(Qt.NoPen)
                    p.setBrush(acento())
                    p.drawEllipse(caja.center(), r, r)
                    fuente.setBold(True)
                    p.setPen(QColor("white"))
                else:
                    fuente.setBold(False)
                    color = QColor(C_CLARO) if dia.weekday() < 5 else QColor("#c4561a" if tema_claro() else "#ffb877")
                    if dia.month != self.mes:
                        color.setAlpha(70)
                    p.setPen(color)
                p.setFont(fuente)
                p.drawText(caja, Qt.AlignCenter, str(dia.day))


# ---------------------------------------------------------------------------
# Sensores: formato, selección por defecto y selector
# ---------------------------------------------------------------------------

# Tipo de sensor de LibreHardwareMonitor -> (sección en el widget, formato)
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


def fmt_sensor(tipo, valor, color=True):
    formato = TIPOS_SENSOR.get(tipo, (tipo, "{:.2f}"))[1]
    if formato == "rpm":
        return f"{valor:,.0f} RPM".replace(",", ".") if valor > 0 else _("parado")
    if formato == "bytes/s":
        return fmt_bytes(valor, True)
    texto = formato.format(valor)
    if color and tipo == "Temperature":
        return f'<span style="color:{color_temp(valor)}">{texto}</span>'
    return texto


def seleccion_auto(sensores):
    """Lo que se ve si no se ha elegido nada: temperaturas con sentido, y los
    ventiladores de las GPUs (paran a 0 RPM en reposo) y los que giran (los
    conectores vacíos de la placa marcan 0 siempre)."""
    temps, por_dispositivo, vistos = [], {}, set()
    for kind, hw, tipo, nombre, valor, ident in sensores:
        if tipo != "Temperature" or "distance" in nombre.lower() or not 5 < valor < 115:
            continue
        # Como mucho dos por dispositivo (la placa tiene muchos) y sin repetidos.
        if (hw, nombre) in vistos or por_dispositivo.get(hw, 0) >= 2:
            continue
        vistos.add((hw, nombre))
        por_dispositivo[hw] = por_dispositivo.get(hw, 0) + 1
        temps.append(ident)
    fans = [x[5] for x in sensores if x[2] == "Fan" and (x[0].startswith("Gpu") or x[4] > 0)]
    return temps[:12] + fans[:6]


class ListaSensores(QWidget):
    """Lista de sensores que se adapta al espacio: varias columnas si es ancha y, si
    aun así no caben, los que quepan y "… y N más" (en vez de aplastar las filas)."""

    FILA = 19
    ANCHO_COLUMNA = 250
    ANCHO_VALOR = 84

    def __init__(self):
        super().__init__()
        self.lineas = []   # ("seccion", texto) o ("sensor", nombre, valor, color)
        # Sin "alto para el ancho": Qt no deja bajar de ese alto, y en una celda pequeña
        # tiene que poder encoger (enseña "… y N más").
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_lineas(self, lineas):
        cambia_alto = len(lineas) != len(self.lineas)
        self.lineas = lineas
        if cambia_alto:
            self.updateGeometry()
        self.update()

    def columnas(self, ancho):
        return max(1, min(ancho // self.ANCHO_COLUMNA, len(self.lineas) or 1))

    def alto_para(self, ancho):
        return -(-len(self.lineas) // self.columnas(ancho)) * self.FILA

    def sizeHint(self):
        return QSize(ANCHO - 32, self.alto_para(ANCHO - 32))

    def minimumSizeHint(self):
        return QSize(100, self.FILA * 3)

    @staticmethod
    def huecos(lineas, por_columna):
        """Posición (hueco) de cada línea: un título nunca queda el último de una
        columna separado de sus sensores; pasa a la siguiente."""
        posiciones, hueco = [], 0
        for linea in lineas:
            if linea[0] == "seccion" and hueco % por_columna == por_columna - 1:
                hueco += 1
            posiciones.append(hueco)
            hueco += 1
        return posiciones, hueco

    def paintEvent(self, _e):
        p = QPainter(self)
        cols = self.columnas(self.width())
        maximo = max(1, self.height() // self.FILA)
        lineas = self.lineas
        # Columnas equilibradas: la altura mínima con la que todo cabe.
        por_columna = -(-len(lineas) // cols) or 1
        while por_columna < maximo and self.huecos(lineas, por_columna)[1] > cols * por_columna:
            por_columna += 1
        if por_columna > maximo or self.huecos(lineas, por_columna)[1] > cols * por_columna:
            por_columna = maximo
            while lineas and self.huecos(lineas, por_columna)[1] > cols * por_columna - 1:
                lineas = lineas[:-1]
            ocultas = sum(1 for x in self.lineas[len(lineas):] if x[0] == "sensor")
            lineas = lineas + [("mas", _("… y {n} más (amplía el widget)").format(n=ocultas))]
        posiciones, _x = self.huecos(lineas, por_columna)
        ancho_col = (self.width() - 16 * (cols - 1)) / cols
        normal = QFont(self.font())
        normal.setPointSizeF(9.5)
        seccion = QFont(normal)
        seccion.setPointSizeF(7.5)
        seccion.setBold(True)
        for i, linea in zip(posiciones, lineas):
            x = (i // por_columna) * (ancho_col + 16)
            y = (i % por_columna) * self.FILA
            caja = QRectF(x, y, ancho_col, self.FILA)
            if linea[0] == "seccion":
                p.setFont(seccion)
                p.setPen(QColor(C_TITULO))
                p.drawText(caja, Qt.AlignLeft | Qt.AlignBottom, linea[1])
            elif linea[0] == "mas":
                p.setFont(normal)
                p.setPen(QColor(C_SEC))
                p.drawText(caja.adjusted(0, 0, 400, 0), Qt.AlignLeft | Qt.AlignVCenter, linea[1])
            else:
                _x, nombre, valor, color = linea
                p.setFont(normal)
                p.setPen(QColor(color))
                p.drawText(caja, Qt.AlignRight | Qt.AlignVCenter, valor)
                p.setPen(QColor(C_NORMAL))
                ancho_nombre = int(ancho_col - self.ANCHO_VALOR)
                p.drawText(caja.adjusted(0, 0, -self.ANCHO_VALOR, 0), Qt.AlignLeft | Qt.AlignVCenter,
                           p.fontMetrics().elidedText(nombre, Qt.ElideRight, ancho_nombre))


class SelectorSensores(QDialog):
    """Ventana para marcar qué sensores se muestran, agrupados por dispositivo y tipo."""

    ESTILO = """
    QDialog { background: #1b1e25; }
    QLabel { color: #d0d6e0; }
    QLineEdit { background: #262a33; color: #f2f4f8; border: 1px solid #3a3f4b; border-radius: 6px; padding: 6px 8px; }
    QTreeWidget { background: #20232b; color: #e6e9ef; border: 1px solid #3a3f4b; border-radius: 6px; }
    QTreeWidget::item { padding: 2px 0; }
    QHeaderView::section { background: #262a33; color: #aab3c2; border: none; padding: 4px 6px; }
    QPushButton { background: #2c313b; color: #e6e9ef; border: none; border-radius: 6px; padding: 7px 14px; }
    QPushButton:hover { background: #363c48; }
    QPushButton#aceptar { background: #4d8dff; color: white; font-weight: 600; }
    """

    def __init__(self, sensores, seleccion, padre=None):
        super().__init__(padre)
        self.setWindowTitle(_("Elegir sensores"))
        self.setStyleSheet(self.ESTILO)
        self.resize(600, 680)
        self.por_defecto = False
        caja = QVBoxLayout(self)
        caja.addWidget(QLabel(_("Marca los sensores que quieres ver en el widget Sensores "
                                "(hasta {n}).").format(n=MAX_SENSORES)))
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText(_("Buscar: «cpu», «voltaje», «fan», «nvme»…"))
        self.buscar.textChanged.connect(self.filtrar)
        caja.addWidget(self.buscar)

        self.arbol = QTreeWidget()
        self.arbol.setHeaderLabels([_("Sensor"), _("Valor")])
        self.arbol.setColumnWidth(0, 420)
        marcados = set(seleccion)
        dispositivos = {}
        for kind, hw, tipo, nombre, valor, ident in sensores:
            disp = dispositivos.get(hw)
            if disp is None:
                disp = dispositivos[hw] = QTreeWidgetItem(self.arbol, [hw])
                disp.setFlags(disp.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                disp.secciones = {}
            seccion_txt = _(TIPOS_SENSOR.get(tipo, (tipo,))[0])
            seccion = disp.secciones.get(seccion_txt)
            if seccion is None:
                seccion = disp.secciones[seccion_txt] = QTreeWidgetItem(disp, [seccion_txt])
                seccion.setFlags(seccion.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
            item = QTreeWidgetItem(seccion, [nombre, fmt_sensor(tipo, valor, color=False)])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked if ident in marcados else Qt.Unchecked)
            item.ident = ident
            item.busqueda = f"{hw} {seccion_txt} {tipo} {nombre}".lower()
        for disp in dispositivos.values():
            # Abiertos los grupos con algo marcado, para ver de un vistazo lo elegido.
            disp.setExpanded(disp.checkState(0) != Qt.Unchecked)
            for seccion in disp.secciones.values():
                seccion.setExpanded(seccion.checkState(0) != Qt.Unchecked)
        caja.addWidget(self.arbol, 1)

        botones = QHBoxLayout()
        for texto, fn in ((_("Por defecto"), self.restablecer), (_("Ninguno"), self.ninguno)):
            b = QPushButton(texto)
            b.clicked.connect(fn)
            botones.addWidget(b)
        botones.addStretch()
        cancelar = QPushButton(_("Cancelar"))
        cancelar.clicked.connect(self.reject)
        aceptar = QPushButton(_("Aceptar"))
        aceptar.setObjectName("aceptar")
        aceptar.clicked.connect(self.accept)
        botones.addWidget(cancelar)
        botones.addWidget(aceptar)
        caja.addLayout(botones)

    def hojas(self):
        for i in range(self.arbol.topLevelItemCount()):
            disp = self.arbol.topLevelItem(i)
            for j in range(disp.childCount()):
                seccion = disp.child(j)
                for k in range(seccion.childCount()):
                    yield seccion.child(k)

    def seleccion(self):
        return [h.ident for h in self.hojas() if h.checkState(0) == Qt.Checked][:MAX_SENSORES]

    def filtrar(self, texto):
        texto = texto.lower().strip()
        for h in self.hojas():
            h.setHidden(bool(texto) and texto not in h.busqueda)
        for i in range(self.arbol.topLevelItemCount()):
            disp = self.arbol.topLevelItem(i)
            for j in range(disp.childCount()):
                seccion = disp.child(j)
                visibles = any(not seccion.child(k).isHidden() for k in range(seccion.childCount()))
                seccion.setHidden(not visibles)
                seccion.setExpanded(bool(texto) or seccion.isExpanded())
            disp.setHidden(all(disp.child(j).isHidden() for j in range(disp.childCount())))
            disp.setExpanded(bool(texto) or disp.isExpanded())

    def ninguno(self):
        for h in self.hojas():
            h.setCheckState(0, Qt.Unchecked)

    def restablecer(self):
        self.por_defecto = True
        self.accept()


# ---------------------------------------------------------------------------
# Widget de escritorio (una tarjeta = una ventana con cristal)
# ---------------------------------------------------------------------------

ESTILO = """
Tarjeta { background: transparent; }
QLabel { background: transparent; }
QLabel[estilo="titulo"] { color: #aab3c2; font-weight: bold; font-size: 10pt; letter-spacing: 1px; }
QLabel[estilo="grande"] { color: #f2f4f8; font-size: 22pt; font-weight: 600; }
QLabel[estilo="sub"] { color: #d0d6e0; font-size: 10pt; }
QLabel[estilo="dim"] { color: #9aa3b2; font-size: 9pt; }
QLabel[estilo="seccion"] { color: #aab3c2; font-weight: bold; font-size: 8pt; letter-spacing: 1px; }
QToolButton { background: transparent; border: none; color: #e6e9ef; padding: 3px; border-radius: 5px; }
QToolButton:hover { background: rgba(255, 255, 255, 30); }
QToolButton:disabled { color: rgba(255, 255, 255, 55); }
QSlider::groove:horizontal { height: 4px; background: rgba(255, 255, 255, 40); border-radius: 2px; }
QSlider::sub-page:horizontal { background: #4d8dff; border-radius: 2px; }
QSlider::handle:horizontal { background: #f2f4f8; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
QPushButton[estilo="dispositivo"] { text-align: left; padding: 5px 8px; background: transparent; color: #d0d6e0; }
QPushButton[estilo="dispositivo"]:hover { background: rgba(255, 255, 255, 22); }
QPushButton[estilo="dispositivo"]:checked { background: rgba(77, 141, 255, 55); color: #ffffff; font-weight: 600; }
QPushButton { background: rgba(255, 255, 255, 22); color: #e6e9ef; border: none; border-radius: 6px; padding: 7px 12px; }
QPushButton:hover { background: rgba(255, 255, 255, 38); }
QPushButton:disabled { color: rgba(255, 255, 255, 90); }
QPushButton[estilo="principal"] { background: #4d8dff; color: white; font-weight: 600; }
QPushButton[estilo="principal"]:hover { background: #6a9fff; }
QPushButton:checked { background: rgba(255, 92, 92, 70); color: white; }
"""


def css_tema(t):
    """La hoja de estilo de las tarjetas con los colores, la fuente y el tamaño de letra del tema."""
    g = t["global"]
    ac = QColor(g["acento"])
    claro = QColor(*(round(v * 255) for v in temas.mezcla(temas.hex_rgb(g["acento"]), (1, 1, 1), 0.2)))
    css = ESTILO
    for viejo, nuevo in (("#aab3c2", C_TITULO), ("#f2f4f8", C_TEXTO), ("#d0d6e0", C_NORMAL), ("#9aa3b2", C_SEC),
                         ("#e6e9ef", C_CLARO), ("#6a9fff", claro.name()), ("#4d8dff", ac.name())):
        css = css.replace(viejo, nuevo)
    css = re.sub(r"rgba\(255, 255, 255, (\d+)\)", lambda m: f"rgba({TENUE[0]}, {TENUE[1]}, {TENUE[2]}, {m.group(1)})", css)
    css = re.sub(r"rgba\(77, 141, 255, (\d+)\)", lambda m: f"rgba({ac.red()}, {ac.green()}, {ac.blue()}, {m.group(1)})",
                 css)
    css = re.sub(r"(\d+(?:\.\d+)?)pt", lambda m: f"{float(m.group(1)) * ESCALA:.1f}pt", css)
    if g["fuente"]:
        css = f'* {{ font-family: "{g["fuente"]}"; }}\n' + css
    return css


class Tarjeta(QWidget):
    """Contenido de un widget. Vive en su propia ventana (VentanaWidget) o en el panel."""

    def __init__(self, clave, titulo, app):
        super().__init__()
        self.clave = clave
        self.titulo = titulo
        self.nombre_menu = titulo  # cómo aparece en "Widgets visibles"
        self.app = app
        self.opacidad = 1.0
        self.relleno = "ninguno"  # fondo que pinta: "ninguno", "oscuro" o "claro" (lo decide quien la aloja)
        self.radio = 8
        self.ventana = None       # VentanaWidget cuando está suelta en el escritorio
        self._estira = False      # ya hay un elemento que absorbe la altura sobrante
        self.prescindibles = []   # lo que se quita si la tarjeta es muy baja (ver add)
        self._ajuste = False
        self._arrastre = None     # "mover" o "tam" mientras se edita el panel
        self.brillo = 1.0         # del neón (baja cuando parpadea)
        self._secuencia = []
        self._siguiente = time.monotonic() + random.uniform(1, 8)
        self.setMouseTracking(True)
        self.setStyleSheet(css_tema(app.tema))

        # Todo el contenido va en un contenedor para poder atenuarlo junto.
        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(0, 0, 0, 0)
        self.contenido = QWidget()
        exterior.addWidget(self.contenido)
        self.caja = QVBoxLayout(self.contenido)
        self._margen = None
        self.ajustar_margenes()
        self.caja.setSpacing(6)
        self.lb_titulo = self.add(etiqueta(titulo.upper(), "titulo"))
        # Si cambia el contenido (entra una canción, una persona...), se mira otra vez si cabe.
        self.contenido.installEventFilter(self)

    def add(self, w, prescindible=0):
        """prescindible: si la tarjeta es tan baja que no cabe todo (celda pequeña del
        panel), se quita (1 = lo primero que se quita, 2 = después...) en vez de cortar
        el texto de abajo. Las gráficas encogen antes de quitar nada."""
        # La primera gráfica crece si la tarjeta es más alta que su contenido
        # (filas de la misma altura en modo widgets, cuadrícula en modo panel).
        estirar = isinstance(w, (Grafica, Velocimetro, VistaJuego)) and not self._estira
        self._estira = self._estira or estirar
        self.caja.addWidget(w, 1 if estirar else 0)
        if prescindible:
            w._prescindible, w._quitado = prescindible, False
            self.prescindibles.append(w)
        return w

    def prescindibles_grupo(self, grupo, widgets, base):
        """Filas que se crean sobre la marcha (p. ej. una por app): se quitan en el orden de
        `widgets` con prioridad desde `base`. Sustituye a las del mismo grupo de antes."""
        self.prescindibles = [w for w in self.prescindibles if getattr(w, "_grupo", None) != grupo]
        for i, w in enumerate(widgets):
            w._grupo, w._prescindible, w._quitado = grupo, base + i / 100, False
            self.prescindibles.append(w)
        self.pedir_ajuste()

    def eventFilter(self, obj, e):
        if obj is self.contenido and e.type() == QEvent.LayoutRequest:
            self.pedir_ajuste()
        return False

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.pedir_ajuste()

    def pedir_ajuste(self):
        if self.prescindibles and not self._ajuste:
            self._ajuste = True
            QTimer.singleShot(0, self.ajustar_prescindibles)

    def ajustar_prescindibles(self):
        """Quita lo prescindible que haga falta para que el resto quepa en el alto de la tarjeta."""
        self._ajuste = False
        ancho, alto = self.width(), self.height()
        m = self.caja.contentsMargins()
        interior = max(1, ancho - m.left() - m.right())

        def alto_de(w):
            # Oculto no cuenta en el layout: se usa lo que medía la última vez que se vio.
            if not w.isHidden():
                caja = w.parentWidget().layout() if w.parentWidget() else None
                minimo = (w.heightForWidth(interior) if w.hasHeightForWidth()
                          else max(w.minimumSizeHint().height(), w.minimumHeight()))
                w._alto = minimo + (caja.spacing() if caja else 0)
            return getattr(w, "_alto", 0)

        self.prescindibles = [w for w in self.prescindibles if shiboken_vivo(w)]
        for w in self.prescindibles:
            if w._quitado and not w.isHidden():
                w._quitado = False  # alguien lo ha vuelto a mostrar
        candidatos = [w for w in self.prescindibles if not w.isHidden() or w._quitado]
        caja = self.caja
        necesario = (caja.totalMinimumHeightForWidth(ancho) if caja.hasHeightForWidth()
                     else caja.totalMinimumSize().height())
        necesario += sum(alto_de(w) for w in candidatos if w._quitado)
        for w in candidatos:
            alto_de(w)
        quitar = set()
        for w in sorted(candidatos, key=lambda x: x._prescindible):
            if necesario <= alto:
                break
            necesario -= alto_de(w)
            quitar.add(w)
        for w in candidatos:
            ver = w not in quitar
            if w.isHidden() == ver:
                w._quitado = not ver
                w.setVisible(ver)

    def terminar(self):
        """Sin gráfica que crezca, el espacio sobrante va al final."""
        if not self._estira:
            self.caja.addStretch(1)

    def alto_natural(self, ancho):
        caja = self.layout()
        minimo = caja.totalMinimumSize().height()
        alto = max(caja.totalHeightForWidth(ancho) if caja.hasHeightForWidth() else caja.totalSizeHint().height(),
                   minimo)
        # Lo quitado por falta de sitio también cuenta: en su ventana cabe todo y vuelve a verse.
        return alto + sum(getattr(w, "_alto", 0) for w in self.prescindibles if w._quitado)

    def set_opacidad(self, valor):
        """Atenúa el contenido y el fondo (1.0 = normal)."""
        self.opacidad = valor
        # Con 1.0 se quita el efecto: renderizar a través de él tiene un coste.
        if valor < 1:
            efecto = QGraphicsOpacityEffect(self.contenido)
            efecto.setOpacity(valor)
            self.contenido.setGraphicsEffect(efecto)
        else:
            self.contenido.setGraphicsEffect(None)
        if self.ventana:
            self.ventana.aplicar_tinte()
        self.update()

    def ajustar_margenes(self):
        """Margen interior del contenido; con neón, algo más (el halo va hacia dentro)."""
        m = NEON_MARGEN if self.perfil()["neon"] else 0
        extra = 0 if m else (6 if self.perfil()["neon"] else 0)
        if (m, extra) == self._margen:
            return
        self._margen = (m, extra)
        e = m + extra
        self.caja.setContentsMargins(16 + e, 14 + e, 16 + e, 16 + e)

    def perfil(self):
        """Ajustes del tema que le tocan: los del panel si está dentro de él."""
        return self.app.tema["panel" if self.relleno == "claro" else "widgets"]

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        perfil = self.perfil()
        self.radio = perfil["radio"]
        m = NEON_MARGEN if perfil["neon"] else 0
        r = QRectF(self.rect()).adjusted(m + 0.5, m + 0.5, -m - 0.5, -m - 0.5)
        ruta = QPainterPath()
        ruta.addRoundedRect(r, self.radio, self.radio)
        p.save()
        p.setClipPath(ruta)
        # En su propia ventana con acrílico, el color del fondo ya lo pone el cristal.
        con_acrilico = bool(self.ventana and self.ventana.acrilico_activo)
        pintar_fondo(p, perfil, r, self.opacidad, solo_extras=con_acrilico)
        p.restore()
        if perfil["neon"]:
            pintar_neon(p, perfil, r, self.radio, self.brillo * self.opacidad)
        elif perfil["borde_grosor"] > 0:
            borde = QColor(perfil["borde"])
            borde.setAlphaF(min(1.0, perfil["borde_opacidad"] * self.opacidad))
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(borde, perfil["borde_grosor"]))
            g = perfil["borde_grosor"] / 2
            p.drawRoundedRect(r.adjusted(g - 0.5, g - 0.5, 0.5 - g, 0.5 - g), self.radio, self.radio)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self.en_edicion():
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(acento(170), 1.5, Qt.DashLine))
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), self.radio, self.radio)
            # Asa de tamaño en la esquina inferior derecha.
            p.setPen(QPen(tenue(200), 2, Qt.SolidLine, Qt.RoundCap))
            w, h = self.width(), self.height()
            for d in (6, 11, 16):
                p.drawLine(QPointF(w - 5, h - 5 - d), QPointF(w - 5 - d, h - 5))

    # Parpadeo del neón: de vez en cuando, una serie corta de apagones como un tubo que falla.
    def tic_parpadeo(self, ahora):
        if ahora < self._siguiente:
            return
        if not self._secuencia:
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
            self.update()

    # --- edición del panel ---------------------------------------------------

    ASA = 26  # píxeles de la esquina que sirven para cambiar el tamaño

    def en_edicion(self):
        panel = self.app.panel if self.app.modo == "panel" else None
        return bool(panel and panel.editando and not self.ventana)

    def en_asa(self, pos):
        return pos.x() > self.width() - self.ASA and pos.y() > self.height() - self.ASA

    def mouseMoveEvent(self, e):
        if not self.en_edicion():
            return
        pos = e.position().toPoint()
        if self._arrastre == "mover":
            self.app.panel.arrastre_mover(self, e.globalPosition().toPoint(), self._agarre)
        elif self._arrastre == "tam":
            self.app.panel.arrastre_tam(self, e.globalPosition().toPoint())
        else:
            self.setCursor(Qt.SizeFDiagCursor if self.en_asa(pos) else Qt.SizeAllCursor)

    def mouseReleaseEvent(self, e):
        if self._arrastre == "mover":
            self.app.panel.soltar_mover(self, e.globalPosition().toPoint())
        elif self._arrastre == "tam":
            self.app.panel.soltar_tam(self)
        self._arrastre = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.en_edicion():
            self._agarre = e.position().toPoint()
            self._arrastre = "tam" if self.en_asa(self._agarre) else "mover"
        elif e.button() == Qt.LeftButton and self.ventana:
            if self.app.modo == "widgets":
                # Ya no se recolocan solos (tampoco al reiniciar) hasta "Recolocar widgets".
                self.app.manual = True
                self.app.config["manual"] = True
            self.ventana.windowHandle().startSystemMove()
        elif e.button() == Qt.RightButton:
            self.app.menu_tarjeta(self).popup(e.globalPosition().toPoint())


def poner_encima(ventana):
    """Mantiene la ventana por encima de las demás (p. ej. sobre un juego en ventana).

    En Windows se hace con la API directamente: la librería del acrílico rehace los
    flags de Qt. En otros sistemas basta el flag de Qt, puesto al crear la ventana.
    """
    if sys.platform == "win32":
        HWND_TOPMOST = -1
        SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
        ctypes.windll.user32.SetWindowPos(
            ctypes.c_void_p(int(ventana.winId())), ctypes.c_void_p(HWND_TOPMOST),
            0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)


class VentanaWidget(BaseVentana):
    """Ventana de cristal suelta en el escritorio que aloja una Tarjeta."""

    # Valores para los eventos que lanza la librería del acrílico durante __init__.
    app = None
    tarjeta = None
    encima = False
    acrilico_activo = False

    def __init__(self, tarjeta, app, encima=False):
        super().__init__()
        self.app = app
        self.tarjeta = tarjeta
        self.encima = encima
        self.setWindowTitle(f"MoonDeck · {tarjeta.titulo}")
        if USA_ACRILICO:
            self.titleBar.hide()
            self.setResizeEnabled(False)
            ajustes_ventana_windows(int(self.winId()))
        else:
            encima_flag = Qt.WindowStaysOnTopHint if encima else Qt.WindowType(0)
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | encima_flag)
            self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("VentanaWidget { background: transparent; }")
        self.setFixedWidth(ANCHO)
        caja = QVBoxLayout(self)
        caja.setContentsMargins(0, 0, 0, 0)
        tarjeta.setMinimumWidth(0)
        tarjeta.setMaximumWidth(QWIDGETSIZE_MAX)
        tarjeta.relleno = "ninguno" if USA_ACRILICO else "oscuro"
        tarjeta.ajustar_margenes()
        caja.addWidget(tarjeta)
        tarjeta.ventana = self
        tarjeta.show()
        self.aplicar_tinte()
        self.resize(ANCHO, tarjeta.alto_natural(ANCHO))

        self._guardar = QTimer(self, singleShot=True, interval=600)
        self._guardar.timeout.connect(app.guardar_config)

    def aplicar_tinte(self):
        """Acrílico con el color y la opacidad del tema (o sin cristal, si se desactiva)."""
        if not USA_ACRILICO or not self.app:
            return
        p = self.app.tema["widgets"]
        if p["cristal"]:
            # Con degradado, el color lo pinta Qt encima: el acrílico solo un poco de tinte.
            alfa = 0x18 if p["degradado"] else round(p["opacidad"] * 255 * self.tarjeta.opacidad)
            self.windowEffect.setAcrylicEffect(self.winId(), f"{p['fondo'].lstrip('#').upper()}{alfa:02X}")
            self.acrilico_activo = True
        else:
            try:
                self.windowEffect.removeBackgroundEffect(self.winId())
            except Exception:  # noqa: BLE001 - versiones de la librería sin esa función
                pass
            self.acrilico_activo = False

    def showEvent(self, e):
        super().showEvent(e)
        if self.encima:
            poner_encima(self)

    def soltar(self):
        """Devuelve la tarjeta (para llevarla al panel) y cierra la ventana."""
        t = self.tarjeta
        self.layout().removeWidget(t)
        t.ventana = None
        t.setParent(None)
        self.tarjeta = None
        self.hide()
        self.deleteLater()
        return t

    def moveEvent(self, e):
        super().moveEvent(e)
        # La librería del acrílico puede mover la ventana durante su __init__,
        # antes de que existan self.app y self._guardar.
        app = getattr(self, "app", None)
        if app and app.colocado and hasattr(self, "_guardar"):
            self._guardar.start()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Q and e.modifiers() & Qt.ControlModifier:
            self.app.salir()


# Disposición por defecto del modo panel: (fila, columna, alto, ancho) en una cuadrícula
# de PANEL_COLUMNAS columnas. "gpu1"/"gpu2" son la primera y la segunda GPU que haya.
PANEL_COLUMNAS = 11
PANEL_POR_DEFECTO = {
    "cpu": (0, 0, 3, 2), "gpu1": (0, 2, 2, 3), "memoria": (0, 5, 2, 2), "discos": (0, 7, 2, 2),
    "gpu2": (0, 9, 2, 2), "multimedia": (2, 2, 2, 3), "reloj": (2, 5, 2, 2), "discord": (2, 7, 2, 2),
    "red": (2, 9, 2, 2), "calendario": (3, 0, 2, 2), "audio": (4, 2, 2, 2), "temperaturas": (4, 4, 2, 4),
    "velocidad": (4, 8, 2, 2), "tiempo": (4, 10, 2, 1), "fps": (5, 0, 1, 2),
}


def empaquetar(items, columnas):
    """Coloca (clave, ancho, alto) en orden en la primera posición libre de la cuadrícula.

    Devuelve ({clave: (fila, col, alto, ancho)}, filas usadas). Rellena huecos, así
    que cambiar el tamaño o el orden de un widget nunca deja agujeros.
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


class BarraEdicion(QWidget):
    """Barra flotante del modo "Editar disposición": columnas, filas, restablecer, listo."""

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.setStyleSheet(css_tema(panel.app.tema) + "QToolButton { font-size: 11pt; padding: 3px 9px; }")
        fila = QHBoxLayout(self)
        fila.setContentsMargins(14, 6, 8, 6)
        fila.setSpacing(4)

        def boton(texto, fn):
            b = QToolButton()
            b.setText(texto)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            fila.addWidget(b)
            return b

        fila.addWidget(etiqueta("Columnas", "sub"))
        boton("−", lambda: panel.cambiar_columnas(-1))
        self.columnas = etiqueta("", "sub")
        fila.addWidget(self.columnas)
        boton("+", lambda: panel.cambiar_columnas(1))
        fila.addSpacing(14)
        fila.addWidget(etiqueta("Filas", "sub"))
        boton("−", lambda: panel.cambiar_filas(-1))
        self.filas = etiqueta("", "sub")
        fila.addWidget(self.filas)
        boton("+", lambda: panel.cambiar_filas(1))
        fila.addSpacing(14)
        fila.addWidget(etiqueta("Arrastra un widget a cualquier celda · su esquina ◢ cambia el tamaño", "dim"))
        fila.addSpacing(10)
        boton(_("Restablecer"), panel.restablecer)
        listo = boton(_("Listo"), lambda: panel.set_edicion(False))
        listo.setStyleSheet(f"background: {COLORES['azul'].name()}; color: white; font-weight: 600;")
        self.listo = listo

    def actualizar(self):
        g = self.panel.config_grid()
        self.columnas.setText(str(self.panel.cols))
        self.filas.setText(str(g["filas"]) if g["filas"] else _("auto ({n})").format(n=self.panel.filas))
        self.adjustSize()
        self.move((self.panel.width() - self.width()) // 2, 14)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        fondo = QColor(self.panel.app.tema["widgets"]["fondo"])
        fondo.setAlpha(240)
        p.setBrush(fondo)
        p.setPen(QPen(tenue(40), 1))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)


def acrilico_windows(ventana, rgba):
    """Cristal acrílico de Windows 10/11 aplicado directamente a una ventana sin marco.

    El panel no usa la librería del acrílico: con Qt reciente esta deja que Qt crea
    que la ventana tiene marco y, a pantalla completa, sobra una franja sin pintar.
    """
    if sys.platform != "win32":
        return False

    class Acento(ctypes.Structure):
        _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                    ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]

    class DatosComposicion(ctypes.Structure):
        _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p), ("SizeOfData", ctypes.c_size_t)]

    ACCENT_DISABLED, ACCENT_ENABLE_ACRYLICBLURBEHIND, WCA_ACCENT_POLICY = 0, 4, 19
    if rgba:
        r, g, b, a = bytes.fromhex(rgba)
        acento = Acento(ACCENT_ENABLE_ACRYLICBLURBEHIND, 0, (a << 24) | (b << 16) | (g << 8) | r, 0)  # color en ABGR
    else:  # quitar el cristal
        acento = Acento(ACCENT_DISABLED, 0, 0, 0)
    datos = DatosComposicion(WCA_ACCENT_POLICY, ctypes.cast(ctypes.pointer(acento), ctypes.c_void_p),
                             ctypes.sizeof(acento))
    try:
        return bool(ctypes.windll.user32.SetWindowCompositionAttribute(
            ctypes.c_void_p(int(ventana.winId())), ctypes.byref(datos))) and bool(rgba)
    except (OSError, AttributeError):
        return False


class VentanaPanel(QWidget):
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

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.tarjetas = []
        self.celdas = {}      # clave -> (fila, col, alto, ancho)
        self.cols = 1
        self.filas = 1
        self.editando = False
        self.previa = None    # (fila, col, alto, ancho) donde caería el widget arrastrado
        self.setWindowTitle("MoonDeck")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.cristal = False
        self.aplicar_cristal()
        self.barra = BarraEdicion(self)
        self.barra.hide()

    def aplicar_cristal(self):
        p = self.app.tema["panel"]
        quiere = EFECTO == "acrilico" and p["cristal"]
        self.cristal = acrilico_windows(self, f"{p['panel_fondo'].lstrip('#').upper()}40" if quiere else None)
        self.update()

    def colocar_en(self, pantalla):
        self.setGeometry(pantalla.geometry())

    # --- modelo de la cuadrícula ----------------------------------------------

    def repartir(self, tarjetas):
        self.tarjetas = tarjetas
        for t in tarjetas:
            t.setParent(self)
            t.setMinimumWidth(0)
            t.setMaximumWidth(QWIDGETSIZE_MAX)
            t.relleno = "claro"
            t.ajustar_margenes()
            t.contenido.setAttribute(Qt.WA_TransparentForMouseEvents, self.editando)
            t.show()
        self.barra.raise_()
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
        if self.app.config.get("panel_predeterminado"):  # la que se guardó en Configuración
            return json.loads(json.dumps(self.app.config["panel_predeterminado"]))
        # La disposición de serie; lo que no esté en ella (una tercera GPU...) va a un hueco libre.
        gpus = [t.clave for t in self.app.tarjetas if t.clave.startswith("gpu-")]
        nombres = {f"gpu{i}": clave for i, clave in enumerate(gpus, 1)}
        pos = {nombres.get(k, k): list(v) for k, v in PANEL_POR_DEFECTO.items()}
        if any(t.clave in pos for t in self.tarjetas):
            return {"columnas": PANEL_COLUMNAS, "filas": 0, "pos": pos}
        ancho = self.width() - 2 * self.MARGEN
        alto = self.height() - 2 * self.MARGEN
        # Se aceptan tarjetas algo más estrechas que en modo widgets si así cabe todo.
        max_cols = max(1, min(n, (ancho + self.HUECO) // (self.ANCHO_MIN + self.HUECO)))
        for cols in range(1, max_cols + 1):
            base, resto = divmod(n, -(-n // cols))
            tamanos = [base + 1] * resto + [base] * (-(-n // cols) - resto)
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

    def recalcular(self):
        g = self.config_grid()
        self.cols = max(1, min(g["columnas"], self.MAX_COLUMNAS))
        guardadas = g["pos"]
        # Los que no tienen sitio guardado (una GPU nueva, un widget que se vuelve a
        # mostrar) van al final, al primer hueco libre.
        pos = {t.clave: tuple(guardadas[t.clave]) if t.clave in guardadas else None for t in self.tarjetas}
        self.celdas = self.normalizar(pos)
        usadas = max((f + h for f, _, h, _ in self.celdas.values()), default=1)
        self.filas = max(usadas, g["filas"] or 0, 1)
        self.colocar_tarjetas()

    def guardar_posiciones(self, pos):
        g = self.grid_editable()
        g["pos"].update({c: list(v) for c, v in pos.items()})  # se conservan las de los sacados del panel
        self.recalcular()
        self.app.guardar_config()

    def area(self):
        arriba = self.MARGEN_EDICION if self.editando else self.MARGEN
        return QRectF(self.MARGEN, arriba, self.width() - 2 * self.MARGEN,
                      self.height() - arriba - self.MARGEN)

    def tam_celda(self):
        a = self.area()
        return ((a.width() - self.HUECO * (self.cols - 1)) / self.cols,
                (a.height() - self.HUECO * (self.filas - 1)) / self.filas)

    def rect_celda(self, fila, col, alto=1, ancho=1):
        a = self.area()
        cw, ch = self.tam_celda()
        return QRectF(a.x() + col * (cw + self.HUECO), a.y() + fila * (ch + self.HUECO),
                      ancho * cw + (ancho - 1) * self.HUECO, alto * ch + (alto - 1) * self.HUECO).toRect()

    def colocar_tarjetas(self):
        for t in self.tarjetas:
            if t.clave in self.celdas:
                t.setGeometry(self.rect_celda(*self.celdas[t.clave]))
        if self.editando:
            self.barra.actualizar()
        self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.colocar_tarjetas()

    # --- edición -------------------------------------------------------------

    def set_edicion(self, activo):
        self.editando = activo
        for t in self.tarjetas:
            # En edición, los clics van a la tarjeta (para arrastrarla), no a sus botones.
            t.contenido.setAttribute(Qt.WA_TransparentForMouseEvents, activo)
            t.setCursor(Qt.SizeAllCursor if activo else Qt.ArrowCursor)
            t.update()
        self.barra.setVisible(activo)
        self.barra.raise_()
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
        # Por debajo de las filas ocupadas, vuelve a automático.
        g["filas"] = 0 if filas < usadas else filas
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

    def celda_en(self, punto):
        """Celda (fila, col) más cercana a un punto del panel."""
        a = self.area()
        cw, ch = self.tam_celda()
        return (max(0, round((punto.y() - a.y()) / (ch + self.HUECO))),
                max(0, round((punto.x() - a.x()) / (cw + self.HUECO))))

    # Arrastrar para mover: la tarjeta sigue al ratón y se ve dónde caerá.
    def arrastre_mover(self, tarjeta, pos_global, agarre):
        esquina = self.mapFromGlobal(pos_global) - agarre
        tarjeta.move(esquina)
        tarjeta.raise_()
        _, _, h, w = self.celdas[tarjeta.clave]
        fila, col = self.celda_en(esquina)
        self.previa = (min(fila, self.filas - 1), min(col, self.cols - w), h, w)
        self.update()

    def soltar_mover(self, tarjeta, _pos_global):
        if self.previa:
            origen = self.celdas[tarjeta.clave]
            pos = dict(self.celdas)
            pos[tarjeta.clave] = self.previa
            self.previa = None
            # El que estorbe se va al sitio que deja el arrastrado (como un intercambio).
            self.guardar_posiciones(self.normalizar(pos, primero=tarjeta.clave, hueco=origen[:2]))
        else:
            self.colocar_tarjetas()

    # Arrastrar la esquina: vista previa del nuevo tamaño, en celdas.
    def arrastre_tam(self, tarjeta, pos_global):
        fila, col, _, _ = self.celdas[tarjeta.clave]
        origen = self.rect_celda(fila, col)
        p = self.mapFromGlobal(pos_global)
        cw, ch = self.tam_celda()
        ancho = max(1, min(round((p.x() - origen.x()) / (cw + self.HUECO)), self.cols - col))
        alto = max(1, min(round((p.y() - origen.y()) / (ch + self.HUECO)), self.MAX_ALTO))
        self.previa = (fila, col, alto, ancho)
        self.update()

    def soltar_tam(self, tarjeta):
        if self.previa:
            _, _, alto, ancho = self.previa
            self.previa = None
            self.cambiar_tam(tarjeta, ancho, alto)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # El fondo del tema (color, opacidad, imagen) encima del cristal.
        pintar_fondo(p, self.app.tema["panel"], QRectF(self.rect()), 1.0, "panel_")
        if self.editando:
            # Celdas de la cuadrícula (se ven en los huecos y al mover un widget).
            p.setPen(QPen(tenue(45), 1, Qt.DashLine))
            p.setBrush(tenue(8))
            for f in range(self.filas):
                for c in range(self.cols):
                    p.drawRoundedRect(QRectF(self.rect_celda(f, c)).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        if self.previa:
            p.setPen(QPen(acento(220), 2))
            p.setBrush(acento(50))
            p.drawRoundedRect(QRectF(self.rect_celda(*self.previa)).adjusted(1, 1, -1, -1), 10, 10)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Q and e.modifiers() & Qt.ControlModifier:
            self.app.salir()
        elif e.key() == Qt.Key_Escape and self.editando:
            self.set_edicion(False)

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            menu = QMenu()
            self.app.acciones_comunes(menu, self)
            self._menu = menu
            menu.popup(e.globalPosition().toPoint())


# ---------------------------------------------------------------------------
# Aplicación
# ---------------------------------------------------------------------------

class Puente(QObject):
    datos = Signal(dict)


# ---------------------------------------------------------------------------
# Tiempo
# ---------------------------------------------------------------------------

def _nube(p, cx, cy, r, color):
    """Nube hecha de círculos, centrada en (cx, cy) con "radio" r."""
    ruta = QPainterPath()
    ruta.addEllipse(QPointF(cx - r * 0.55, cy + r * 0.1), r * 0.5, r * 0.5)
    ruta.addEllipse(QPointF(cx + r * 0.05, cy - r * 0.2), r * 0.65, r * 0.65)
    ruta.addEllipse(QPointF(cx + r * 0.65, cy + r * 0.15), r * 0.45, r * 0.45)
    ruta.addRoundedRect(QRectF(cx - r * 1.05, cy + r * 0.1, r * 2.15, r * 0.5), r * 0.25, r * 0.25)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPath(ruta.simplified())


def _sol(p, cx, cy, r):
    p.setPen(QPen(QColor("#ffb52e"), max(1.2, r * 0.18), Qt.SolidLine, Qt.RoundCap))
    for i in range(8):
        a = math.radians(i * 45)
        p.drawLine(QPointF(cx + math.cos(a) * r * 1.25, cy + math.sin(a) * r * 1.25),
                   QPointF(cx + math.cos(a) * r * 1.65, cy + math.sin(a) * r * 1.65))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#ffc93c"))
    p.drawEllipse(QPointF(cx, cy), r, r)


def _luna(p, cx, cy, r):
    ruta = QPainterPath()
    ruta.addEllipse(QPointF(cx, cy), r, r)
    hueco = QPainterPath()
    hueco.addEllipse(QPointF(cx + r * 0.55, cy - r * 0.35), r * 0.85, r * 0.85)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#d9def0"))
    p.drawPath(ruta.subtracted(hueco))


def pintar_icono_tiempo(p, nombre, x, y, tam):
    """Iconos del tiempo dibujados (Windows no trae los del tema de Linux)."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    cx, cy, r = x + tam / 2, y + tam / 2, tam / 2
    noche = nombre.endswith("-night")
    base = nombre.replace("-night", "")
    claro, oscuro = QColor("#e3e8f0"), QColor("#9aa5b5")
    if base == "weather-clear":
        (_luna if noche else _sol)(p, cx, cy, r * 0.5)
    elif base == "weather-few-clouds":
        (_luna if noche else _sol)(p, cx - r * 0.25, cy - r * 0.25, r * 0.38)
        _nube(p, cx + r * 0.12, cy + r * 0.15, r * 0.55, claro)
    elif base in ("weather-overcast", "weather-fog"):
        _nube(p, cx, cy - r * 0.05, r * 0.62, oscuro if base == "weather-fog" else claro)
        if base == "weather-fog":
            p.setPen(QPen(QColor("#c8ced8"), max(1.5, r * 0.12), Qt.SolidLine, Qt.RoundCap))
            for i, dy in enumerate((0.55, 0.8)):
                p.drawLine(QPointF(cx - r * 0.7 + i * r * 0.2, cy + r * dy), QPointF(cx + r * 0.7, cy + r * dy))
    else:  # lluvia, nieve y tormenta: nube y lo que cae
        if base == "weather-showers-scattered":
            _sol(p, cx - r * 0.3, cy - r * 0.35, r * 0.3)
        _nube(p, cx, cy - r * 0.2, r * 0.6, oscuro if base == "weather-storm" else claro)
        if base == "weather-snow":
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("white"))
            for dx, dy in ((-0.4, 0.55), (0.05, 0.75), (0.45, 0.55)):
                p.drawEllipse(QPointF(cx + r * dx, cy + r * dy), r * 0.1, r * 0.1)
        elif base == "weather-storm":
            rayo = QPainterPath(QPointF(cx + r * 0.05, cy + r * 0.25))
            for dx, dy in ((-0.25, 0.65), (0.0, 0.62), (-0.15, 0.95), (0.25, 0.5), (0.02, 0.53), (0.18, 0.25)):
                rayo.lineTo(cx + r * dx, cy + r * dy)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#ffd23c"))
            p.drawPath(rayo)
        else:
            p.setPen(QPen(QColor("#5aa9ff"), max(1.4, r * 0.11), Qt.SolidLine, Qt.RoundCap))
            gotas = ((-0.35, 0.5), (0.05, 0.55), (0.45, 0.5)) if base == "weather-showers" else ((-0.15, 0.5), (0.3, 0.5))
            for dx, dy in gotas:
                p.drawLine(QPointF(cx + r * dx, cy + r * dy), QPointF(cx + r * (dx - 0.1), cy + r * (dy + 0.3)))
    p.restore()


class IconoTiempo(QWidget):
    def __init__(self, tam=56):
        super().__init__()
        self.tam = tam
        self.nombre = None
        self.setFixedSize(tam, tam)

    def poner(self, nombre):
        if nombre != self.nombre:
            self.nombre = nombre
            self.update()

    def paintEvent(self, _e):
        if self.nombre:
            pintar_icono_tiempo(QPainter(self), self.nombre, 0, 0, self.tam)


class CabeceraTiempo(QWidget):
    """Icono grande + grados; en una celda estrecha del panel se queda sin icono."""

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "icono"):
            self.icono.setVisible(self.width() >= 220 and bool(self.icono.nombre))




class PronosticoHoras(QWidget):
    """Las próximas horas: tantas como quepan a lo ancho."""

    COLUMNA = 50

    def __init__(self):
        super().__init__()
        self.horas = []
        self.setFixedHeight(78)

    def poner(self, horas):
        self.horas = horas
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        n = max(1, min(len(self.horas), w // self.COLUMNA))
        ancho = w / n
        pequena, negrita, mini = QFont(self.font()), QFont(self.font()), QFont(self.font())
        pequena.setPixelSize(round(11 * ESCALA))
        negrita.setPixelSize(round(13 * ESCALA))
        negrita.setBold(True)
        mini.setPixelSize(round(10 * ESCALA))
        for i, h in enumerate(self.horas[:n]):
            x = i * ancho
            p.setFont(pequena)
            p.setPen(QColor(C_SEC))
            p.drawText(QRectF(x, 0, ancho, 16), Qt.AlignCenter, f"{h['hora']}h")
            pintar_icono_tiempo(p, describir(h["codigo"], h["dia"])[1], x + (ancho - 26) / 2, 18, 26)
            p.setFont(negrita)
            p.setPen(QColor(C_TEXTO))
            p.drawText(QRectF(x, 46, ancho, 16), Qt.AlignCenter, f"{h['temp']:.0f}°")
            if h["lluvia"]:
                p.setFont(mini)
                p.setPen(acento())
                p.drawText(QRectF(x, 62, ancho, 14), Qt.AlignCenter, f"{h['lluvia']:.0f} %")


class PronosticoDias(QWidget):
    """Los próximos días: icono, lluvia y una barra de mínima a máxima."""

    FILA = 26

    def __init__(self):
        super().__init__()
        self.dias = []
        # Sin "alto para el ancho": Qt no deja bajar de ese alto, y en una celda pequeña
        # tiene que poder encoger (enseña menos días).
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def poner(self, dias):
        cambia = len(dias) != len(self.dias)
        self.dias = dias
        if cambia:
            self.updateGeometry()
        self.update()

    def sizeHint(self):
        return QSize(ANCHO - 32, self.FILA * max(2, len(self.dias)))

    def minimumSizeHint(self):
        return QSize(100, self.FILA * 2)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        dias = self.dias[:max(1, h // self.FILA)]
        if not dias:
            return
        minimo, maximo = min(d["min"] for d in dias), max(d["max"] for d in dias)
        hoy = datetime.date.today()
        estrecho = w < 230
        normal, negrita, mini = QFont(self.font()), QFont(self.font()), QFont(self.font())
        normal.setPixelSize(round(12.5 * ESCALA))
        negrita.setPixelSize(round(12.5 * ESCALA))
        negrita.setBold(True)
        mini.setPixelSize(round(10.5 * ESCALA))
        nombres = [_("Hoy") if datetime.date.fromisoformat(d["fecha"]) == hoy
                   else idioma.dia_corto(datetime.date.fromisoformat(d["fecha"]).weekday()) for d in dias]
        # La columna del día, tan ancha como el nombre más largo ("Hoy", "Сегодня"…).
        col = max(40, max(QFontMetricsF(negrita).horizontalAdvance(n) for n in nombres) + 6)
        for i, d in enumerate(dias):
            y = i * self.FILA
            fila = QRectF(0, y, w, self.FILA)
            fecha = datetime.date.fromisoformat(d["fecha"])
            p.setFont(negrita if fecha == hoy else normal)
            p.setPen(QColor(C_NORMAL))
            p.drawText(QRectF(0, y, col, self.FILA), Qt.AlignLeft | Qt.AlignVCenter, nombres[i])
            pintar_icono_tiempo(p, describir(d["codigo"])[1], col, y + (self.FILA - 20) / 2, 20)
            x = col + 26
            if d["lluvia"] and not estrecho:
                p.setFont(mini)
                p.setPen(acento())
                p.drawText(QRectF(x, y, 40, self.FILA), Qt.AlignLeft | Qt.AlignVCenter, f"{d['lluvia']:.0f} %")
            if estrecho:
                p.setFont(negrita)
                p.setPen(QColor(C_TEXTO))
                p.drawText(fila, Qt.AlignRight | Qt.AlignVCenter, f"{d['max']:.0f}°")
                p.setFont(normal)
                p.setPen(QColor(C_SEC))
                p.drawText(fila.adjusted(0, 0, -34, 0), Qt.AlignRight | Qt.AlignVCenter, f"{d['min']:.0f}°")
                continue
            x += 40
            p.setFont(normal)
            p.setPen(QColor(C_SEC))
            p.drawText(QRectF(x, y, 30, self.FILA), Qt.AlignRight | Qt.AlignVCenter, f"{d['min']:.0f}°")
            p.setFont(negrita)
            p.setPen(QColor(C_TEXTO))
            p.drawText(QRectF(w - 30, y, 30, self.FILA), Qt.AlignRight | Qt.AlignVCenter, f"{d['max']:.0f}°")
            # Barra: todo el rango de la semana, y en color el de ese día.
            bx = x + 38
            bw = max(10, w - 30 - 8 - bx)
            by = y + self.FILA / 2 - 2
            p.setPen(Qt.NoPen)
            p.setBrush(tenue(26))
            p.drawRoundedRect(QRectF(bx, by, bw, 4), 2, 2)
            rango = max(maximo - minimo, 1)
            x1 = bx + bw * (d["min"] - minimo) / rango
            x2 = bx + bw * (d["max"] - minimo) / rango
            deg = QLinearGradient(bx, 0, bx + bw, 0)
            deg.setColorAt(0, acento())
            deg.setColorAt(0.5, COLORES["amarillo"])
            deg.setColorAt(1, COLORES["naranja"])
            p.setBrush(deg)
            p.drawRoundedRect(QRectF(x1, by, max(x2 - x1, 4), 4), 2, 2)


class VistaApps(QWidget):
    """Lanzador: los iconos de las apps que elige el usuario; un clic las abre. Con el clic
    derecho sobre un icono, el menú de la tarjeta trae quitarlo o moverlo."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.encima = None        # icono bajo el ratón
        self.menu_indice = None   # icono sobre el que se abrió el menú
        self._iconos = {}         # (id, color, escala) -> QPixmap
        self._alto = None
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(lanzador.TAM)

    def apps(self):
        return self.app.config.setdefault("apps", [])

    def cambiado(self):
        self.app.guardar_config()
        self._ajustar()
        self.update()

    def _ajustar(self):
        _pos, alto = lanzador.rejilla(len(self.apps()), self.width())
        alto = max(lanzador.TAM, alto)
        if alto != self._alto:
            self._alto = alto
            self.setFixedHeight(alto)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._ajustar()

    def _indice(self, pos):
        rejilla, _alto = lanzador.rejilla(len(self.apps()), self.width())
        return next((i for i, (ix, iy) in enumerate(rejilla)
                     if ix <= pos.x() < ix + lanzador.TAM and iy <= pos.y() < iy + lanzador.TAM), None)

    def _poner_encima(self, i):
        if i != self.encima:
            self.encima = i
            self.setCursor(Qt.PointingHandCursor if i is not None else Qt.ArrowCursor)
            self.update()

    def mouseMoveEvent(self, e):
        self._poner_encima(self._indice(e.position()))
        e.ignore()

    def leaveEvent(self, e):
        self._poner_encima(None)

    def _tarjeta(self):
        w = self.parentWidget()
        while w and not isinstance(w, Tarjeta):
            w = w.parentWidget()
        return w

    def mousePressEvent(self, e):
        tarjeta = self._tarjeta()
        i = self._indice(e.position())
        if tarjeta and tarjeta.en_edicion():
            e.ignore()
        elif e.button() == Qt.RightButton:
            self.menu_indice = i
            e.ignore()  # el menú de la tarjeta
        elif e.button() == Qt.LeftButton and i is not None:
            self.abrir(self.apps()[i])
        else:
            e.ignore()

    def abrir(self, a):
        try:
            os.startfile(a["id"])
        except OSError as e:
            print("No se pudo abrir", a["id"], e, file=sys.stderr)

    def _icono(self, a, color):
        escala = self.devicePixelRatioF()
        clave = (a["id"], color, escala)
        if clave not in self._iconos:
            lado = round(lanzador.TAM * escala)
            pm = QFileIconProvider().icon(QFileInfo(a["id"])).pixmap(lado, lado)
            if not pm.isNull() and (pm.width() != lado or pm.height() != lado):
                pm = pm.scaled(lado, lado, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if not pm.isNull() and color:
                img = pm.toImage().convertToFormat(QImage.Format_RGBA8888)
                w, h, fila = img.width(), img.height(), img.bytesPerLine()
                crudo = bytes(img.constBits())
                rgba = b"".join(crudo[y * fila:y * fila + w * 4] for y in range(h))
                datos = lanzador.tenir_icono(rgba, color)
                pm = QPixmap.fromImage(QImage(datos, w, h, w * 4, QImage.Format_RGBA8888).copy())
            pm.setDevicePixelRatio(escala)
            self._iconos[clave] = None if pm.isNull() else pm
        return self._iconos[clave]

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        apps = self.apps()
        if not apps:
            p.setPen(QColor(C_SEC))
            f = QFont(self.font())
            f.setPixelSize(round(12 * ESCALA))
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter, _("Clic derecho > Añadir aplicación…"))
            return
        modo = self.app.config.get("apps_color", "original")
        color = {"acento": rgb(acento()), "texto": rgb(QColor(C_TEXTO))}.get(modo)
        rejilla, _alto = lanzador.rejilla(len(apps), self.width())
        t = lanzador.TAM
        for i, (a, (x, y)) in enumerate(zip(apps, rejilla)):
            if i == self.encima:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(*TENUE, 36))
                p.drawRoundedRect(QRectF(x - 3, y - 3, t + 6, t + 6), 9, 9)
            pm = self._icono(a, color)
            if pm:
                p.drawPixmap(QPointF(x, y), pm)


class SelectorApps(QDialog):
    """Elegir apps del menú Inicio (o cualquier .exe) para el lanzador."""

    def __init__(self, ya, padre=None):
        super().__init__(padre)
        self.setWindowTitle(_("Añadir aplicación"))
        self.setStyleSheet(SelectorSensores.ESTILO + "QListWidget { background: #20232b; color: #e6e9ef; "
                           "border: 1px solid #3a3f4b; border-radius: 6px; } QListWidget::item { padding: 4px; }")
        self.resize(440, 540)
        self.extra = []
        caja = QVBoxLayout(self)
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText(_("Buscar…"))
        self.buscar.textChanged.connect(self.filtrar)
        caja.addWidget(self.buscar)
        self.lista = QListWidget()
        self.lista.setSelectionMode(QListWidget.ExtendedSelection)
        self.lista.setIconSize(QSize(24, 24))
        self.lista.itemDoubleClicked.connect(lambda _i: self.accept())
        iconos = QFileIconProvider()
        for a in lanzador.apps_windows():
            if a["id"] in ya:
                continue
            item = QListWidgetItem(iconos.icon(QFileInfo(a["id"])), a["nombre"])
            item.setData(Qt.UserRole, a)
            self.lista.addItem(item)
        caja.addWidget(self.lista, 1)
        botones = QHBoxLayout()
        exe = QPushButton(_("Elegir un programa (.exe)…"))
        exe.clicked.connect(self.elegir_exe)
        botones.addWidget(exe)
        botones.addStretch(1)
        for texto, fn, principal in ((_("Cancelar"), self.reject, False), (_("Añadir"), self.accept, True)):
            b = QPushButton(texto)
            b.clicked.connect(fn)
            if principal:
                b.setProperty("estilo", "principal")
                b.setDefault(True)
            botones.addWidget(b)
        caja.addLayout(botones)

    def filtrar(self, texto):
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            item.setHidden(texto.lower() not in item.text().lower())

    def elegir_exe(self):
        ruta, _x = QFileDialog.getOpenFileName(self, _("Elegir un programa (.exe)…"), os.environ.get("ProgramFiles", ""),
                                               _("Programas (*.exe)"))
        if ruta:
            ruta = os.path.normpath(ruta)
            self.extra.append({"id": ruta, "nombre": os.path.splitext(os.path.basename(ruta))[0]})
            self.accept()

    def elegidas(self):
        return [i.data(Qt.UserRole) for i in self.lista.selectedItems()] + self.extra


class DialogoCiudad(QDialog):
    """Buscar y elegir la ciudad del widget del tiempo."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setWindowTitle(_("Ciudad del tiempo"))
        self.setStyleSheet(SelectorSensores.ESTILO + "QListWidget { background: #20232b; color: #e6e9ef; "
                           "border: 1px solid #3a3f4b; border-radius: 6px; } QListWidget::item { padding: 6px; }")
        self.resize(440, 380)
        self.elegida = None
        caja = QVBoxLayout(self)
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText(_("Escribe una ciudad y pulsa Enter"))
        self.buscar.returnPressed.connect(self.lanzar)
        caja.addWidget(self.buscar)
        self.estado = QLabel("")
        caja.addWidget(self.estado)
        self.lista = QListWidget()
        self.lista.itemActivated.connect(self.elegir)
        self.lista.itemClicked.connect(self.elegir)
        caja.addWidget(self.lista, 1)
        self.resultados = []
        self.puente = Puente()
        self.puente.datos.connect(self.mostrar)

    def lanzar(self):
        texto = self.buscar.text().strip()
        if not texto:
            return
        self.estado.setText(_("Buscando…"))

        def trabajo():
            try:
                self.puente.datos.emit({"r": buscar_ciudades(texto), "e": None})
            except (OSError, ValueError) as e:
                self.puente.datos.emit({"r": [], "e": str(e)})
        threading.Thread(target=trabajo, daemon=True).start()

    def mostrar(self, d):
        self.lista.clear()
        self.resultados = d["r"]
        self.estado.setText(_("Error: {error}").format(error=d["e"]) if d["e"] else
                            "" if d["r"] else _("No se ha encontrado ninguna ciudad con ese nombre."))
        for r in d["r"]:
            self.lista.addItem(f"{r['nombre']}   ·   {r['region']}")

    def elegir(self, item):
        self.elegida = self.resultados[self.lista.row(item)]
        self.accept()


# ---------------------------------------------------------------------------
# Discord: canal de voz
# ---------------------------------------------------------------------------

def pixmap_redondo(datos, tam, dpr):
    img = QPixmap()
    final = QPixmap(int(tam * dpr), int(tam * dpr))
    final.setDevicePixelRatio(dpr)
    final.fill(Qt.transparent)
    if not datos or not img.loadFromData(datos):
        return None
    p = QPainter(final)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    ruta = QPainterPath()
    ruta.addEllipse(QRectF(0, 0, tam, tam))
    p.setClipPath(ruta)
    img = img.scaled(int(tam * dpr), int(tam * dpr), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    img.setDevicePixelRatio(dpr)
    p.drawPixmap(QPointF(0, 0), img)
    p.end()
    return final


class Avatar(QWidget):
    """Avatar redondo; con un aro verde mientras la persona habla."""

    TAM = 26

    def __init__(self):
        super().__init__()
        self.setFixedSize(self.TAM + 4, self.TAM + 4)
        self.url = None
        self.pix = None
        self.hablando = False
        self.inicial = "?"

    def poner(self, url, datos, inicial):
        self.inicial = (inicial or "?")[:1].upper()
        if url != self.url or (datos and not self.pix):
            self.url = url
            self.pix = pixmap_redondo(datos, self.TAM, self.devicePixelRatioF())
            self.update()

    def set_hablando(self, si):
        if si != self.hablando:
            self.hablando = si
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.TAM / 2 + 2, self.TAM / 2 + 2)
        if self.pix:
            p.drawPixmap(QPointF(2, 2), self.pix)
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#5865f2"))  # azul de Discord
            p.drawEllipse(c, self.TAM / 2, self.TAM / 2)
            f = QFont(self.font())
            f.setPixelSize(12)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("white"))
            p.drawText(QRectF(2, 2, self.TAM, self.TAM), Qt.AlignCenter, self.inicial)
        if self.hablando:
            p.setPen(QPen(COLORES["verde"], 2.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, self.TAM / 2 + 0.8, self.TAM / 2 + 0.8)


class FilaDiscord(QWidget):
    """Una persona del canal: avatar, nombre, micro/cascos y su volumen (solo para mí)."""

    def __init__(self, discord, uid, soy_yo):
        super().__init__()
        self.discord = discord
        self.uid = uid
        self._mute = False
        self._pendiente = None
        self._actualizando = False
        self._enviar = QTimer(self, singleShot=True, interval=150)  # Discord limita las peticiones
        self._enviar.timeout.connect(lambda: self.discord.volumen_usuario(self.uid, self._pendiente))
        caja = QVBoxLayout(self)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(2)
        arriba = QHBoxLayout()
        arriba.setSpacing(8)
        self.avatar = Avatar()
        arriba.addWidget(self.avatar)
        self.nombre = etiqueta("", "sub")
        arriba.addWidget(self.nombre, 1)
        self.estado = etiqueta("", "sub")
        arriba.addWidget(self.estado)
        self.b_vol = None
        if not soy_yo:
            self.b_vol = boton_icono("volumen", 10)
            self.b_vol.setToolTip(_("Volumen de esta persona (solo para ti)"))
            self.b_vol.clicked.connect(lambda: self.abajo.setVisible(not self.abajo.isVisible()))
            arriba.addWidget(self.b_vol)
        caja.addLayout(arriba)
        if not soy_yo:
            self.abajo = QWidget()
            fila = QHBoxLayout(self.abajo)
            fila.setContentsMargins(34, 0, 0, 0)
            fila.setSpacing(6)
            self.slider = QSlider(Qt.Horizontal)
            self.slider.setRange(0, 200)
            self.slider.setCursor(Qt.PointingHandCursor)
            self.slider.valueChanged.connect(self._cambio)
            fila.addWidget(self.slider, 1)
            self.valor = etiqueta("", "dim")
            self.valor.setFixedWidth(40)
            self.valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            fila.addWidget(self.valor)
            self.b_mute = QPushButton(_("Silenciar"))
            self.b_mute.setCheckable(True)
            self.b_mute.setCursor(Qt.PointingHandCursor)
            self.b_mute.setToolTip(_("Silenciar a esta persona solo para ti"))
            self.b_mute.clicked.connect(lambda: self.discord.silenciar_usuario(self.uid, not self._mute))
            fila.addWidget(self.b_mute)
            self.abajo.hide()
            caja.addWidget(self.abajo)

    def _cambio(self, v):
        self.valor.setText(f"{v} %")
        if not self._actualizando:
            self._pendiente = v
            self._enviar.start()

    def actualizar(self, m, hablando, avatar):
        recortar(self.nombre, m["nombre"] + (_(" · bot") if m["bot"] else ""), ANCHO - 140)
        self.nombre.setStyleSheet(f"color: {COLORES['verde'].name()};" if hablando else "")
        self.avatar.poner(m["avatar"], avatar, m["nombre"])
        self.avatar.set_hablando(hablando)
        rojo = COLORES["rojo"].name()
        self.estado.setText(f'<span style="color:{rojo}">🎧 ✕</span>' if m["ensordecido"] else
                            f'<span style="color:{rojo}">🎙 ✕</span>' if m["micro_off"] else "")
        if self.b_vol:
            self._mute = m["silenciado_local"]
            self.b_mute.setChecked(self._mute)
            self.b_mute.setText(_("Activar") if self._mute else _("Silenciar"))
            poner_icono(self.b_vol, "silencio" if self._mute else "volumen", 10)
            if not self._enviar.isActive() and not self.slider.isSliderDown():
                self._actualizando = True
                self.slider.setValue(round(m["volumen"]))
                self._actualizando = False
                self.valor.setText(f"{round(m['volumen'])} %")


def guia_discord():
    """La guía paso a paso de Discord en GitHub (en español o en inglés)."""
    nombre = "DISCORD.md" if idioma.actual() == "es" else "DISCORD.en.md"
    return f"https://github.com/{REPO}/blob/main/docs/{nombre}"


class DialogoDiscord(QDialog):
    """Conectar con Discord paso a paso: pide el Client ID y el Client Secret."""

    def __init__(self, client_id, padre=None):
        super().__init__(padre)
        self.setWindowTitle(_("Conectar con Discord"))
        self.setStyleSheet(SelectorSensores.ESTILO)
        self.resize(580, 420)
        caja = QVBoxLayout(self)

        def texto(html, sub=False):
            lb = QLabel(html)
            lb.setWordWrap(True)
            if sub:
                lb.setStyleSheet("color: #8b94a4;")
            caja.addWidget(lb)

        texto(_("Discord solo deja controlar la voz a aplicaciones registradas. Crea la tuya "
                "(gratis, una sola vez, unos 3 minutos):"))
        if CLIENT_SECRET_POR_DEFECTO:
            texto(_("<b>¿Te han invitado como tester de la aplicación de MoonDeck?</b> Acepta la invitación, "
                    "deja el Client Secret vacío y pulsa Conectar."))
        pasos = (
            _("Abre <b>discord.com/developers</b> y pulsa <b>New Application</b> (el nombre da igual)."),
            _("En <b>OAuth2</b>, copia el <b>Client ID</b>; pulsa <b>Reset Secret</b> y copia el <b>Client Secret</b>."),
            _("En la misma página, en <b>Redirects</b>: <b>Add Redirect</b>, escribe <tt>http://localhost</tt> "
              "y pulsa <b>Save Changes</b>."),
            _("Pega aquí los dos datos y pulsa <b>Conectar</b>. Con Discord abierto, acepta <b>Autorizar</b>."),
        )
        for n, paso in enumerate(pasos, 1):
            texto(f"<b>{n}.</b>&nbsp; {paso}")
        enlaces = QHBoxLayout()
        for etiq, url in ((_("Abrir discord.com/developers"), "https://discord.com/developers/applications"),
                          (_("Ver la guía paso a paso"), guia_discord())):
            b = QPushButton(etiq)
            b.clicked.connect(lambda _x=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            enlaces.addWidget(b)
        enlaces.addStretch()
        caja.addLayout(enlaces)
        rejilla = QGridLayout()
        self.id = QLineEdit(client_id)
        self.id.setPlaceholderText(_("Un número largo, de OAuth2 > Client ID"))
        self.secreto = QLineEdit()
        self.secreto.setEchoMode(QLineEdit.Password)
        self.secreto.setPlaceholderText(_("Vacío = el de la aplicación de MoonDeck") if CLIENT_SECRET_POR_DEFECTO
                                        else _("De OAuth2 > Reset Secret"))
        for fila, (nombre, campo) in enumerate((("Client ID", self.id), ("Client Secret", self.secreto))):
            rejilla.addWidget(QLabel(nombre), fila, 0)
            rejilla.addWidget(campo, fila, 1)
        caja.addLayout(rejilla)
        texto(_("Se guardan solo en tu equipo."), sub=True)
        botones = QHBoxLayout()
        botones.addStretch()
        cancelar = QPushButton(_("Cancelar"))
        cancelar.clicked.connect(self.reject)
        ok = QPushButton(_("Conectar"))
        ok.setObjectName("aceptar")
        ok.clicked.connect(self.accept)
        botones.addWidget(cancelar)
        botones.addWidget(ok)
        caja.addLayout(botones)


# ---------------------------------------------------------------------------
# Ventana de configuración
# ---------------------------------------------------------------------------

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


class MuestraTema(QWidget):
    """Miniatura de un tema: fondo del panel, una tarjeta y el acento."""

    def __init__(self, tema):
        super().__init__()
        self.tema = temas.completo(tema)
        self.setFixedSize(130, 64)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _e):
        t = self.tema
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        ruta = QPainterPath()
        ruta.addRoundedRect(r, 8, 8)
        p.setClipPath(ruta)
        p.fillRect(r, QColor(90, 64, 102))  # algo detrás, como el fondo de pantalla
        pintar_fondo(p, t["panel"], r, 1.0, "panel_")
        w = dict(t["widgets"], imagen="")
        tarjeta = r.adjusted(10, 10, -10, -10)
        radio = min(w["radio"], 10)
        ruta = QPainterPath()
        ruta.addRoundedRect(tarjeta, radio, radio)
        p.save()
        p.setClipPath(ruta)
        pintar_fondo(p, w, tarjeta, 1.0)
        p.restore()
        borde = QColor(w["borde"])
        borde.setAlphaF(max(w["borde_opacidad"], 0.15))
        p.setPen(QPen(borde, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(tarjeta, radio, radio)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t["global"]["texto"]))
        p.drawRect(QRectF(20, 20, 40, 7))
        p.setBrush(QColor(t["global"]["texto_sec"]))
        p.drawRect(QRectF(20, 32, 60, 4))
        p.setBrush(QColor(t["global"]["acento"]))
        p.drawRoundedRect(QRectF(20, 42, r.width() - 40, 5), 2.5, 2.5)


class VentanaConfig(QWidget):
    """Temas, colores, fuentes, fondos, disposición por defecto y ajustes generales.
    Todo se aplica al momento."""

    PAGINAS = (("tema", "Tema"), ("ajustes", "Widgets"), ("widgets", "Tarjetas · modo widgets"),
               ("panel", "Tarjetas · modo panel"), ("fondo", "Fondo del panel"), ("disposicion", "Disposición"),
               ("general", "General"))
    ESTILO = SelectorSensores.ESTILO + """
    QWidget#raiz { background: #1b1e25; }
    QListWidget { background: #16181e; color: #d0d6e0; border: none; font-size: 10pt; outline: none; }
    QListWidget::item { padding: 10px 14px; }
    QListWidget::item:selected { background: #2c3445; color: white; }
    QScrollArea, QScrollArea > QWidget > QWidget { background: #1b1e25; border: none; }
    QLabel#grupo { color: #f2f4f8; font-weight: 600; font-size: 10.5pt; margin-top: 6px; }
    QLabel#ayuda, QLabel#sub { color: #8b94a4; }
    QFrame#caja { background: #20232b; border: 1px solid #2f343e; border-radius: 8px; }
    QCheckBox { color: #e6e9ef; }
    QSpinBox, QDoubleSpinBox, QFontComboBox { background: #262a33; color: #f2f4f8; border: 1px solid #3a3f4b;
        border-radius: 6px; padding: 4px 6px; }
    QSlider::groove:horizontal { height: 4px; background: #3a3f4b; border-radius: 2px; }
    QSlider::sub-page:horizontal { background: #4d8dff; border-radius: 2px; }
    QSlider::handle:horizontal { background: #f2f4f8; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
    QPushButton#tema { background: transparent; padding: 6px; }
    QPushButton#tema:hover { background: #2c313b; }
    """

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setObjectName("raiz")
        self.setWindowTitle(_("Configuración · MoonDeck"))
        self.setStyleSheet(self.ESTILO)
        self.resize(1000, 720)
        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(0)
        self.lista = QListWidget()
        self.lista.setFixedWidth(220)
        fila.addWidget(self.lista)
        self.pila = QStackedWidget()
        fila.addWidget(self.pila, 1)
        for _x, titulo in self.PAGINAS:
            self.lista.addItem(QListWidgetItem(_(titulo)))
        self.lista.currentRowChanged.connect(self.pila.setCurrentIndex)
        self.construir()
        self.lista.setCurrentRow(0)

    def construir(self):
        """(Re)hace todas las páginas con los valores actuales (p. ej. tras elegir un tema)."""
        actual = self.pila.currentIndex()
        while self.pila.count():
            w = self.pila.widget(0)
            self.pila.removeWidget(w)
            w.deleteLater()
        for clave, _ in self.PAGINAS:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cont = QWidget()
            caja = QVBoxLayout(cont)
            caja.setContentsMargins(22, 18, 22, 22)
            caja.setSpacing(8)
            getattr(self, f"pagina_{clave}")(caja)
            caja.addStretch()
            scroll.setWidget(cont)
            self.pila.addWidget(scroll)
        if actual >= 0:
            self.pila.setCurrentIndex(actual)

    # --- piezas -----------------------------------------------------------------

    def grupo(self, caja, titulo, texto=None):
        lb = QLabel(_(titulo))
        lb.setObjectName("grupo")
        caja.addWidget(lb)
        if texto:
            ayuda = QLabel(_(texto))
            ayuda.setObjectName("ayuda")
            ayuda.setWordWrap(True)
            caja.addWidget(ayuda)
        marco = QFrame()
        marco.setObjectName("caja")
        lista = QVBoxLayout(marco)
        lista.setContentsMargins(14, 6, 14, 6)
        lista.setSpacing(0)
        caja.addWidget(marco)
        return lista

    @staticmethod
    def fila(lista, titulo, control, subtitulo=None):
        fila = QHBoxLayout()
        fila.setContentsMargins(0, 8, 0, 8)
        textos = QVBoxLayout()
        textos.setSpacing(1)
        textos.addWidget(QLabel(_(titulo)))
        if subtitulo:
            sub = QLabel(_(subtitulo))
            sub.setObjectName("sub")
            sub.setWordWrap(True)
            textos.addWidget(sub)
        fila.addLayout(textos, 1)
        if isinstance(control, QWidget):
            fila.addWidget(control)
        else:
            fila.addLayout(control)
        lista.addLayout(fila)
        return control

    def cambiar(self, seccion, clave, valor):
        t = self.app.tema
        t[seccion][clave] = valor
        self.app.config["tema"] = t
        self.app.aplicar_tema()

    def color(self, seccion, clave):
        b = QPushButton()
        b.setFixedSize(44, 28)
        b.setCursor(Qt.PointingHandCursor)

        def pintar():
            b.setStyleSheet(f"background: {self.app.tema[seccion][clave]}; border: 1px solid #555; border-radius: 6px;")

        def elegir():
            c = QColorDialog.getColor(QColor(self.app.tema[seccion][clave]), self, _("Elegir color"))
            if c.isValid():
                self.cambiar(seccion, clave, c.name())
                pintar()
        pintar()
        b.clicked.connect(elegir)
        return b

    def deslizador(self, seccion, clave, minimo, maximo, factor=1.0, sufijo=" %"):
        """Deslizador para un número del tema; `factor` pasa del valor guardado al mostrado."""
        fila = QHBoxLayout()
        sl = QSlider(Qt.Horizontal)
        sl.setRange(minimo, maximo)
        sl.setFixedWidth(230)
        sl.setValue(round(self.app.tema[seccion][clave] * factor))
        valor = QLabel(f"{sl.value()}{sufijo}")
        valor.setFixedWidth(48)
        valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        def cambio(v):
            valor.setText(f"{v}{sufijo}")
            self.cambiar(seccion, clave, v / factor)
        sl.valueChanged.connect(cambio)
        fila.addWidget(sl)
        fila.addWidget(valor)
        return fila

    def interruptor(self, seccion, clave):
        c = QCheckBox()
        c.setChecked(bool(self.app.tema[seccion][clave]))
        c.toggled.connect(lambda v: self.cambiar(seccion, clave, v))
        return c

    def imagen(self, seccion, clave):
        fila = QHBoxLayout()
        nombre = QLabel(os.path.basename(self.app.tema[seccion][clave]) or _("(ninguna)"))
        nombre.setObjectName("sub")
        nombre.setFixedWidth(150)
        elegir = QPushButton(_("Elegir…"))
        quitar = QPushButton(_("Quitar"))

        def abrir():
            ruta, _x = QFileDialog.getOpenFileName(self, _("Elegir imagen"), os.path.expanduser("~"),
                                                  _("Imágenes (*.png *.jpg *.jpeg *.webp *.bmp *.gif)"))
            if ruta:
                self.cambiar(seccion, clave, ruta)
                nombre.setText(os.path.basename(ruta))
        elegir.clicked.connect(abrir)
        quitar.clicked.connect(lambda: (self.cambiar(seccion, clave, ""), nombre.setText(_("(ninguna)"))))
        for w in (nombre, elegir, quitar):
            fila.addWidget(w)
        return fila

    # --- páginas -------------------------------------------------------------------

    def pagina_tema(self, caja):
        lista = self.grupo(caja, "Temas de serie", "Un clic y se aplica a todo. Después puedes retocar lo que quieras.")
        rejilla = QGridLayout()
        rejilla.setSpacing(8)
        for i, (nombre, t) in enumerate(temas.PREDEFINIDOS.items()):
            b = QPushButton()
            b.setObjectName("tema")
            b.setCursor(Qt.PointingHandCursor)
            dentro = QVBoxLayout(b)
            dentro.setContentsMargins(6, 6, 6, 6)
            dentro.addWidget(MuestraTema(t), 0, Qt.AlignHCenter)
            lb = QLabel(_(nombre))
            lb.setAlignment(Qt.AlignCenter)
            lb.setAttribute(Qt.WA_TransparentForMouseEvents)
            dentro.addWidget(lb)
            b.setFixedSize(146, 104)
            b.clicked.connect(lambda _=False, t=t: self.elegir_tema(t))
            rejilla.addWidget(b, i // 4, i % 4)
        lista.addLayout(rejilla)

        g = "global"
        lista = self.grupo(caja, "Colores")
        self.fila(lista, "Color de acento", self.color(g, "acento"), "Barras, botones, el día de hoy, deslizadores…")
        self.fila(lista, "Texto principal", self.color(g, "texto"), "Cifras grandes, horas, nombres")
        self.fila(lista, "Texto secundario", self.color(g, "texto_sec"), "Detalles y leyendas")

        lista = self.grupo(caja, "Letra")
        fila = QHBoxLayout()
        fuente = QFontComboBox()
        if self.app.tema[g]["fuente"]:
            fuente.setCurrentFont(QFont(self.app.tema[g]["fuente"]))
        fuente.currentFontChanged.connect(lambda f: self.cambiar(g, "fuente", f.family()))
        sistema = QPushButton(_("La del sistema"))
        sistema.clicked.connect(lambda: (self.cambiar(g, "fuente", ""), self.construir()))
        fila.addWidget(fuente)
        fila.addWidget(sistema)
        self.fila(lista, "Fuente", fila)
        self.fila(lista, "Tamaño de letra", self.deslizador(g, "escala", 70, 150, 100))

        lista = self.grupo(caja, "Compartir el tema", "Guarda tu tema en un archivo para pasárselo a quien quieras, "
                                                      "o carga uno. Las imágenes de fondo van por su ruta: quien lo "
                                                      "cargue tiene que tener esas imágenes en su equipo.")
        fila = QHBoxLayout()
        for texto, fn in ((_("Exportar…"), self.exportar), (_("Importar…"), self.importar),
                          (_("Volver al tema de serie"), lambda: self.elegir_tema(temas.POR_DEFECTO))):
            b = QPushButton(texto)
            b.clicked.connect(lambda _=False, fn=fn: fn())
            fila.addWidget(b)
        self.fila(lista, "Archivo de tema", fila)

    def elegir_tema(self, t):
        nuevo = temas.completo(t)
        for clave in ("fuente", "escala"):  # la letra es cosa de cada uno: un tema no la cambia
            nuevo["global"][clave] = self.app.tema["global"][clave]
        self.app.config["tema"] = nuevo
        self.app.aplicar_tema()
        self.construir()

    def pagina_ajustes(self, caja):
        """Ajustes de cada widget: el tiempo, el calendario, el reloj y los títulos."""
        app = self.app
        lista = self.grupo(caja, "Tiempo")
        fila = QHBoxLayout()
        c = app.tiempo.ciudad
        lugar = QLabel(f"{c['nombre']}" + (f" · {c['region']}" if c.get("region") else ""))
        lugar.setObjectName("sub")
        cambiar = QPushButton(_("Cambiar…"))
        cambiar.clicked.connect(lambda: (app.elegir_ciudad(self), self.construir()))
        fila.addWidget(lugar)
        fila.addWidget(cambiar)
        self.fila(lista, "Ciudad", fila, "Busca tu ciudad para ver su tiempo")

        lista = self.grupo(caja, "Calendario")
        semana = QComboBox()
        for dia in (0, 6):
            semana.addItem(idioma.dia_semana(dia).capitalize(), dia)
        semana.setCurrentIndex(1 if app.primer_dia() == 6 else 0)
        semana.currentIndexChanged.connect(lambda i: app.cambiar_semana(semana.itemData(i)))
        self.fila(lista, "La semana empieza en", semana)

        lista = self.grupo(caja, "Reloj")
        o = app.config["reloj"]
        tipo = QComboBox()
        for clave, nombre in ESTILOS_RELOJ:
            tipo.addItem(_(nombre), clave)
        tipo.setCurrentIndex(max(0, tipo.findData(o["estilo"])))
        tipo.currentIndexChanged.connect(lambda i: app.cambiar_reloj(estilo=tipo.itemData(i)))
        self.fila(lista, "Tipo de reloj", tipo, "Las ciudades del reloj mundial, con clic derecho en el reloj")
        for texto, clave in (("Formato 24 horas", "h24"), ("Mostrar segundos", "segundos")):
            ch = QCheckBox()
            ch.setChecked(bool(o[clave]))
            ch.toggled.connect(lambda v, c=clave: app.cambiar_reloj(**{c: v}))
            self.fila(lista, texto, ch)

        lista = self.grupo(caja, "Test de velocidad")
        estilo = QComboBox()
        for clave, nombre in esferas.ESTILOS_VELOCIMETRO:
            estilo.addItem(_(nombre), clave)
        estilo.setCurrentIndex(max(0, estilo.findData(app.vel_reloj.estilo)))
        estilo.currentIndexChanged.connect(lambda i: app.cambiar_velocimetro(estilo.itemData(i)))
        self.fila(lista, "Estilo del velocímetro", estilo)

        lista = self.grupo(caja, "Discord")
        o = app.config["discord"]
        al_abrir = QComboBox()
        for clave, nombre in (("nada", "Solo mostrar los canales"), ("ultimo", "Entrar en el último canal"),
                              ("gente", "Entrar donde haya más gente")):
            al_abrir.addItem(_(nombre), clave)
        al_abrir.setCurrentIndex(max(0, al_abrir.findData(o["al_abrir"])))
        al_abrir.currentIndexChanged.connect(lambda i: app.cambiar_discord(al_abrir=al_abrir.itemData(i)))
        self.fila(lista, "Al abrir Discord desde el widget", al_abrir)
        servidores = app.discord.instantanea()["servidores"]
        lista = self.grupo(caja, "Tu servidor de Discord",
                           "Sus canales de voz salen en el widget cuando no estás en ninguno; pulsa uno para entrar.")
        if not servidores:
            self.fila(lista, "Abre Discord para ver tus servidores", QLabel())
        for g in servidores:
            ch = QCheckBox()
            ch.setChecked(g["id"] in o["servidores"])
            ch.toggled.connect(lambda v, i=g["id"]: app.cambiar_discord(
                servidores=[e for e in o["servidores"] if e != i] + ([i] if v else [])))
            self.fila(lista, g["nombre"], ch)

        lista = self.grupo(caja, "Aplicaciones", "Añade apps con el clic derecho en el widget de aplicaciones.")
        color = QComboBox()
        for clave, nombre in lanzador.COLORES_ICONOS:
            color.addItem(_(nombre), clave)
        color.setCurrentIndex(max(0, color.findData(app.config.get("apps_color", "original"))))
        color.currentIndexChanged.connect(lambda i: app.color_apps(color.itemData(i)))
        self.fila(lista, "Color de los iconos", color, "Los del tema se adaptan al cambiar de tema")

        lista = self.grupo(caja, "Títulos", "El nombre que sale arriba de cada widget (CPU, RELOJ…).")
        sin = app.config.get("sin_titulo", [])
        for t in app.tarjetas:
            ch = QCheckBox()
            ch.setChecked(t.clave not in sin)
            ch.toggled.connect(lambda v, t=t: app.alternar_titulo(t, v))
            self.fila(lista, t.nombre_menu, ch)

    def pagina_tarjetas(self, caja, s):
        lista = self.grupo(caja, "Fondo")
        self.fila(lista, "Color", self.color(s, "fondo"))
        self.fila(lista, "Opacidad", self.deslizador(s, "opacidad", 0, 100, 100), "0 % = solo cristal")
        self.fila(lista, "Degradado", self.interruptor(s, "degradado"), "Del color de fondo a un segundo color")
        self.fila(lista, "Segundo color", self.color(s, "fondo2"))
        self.fila(lista, "Dirección del degradado", self.deslizador(s, "angulo", 0, 360, 1, "°"))
        self.fila(lista, "Cristal acrílico", self.interruptor(s, "cristal"),
                  _("Desenfoca lo que hay detrás") + (_(" de las tarjetas") if s == "widgets" else _(" del panel")))
        lista = self.grupo(caja, "Imagen de fondo", "Se ve debajo del color: baja la opacidad del fondo para "
                                                    "que se vea más.")
        self.fila(lista, "Imagen", self.imagen(s, "imagen"))
        self.fila(lista, "Opacidad de la imagen", self.deslizador(s, "imagen_opacidad", 0, 100, 100))
        lista = self.grupo(caja, "Borde y esquinas")
        self.fila(lista, "Color del borde", self.color(s, "borde"))
        self.fila(lista, "Opacidad del borde", self.deslizador(s, "borde_opacidad", 0, 100, 100))
        self.fila(lista, "Grosor del borde", self.deslizador(s, "borde_grosor", 0, 4, 1, " px"))
        self.fila(lista, "Esquinas redondeadas", self.deslizador(s, "radio", 0, 30, 1, " px"),
                  "En los widgets sueltos, Windows redondea la ventana a su manera" if s == "widgets" else None)
        lista = self.grupo(caja, "Neón", "El borde se convierte en un tubo de luz de su color (sube la opacidad "
                                         "del borde para que brille más).")
        self.fila(lista, "Modo neón", self.interruptor(s, "neon"))
        self.fila(lista, "Parpadeo", self.interruptor(s, "parpadeo"), "De vez en cuando el neón falla, como un tubo viejo")

    def pagina_widgets(self, caja):
        self.pagina_tarjetas(caja, "widgets")

    def pagina_panel(self, caja):
        self.pagina_tarjetas(caja, "panel")

    def pagina_fondo(self, caja):
        s = "panel"
        lista = self.grupo(caja, "Fondo del panel", "El velo que cubre toda la pantalla en el modo panel.")
        self.fila(lista, "Color", self.color(s, "panel_fondo"))
        self.fila(lista, "Opacidad", self.deslizador(s, "panel_opacidad", 0, 100, 100), "0 % = solo cristal")
        self.fila(lista, "Imagen", self.imagen(s, "panel_imagen"), "Una foto o un fondo para todo el panel")
        self.fila(lista, "Opacidad de la imagen", self.deslizador(s, "panel_imagen_opacidad", 0, 100, 100))

    def pagina_disposicion(self, caja):
        cfg = self.app.config
        lista = self.grupo(caja, "Modo panel", "«Restablecer disposición» vuelve a la que guardes aquí.")
        b = QPushButton(_("Guardar la actual"))
        b.clicked.connect(self.guardar_panel)
        self.fila(lista, "Disposición predeterminada", b,
                  _("Personalizada") if cfg.get("panel_predeterminado") else _("La de fábrica"))
        b = QPushButton(_("Volver a la de fábrica"))
        b.setEnabled(bool(cfg.get("panel_predeterminado")))
        b.clicked.connect(lambda: (cfg.pop("panel_predeterminado", None), self.app.guardar_config(), self.construir()))
        self.fila(lista, "Disposición de fábrica", b)
        lista = self.grupo(caja, "Modo widgets", "«Recolocar widgets» los pondrá donde estén ahora.")
        b = QPushButton(_("Guardar las actuales"))
        b.setEnabled(self.app.modo == "widgets")
        b.clicked.connect(self.guardar_widgets)
        self.fila(lista, "Posiciones predeterminadas", b,
                  (_("Personalizadas") if cfg.get("posiciones_predeterminadas") else _("Automáticas (por columnas)"))
                  + ("" if self.app.modo == "widgets" else _(" · cambia a modo widgets para guardarlas")))
        b = QPushButton(_("Volver a automáticas"))
        b.setEnabled(bool(cfg.get("posiciones_predeterminadas")))
        b.clicked.connect(lambda: (cfg.pop("posiciones_predeterminadas", None), self.app.guardar_config(),
                                   self.construir()))
        self.fila(lista, "Colocación automática", b)

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
            t.clave: [t.ventana.x(), t.ventana.y()] for t in self.app.tarjetas if t.ventana}
        self.app.guardar_config()
        self.construir()

    def pagina_general(self, caja):
        app = self.app
        lista = self.grupo(caja, "Idioma")
        fila = QHBoxLayout()
        elegir = QComboBox()
        for codigo, nombre in idioma.IDIOMAS:
            elegir.addItem(nombre, codigo)
        elegir.setCurrentIndex(max(0, elegir.findData(idioma.actual())))
        reiniciar = QPushButton(_("Reiniciar ahora"))
        reiniciar.hide()
        reiniciar.clicked.connect(lambda: app.actualizador.reiniciar(app.salir))

        def cambio(i):
            app.config["idioma"] = elegir.itemData(i)
            app.guardar_config()
            reiniciar.setVisible(elegir.itemData(i) != idioma.actual())
        elegir.currentIndexChanged.connect(cambio)
        fila.addWidget(elegir)
        fila.addWidget(reiniciar)
        self.fila(lista, "Idioma", fila, "Se aplica al reiniciar MoonDeck")

        lista = self.grupo(caja, "Arranque")
        c = QCheckBox()
        c.setChecked(app.autoarranque_activo())
        c.setEnabled(ES_WINDOWS)
        c.toggled.connect(app.autoarranque)
        self.fila(lista, "Abrir al iniciar sesión", c, "Como administrador y sin aviso de Windows (tarea programada)")
        lista = self.grupo(caja, "Widgets")
        ancho = QSpinBox()
        ancho.setRange(260, 560)
        ancho.setSingleStep(10)
        ancho.setValue(ANCHO)
        ancho.valueChanged.connect(app.cambiar_ancho)
        self.fila(lista, "Ancho de cada widget", ancho, "En píxeles, en el modo widgets")
        cols = QSpinBox()
        cols.setRange(1, 8)
        cols.setValue(COLUMNAS)
        cols.valueChanged.connect(app.cambiar_columnas)
        self.fila(lista, "Columnas al colocarlos", cols, "Las mínimas: si no caben en alto, se usan más")
        intervalo = QDoubleSpinBox()
        intervalo.setRange(0.5, 5)
        intervalo.setSingleStep(0.5)
        intervalo.setDecimals(1)
        intervalo.setValue(INTERVALO)
        intervalo.valueChanged.connect(app.cambiar_intervalo)
        self.fila(lista, "Actualizar cada", intervalo, "Segundos entre lecturas de los sensores")

        lista = self.grupo(caja, "Actualizaciones", _("Busca la última versión estable en github.com/{repo}. "
                                                      "Tu configuración se conserva.").format(repo=REPO))
        fila = QHBoxLayout()
        self.upd_boton = QPushButton(_("Buscar actualizaciones"))
        self.upd_boton.setObjectName("aceptar")
        self.upd_boton.clicked.connect(self.pulsar_actualizar)
        self.upd_atras = QPushButton(_("Volver a la anterior"))
        self.upd_atras.setToolTip(_("Deshace la última actualización"))
        self.upd_atras.clicked.connect(lambda: app.actualizador.volver_atras())
        fila.addWidget(self.upd_boton)
        fila.addWidget(self.upd_atras)
        self.fila(lista, f"MoonDeck {VERSION}", fila)
        self.upd_estado = QLabel("")
        self.upd_estado.setWordWrap(True)
        self.upd_estado.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.upd_notas = QLabel("")
        self.upd_notas.setObjectName("sub")
        self.upd_notas.setWordWrap(True)
        self.upd_notas.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lista.addWidget(self.upd_estado)
        lista.addWidget(self.upd_notas)
        self._accion_actualizar = "buscar"
        if not hasattr(self, "_t_actualizar"):
            self._t_actualizar = QTimer(self, interval=300)
            self._t_actualizar.timeout.connect(self.refrescar_actualizacion)
            self._t_actualizar.start()
        self.refrescar_actualizacion()

    def pulsar_actualizar(self):
        a = self.app.actualizador
        {"buscar": a.buscar, "actualizar": a.actualizar,
         "reiniciar": lambda: a.reiniciar(self.app.salir)}.get(self._accion_actualizar, lambda: None)()
        self.refrescar_actualizacion()

    def refrescar_actualizacion(self):
        try:
            self.upd_estado.isVisible()
        except RuntimeError:  # la página se rehízo: sus etiquetas ya no existen
            return
        a = self.app.actualizador
        texto, boton, accion = texto_actualizacion(a)
        self._accion_actualizar = accion
        self.upd_estado.setText(texto)
        self.upd_estado.setVisible(bool(texto))
        notas = a.notas if a.estado == "nueva" else ""
        self.upd_notas.setText(notas[:800])
        self.upd_notas.setVisible(bool(notas))
        self.upd_boton.setText(boton)
        self.upd_boton.setEnabled(accion is not None)
        self.upd_atras.setEnabled(a.hay_anterior() and not a.ocupado and not a.desde_codigo)

    # --- archivos de tema -------------------------------------------------------

    def exportar(self):
        ruta, _x = QFileDialog.getSaveFileName(self, _("Exportar tema"), os.path.join(os.path.expanduser("~"), "mi-tema.json"),
                                              _("Temas (*.json)"))
        if ruta:
            try:
                with open(ruta, "w", encoding="utf-8") as f:
                    json.dump({"tema_moondeck": 1, **self.app.tema}, f, indent=1, ensure_ascii=False)
            except OSError as e:
                QMessageBox.warning(self, _("Exportar tema"), _("No se pudo guardar: {error}").format(error=e))

    def importar(self):
        ruta, _x = QFileDialog.getOpenFileName(self, _("Importar tema"), os.path.expanduser("~"), _("Temas (*.json)"))
        if not ruta:
            return
        try:
            with open(ruta, encoding="utf-8") as f:
                datos = json.load(f)
            if not isinstance(datos, dict) or not any(k in datos for k in ("global", "widgets", "panel")):
                raise ValueError(_("no es un archivo de tema"))
            self.elegir_tema(datos)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, _("Importar tema"), _("No se pudo cargar el tema: {error}").format(error=e))

    def closeEvent(self, e):
        self.app.ventana_config = None
        super().closeEvent(e)




class Monitor:
    def __init__(self, qapp):
        self.qapp = qapp
        self.colocado = False
        log("Efecto acrílico:", USA_ACRILICO)
        idioma.poner(self.cargar_config().get("idioma") or idioma.detectar())
        log("Abriendo sensores...")
        self.sampler = Sampler()
        log("LibreHardwareMonitor:", "OK" if self.sampler.lhm.ok else self.sampler.lhm.error)
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
        global ANCHO, COLUMNAS, INTERVALO
        ANCHO = int(self.config.get("ancho", ANCHO))
        COLUMNAS = int(self.config.get("columnas", COLUMNAS))
        INTERVALO = float(self.config.get("intervalo", INTERVALO))
        self.ventana_config = None
        self.panel = None
        self.tarjetas = []
        self.aplicar_tema(guardar=False)
        self.discord = Discord(CARPETA)
        self.config["discord"] = dict(DISCORD_POR_DEFECTO, **self.config.get("discord", {}))
        self.discord_no_instalado = False
        self.discord_abriendo = 0  # cuándo se pulsó "Abrir Discord" (para lo que haya que hacer al conectar)
        self.vigilar_discord()
        self.actualizador = Actualizador(os.path.dirname(os.path.abspath(__file__)))
        self.tiempo = Tiempo(self.config.get("tiempo_ciudad") or CIUDAD_POR_DEFECTO)
        self.manual = False  # True cuando el usuario arrastra un widget
        self.reproductores = Reproductores()
        self.mezclador = Mezclador()
        self.dispositivos = Dispositivos()
        self.test = TestVelocidad()
        self.test.resultado = self.config.get("velocidad")
        self.t_velocidad = QTimer(interval=250)  # solo corre mientras se mide
        log("Mezclador:", "OK" if self.mezclador.ok else self.mezclador.error,
            "| dispositivos:", "OK" if self.dispositivos.ok else self.dispositivos.error)

        self.modo = self.config.get("modo", "widgets")
        # El menú de la bandeja depende del modo: se rehace cada vez que se abre.
        self.menu = QMenu()
        self.menu.aboutToShow.connect(lambda: (self.menu.clear(), self.acciones_comunes(self.menu)))

        self.tray = QSystemTrayIcon(qapp.style().standardIcon(QStyle.SP_ComputerIcon))
        self.tray.setToolTip("MoonDeck")
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(
            lambda r: self.alternar() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

        self.tarjetas = []
        self.construir(first)
        self.aplicar(first)
        self.actualizar_multimedia()
        self.actualizar_reloj()
        self.actualizar_audio()
        for t in self.tarjetas:
            t.set_opacidad(self.config["opacidad"].get(t.clave, 1.0))
        self.poner_titulos()
        self.panel = None
        self.aplicar_modo(inicio=True)
        self.colocado = True
        log("Modo:", self.modo, "| widgets:", [(t.clave, t.window().x(), t.window().y(), t.width(), t.height())
                                              for t in self.tarjetas])

        if self.multimedia:
            self.t_multimedia = QTimer(interval=1000)
            self.t_multimedia.timeout.connect(self.actualizar_multimedia)
            self.t_multimedia.start()
            QTimer.singleShot(4000, lambda: log(
                "Reproductores:", "OK" if self.reproductores.ok else self.reproductores.error))

        self.t_reloj = QTimer(interval=1000)
        self.t_reloj.timeout.connect(self.actualizar_reloj)
        self.t_reloj.start()
        if self.audio:
            self.t_audio = QTimer(interval=2000)
            self.t_audio.timeout.connect(self.actualizar_audio)
            self.t_audio.start()
        self.t_velocidad.timeout.connect(self.actualizar_velocidad)
        self.t_discord = QTimer(interval=150)  # rápido: quién habla
        self.t_discord.timeout.connect(self.actualizar_discord)
        self.t_discord.start()
        self.t_tiempo = QTimer(interval=1000)
        self.t_tiempo.timeout.connect(self.actualizar_tiempo)
        self.t_tiempo.start()
        self.t_parpadeo = QTimer(interval=40)
        self.t_parpadeo.timeout.connect(self.parpadear)
        self.t_parpadeo.start()

        self.puente = Puente()
        self.puente.datos.connect(self.aplicar)
        self._activo = True
        threading.Thread(target=self.bucle, daemon=True).start()

    def tarjeta(self, clave, titulo):
        t = Tarjeta(clave, _(titulo), self)
        self.tarjetas.append(t)
        return t

    def construir(self, s):
        # CPU
        c = self.tarjeta("cpu", "CPU")
        c.add(etiqueta(self.modelo_cpu(), "dim"))
        self.cpu_big = c.add(etiqueta("", "grande"))
        self.cpu_sub = c.add(etiqueta())
        self.cpu_temp = c.add(etiqueta())
        self.cpu_graf = c.add(Grafica(["azul", "naranja"]), prescindible=9)
        c.add(leyenda(("Uso %", "azul"), ("Temp °C", "naranja")), prescindible=2)
        self.cpu_nucleos = c.add(BarrasNucleos(len(s["cores"])), prescindible=3)
        self.uptime = c.add(etiqueta("", "dim"), prescindible=1)

        # Memoria
        c = self.tarjeta("memoria", "Memoria")
        self.mem_big = c.add(etiqueta("", "grande"))
        self.mem_sub = c.add(etiqueta())
        self.mem_barra = c.add(Barra())
        self.swap_sub = c.add(etiqueta(), prescindible=2)
        self.swap_barra = c.add(Barra(), prescindible=2)
        self.mem_graf = c.add(Grafica(["morado", "naranja"]), prescindible=9)
        c.add(leyenda(("RAM %", "morado"), ("Archivo de paginación %", "naranja")), prescindible=1)

        # Una tarjeta por GPU
        self.gpus = {}
        for g in s["gpus"]:
            c = self.tarjeta(f"gpu-{g['id']}", "GPU")
            c.nombre_menu = f"GPU · {g['name']}"
            c.add(etiqueta(g["name"], "dim"))
            w = {"big": c.add(etiqueta("", "grande")), "temp": c.add(etiqueta()),
                 "sub": c.add(etiqueta(), prescindible=3), "sub2": c.add(etiqueta(), prescindible=2),
                 "graf": c.add(Grafica(["verde", "azul"]), prescindible=9)}
            c.add(leyenda(("Uso %", "verde"), ("VRAM %", "azul")), prescindible=1)
            self.gpus[g["id"]] = w

        # FPS (solo Windows: usa PresentMon)
        self.fps = None
        if ES_WINDOWS:
            c = self.tarjeta("fps", "FPS")
            self.fps = {"big": c.add(etiqueta("", "grande")), "app": c.add(etiqueta()),
                        "sub": c.add(etiqueta("", "dim")),
                        "graf": c.add(Grafica(["verde", "naranja"], maximo=None), prescindible=9)}
            c.add(leyenda(("FPS", "verde"), ("1% low", "naranja")), prescindible=1)
            self.fps["sub"].setWordWrap(True)

        # Red
        c = self.tarjeta("red", "Red")
        self.red_big = c.add(etiqueta("", "grande"))
        self.red_sub = c.add(etiqueta())
        self.red_graf = c.add(Grafica(["verde", "morado"], maximo=None), prescindible=9)
        c.add(leyenda(("Bajada", "verde"), ("Subida", "morado")), prescindible=1)

        # Discos
        c = self.tarjeta("discos", "Almacenamiento")
        self.disco_big = c.add(etiqueta("", "grande"))
        self.disco_sub = c.add(etiqueta())
        self.disco_graf = c.add(Grafica(["azul", "naranja"], maximo=None), prescindible=9)
        c.add(leyenda(("Lectura", "azul"), ("Escritura", "naranja")), prescindible=7)
        self.particiones = {}
        partes = s["parts"][:6]
        for i, (mount, *_x) in enumerate(partes):
            # Si no caben, se van quitando las últimas particiones.
            n = len(partes) - i
            self.particiones[mount] = (c.add(etiqueta(), prescindible=n), c.add(Barra(), prescindible=n))

        # Sensores: los elegidos en "Elegir sensores…" (o una selección automática).
        c = self.tarjeta("temperaturas", "Sensores")
        if s["lhm_error"] and ES_WINDOWS:
            aviso = c.add(etiqueta(s["lhm_error"] + _(". Abre la app con iniciar.bat (como administrador)."), "dim"))
            aviso.setWordWrap(True)
        self.sens_lista = ListaSensores()
        c.add(self.sens_lista)
        c._estira = True  # la lista absorbe el alto sobrante
        self.construir_sensores(s)

        # Multimedia (solo Windows): lo que suena y volumen por app
        self.multimedia = None
        if ES_WINDOWS:
            c = self.tarjeta("multimedia", "Multimedia")
            m = {"reproductores": QWidget(), "filas_rep": [], "claves_rep": None,
                 "volumen": QWidget(), "filas_vol": [], "claves_vol": None}
            m["caja_rep"] = QVBoxLayout(m["reproductores"])
            m["caja_rep"].setContentsMargins(0, 0, 0, 0)
            m["caja_rep"].setSpacing(10)
            c.add(m["reproductores"])
            m["nada"] = c.add(etiqueta("No está sonando nada.", "dim"))
            m["seccion_vol"] = c.add(etiqueta("VOLUMEN", "seccion"))
            m["seccion_vol"].setContentsMargins(0, 8, 0, 0)
            m["caja_vol"] = QVBoxLayout(m["volumen"])
            m["caja_vol"].setContentsMargins(0, 0, 0, 0)
            m["caja_vol"].setSpacing(4)
            c.add(m["volumen"])
            m["aviso"] = c.add(etiqueta("", "dim"))
            m["aviso"].setWordWrap(True)
            m["tarjeta"] = c
            self.multimedia = m

        # Reloj (tipo y opciones en el clic derecho)
        c = self.tarjeta("reloj", "Reloj")
        opciones = dict(RELOJ_POR_DEFECTO, **self.config.get("reloj", {}))
        self.config["reloj"] = opciones
        self.reloj = RelojVista(opciones)
        c.add(self.reloj)
        c._estira = True

        # Calendario
        c = self.tarjeta("calendario", "Calendario")
        cab = QHBoxLayout()
        cab.setContentsMargins(0, 0, 0, 0)
        anterior, siguiente = QToolButton(), QToolButton()
        anterior.setText("‹")
        siguiente.setText("›")
        self.cal_titulo = QToolButton()
        self.cal_titulo.setToolTip(_("Volver a hoy"))
        self.cal_titulo.setStyleSheet("font-weight: 600; font-size: 11pt;")
        for b in (anterior, self.cal_titulo, siguiente):
            b.setCursor(Qt.PointingHandCursor)
        anterior.setStyleSheet("font-size: 15pt; padding: 0 8px;")
        siguiente.setStyleSheet("font-size: 15pt; padding: 0 8px;")
        cab.addWidget(anterior)
        cab.addStretch()
        cab.addWidget(self.cal_titulo)
        cab.addStretch()
        cab.addWidget(siguiente)
        caja_cab = QWidget()
        caja_cab.setLayout(cab)
        c.add(caja_cab)
        self.calendario = CalendarioMes(self.primer_dia())
        c.add(self.calendario)
        c._estira = True
        anterior.clicked.connect(lambda: self.mover_calendario(-1))
        siguiente.clicked.connect(lambda: self.mover_calendario(1))
        self.cal_titulo.clicked.connect(lambda: self.mover_calendario(0))
        self.cal_titulo.setText(self.calendario.titulo())

        # Tiempo
        c = self.tarjeta("tiempo", "Tiempo")
        t = {"version": None}
        arriba = CabeceraTiempo()
        fila = QHBoxLayout(arriba)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(12)
        t["icono"] = arriba.icono = IconoTiempo(56)
        fila.addWidget(t["icono"])
        textos = QVBoxLayout()
        textos.setSpacing(0)
        t["temp"] = etiqueta("—", "grande")
        t["desc"] = etiqueta("", "sub")
        textos.addWidget(t["temp"])
        textos.addWidget(t["desc"])
        fila.addLayout(textos, 1)
        c.add(arriba)
        t["detalle"] = c.add(etiqueta("", "dim"), prescindible=3)
        t["detalle"].setWordWrap(True)
        t["horas"] = c.add(PronosticoHoras(), prescindible=2)
        t["dias"] = c.add(PronosticoDias())
        c._estira = True  # los días absorben el alto sobrante
        t["ciudad"] = c.add(etiqueta("", "dim"), prescindible=1)
        self.tm = t

        # Dispositivos de audio (solo Windows)
        self.audio = None
        if ES_WINDOWS:
            c = self.tarjeta("audio", "Dispositivos de audio")
            a = {"claves": None, "filas": {}}
            # Se ve el dispositivo en uso; "Cambiar" despliega los demás.
            for clave, titulo in (("salida", "SALIDA"), ("entrada", "ENTRADA")):
                cab = QWidget()
                fila_cab = QHBoxLayout(cab)
                fila_cab.setContentsMargins(0, 0, 0, 0)
                fila_cab.addWidget(etiqueta(titulo, "seccion"))
                fila_cab.addStretch()
                b = QToolButton()
                b.setText(_("Cambiar ▾"))
                b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet("font-size: 8pt;")
                b.clicked.connect(lambda _=False, k=clave: self.desplegar_audio(k))
                fila_cab.addWidget(b)
                a[clave + "_tit"] = c.add(cab)
                a[clave + "_boton"] = b
                a[clave + "_abierto"] = False
                caja = QVBoxLayout()
                caja.setContentsMargins(0, 0, 0, 0)
                caja.setSpacing(2)
                contenedor = QWidget()
                contenedor.setLayout(caja)
                a[clave] = caja
                c.add(contenedor)
            a["entrada_tit"].setContentsMargins(0, 6, 0, 0)
            a["mic"] = QPushButton(_("Silenciar micrófono"))
            a["mic"].setCheckable(True)
            a["mic"].setCursor(Qt.PointingHandCursor)
            a["mic"].clicked.connect(self.silenciar_mic)
            c.add(a["mic"], prescindible=1)
            a["aviso"] = c.add(etiqueta("", "dim"))
            a["aviso"].setWordWrap(True)
            self.audio = a

        # Discord: el canal de voz en el que estoy
        c = self.tarjeta("discord", "Discord")
        d = {"version": None, "filas": {}, "ids": None}
        d["canal"] = c.add(etiqueta("", "sub"))
        d["canal"].setStyleSheet("font-weight: 600;")
        d["servidor"] = c.add(etiqueta("", "dim"))
        d["aviso"] = c.add(etiqueta("", "dim"))
        d["aviso"].setWordWrap(True)
        d["conectar"] = c.add(QPushButton(_("Conectar con Discord…")))
        d["conectar"].setProperty("estilo", "principal")
        d["conectar"].setCursor(Qt.PointingHandCursor)
        d["conectar"].clicked.connect(lambda: self.conectar_discord(c.window()))
        d["abrir"] = c.add(QPushButton(_("Abrir Discord")))
        d["abrir"].setProperty("estilo", "principal")
        d["abrir"].setCursor(Qt.PointingHandCursor)
        d["abrir"].clicked.connect(self.abrir_discord)
        d["canales"] = QWidget()
        d["caja_canales"] = QVBoxLayout(d["canales"])
        d["caja_canales"].setContentsMargins(0, 0, 0, 0)
        d["caja_canales"].setSpacing(4)
        d["canales_ids"] = None
        c.add(d["canales"])
        d["ultimo"] = c.add(QPushButton())
        d["ultimo"].setCursor(Qt.PointingHandCursor)
        d["ultimo"].clicked.connect(self.entrar_ultimo_discord)
        d["lista"] = QWidget()
        d["caja_lista"] = QVBoxLayout(d["lista"])
        d["caja_lista"].setContentsMargins(0, 4, 0, 0)
        d["caja_lista"].setSpacing(4)
        c.add(d["lista"])
        d["controles"] = QWidget()
        cc = QVBoxLayout(d["controles"])
        cc.setContentsMargins(0, 6, 0, 0)
        cc.setSpacing(4)
        for clave, texto, maximo, fn in (("entrada", "Micro", 100, self.discord.volumen_entrada),
                                         ("salida", "Salida", 200, self.discord.volumen_salida)):
            fila = QHBoxLayout()
            lb = etiqueta(texto, "sub")
            lb.setFixedWidth(50)
            fila.addWidget(lb)
            sl = QSlider(Qt.Horizontal)
            sl.setRange(0, maximo)
            sl.setCursor(Qt.PointingHandCursor)
            val = etiqueta("", "dim")
            val.setFixedWidth(40)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            envio = QTimer(sl, singleShot=True, interval=150)
            envio.timeout.connect(lambda sl=sl, fn=fn: fn(sl.value()))
            sl.valueChanged.connect(lambda v, sl=sl, val=val, envio=envio: (
                val.setText(f"{v} %"), None if getattr(sl, "_actualizando", False) else
                (setattr(sl, "_tocado", time.monotonic()), envio.start())))
            fila.addWidget(sl, 1)
            fila.addWidget(val)
            d[clave] = (sl, val, envio)
            cc.addLayout(fila)
        botones = QHBoxLayout()
        botones.setSpacing(6)
        d["mute"], d["deaf"], d["salir"] = QPushButton(_("Silenciar")), QPushButton(_("Ensordecer")), QPushButton(_("Salir"))
        for b in (d["mute"], d["deaf"]):
            b.setCheckable(True)
        d["mute"].clicked.connect(lambda: self.discord.silenciar(not self.discord.ajustes.get("mute")))
        d["deaf"].clicked.connect(lambda: self.discord.ensordecer(not self.discord.ajustes.get("deaf")))
        d["salir"].clicked.connect(self.discord.salir)
        for b in (d["mute"], d["deaf"], d["salir"]):
            b.setCursor(Qt.PointingHandCursor)
            botones.addWidget(b)
        cc.addLayout(botones)
        c.add(d["controles"])
        d["tarjeta"] = c
        self.dc = d

        # Test de velocidad
        c = self.tarjeta("velocidad", "Test de velocidad")
        self.vel_reloj = c.add(Velocimetro())
        self.vel_reloj.estilo = self.config.get("velocimetro", "deportivo")
        self.vel_resto = c.add(etiqueta(), prescindible=2)
        self.vel_resto.setAlignment(Qt.AlignHCenter)
        self.vel_estado = c.add(etiqueta("", "dim"), prescindible=1)
        self.vel_estado.setWordWrap(True)
        self.vel_estado.setAlignment(Qt.AlignHCenter)
        self.vel_boton = QPushButton(_("Iniciar test"))
        self.vel_boton.setProperty("estilo", "principal")
        self.vel_boton.setCursor(Qt.PointingHandCursor)
        self.vel_boton.clicked.connect(self.iniciar_test)
        c.add(self.vel_boton)

        # Juegos: Buscaminas, 2048 y el dinosaurio de Chrome (se elige con el clic derecho).
        c = self.tarjeta("juegos", "Juegos")
        self.juego_vista = VistaJuego(self)
        c.add(self.juego_vista)
        c._estira = True

        # Aplicaciones: un lanzador con los iconos que elija el usuario.
        c = self.tarjeta("apps", "Aplicaciones")
        self.apps_vista = VistaApps(self)
        c.add(self.apps_vista)
        self.actualizar_velocidad()

        for t in self.tarjetas:
            t.terminar()

    @staticmethod
    def modelo_cpu():
        if ES_WINDOWS:
            try:
                import winreg
                k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                   r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
            except OSError:
                return "CPU"
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
        return "CPU"

    # --- sensores ------------------------------------------------------------

    def construir_sensores(self, s):
        """Decide qué sensores muestra el widget Sensores y en qué orden (por tipo)."""
        elegidos = self.config.get("sensores")
        if elegidos is None:
            elegidos = seleccion_auto(s["sensores"])
        tipos = {x[5]: x[2] for x in s["sensores"]}
        orden = list(dict.fromkeys(v[0] for v in TIPOS_SENSOR.values()))
        por_seccion = {}
        for ident in elegidos:
            if ident in tipos:
                seccion = TIPOS_SENSOR.get(tipos[ident], (tipos[ident],))[0]
                por_seccion.setdefault(seccion, []).append(ident)
        self.sens_secciones = [(sec, por_seccion[sec]) for sec in
                               sorted(por_seccion, key=lambda x: orden.index(x) if x in orden else 99)]
        self.pintar_sensores(s)

    def pintar_sensores(self, s):
        valores = {x[5]: x for x in s["sensores"]}
        lineas = []
        for seccion, idents in self.sens_secciones:
            if len(self.sens_secciones) > 1:
                lineas.append(("seccion", _(seccion).upper()))
            for ident in idents:
                x = valores.get(ident)
                if x:
                    _x, hw, tipo, nombre, valor, _x = x
                    color = color_temp(valor) if tipo == "Temperature" else C_CLARO
                    lineas.append(("sensor", f"{hw} · {nombre}", fmt_sensor(tipo, valor, color=False), color))
        if not lineas:
            lineas = [("mas", _("Ningún sensor elegido: clic derecho > «Elegir sensores…»"))]
        self.sens_lista.set_lineas(lineas)

    def elegir_sensores(self, padre=None):
        s = getattr(self, "ultimo", None)
        if not s:
            return
        actual = self.config.get("sensores")
        dialogo = SelectorSensores(s["sensores"], seleccion_auto(s["sensores"]) if actual is None else actual,
                                   padre)
        if dialogo.exec():
            self.config["sensores"] = None if dialogo.por_defecto else dialogo.seleccion()
            self.construir_sensores(s)
            self.aplicar(s)
            self.guardar_config()

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

    # --- posiciones -------------------------------------------------------

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
        destino = self.config["posiciones" if self.modo == "widgets" else "posiciones_sueltas"]
        for t in self.tarjetas:
            if t.ventana:
                destino[t.clave] = [t.ventana.x(), t.ventana.y()]
        self.config["modo"] = self.modo
        try:
            with open(CONFIG, "w") as f:
                json.dump(self.config, f, indent=1)
        except OSError:
            pass

    def pantalla_guardada(self):
        nombre = self.config.get("pantalla")
        return next((sc for sc in QGuiApplication.screens() if sc.name() == nombre), None)

    @staticmethod
    def en_alguna_pantalla(pos):
        return pos and any(sc.availableGeometry().contains(pos[0] + 20, pos[1] + 20)
                           for sc in QGuiApplication.screens())

    # --- modos ---------------------------------------------------------------

    def aplicar_modo(self, inicio=False):
        """Pone cada tarjeta donde le toca según el modo actual."""
        if self.modo == "panel":
            if self.panel is None:
                self.panel = VentanaPanel(self)
            self.panel.colocar_en(self.pantalla_guardada() or QGuiApplication.primaryScreen())
            en_panel = []
            visibles = self.visibles()
            for t in self.tarjetas:
                if t not in visibles:
                    if t.ventana:
                        t.ventana.soltar()
                    t.hide()
                elif t.clave in self.config["sueltas"]:
                    if not t.ventana:
                        self.ventana_para(t, encima=True, pos=self.config["posiciones_sueltas"].get(t.clave))
                else:
                    if t.ventana:
                        t.ventana.soltar()
                    en_panel.append(t)
            self.panel.repartir(en_panel)
            self.panel.show()
            for t in self.tarjetas:
                if t.ventana:
                    t.ventana.show()
                    t.ventana.raise_()
        else:
            visibles = self.visibles()
            for t in self.tarjetas:
                if t.ventana and (t.ventana.encima or t not in visibles):
                    t.ventana.soltar()  # se rehace sin "siempre encima", o se oculta
                if t not in visibles:
                    t.hide()
                elif not t.ventana:
                    self.ventana_para(t, encima=False)
            if self.panel:
                self.panel.set_edicion(False)
                self.panel.hide()
                self.panel.deleteLater()
                self.panel = None
            # Si se colocaron a mano, se quedan donde estaban (también al reiniciar).
            self.manual = bool(self.config.get("manual")) and not (RECOLOCAR_AL_ABRIR and inicio)
            self.colocar(ignorar_guardadas=not self.manual, pantalla=self.pantalla_guardada())
            for t in visibles:
                t.ventana.show()
        self.discord.permitir(any(t.clave == "discord" for t in self.visibles()))

    def ventana_para(self, tarjeta, encima, pos=None):
        if tarjeta.parent():
            tarjeta.setParent(None)
        v = VentanaWidget(tarjeta, self, encima)
        if self.en_alguna_pantalla(pos):
            v.move(pos[0], pos[1])
        return v

    def cambiar_modo(self, modo, pantalla=None):
        if pantalla:
            self.config["pantalla"] = pantalla.name()
        self.modo = modo
        self.aplicar_modo()
        self.guardar_config()
        log("Modo:", modo)

    def sacar_del_panel(self, tarjeta):
        """Saca una tarjeta del panel a su propia ventana, en el mismo sitio."""
        pos = tarjeta.mapToGlobal(tarjeta.rect().topLeft())
        self.config["sueltas"].append(tarjeta.clave)
        self.config["posiciones_sueltas"][tarjeta.clave] = [pos.x(), pos.y()]
        self.aplicar_modo()
        self.guardar_config()

    def devolver_al_panel(self, tarjeta):
        self.config["sueltas"] = [c for c in self.config["sueltas"] if c != tarjeta.clave]
        self.aplicar_modo()
        self.guardar_config()

    # --- modo widgets: cuadrícula --------------------------------------------

    def colocar(self, ignorar_guardadas=False, pantalla=None):
        """Reparte las ventanas por columnas, cada widget con su altura natural y justo
        debajo del anterior de su columna (sin estirarlos ni dejar huecos). Los que
        tienen una posición guardada (los que moviste a mano) se quedan en ella."""
        guardadas = {} if ignorar_guardadas else self.config["posiciones"]
        area = (pantalla or QGuiApplication.primaryScreen()).availableGeometry()
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
        max_cols = max(1, min(len(tarjetas), (area.width() + SEPARACION) // (ANCHO + SEPARACION)))
        cols = min(COLUMNAS, max_cols)
        sitios, alto_total = repartir(cols)
        while alto_total > area.height() and cols < max_cols:
            cols += 1
            sitios, alto_total = repartir(cols)
        ancho_total = cols * ANCHO + SEPARACION * (cols - 1)
        x0 = area.x() + max((area.width() - ancho_total) // 2, 0)
        y0 = area.y() + max((area.height() - alto_total) // 2, 0)
        for t, alto, (col, y) in zip(tarjetas, altos, sitios):
            v = t.ventana
            v.resize(ANCHO, alto)
            pos = guardadas.get(t.clave)
            if self.en_alguna_pantalla(pos):
                v.move(pos[0], pos[1])
            else:
                v.move(x0 + col * (ANCHO + SEPARACION), y0 + y)
        self._altos = altos

    def recolocar(self, pantalla=None):
        """Coloca en cuadrícula y recuerda la pantalla para las próximas veces."""
        pantalla = pantalla or self.pantalla_guardada()
        if pantalla:
            self.config["pantalla"] = pantalla.name()
        # Las posiciones guardadas en Configuración > Disposición, o la colocación automática.
        predeterminadas = self.config.get("posiciones_predeterminadas")
        self.manual = bool(predeterminadas)
        self.config["manual"] = self.manual
        self.config["posiciones"] = dict(predeterminadas or {})
        self.colocar(ignorar_guardadas=not self.manual, pantalla=pantalla)
        self.guardar_config()

    def ajustar_alturas(self):
        """Adapta las ventanas al contenido (p. ej. empieza a sonar música)."""
        if not self.colocado:
            return
        if self.modo == "widgets" and not self.manual:
            # Sin colocar a mano: si uno crece o encoge, se reparten otra vez.
            altos = [t.alto_natural(ANCHO) for t in self.visibles() if t.ventana]
            if altos != getattr(self, "_altos", None):
                self.colocar(ignorar_guardadas=True, pantalla=self.pantalla_guardada())
            return
        # Ventanas sueltas o movidas a mano: cada una a su altura.
        for t in self.tarjetas:
            if t.ventana:
                alto = t.alto_natural(ANCHO)
                if alto != t.ventana.height():
                    t.ventana.resize(ANCHO, alto)

    # --- menús ---------------------------------------------------------------

    def acciones_comunes(self, menu, padre=None):
        menu.addAction(_("Configuración…"), self.abrir_configuracion)
        menu.addAction(_("Mostrar / ocultar"), self.alternar)
        sub = menu.addMenu(_("Widgets visibles"))
        for t in self.tarjetas:
            a = sub.addAction(t.nombre_menu, lambda _=False, t=t: self.alternar_widget(t))
            a.setCheckable(True)
            a.setChecked(t in self.visibles())
        menu.addAction(_("Elegir sensores…"), lambda: self.elegir_sensores(padre))
        if self.modo == "widgets":
            # Los submenús de pantallas se rellenan al abrirse: puede conectarse o quitarse un monitor.
            sub = menu.addMenu(_("Recolocar widgets en..."))
            sub.aboutToShow.connect(lambda m=sub: self.listar_pantallas(m, self.recolocar))
            sub = menu.addMenu(_("Modo panel (pantalla completa) en..."))
            sub.aboutToShow.connect(lambda m=sub: self.listar_pantallas(
                m, lambda sc: self.cambiar_modo("panel", sc), marcar=False))
        else:
            editar = menu.addAction(_("Editar disposición (mover y redimensionar)"),
                                    lambda: self.panel.set_edicion(not self.panel.editando))
            editar.setCheckable(True)
            editar.setChecked(bool(self.panel and self.panel.editando))
            menu.addAction(_("Restablecer disposición"), lambda: self.panel.restablecer())
            sub = menu.addMenu(_("Mover el panel a..."))
            sub.aboutToShow.connect(lambda m=sub: self.listar_pantallas(
                m, lambda sc: self.cambiar_modo("panel", sc)))
            menu.addAction(_("Volver a modo widgets"), lambda: self.cambiar_modo("widgets"))
        menu.addSeparator()
        menu.addAction(_("Salir"), self.salir)

    def listar_pantallas(self, menu, accion, marcar=True):
        menu.clear()
        principal = QGuiApplication.primaryScreen()
        elegida = self.pantalla_guardada() or principal
        for i, sc in enumerate(QGuiApplication.screens(), 1):
            g = sc.geometry()
            texto = _("Pantalla {n}").format(n=i) + f"{_(' (principal)') if sc is principal else ''} · {g.width()}×{g.height()}"
            a = menu.addAction(_(texto), lambda _=False, sc=sc: accion(sc))
            if marcar:
                a.setCheckable(True)
                a.setChecked(sc is elegida)

    def menu_tarjeta(self, tarjeta):
        """Menú del clic derecho: opacidad de ese widget, sacar/devolver y lo general."""
        menu = QMenu()
        sub = menu.addMenu(_("Opacidad de este widget"))
        for nivel in OPACIDADES:
            accion = sub.addAction(f"{nivel} %", lambda _=False, v=nivel / 100: self.cambiar_opacidad([tarjeta], v))
            accion.setCheckable(True)
            accion.setChecked(round(tarjeta.opacidad * 100) == nivel)
        sub.addSeparator()
        sub.addAction(_("Aplicar a todos los widgets"),
                      lambda: self.cambiar_opacidad(self.tarjetas, tarjeta.opacidad))
        if tarjeta.clave == "temperaturas":
            menu.addAction(_("Elegir sensores…"), lambda: self.elegir_sensores(tarjeta.window()))
        if tarjeta.clave == "reloj":
            self.menu_reloj(menu)
        if tarjeta.clave == "calendario":
            sub = menu.addMenu(_("La semana empieza en"))
            for dia in (0, 6):
                a = sub.addAction(idioma.dia_semana(dia).capitalize(), lambda _x=False, d=dia: self.cambiar_semana(d))
                a.setCheckable(True)
                a.setChecked(self.primer_dia() == dia)
            menu.addSeparator()
        if tarjeta.clave == "juegos":
            sub = menu.addMenu(_("Juego"))
            for clave, nombre in juegos.JUEGOS:
                a = sub.addAction(_(nombre), lambda _x=False, c=clave: self.juego_vista.poner(c))
                a.setCheckable(True)
                a.setChecked(self.juego_vista.juego.nombre == clave)
            menu.addAction(_("Nueva partida"), self.juego_vista.nueva)
            menu.addSeparator()
        if tarjeta.clave == "apps":
            self.menu_apps(menu, tarjeta.window())
        if tarjeta.clave == "velocidad":
            sub = menu.addMenu(_("Estilo del velocímetro"))
            for clave, nombre in esferas.ESTILOS_VELOCIMETRO:
                a = sub.addAction(_(nombre), lambda _x=False, c=clave: self.cambiar_velocimetro(c))
                a.setCheckable(True)
                a.setChecked(self.vel_reloj.estilo == clave)
            menu.addSeparator()
        if tarjeta.clave == "tiempo":
            menu.addAction(_("Cambiar ciudad…"), lambda: self.elegir_ciudad(tarjeta.window()))
            menu.addAction(_("Actualizar ahora"), self.tiempo._despertar.set)
            menu.addSeparator()
        if tarjeta.clave == "discord":
            self.menu_discord(menu, tarjeta.window())
        if self.modo == "panel" and not tarjeta.ventana and tarjeta.clave in self.panel.celdas:
            _x, _x, alto, ancho = self.panel.celdas[tarjeta.clave]
            sub = menu.addMenu(_("Tamaño en la cuadrícula"))
            for titulo, actual, maximo, campo in (("Ancho", ancho, self.panel.cols, "ancho"),
                                                  ("Alto", alto, VentanaPanel.MAX_ALTO, "alto")):
                s2 = sub.addMenu(f"{_(titulo)}: {actual}")
                for v in range(1, maximo + 1):
                    a = s2.addAction(str(v), lambda _=False, v=v, campo=campo:
                                     self.panel.cambiar_tam(tarjeta, **{campo: v}))
                    a.setCheckable(True)
                    a.setChecked(v == actual)
        if self.modo == "panel":
            if tarjeta.ventana:
                menu.addAction(_("Devolver al panel"), lambda: self.devolver_al_panel(tarjeta))
            else:
                menu.addAction(_("Sacar del panel (ventana aparte, siempre encima)"),
                               lambda: self.sacar_del_panel(tarjeta))
        a = menu.addAction(_("Mostrar título"), lambda: self.alternar_titulo(tarjeta))
        a.setCheckable(True)
        a.setChecked(tarjeta.clave not in self.config.get("sin_titulo", []))
        menu.addAction(_("Ocultar este widget"), lambda: self.alternar_widget(tarjeta))
        menu.addSeparator()
        self.acciones_comunes(menu, tarjeta.window())
        self._menu_tarjeta = menu  # que no lo borre el recolector mientras se muestra
        return menu

    def cambiar_opacidad(self, tarjetas, valor):
        for t in tarjetas:
            t.set_opacidad(valor)
            self.config["opacidad"][t.clave] = valor
        self.guardar_config()

    def ventanas(self):
        return [t.ventana for t in self.tarjetas if t.ventana] + ([self.panel] if self.panel else [])

    def alternar(self):
        ventanas = self.ventanas()
        visible = any(v.isVisible() for v in ventanas)
        for v in ventanas:
            v.setVisible(not visible)

    def salir(self):
        self._activo = False
        if self.ventana_config:
            self.ventana_config.close()
        self.reproductores.close()
        self.guardar_config()
        self.tray.hide()
        self.sampler.close()
        self.qapp.quit()

    # --- datos -------------------------------------------------------------

    def bucle(self):
        while self._activo:
            time.sleep(INTERVALO)
            try:
                datos = self.sampler.sample()
                if self._activo:  # al salir, Qt ya no está para recibirlo
                    self.puente.datos.emit(datos)
            except Exception as e:  # noqa: BLE001 - seguir aunque falle una lectura
                log("Error leyendo sensores:", e)

    def aplicar(self, s):
        # CPU
        self.cpu_big.setText(f"{s['cpu']:.0f} %")
        freq = f"{s['freq'] / 1000:.2f} GHz" if s["freq"] else "—"
        extra = f" · {s['cpu_power']:.0f} W" if s.get("cpu_power") is not None else ""
        self.cpu_sub.setText(f"{freq} · " + _("{n} procesos").format(n=s["procs"]) + extra)
        t = s["cpu_temp"]
        temp = f"{t:.1f} °C" if t is not None else "—"
        self.cpu_temp.setText(f'<span style="color:{color_temp(t)}">' + _("Temperatura {t}").format(t=temp) + "</span>")
        self.cpu_graf.push(s["cpu"], t)
        self.cpu_nucleos.set(s["cores"])
        up = int(s["uptime"])
        self.uptime.setText(_("{n} hilos · Encendido {tiempo}").format(
            n=len(s["cores"]), tiempo=f"{up // 86400}d {up % 86400 // 3600}h {up % 3600 // 60}m"))

        # Memoria
        used, total, pct = s["mem"]
        self.mem_big.setText(f"{pct:.0f} %")
        self.mem_sub.setText(f"RAM {fmt_bytes(used)} / {fmt_bytes(total)}")
        self.mem_barra.set(pct)
        su, st, sp = s["swap"]
        self.swap_sub.setText(_("Paginación {usado} / {total}").format(usado=fmt_bytes(su), total=fmt_bytes(st)) if st else _("Sin archivo de paginación"))
        self.swap_barra.set(sp if st else 0)
        self.mem_graf.push(pct, sp if st else 0)

        # GPUs
        for g in s["gpus"]:
            w = self.gpus.get(g["id"])
            if not w:
                continue
            w["big"].setText(f"{g['util']:.0f} %" if g["util"] is not None else "—")
            temp = f"{g['temp']:.0f} °C" if g["temp"] is not None else "—"
            w["temp"].setText(f'<span style="color:{color_temp(g["temp"])}">' + _("Temperatura {t}").format(t=temp) + "</span>")
            vram_pct = 0
            if g["vram"]:
                vram_pct = 100 * g["vram"][0] / g["vram"][1]
                w["sub"].setText(f"VRAM {fmt_bytes(g['vram'][0])} / {fmt_bytes(g['vram'][1])} ({vram_pct:.0f} %)")
            else:
                w["sub"].setText(_("VRAM —"))
            partes = []
            if g["power"] is not None:
                partes.append(f"{g['power']:.0f} W" + (f" / {g['power_limit']:.0f} W" if g["power_limit"] else ""))
            if g["clock"] is not None:
                partes.append(f"{g['clock']:.0f} MHz")
            if g["fan"] is not None:
                partes.append(_("Ventilador {n} %").format(n=f"{g['fan']:.0f}"))
            w["sub2"].setText(" · ".join(partes))
            w["graf"].push(g["util"], vram_pct)

        # FPS
        if self.fps:
            f = s["fps"]
            if f:
                self.fps["big"].setText(f"{f['fps']:.0f} FPS")
                self.fps["app"].setText(f["app"])
                self.fps["sub"].setText(f"1% low {f['low1']:.0f} FPS · frametime {f['frametime']:.1f} ms")
                self.fps["graf"].push(f["fps"], f["low1"])
            else:
                self.fps["big"].setText("—")
                self.fps["app"].setText(_("Sin juegos ni apps 3D activos"))
                self.fps["sub"].setText(s["fps_error"] or _("Abre un juego para medir sus FPS."))
                self.fps["graf"].push(0, 0)

        # Red
        rx, tx = s["net"]
        self.red_big.setText(f"↓ {fmt_bytes(rx, True)}")
        self.red_sub.setText(f"↑ {fmt_bytes(tx, True)}")
        self.red_graf.push(rx, tx)

        # Discos
        r, w_ = s["disk_io"]
        self.disco_big.setText(_("L {v}").format(v=fmt_bytes(r, True)))
        self.disco_sub.setText(_("E {v}").format(v=fmt_bytes(w_, True)))
        self.disco_graf.push(r, w_)
        for mount, used, total, pct in s["parts"]:
            if mount in self.particiones:
                lb, barra = self.particiones[mount]
                lb.setText(f"{mount}  {fmt_bytes(used)} / {fmt_bytes(total)} · {pct:.0f} %")
                barra.set(pct)

        # Sensores
        self.ultimo = s
        self.pintar_sensores(s)

        self.ajustar_alturas()

    # --- reloj y calendario ----------------------------------------------------

    def actualizar_reloj(self):
        ahora = datetime.datetime.now()
        self.reloj.update()
        # A medianoche cambia el día marcado en el calendario.
        if ahora.date() != getattr(self, "_hoy", None):
            self._hoy = ahora.date()
            self.calendario.update()

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
        tipos = menu.addMenu(_("Tipo de reloj"))
        for clave, nombre in ESTILOS_RELOJ:
            a = tipos.addAction(_(nombre), lambda _=False, c=clave: self.cambiar_reloj(estilo=c))
            a.setCheckable(True)
            a.setChecked(o["estilo"] == clave)
        for texto, clave in (("Formato 24 horas", "h24"), ("Mostrar segundos", "segundos")):
            a = menu.addAction(_(texto), lambda _=False, c=clave: self.cambiar_reloj(**{c: not o[c]}))
            a.setCheckable(True)
            a.setChecked(o[clave])
        ciudades = menu.addMenu(_("Ciudades (reloj mundial, hasta 8)"))
        for nombre, zona in CIUDADES:
            a = ciudades.addAction(_(nombre), lambda _=False, z=zona: self.cambiar_reloj(zona=z))
            a.setCheckable(True)
            a.setChecked(zona in o["zonas"])
        menu.addSeparator()

    def mover_calendario(self, meses):
        if meses:
            self.calendario.cambiar(meses)
        else:
            self.calendario.ir_a_hoy()
        self.cal_titulo.setText(self.calendario.titulo())

    # --- dispositivos de audio -------------------------------------------------

    def actualizar_audio(self):
        a = self.audio
        if not a:
            return
        datos = self.dispositivos.leer()
        if datos:
            claves = tuple((k, tuple((i, n) for i, n, _x in datos[k])) for k in ("salida", "entrada"))
            if claves != a["claves"]:
                a["claves"] = claves
                for b in a["filas"].values():
                    b.deleteLater()
                a["filas"] = {}
                for k in ("salida", "entrada"):
                    for ident, nombre, _x in datos[k]:
                        b = QPushButton()
                        b.setProperty("estilo", "dispositivo")
                        b.setCheckable(True)
                        b.setCursor(Qt.PointingHandCursor)
                        # El ancho lo pone la tarjeta (el nombre se recorta), no el texto.
                        b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
                        b.setToolTip(nombre)
                        b.clicked.connect(lambda _=False, i=ident: self.elegir_dispositivo(i))
                        a[k].addWidget(b)
                        a["filas"][ident] = b
                    if not datos[k]:
                        b = QPushButton()
                        b.setProperty("estilo", "dispositivo")
                        b.setText(_("Ninguno conectado"))
                        b.setEnabled(False)
                        a[k].addWidget(b)
                        a["filas"][f"ninguno-{k}"] = b
            for k in ("salida", "entrada"):
                hay_pred = any(p for *_x, p in datos[k])
                for ident, nombre, pred in datos[k]:
                    b = a["filas"][ident]
                    b.setChecked(pred)
                    marca = "◉" if pred else "○"
                    ancho = b.width() - 50 if b.isVisible() and b.width() > 100 else ANCHO - 90
                    b.setText(f"{marca}  " + b.fontMetrics().elidedText(nombre, Qt.ElideRight, ancho))
                    b.setVisible(pred or a[k + "_abierto"] or not hay_pred)
                a[k + "_boton"].setVisible(len(datos[k]) > 1)
                a[k + "_boton"].setText(_("Cerrar ▴") if a[k + "_abierto"] else _("Cambiar ▾"))
            mic = datos["mic_silenciado"]
            a["mic"].setEnabled(mic is not None)
            a["mic"].setChecked(bool(mic))
            a["mic"].setText(_("Micrófono silenciado · clic para activar") if mic else _("Silenciar micrófono"))
        a["aviso"].setText(self.dispositivos.error or "")
        a["aviso"].setVisible(bool(self.dispositivos.error))
        self.ajustar_alturas()

    def silenciar_mic(self, activo):
        log("Micrófono:", self.dispositivos.silenciar_mic(activo))
        self.actualizar_audio()  # refleja enseguida el estado real

    def desplegar_audio(self, clave):
        self.audio[clave + "_abierto"] = not self.audio[clave + "_abierto"]
        self.actualizar_audio()

    def elegir_dispositivo(self, ident):
        for k in ("salida", "entrada"):
            self.audio[k + "_abierto"] = False  # elegido: se pliega la lista
        self.dispositivos.predeterminar(ident)
        self.actualizar_audio()

    # --- títulos de los widgets y calendario ------------------------------------

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

    def poner_titulos(self):
        sin = self.config.get("sin_titulo", [])
        for t in self.tarjetas:
            t.lb_titulo.setVisible(t.clave not in sin)

    def cambiar_semana(self, primer_dia):
        self.config.setdefault("calendario", {})["semana"] = "domingo" if primer_dia == 6 else "lunes"
        self.calendario.primer_dia = primer_dia
        self.calendario.update()
        self.guardar_config()

    def primer_dia(self):
        return 6 if self.config.get("calendario", {}).get("semana") == "domingo" else 0

    # --- tema y ajustes ----------------------------------------------------------

    def aplicar_tema(self, guardar=True):
        self.tema = temas.completo(self.config.get("tema"))
        aplicar_colores(self.tema)
        css = css_tema(self.tema)
        for t in self.tarjetas:
            t.setStyleSheet(css)
            t.ajustar_margenes()
            if t.ventana:
                t.ventana.aplicar_tinte()
            t.update()
        if self.panel:
            self.panel.aplicar_cristal()
            self.panel.barra.setStyleSheet(css + "QToolButton { font-size: 11pt; padding: 3px 9px; }")
            self.panel.barra.listo.setStyleSheet(f"background: {COLORES['azul'].name()}; color: white; font-weight: 600;")
            self.panel.update()
        if guardar:
            self.ajustar_alturas()
            # Al arrastrar un deslizador llegan muchos cambios: se guarda al parar.
            if not hasattr(self, "_guardar_tema"):
                self._guardar_tema = QTimer(singleShot=True, interval=500)
                self._guardar_tema.timeout.connect(self.guardar_config)
            self._guardar_tema.start()

    def abrir_configuracion(self):
        if not self.ventana_config:
            self.ventana_config = VentanaConfig(self)
        self.ventana_config.show()
        self.ventana_config.raise_()
        self.ventana_config.activateWindow()

    TAREA = "MoonDeck"  # la tarea programada que crea instalar.ps1

    def autoarranque_activo(self):
        if not ES_WINDOWS:
            return False
        import subprocess
        r = subprocess.run(["schtasks", "/Query", "/TN", self.TAREA], capture_output=True,
                           creationflags=0x08000000)
        return r.returncode == 0

    def autoarranque(self, activo):
        """Crea o quita la tarea programada (la app ya corre como administrador)."""
        if not ES_WINDOWS:
            return
        import subprocess
        if activo:
            pythonw = sys.executable.replace("python.exe", "pythonw.exe")
            script = os.path.abspath(__file__)
            usuario = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}"
            orden = (f"$a = New-ScheduledTaskAction -Execute '{pythonw}' -Argument '\"{script}\"' "
                     f"-WorkingDirectory '{os.path.dirname(script)}'; "
                     f"$d = New-ScheduledTaskTrigger -AtLogOn -User '{usuario}'; "
                     "$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
                     "-ExecutionTimeLimit 0; "
                     f"$q = New-ScheduledTaskPrincipal -UserId '{usuario}' -LogonType Interactive -RunLevel Highest; "
                     f"Register-ScheduledTask -TaskName '{self.TAREA}' -Action $a -Trigger $d -Settings $s "
                     "-Principal $q -Force")
        else:
            orden = f"Unregister-ScheduledTask -TaskName '{self.TAREA}' -Confirm:$false"
        r = subprocess.run(["powershell", "-NoProfile", "-Command", orden], capture_output=True, text=True,
                           creationflags=0x08000000)
        log("Arranque automático:", activo, "->", r.returncode, r.stderr.strip()[:300])

    def cambiar_ancho(self, valor):
        global ANCHO
        ANCHO = int(valor)
        self.config["ancho"] = ANCHO
        for t in self.tarjetas:
            if t.ventana:
                t.ventana.setFixedWidth(ANCHO)
                t.ventana.resize(ANCHO, t.alto_natural(ANCHO))
        if self.modo == "widgets" and not self.manual:
            self.colocar(ignorar_guardadas=True, pantalla=self.pantalla_guardada())
        self.guardar_config()

    def cambiar_columnas(self, valor):
        global COLUMNAS
        COLUMNAS = int(valor)
        self.config["columnas"] = COLUMNAS
        if self.modo == "widgets" and not self.manual:
            self.colocar(ignorar_guardadas=True, pantalla=self.pantalla_guardada())
        self.guardar_config()

    def cambiar_intervalo(self, valor):
        global INTERVALO
        INTERVALO = float(valor)
        self.config["intervalo"] = INTERVALO
        self.guardar_config()

    def parpadear(self):
        """Avanza el parpadeo de los neones (solo si está activado en algún modo)."""
        activo = {k: self.tema[k]["neon"] and self.tema[k]["parpadeo"] for k in ("widgets", "panel")}
        if not any(activo.values()) and all(t.brillo == 1.0 for t in self.tarjetas):
            return
        ahora = time.monotonic()
        for t in self.tarjetas:
            if t.isVisible() and activo["panel" if t.relleno == "claro" else "widgets"]:
                t.tic_parpadeo(ahora)
            elif t.brillo != 1.0:
                t.brillo = 1.0
                t.update()

    # --- tiempo ------------------------------------------------------------------

    def elegir_ciudad(self, padre=None):
        dlg = DialogoCiudad(padre)
        if dlg.exec() and dlg.elegida:
            self.config["tiempo_ciudad"] = dlg.elegida
            self.tiempo.cambiar_ciudad(dlg.elegida)
            self.guardar_config()

    def actualizar_tiempo(self):
        t = self.tm
        if self.tiempo.version == t["version"]:
            return
        t["version"] = self.tiempo.version
        d, c = self.tiempo.datos, self.tiempo.ciudad
        if d:
            texto, icono = describir(d["codigo"], d["dia"])
            texto = _(texto)
            t["icono"].poner(icono)
            t["icono"].setVisible(t["icono"].parentWidget().width() >= 220)
            t["temp"].setText(f"{d['temp']:.0f} °C")
            t["desc"].setText(texto)
            t["detalle"].setText(_("Sensación {s}° · Humedad {h} % · Viento {v} km/h · Sol {a}–{b}").format(
                s=f"{d['sensacion']:.0f}", h=f"{d['humedad']:.0f}", v=f"{d['viento']:.0f}", a=d["salida"], b=d["puesta"]))
            t["horas"].poner(d["horas"])
            t["dias"].poner(d["dias"])
        else:
            t["temp"].setText("—")
            t["desc"].setText(_("Cargando…") if not self.tiempo.error else "")
            t["detalle"].setText(self.tiempo.error or "")
        lugar = c["nombre"] + (f" · {d['leido']}" if d else "")
        t["ciudad"].setText(lugar + (_(" · sin conexión") if self.tiempo.error and d else ""))
        self.ajustar_alturas()

    # --- Discord ----------------------------------------------------------------

    def conectar_discord(self, padre=None):
        # La aplicación de serie solo sirve si este MoonDeck trae su secreto (versión para amigos).
        propio = self.discord.cfg.get("client_id")
        dlg = DialogoDiscord(propio or (CLIENT_ID_POR_DEFECTO if CLIENT_SECRET_POR_DEFECTO else ""), padre)
        if dlg.exec():
            ident, secreto = dlg.id.text().strip(), dlg.secreto.text().strip()
            if secreto or (CLIENT_SECRET_POR_DEFECTO and ident in ("", CLIENT_ID_POR_DEFECTO)):
                self.discord.configurar(ident or CLIENT_ID_POR_DEFECTO, secreto)

    def menu_discord(self, menu, padre=None):
        recientes = self.config.get("discord_recientes", [])
        if recientes and self.discord.estado == "conectado":
            sub = menu.addMenu(_("Entrar en un canal reciente"))
            for r in recientes:
                sub.addAction(f"{r['nombre']} · {r['servidor']}" if r["servidor"] else r["nombre"],
                              lambda _=False, i=r["id"]: self.discord.entrar(i))
        menu.addAction(_("Conectar con Discord…") if self.discord.estado == "sin_config"
                       else "Cambiar Client ID / Secret…", lambda: self.conectar_discord(padre))
        if self.discord.estado != "sin_config":
            menu.addAction(_("Desconectar de Discord (olvidar la autorización)"), self.discord.olvidar)
        menu.addSeparator()

    def menu_apps(self, menu, padre=None):
        v = self.apps_vista
        apps = v.apps()
        i, v.menu_indice = v.menu_indice, None
        menu.addAction(_("Añadir aplicación…"), lambda: self.anadir_apps(padre))
        if i is not None and i < len(apps):
            menu.addAction(_("Quitar {app}").format(app=apps[i]["nombre"]), lambda: self.mover_app(i, None))
            if i > 0:
                menu.addAction(_("Mover a la izquierda"), lambda: self.mover_app(i, i - 1))
            if i < len(apps) - 1:
                menu.addAction(_("Mover a la derecha"), lambda: self.mover_app(i, i + 1))
        sub = menu.addMenu(_("Color de los iconos"))
        for clave, nombre in lanzador.COLORES_ICONOS:
            a = sub.addAction(_(nombre), lambda _x=False, c=clave: self.color_apps(c))
            a.setCheckable(True)
            a.setChecked(self.config.get("apps_color", "original") == clave)
        menu.addSeparator()

    def anadir_apps(self, padre=None):
        apps = self.apps_vista.apps()
        dlg = SelectorApps({a["id"] for a in apps}, padre)
        if dlg.exec() == QDialog.Accepted:
            apps.extend(dlg.elegidas())
            self.apps_vista.cambiado()
            self.ajustar_alturas()

    def mover_app(self, i, destino):
        apps = self.apps_vista.apps()
        a = apps.pop(i)
        if destino is not None:
            apps.insert(destino, a)
        self.apps_vista.cambiado()
        self.ajustar_alturas()

    def color_apps(self, modo):
        self.config["apps_color"] = modo
        self.apps_vista.cambiado()

    def recordar_canal(self, canal):
        recientes = [r for r in self.config.get("discord_recientes", []) if r["id"] != canal["id"]]
        recientes.insert(0, {"id": canal["id"], "nombre": canal["nombre"], "servidor": canal["servidor"],
                             "guild_id": canal.get("guild_id")})
        if recientes[:8] != self.config.get("discord_recientes"):
            self.config["discord_recientes"] = recientes[:8]
            self.guardar_config()

    def vigilar_discord(self):
        self.discord.vigilar(self.config["discord"]["servidores"])

    def cambiar_discord(self, **cambios):
        self.config["discord"].update(cambios)
        self.guardar_config()
        self.vigilar_discord()
        self.dc["version"] = None

    def abrir_discord(self):
        self.discord_no_instalado = not abrir_discord()
        if not self.discord_no_instalado:
            self.discord_abriendo = time.monotonic()
            self.discord._despertar.set()
        self.dc["version"] = None

    def entrar_ultimo_discord(self):
        recientes = self.config.get("discord_recientes", [])
        if recientes:
            self.discord.entrar(recientes[0]["id"])

    def al_conectar_discord(self, s):
        """Tras abrir Discord desde el widget: entra en el último canal o donde haya gente."""
        if not self.discord_abriendo or time.monotonic() - self.discord_abriendo > 120:
            self.discord_abriendo = 0
            return
        if s["estado"] != "conectado" or (s["canales_voz"] is None and self.config["discord"]["servidores"]):
            return  # aún arrancando o sin haber mirado los canales
        self.discord_abriendo = 0
        accion = self.config["discord"]["al_abrir"]
        if s["canal"]:
            return
        if accion == "ultimo":
            self.entrar_ultimo_discord()
        elif accion == "gente":
            canales = [c for c in s["canales_voz"] or [] if c["personas"]]
            if canales:
                self.discord.entrar(max(canales, key=lambda c: len(c["personas"]))["id"])

    def boton_canal_discord(self, c, con_servidor):
        b = QPushButton()
        b.setProperty("estilo", "dispositivo")
        b.setCursor(Qt.PointingHandCursor)
        textos = QVBoxLayout(b)
        textos.setContentsMargins(8, 5, 8, 5)
        textos.setSpacing(0)
        nombre = etiqueta("", "sub")
        nombre.setStyleSheet("font-weight: 600;")
        recortar(nombre, f"🔊 {c['nombre']}" + (f" · {len(c['personas'])}" if c["personas"] else ""), ANCHO - 48)
        textos.addWidget(nombre)
        lineas = ([", ".join(c["personas"])] if c["personas"] else []) + \
                 ([c["servidor"]] if con_servidor and c["servidor"] else [])
        for texto in lineas:
            lb = etiqueta("", "dim")
            recortar(lb, texto, ANCHO - 48)
            textos.addWidget(lb)
        for lb in b.findChildren(QLabel):
            lb.setAttribute(Qt.WA_TransparentForMouseEvents)
        b.setMinimumHeight(textos.sizeHint().height())
        b.clicked.connect(lambda _=False, i=c["id"]: self.discord.entrar(i))
        return b

    def actualizar_discord(self):
        d = self.dc
        s = self.discord.instantanea()
        if s["version"] == d["version"]:
            return
        d["version"] = s["version"]
        estado, canal = s["estado"], s["canal"]
        textos = {
            "sin_config": _("Conecta el widget con tu cuenta para ver y controlar tu canal de voz."),
            "desconectado": _("Discord no está abierto."),
            "conectando": _("Conectando con Discord…"),
            "autorizando": _("Mira Discord: te está pidiendo que autorices el widget."),
        }
        aviso = s["error"] if estado == "error" else textos.get(estado, "")
        if estado == "desconectado" and self.discord_abriendo:
            aviso = _("Abriendo Discord…")
        elif estado == "desconectado" and self.discord_no_instalado:
            aviso = _("No encuentro Discord instalado.")
        elif estado == "conectado" and not canal:
            aviso = (_("Elige tu servidor de Discord en Configuración > Widgets.")
                     if not self.config["discord"]["servidores"] else
                     _("Buscando canales…") if s["canales_voz"] is None else
                     _("Nadie en voz ahora mismo.") if not any(c["personas"] for c in s["canales_voz"]) else "")
        elif estado == "conectado" and s["error"]:
            aviso = s["error"]
        self.al_conectar_discord(s)
        d["aviso"].setText(aviso)
        d["aviso"].setVisible(bool(aviso))
        d["conectar"].setVisible(estado in ("sin_config", "error"))
        d["abrir"].setVisible(estado == "desconectado")
        d["abrir"].setEnabled(not self.discord_abriendo)
        en_canal = estado == "conectado" and bool(canal)

        # Sin canal: los canales de voz de mi servidor para entrar con un clic.
        canales = (s["canales_voz"] or []) if estado == "conectado" and not canal else []
        ids = [(c["id"], tuple(c["personas"])) for c in canales]
        if ids != d["canales_ids"]:
            d["canales_ids"] = ids
            while d["caja_canales"].count():
                d["caja_canales"].takeAt(0).widget().deleteLater()
            varios = len({c["guild_id"] for c in canales}) > 1
            botones = [self.boton_canal_discord(c, varios) for c in canales]
            for b in botones:
                d["caja_canales"].addWidget(b)
            # Si no caben, se quitan antes los vacíos (los últimos primero) y luego los demás.
            vacios = [b for b, c in zip(botones, canales) if not c["personas"]]
            llenos = [b for b, c in zip(botones, canales) if c["personas"]]
            d["tarjeta"].prescindibles_grupo("canales", vacios[::-1] + llenos[::-1], 1)
        d["canales"].setVisible(bool(canales))
        recientes = self.config.get("discord_recientes", [])
        ultimo = (estado == "conectado" and not canal and not self.config["discord"]["servidores"]
                  and bool(recientes))
        if ultimo:
            d["ultimo"].setText(_("Entrar en {canal}").format(canal=recientes[0]["nombre"]))
        d["ultimo"].setVisible(ultimo)
        recortar(d["canal"], f"🔊 {canal['nombre']}" if en_canal else _("Sin canal de voz"), ANCHO - 32)
        recortar(d["servidor"], canal["servidor"] if en_canal else "", ANCHO - 32)
        d["servidor"].setVisible(en_canal and bool(canal["servidor"]))
        d["controles"].setVisible(estado == "conectado")
        d["salir"].setEnabled(en_canal)
        if en_canal and canal["servidor"]:
            self.recordar_canal(canal)
        miembros = s["miembros"] if en_canal else []
        ids = [m["id"] for m in miembros]
        if ids != d["ids"]:
            d["ids"] = ids
            for f in d["filas"].values():
                f.deleteLater()
            d["filas"] = {}
            for m in miembros:
                f = FilaDiscord(self.discord, m["id"], m["id"] == s["yo"])
                d["caja_lista"].addWidget(f)
                d["filas"][m["id"]] = f
            # Si no caben todos, se quitan los últimos de la lista.
            d["tarjeta"].prescindibles_grupo("miembros", list(d["filas"].values())[::-1], 1)
        for m in miembros:
            d["filas"][m["id"]].actualizar(m, m["id"] in s["hablando"], self.discord.avatares.get(m["avatar"]))
        d["lista"].setVisible(bool(miembros))
        a = s["ajustes"]
        d["mute"].setChecked(bool(a.get("mute")))
        d["mute"].setText(_("Micro silenciado") if a.get("mute") else _("Silenciar"))
        d["deaf"].setChecked(bool(a.get("deaf")))
        d["deaf"].setText(_("Ensordecido") if a.get("deaf") else _("Ensordecer"))
        for clave in ("entrada", "salida"):
            sl, val, envio = d[clave]
            v = a.get(clave)
            if v is not None and time.monotonic() - getattr(sl, "_tocado", 0) > 1.5 and not envio.isActive() \
                    and not sl.isSliderDown():
                sl._actualizando = True
                sl.setValue(round(v))
                sl._actualizando = False
            val.setText(f"{sl.value()} %")
        self.ajustar_alturas()

    # --- test de velocidad -----------------------------------------------------

    @staticmethod
    def fmt_mbps(v):
        return f"{v:.0f} Mbps" if v >= 100 else f"{v:.1f} Mbps"

    def iniciar_test(self):
        self.test.iniciar()
        self.t_velocidad.start()
        self.actualizar_velocidad()

    def actualizar_velocidad(self):
        t = self.test
        r = t.resultado
        if t.midiendo:
            p = t.parcial
            fase = {"ping": _("Midiendo ping…"), "bajada": _("Midiendo bajada…"),
                    "subida": _("Midiendo subida…")}.get(t.fase, _("Preparando…"))
            self.vel_estado.setText(fase)
            # La escala crece si hace falta (como el cambio de rango de un velocímetro), nunca encoge.
            self._vel_tope = max(getattr(self, "_vel_tope", 0) or 0,
                                 velocimetro.tope(t.actual if t.fase in ("bajada", "subida") else 0,
                                                  p.get("bajada")))
            if t.fase == "ping" or not t.fase:
                self.vel_reloj.poner(0, self._vel_tope, "…", _("PING"), "amarillo", t.progreso, "ms")
            else:
                self.vel_reloj.poner(t.actual or 0, self._vel_tope, self.fmt_cifra(t.actual),
                                     (_("Bajada") if t.fase == "bajada" else _("Subida")).upper(),
                                     "azul" if t.fase == "bajada" else "morado", t.progreso)
            partes = [f"↓ {self.fmt_mbps(p['bajada'])}" if "bajada" in p else None,
                      f"ping {p['ping']:.0f} ms" if "ping" in p else None]
            self.vel_resto.setText(" · ".join(x for x in partes if x) or " ")
            self.vel_boton.setEnabled(False)
            self.vel_boton.setText(_("Midiendo…"))
            return
        self.t_velocidad.stop()
        self._vel_tope = 0
        self.vel_boton.setEnabled(True)
        self.vel_boton.setText(_("Repetir test") if r else _("Iniciar test"))
        if r and r is not self.config.get("velocidad"):
            self.config["velocidad"] = r
            self.guardar_config()
        if r:
            self.vel_reloj.poner(r["bajada"], velocimetro.tope(r["bajada"]), self.fmt_cifra(r["bajada"]),
                                 _("Bajada").upper())
            self.vel_resto.setText(f"↑ {self.fmt_mbps(r['subida'])} · ping {r['ping']:.0f} ms")
        else:
            self.vel_reloj.poner(0, 100, "—", _("Bajada").upper())
            self.vel_resto.setText(_("↑ — · ping —"))
        if t.error:
            self.vel_estado.setText(t.error)
        else:
            self.vel_estado.setText(_("Último test: {fecha} · servidores de Cloudflare").format(fecha=r["fecha"]) if r else
                                    _("Mide ping, bajada y subida (unos 15 s)."))

    def cambiar_velocimetro(self, estilo):
        self.config["velocimetro"] = estilo
        self.vel_reloj.estilo = estilo
        self.vel_reloj.update()
        self.guardar_config()

    @staticmethod
    def fmt_cifra(v):
        if not v:
            return "0"
        return f"{v:.0f}" if v >= 100 else f"{v:.1f}"

    # --- multimedia ---------------------------------------------------------

    def actualizar_multimedia(self):
        m = self.multimedia
        if not m:
            return
        # Reproductores: se rehacen las filas solo si cambian las apps.
        lista = self.reproductores.leer()[:MAX_REPRODUCTORES]
        claves = [d["id"] for d in lista]
        if claves != m["claves_rep"]:
            m["claves_rep"] = claves
            for f in m["filas_rep"]:
                f.deleteLater()
            m["filas_rep"] = [FilaReproductor(self.reproductores) for _x in lista]
            for f in m["filas_rep"]:
                m["caja_rep"].addWidget(f)
            # Si no cabe todo, lo que suena (el primero) es lo último que se quita.
            m["tarjeta"].prescindibles_grupo("reproductores", m["filas_rep"][:0:-1], 2)
        for f, d in zip(m["filas_rep"], lista):
            f.actualizar(d)
        m["reproductores"].setVisible(bool(lista))
        m["nada"].setVisible(not lista)

        # Mezclador: volumen general + una fila por app con sonido.
        datos = self.mezclador.leer()
        if datos:
            apps = datos["apps"][:MAX_APPS_VOLUMEN]
            claves = [datos["dispositivo"]] + [a[0] for a in apps]
            if claves != m["claves_vol"]:
                m["claves_vol"] = claves
                for f in m["filas_vol"]:
                    f.deleteLater()
                m["filas_vol"] = [FilaVolumen(self.mezclador, None, _("General"))]
                m["filas_vol"] += [FilaVolumen(self.mezclador, nombre, nombre) for nombre, _x, _x in apps]
                for f in m["filas_vol"]:
                    m["caja_vol"].addWidget(f)
                m["tarjeta"].prescindibles_grupo("volumen", m["filas_vol"][::-1], 1)
            m["filas_vol"][0].actualizar(*datos["general"])
            for f, (_x, vol, mute) in zip(m["filas_vol"][1:], apps):
                f.actualizar(vol, mute)
            m["seccion_vol"].setText(_("VOLUMEN") + f" · {datos['dispositivo'].upper()}")
            recortar(m["seccion_vol"], m["seccion_vol"].text(), ANCHO - 32)
        m["volumen"].setVisible(bool(datos))
        m["seccion_vol"].setVisible(bool(datos))
        errores = [e for e in (self.reproductores.error, self.mezclador.error) if e]
        m["aviso"].setText("\n".join(errores))
        m["aviso"].setVisible(bool(errores))
        self.ajustar_alturas()


def main():
    if ES_WINDOWS:
        # Icono propio en la barra de tareas/bandeja en lugar del de Python.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MoonDeck")
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setFont(QFont("Segoe UI Variable Text" if ES_WINDOWS else qapp.font().family(), 10))
    try:
        qapp.monitor = Monitor(qapp)  # mantener la referencia viva
    except Exception:
        _excepthook(*sys.exc_info())
        sys.exit(1)
    log("En marcha.")
    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
