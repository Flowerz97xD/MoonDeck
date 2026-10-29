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
import instancia  # noqa: E402
if not instancia.unica(CARPETA):
    sys.exit(0)  # ya hay un MoonDeck abierto: se le ha pedido que se muestre
instancia.quieren_verme(CARPETA)  # un aviso viejo, de antes de abrir esta
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
    from PySide6.QtGui import (QBrush, QColor, QDesktopServices, QFont, QFontDatabase, QFontMetricsF,
                               QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                               QPolygonF)
    from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDoubleSpinBox,
                                   QFileDialog, QFileIconProvider, QFontComboBox, QFrame, QGraphicsOpacityEffect, QGridLayout,
                                   QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
                                   QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox,
                                   QStackedWidget, QStyle, QSystemTrayIcon, QToolButton, QTreeWidget,
                                   QTreeWidgetItem, QVBoxLayout, QWidget)

    from multimedia import Dispositivos, Mezclador, Reproductores
    import velocimetro
    import esferas
    import packs
    from sensores import ES_WINDOWS, Sampler
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


def pintar_fondo(p, perfil, rect, opacidad, prefijo="", solo_extras=False):
    """Fondo según el tema: el color o el degradado.
    `prefijo` = "panel_" para el fondo del panel entero. Con `solo_extras` (el
    acrílico ya pone el color) solo se pinta el degradado."""
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

def poner_visible(w, ver):
    """Muestra u oculta, pero sin volver a enseñar lo que la tarjeta quitó por falta de sitio:
    se vería un instante antes de que lo quite otra vez (parpadeo). Ya lo devuelve ella si cabe."""
    if getattr(w, "_quitado", False):
        if ver:
            return
        w._quitado = False
    w.setVisible(ver)


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
          "volumen": "\uE767", "silencio": "\uE74F", "micro": "\uE720", "micro_off": "\uEC54"}
ICONOS_UNICODE = {"anterior": "⏮", "play": "▶", "pausa": "⏸", "siguiente": "⏭",
                  "volumen": "🔊", "silencio": "🔇", "micro": "🎙", "micro_off": "🚫"}
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
            import dino_sprite
            import juegos
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


class ListaDesplazable(QScrollArea):
    """Una lista que se desplaza con la rueda si no cabe. Pide el alto de su contenido
    (para que la tarjeta mida lo justo) pero se conforma con `minimo`. Sin barra: el
    contenido se funde arriba o abajo cuando queda más por ese lado."""

    ESTIRA = True  # se queda con el alto que sobre en la tarjeta
    FUNDIDO = 22   # píxeles del degradado

    def __init__(self, contenido, minimo=30):
        super().__init__()
        self.minimo = minimo
        self.setWidget(contenido)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # la rueda sigue desplazando
        self.viewport().setAutoFillBackground(False)
        contenido.setAutoFillBackground(False)
        self.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        self._fundido = QGraphicsOpacityEffect(self)
        self._fundido.setEnabled(False)
        self.setGraphicsEffect(self._fundido)
        self.verticalScrollBar().valueChanged.connect(self._difuminar)
        self.verticalScrollBar().rangeChanged.connect(self._difuminar)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._difuminar()

    def _difuminar(self, *_x):
        sb = self.verticalScrollBar()
        arriba, abajo = sb.value() > 0, sb.value() < sb.maximum()
        self._fundido.setEnabled(arriba or abajo)
        if not (arriba or abajo):
            return
        h = max(1, self.height())
        f = min(0.45, self.FUNDIDO / h)
        mascara = QLinearGradient(0, 0, 0, h)
        for pos, alfa in ((0, 0 if arriba else 255), (f, 255), (1 - f, 255), (1, 0 if abajo else 255)):
            mascara.setColorAt(pos, QColor(0, 0, 0, alfa))
        self._fundido.setOpacityMask(QBrush(mascara))

    def sizeHint(self):
        return QSize(super().sizeHint().width(), self.widget().sizeHint().height())

    def minimumSizeHint(self):
        return QSize(0, self.minimo)


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

RELOJ_POR_DEFECTO = {"estilo": "digital", "h24": True, "segundos": True, "fecha": True,
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
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._fluido)
        self._timer.start(33)

    def _fluido(self):
        """Con agujas o anillos y segundero, se redibuja ~30 veces por segundo para que
        se muevan suaves (el resto de estilos cambia solo cada segundo)."""
        o = self.opciones
        if o["segundos"] and o["estilo"] in ("analogico", "anillos") and self.isVisible():
            self.update()

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
        alto_fecha = 0 if not o["fecha"] or (minimal and h < 140) else max(14, h * 0.16)
        hora = self.hora(ahora)
        extra = ahora.strftime("%S") if o["segundos"] and not minimal else ""
        ampm = "" if o["h24"] else ("AM" if ahora.hour < 12 else "PM")
        zona = QRectF(0, 0, w, h - 2 * alto_fecha)
        f = fuente_que_quepa(hora + (" 00" if extra or ampm else ""), w * 0.98, zona.height() * 0.92,
                             QFont.ExtraLight if minimal else QFont.Light, self.font())
        p.setFont(f)
        metr = p.fontMetrics()
        ancho_hora = metr.horizontalAdvance(hora)
        f2 = QFont(f)
        f2.setPixelSize(max(8, f.pixelSize() // 3))
        p.setPen(QColor(C_TEXTO))
        ancho_extra = (QFontMetricsF(f2).horizontalAdvance(extra or ampm) + f.pixelSize() * 0.12
                       if extra or ampm else 0)
        x0 = (w - ancho_hora - ancho_extra) / 2
        # La hora, centrada en el widget (la fecha va debajo, sin moverla).
        hueco = metr.capHeight() * 0.35
        arriba = max(0, (h - metr.capHeight()) / 2)
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
                       Qt.AlignHCenter | Qt.AlignVCenter, fecha_larga(ahora.date()))

    def minimal(self, p, ahora):
        self.digital(p, ahora, minimal=True)

    def analogico(self, p, ahora):
        w, h = self.width(), self.height()
        alto_fecha = 20 if self.opciones["fecha"] and h > 180 else 0
        r = min(w, h - 2 * alto_fecha) / 2 - 4
        c = QPointF(w / 2, h / 2)
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
        seg = ahora.second + ahora.microsecond / 1e6
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

# Estilo de los diálogos (elegir sensores, ciudad, apps...)
ESTILO_DIALOGO = """
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


def pulsar_teclas(*teclas):
    """Pulsa las teclas a la vez (códigos virtuales) y las suelta en orden inverso, con su
    código de tecla física: Windows no hace caso a Win+... si solo llega el código virtual."""
    if not ES_WINDOWS:
        return
    user32 = ctypes.windll.user32
    extendidas = {0x5B, 0x25, 0x26, 0x27, 0x28}  # Win y las flechas
    for t in teclas:
        user32.keybd_event(t, user32.MapVirtualKeyW(t, 0), 0x1 if t in extendidas else 0, 0)
        time.sleep(0.01)
    for t in reversed(teclas):
        user32.keybd_event(t, user32.MapVirtualKeyW(t, 0), 0x2 | (0x1 if t in extendidas else 0), 0)  # soltar


def cambiar_escritorio(paso):
    """Escritorio virtual siguiente (+1) o anterior (-1): pulsa Ctrl+Win+→/←."""
    pulsar_teclas(0x11, 0x5B, 0x27 if paso > 0 else 0x25)


def vista_escritorios():
    """La vista de tareas de Windows, con todos los escritorios: pulsa Win+Tab."""
    pulsar_teclas(0x5B, 0x09)


def area_panel(pantalla):
    """Dónde va el panel en una pantalla: sin tapar la barra de tareas. Si la barra se oculta
    sola, se deja libre 1 px en su borde: un panel que tape la pantalla entera es para
    Windows una app a pantalla completa, y la barra ya no sale al llevar el ratón al borde."""
    g = pantalla.availableGeometry()
    if g != pantalla.geometry() or not ES_WINDOWS:
        return g

    class DatosBarra(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint32), ("hWnd", ctypes.c_void_p), ("uCallbackMessage", ctypes.c_uint32),
                    ("uEdge", ctypes.c_uint32), ("rc", ctypes.c_long * 4), ("lParam", ctypes.c_ssize_t)]
    datos = DatosBarra(cbSize=ctypes.sizeof(DatosBarra))
    ABM_GETTASKBARPOS = 5
    try:
        if not ctypes.windll.shell32.SHAppBarMessage(ABM_GETTASKBARPOS, ctypes.byref(datos)):
            datos.uEdge = 3
    except (OSError, AttributeError):
        datos.uEdge = 3
    # uEdge: 0 izquierda, 1 arriba, 2 derecha, 3 abajo
    return g.adjusted(*{0: (1, 0, 0, 0), 1: (0, 1, 0, 0), 2: (0, 0, -1, 0)}.get(datos.uEdge, (0, 0, 0, -1)))


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
        self._pendiente = None    # la última posición del ratón aún sin aplicar al arrastre
        self._t_arrastre = QTimer(self, singleShot=True, interval=16)
        self._t_arrastre.timeout.connect(self._arrastrar)
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
        estirar = (isinstance(w, Grafica) or getattr(w, "ESTIRA", False)) and not self._estira
        self._estira = self._estira or estirar
        self.caja.addWidget(w, 1 if estirar else 0)
        if prescindible:
            w._prescindible, w._quitado = prescindible, False
            self.prescindibles.append(w)
        return w

    def poner_esquina(self, w):
        """Un botón pequeño a la derecha del título (p. ej. silenciar si el volumen no cabe).
        Empieza oculto: lo muestra quien lo pone."""
        cab = QWidget()
        fila = QHBoxLayout(cab)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(6)
        self.caja.replaceWidget(self.lb_titulo, cab)
        fila.addWidget(self.lb_titulo, 1)
        fila.addWidget(w)
        w.hide()
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

    def sin_fondo(self):
        """El usuario puede quitar el fondo y el borde de cada widget (solo queda el contenido)."""
        app = getattr(self, "app", None)
        return bool(app) and self.clave in app.config.get("sin_fondo", [])

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        perfil = self.perfil()
        self.radio = perfil["radio"]
        m = NEON_MARGEN if perfil["neon"] else 0
        r = QRectF(self.rect()).adjusted(m + 0.5, m + 0.5, -m - 0.5, -m - 0.5)
        ruta = QPainterPath()
        ruta.addRoundedRect(r, self.radio, self.radio)
        if self.sin_fondo():
            # Casi invisible, pero no del todo: en Windows los píxeles transparentes no reciben clics.
            p.fillPath(ruta, QColor(0, 0, 0, 1))
            if self.en_edicion():
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(acento(170), 1.5, Qt.DashLine))
                p.drawRoundedRect(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5), self.radio, self.radio)
            return
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
        if self._arrastre:
            # Como mucho unas 60 veces por segundo (los ratones mandan cientos de movimientos).
            self._pendiente = e.globalPosition().toPoint()
            if not self._t_arrastre.isActive():
                self._t_arrastre.start()
        else:
            self.setCursor(Qt.SizeFDiagCursor if self.en_asa(pos) else Qt.SizeAllCursor)

    def _arrastrar(self):
        if self._pendiente is None or not self._arrastre:
            return
        pos, self._pendiente = self._pendiente, None
        if self._arrastre == "mover":
            self.app.panel.arrastre_mover(self, pos, self._agarre)
        else:
            self.app.panel.arrastre_tam(self, pos)

    def mouseReleaseEvent(self, e):
        self._t_arrastre.stop()
        self._pendiente = e.globalPosition().toPoint()
        self._arrastrar()
        if self._arrastre == "mover":
            self.app.panel.soltar_mover(self, e.globalPosition().toPoint())
        elif self._arrastre == "tam":
            self.app.panel.soltar_tam(self)
        self._arrastre = None

    def wheelEvent(self, e):
        # La rueda sobre lo que no la usa (todo menos las barras deslizantes) cambia de escritorio.
        if not self.app.rueda(e):
            e.ignore()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.en_edicion():
            self._agarre = e.position().toPoint()
            self._arrastre = "tam" if self.en_asa(self._agarre) else "mover"
            if self._arrastre == "mover":
                self.raise_()
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
        if p["cristal"] and not self.tarjeta.sin_fondo():
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

    def wheelEvent(self, e):
        # La rueda sobre el fondo del panel también cambia de escritorio.
        if not self.app.rueda(e):
            e.ignore()

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
        # Ventana de herramienta (como los widgets sueltos): Windows la deja en todos los
        # escritorios virtuales; se queda en su pantalla (colocar_en).
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
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
        self.setGeometry(area_panel(pantalla))
        # Si cambia la barra de tareas (se mueve, se oculta sola...), se vuelve a colocar.
        if getattr(self, "_pantalla", None) is not pantalla:
            if getattr(self, "_pantalla", None):
                self._pantalla.availableGeometryChanged.disconnect(self._recolocar)
            self._pantalla = pantalla
            pantalla.availableGeometryChanged.connect(self._recolocar)

    def _recolocar(self, *_x):
        self.setGeometry(area_panel(self._pantalla))

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
        _, _, h, w = self.celdas[tarjeta.clave]
        fila, col = self.celda_en(esquina)
        self.poner_previa((min(fila, self.filas - 1), min(col, self.cols - w), h, w))

    def poner_previa(self, previa):
        """Cambia la vista previa repintando solo donde estaba y donde está (el panel ocupa
        toda la pantalla: repintarlo entero a cada movimiento del ratón va a tirones)."""
        if previa == self.previa:
            return
        for r in (self.previa, previa):
            if r:
                self.update(self.rect_celda(*r).adjusted(-4, -4, 4, 4))
        self.previa = previa

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
        self.poner_previa((fila, col, alto, ancho))

    def soltar_tam(self, tarjeta):
        if self.previa:
            _, _, alto, ancho = self.previa
            self.previa = None
            self.cambiar_tam(tarjeta, ancho, alto)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # El fondo del tema (color, opacidad) encima del cristal.
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


class DialogoCiudad(QDialog):
    """Buscar y elegir la ciudad del widget del tiempo."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setWindowTitle(_("Ciudad del tiempo"))
        self.setStyleSheet(ESTILO_DIALOGO + "QListWidget { background: #20232b; color: #e6e9ef; "
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
        w = t["widgets"]
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
    ESTILO = ESTILO_DIALOGO + """
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
        for _x, titulo, _y in self.PAGINAS:
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
        for clave, _x, intro in self.PAGINAS:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cont = QWidget()
            caja = QVBoxLayout(cont)
            caja.setContentsMargins(22, 18, 22, 22)
            caja.setSpacing(8)
            if intro:
                lb = QLabel(_(intro))
                lb.setObjectName("ayuda")
                lb.setWordWrap(True)
                caja.addWidget(lb)
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
        for texto, clave in (("Formato 24 horas", "h24"), ("Mostrar segundos", "segundos"), ("Mostrar la fecha", "fecha")):
            ch = QCheckBox()
            ch.setChecked(bool(o[clave]))
            ch.toggled.connect(lambda v, c=clave: app.cambiar_reloj(**{c: v}))
            self.fila(lista, texto, ch)
        nixie = QPushButton()
        nixie.setFixedSize(44, 28)
        nixie.setCursor(Qt.PointingHandCursor)

        def pintar_nixie():
            nixie.setStyleSheet(f"background: {o.get('nixie', esferas.NIXIE_POR_DEFECTO)}; "
                                "border: 1px solid #555; border-radius: 6px;")

        def elegir_nixie():
            app.elegir_color_nixie(self)
            pintar_nixie()
        pintar_nixie()
        nixie.clicked.connect(elegir_nixie)
        self.fila(lista, "Color de los tubos Nixie", nixie)

        packs.llamar(app.packs, "ajustes", self, caja)

    def pagina_titulos(self, caja):
        """Título (CPU, RELOJ…) y fondo con borde de cada widget, en una sola lista."""
        app = self.app
        lista = self.grupo(caja, "Cada widget", "Sin título se gana espacio; sin fondo ni borde, del widget "
                                                "solo se ve su contenido.")
        sin = app.config.get("sin_titulo", [])
        for t in app.tarjetas:
            botones = QHBoxLayout()
            botones.setSpacing(14)
            titulo = QCheckBox(_("Título"))
            titulo.setChecked(t.clave not in sin)
            titulo.toggled.connect(lambda v, t=t: app.alternar_titulo(t, v))
            fondo = QCheckBox(_("Fondo"))
            fondo.setChecked(not t.sin_fondo())
            fondo.toggled.connect(lambda v, t=t: app.alternar_fondo(t, v))
            botones.addWidget(titulo)
            botones.addWidget(fondo)
            self.fila(lista, t.nombre_menu, botones)

    def pagina_tarjetas(self, caja, s):
        lista = self.grupo(caja, "Fondo")
        self.fila(lista, "Color", self.color(s, "fondo"))
        self.fila(lista, "Opacidad", self.deslizador(s, "opacidad", 0, 100, 100), "0 % = solo cristal")
        self.fila(lista, "Degradado", self.interruptor(s, "degradado"), "Del color de fondo a un segundo color")
        self.fila(lista, "Segundo color", self.color(s, "fondo2"))
        self.fila(lista, "Dirección del degradado", self.deslizador(s, "angulo", 0, 360, 1, "°"))
        self.fila(lista, "Cristal acrílico", self.interruptor(s, "cristal"),
                  _("Desenfoca lo que hay detrás") + (_(" de las tarjetas") if s == "widgets" else _(" del panel")))
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
        s = "panel"
        lista = self.grupo(caja, "Fondo del panel", "El velo que cubre toda la pantalla en el modo panel.")
        self.fila(lista, "Color", self.color(s, "panel_fondo"))
        self.fila(lista, "Opacidad", self.deslizador(s, "panel_opacidad", 0, 100, 100), "0 % = solo cristal")
        self.pagina_tarjetas(caja, s)

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

        lista = self.grupo(caja, "Tamaño", "En el modo widgets.")
        ancho = QSpinBox()
        ancho.setRange(260, 560)
        ancho.setSingleStep(10)
        ancho.setValue(ANCHO)
        ancho.valueChanged.connect(self.app.cambiar_ancho)
        self.fila(lista, "Ancho de cada widget", ancho, "En píxeles")
        cols = QSpinBox()
        cols.setRange(1, 8)
        cols.setValue(COLUMNAS)
        cols.valueChanged.connect(self.app.cambiar_columnas)
        self.fila(lista, "Columnas al colocarlos", cols, "Las mínimas: si no caben en alto, se usan más")

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

    def pagina_packs(self, caja):
        """La tienda: borrar los widgets que no se usan y volver a descargarlos de GitHub."""
        app = self.app
        g = app.gestor_packs
        lista = self.grupo(caja, "Widgets", "Instala solo los que uses: bórralos cuando quieras y vuelve a "
                                             "descargarlos de GitHub. Se aplica al reiniciar MoonDeck.")
        for ident, nombre, texto, widgets, _x in packs.CATALOGO:
            if not packs.borrable(ident):
                control = QLabel(_("Incluido"))
                control.setObjectName("sub")
            elif g.ocupado_con == ident:
                control = QPushButton(_("Descargando…"))
                control.setEnabled(False)
            elif g.instalado(ident):
                control = QPushButton(_("Borrar"))
                control.setEnabled(not g.ocupado and not g.desde_codigo)
                if g.desde_codigo:
                    control.setToolTip(_("Ejecutando desde el código: aquí no se borra nada."))
                control.clicked.connect(lambda _x=False, i=ident: (g.borrar(i), self.construir()))
            else:
                control = QPushButton(_("Descargar"))
                control.setObjectName("aceptar")
                control.setEnabled(not g.ocupado)
                control.clicked.connect(lambda _x=False, i=ident: self.descargar_pack(i))
            self.fila(lista, nombre, control, _(texto) + ("" if widgets == (nombre,) else
                                                      "\n" + " · ".join(_(w) for w in widgets)))
        aviso = (_("No se pudo descargar: {error}").format(error=g.error) if g.estado == "error" else
                 _("Reinicia MoonDeck para ver los cambios.") if g.cambiado else "")
        if aviso:
            fila = QHBoxLayout()
            lb = QLabel(aviso)
            lb.setWordWrap(True)
            fila.addWidget(lb, 1)
            if g.cambiado and g.estado != "error":
                reiniciar = QPushButton(_("Reiniciar ahora"))
                reiniciar.setObjectName("aceptar")
                reiniciar.clicked.connect(lambda: app.actualizador.reiniciar(app.salir))
                fila.addWidget(reiniciar)
            caja.addLayout(fila)

    def descargar_pack(self, ident):
        self.app.gestor_packs.descargar(ident)
        self.construir()

        def mirar():
            if self.app.gestor_packs.ocupado:
                QTimer.singleShot(300, mirar)
            elif self.isVisible():
                self.construir()
        QTimer.singleShot(300, mirar)

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
        lista = self.grupo(caja, "Escritorios virtuales")
        c = QCheckBox()
        c.setChecked(app.config.get("rueda_escritorios", True))
        c.toggled.connect(lambda v: (app.config.__setitem__("rueda_escritorios", v), app.guardar_config()))
        self.fila(lista, "Cambiar de escritorio con la rueda del ratón", c,
                  "Girando la rueda sobre un widget (menos en las barras de volumen y similares). "
                  "Con Ctrl + rueda abajo, se ven todos los escritorios.")
        lista = self.grupo(caja, "Sensores")
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


# Los packs de widgets (pack_*.py): sus métodos se añaden a Monitor.
PACKS = packs.cargar(os.path.dirname(os.path.abspath(__file__)), log, CONFIG)


class Monitor(*[p.Metodos for p in PACKS if hasattr(p, "Metodos")]):
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
        for clave in ("immich", "docker"):
            if not self.config.get(f"{clave}_visto"):  # widgets nuevos: llegan ocultos
                self.config.setdefault("ocultos", []).append(clave)
                self.config[f"{clave}_visto"] = True
        global ANCHO, COLUMNAS, INTERVALO
        ANCHO = int(self.config.get("ancho", ANCHO))
        COLUMNAS = int(self.config.get("columnas", COLUMNAS))
        INTERVALO = float(self.config.get("intervalo", INTERVALO))
        self.ventana_config = None
        self.panel = None
        self.tarjetas = []
        self.aplicar_tema(guardar=False)
        self._rueda, self._rueda_t, self._rueda_ult = 0.0, 0.0, 0.0
        self.actualizador = Actualizador(os.path.dirname(os.path.abspath(__file__)))
        self.tiempo = Tiempo(self.config.get("tiempo_ciudad") or CIUDAD_POR_DEFECTO)
        self.actualizador.omitir = packs.omitidos(self.config.get("packs_borrados", []))
        self.gestor_packs = packs.Gestor(self.actualizador.carpeta, self.config, self.guardar_config)
        self.packs = PACKS
        packs.llamar(self.packs, "iniciar", self)
        self.manual = False  # True cuando el usuario arrastra un widget
        self.reproductores = Reproductores()
        self.mezclador = Mezclador()
        self.dispositivos = Dispositivos()
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
        packs.llamar(self.packs, "arrancar", self)
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
        self.t_aperturas = QTimer(interval=1000)
        self.t_aperturas.timeout.connect(self.mirar_aperturas)
        self.t_aperturas.start()
        if self.audio:
            self.t_audio = QTimer(interval=2000)
            self.t_audio.timeout.connect(self.actualizar_audio)
            self.t_audio.start()
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
            m["caja_vol"].addStretch()
            # El volumen por app se desplaza con la rueda si no cabe (en vez de quitar filas).
            m["scroll_vol"] = c.add(ListaDesplazable(m["volumen"]))
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
            # Silenciar el micro: arriba a la derecha, siempre a mano (antes era lo primero que se
            # quitaba). Pide lo contrario de lo que hay de verdad, no lo que diga el botón.
            a["mic"] = c.poner_esquina(boton_icono("micro", 10))
            a["mic"].clicked.connect(lambda: self.silenciar_mic(not a.get("mic_estado")))
            a["aviso"] = c.add(etiqueta("", "dim"))
            a["aviso"].setWordWrap(True)
            self.audio = a

        # Lo de los packs (pack_*.py)
        packs.llamar(self.packs, "construir", self, s)

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
        packs.llamar(self.packs, "visibles", self, {t.clave for t in self.visibles()})

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
        packs.llamar(self.packs, "acciones", self, menu, padre)
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
        if tarjeta.clave == "reloj":
            self.menu_reloj(menu)
        if tarjeta.clave == "calendario":
            sub = menu.addMenu(_("La semana empieza en"))
            for dia in (0, 6):
                a = sub.addAction(idioma.dia_semana(dia).capitalize(), lambda _x=False, d=dia: self.cambiar_semana(d))
                a.setCheckable(True)
                a.setChecked(self.primer_dia() == dia)
            menu.addSeparator()
        packs.llamar([p for p in self.packs if tarjeta.clave in getattr(p, "WIDGETS", ())], "menu", self, tarjeta, menu)
        if tarjeta.clave == "tiempo":
            menu.addAction(_("Cambiar ciudad…"), lambda: self.elegir_ciudad(tarjeta.window()))
            menu.addAction(_("Actualizar ahora"), self.tiempo._despertar.set)
            menu.addSeparator()
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
        a = menu.addAction(_("Mostrar fondo y borde"), lambda: self.alternar_fondo(tarjeta))
        a.setCheckable(True)
        a.setChecked(not tarjeta.sin_fondo())
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

        self.ultimo = s
        packs.llamar(self.packs, "aplicar", self, s)

        self.ajustar_alturas()

    def mirar_aperturas(self):
        if instancia.quieren_verme(CARPETA):  # la han vuelto a abrir: se muestra la que ya estaba
            for v in self.ventanas():
                v.setVisible(True)
                v.raise_()
                v.activateWindow()

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
        for texto, clave in (("Formato 24 horas", "h24"), ("Mostrar segundos", "segundos"), ("Mostrar la fecha", "fecha")):
            a = menu.addAction(_(texto), lambda _=False, c=clave: self.cambiar_reloj(**{c: not o[c]}))
            a.setCheckable(True)
            a.setChecked(o[clave])
        ciudades = menu.addMenu(_("Ciudades (reloj mundial, hasta 8)"))
        for nombre, zona in CIUDADES:
            a = ciudades.addAction(_(nombre), lambda _=False, z=zona: self.cambiar_reloj(zona=z))
            a.setCheckable(True)
            a.setChecked(zona in o["zonas"])
        if o["estilo"] == "nixie":
            actual = o.get("nixie", esferas.NIXIE_POR_DEFECTO)
            sub = menu.addMenu(_("Color de los tubos"))
            for color, nombre in esferas.COLORES_NIXIE:
                a = sub.addAction(_(nombre), lambda _x=False, c=color: self.cambiar_reloj(nixie=c))
                a.setCheckable(True)
                a.setChecked(actual == color)
            sub.addAction(_("Otro color…"), lambda: self.elegir_color_nixie())
        menu.addSeparator()

    def elegir_color_nixie(self, padre=None):
        c = QColorDialog.getColor(QColor(self.config["reloj"].get("nixie", esferas.NIXIE_POR_DEFECTO)), padre,
                                  _("Color de los tubos"))
        if c.isValid():
            self.cambiar_reloj(nixie=c.name())

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
            a["mic_estado"] = bool(mic)
            a["mic"].setVisible(mic is not None)
            poner_icono(a["mic"], "micro_off" if mic else "micro", 10)
            a["mic"].setStyleSheet(f"color: {COLORES['rojo'].name()};" if mic else "")
            a["mic"].setToolTip(_("Micrófono silenciado · clic para activar") if mic else _("Silenciar micrófono"))
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

    def alternar_fondo(self, tarjeta, mostrar=None):
        sin = self.config.setdefault("sin_fondo", [])
        if mostrar is None:
            mostrar = tarjeta.clave in sin
        if mostrar and tarjeta.clave in sin:
            sin.remove(tarjeta.clave)
        elif not mostrar and tarjeta.clave not in sin:
            sin.append(tarjeta.clave)
        if tarjeta.ventana:
            tarjeta.ventana.aplicar_tinte()
        tarjeta.update()
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

    # --- escritorios virtuales -------------------------------------------------------

    def rueda(self, e):
        """Rueda abajo: escritorio siguiente; arriba: el anterior; Ctrl + rueda abajo: todos
        los escritorios. En los touchpads (giro
        en trocitos) se acumula, y como mucho cambia uno cada 0,3 s."""
        if not self.config.get("rueda_escritorios", True) or not ES_WINDOWS:
            return False
        delta = -e.angleDelta().y() / 120
        if not delta:
            return False
        ahora = time.monotonic()
        if ahora - self._rueda_ult > 0.6:  # un giro nuevo: lo de antes no cuenta
            self._rueda = 0.0
        self._rueda_ult = ahora
        self._rueda += delta
        if abs(self._rueda) >= 1 and ahora - self._rueda_t > 0.3:
            if e.modifiers() & Qt.ControlModifier:
                if self._rueda > 0:  # Ctrl + rueda abajo: la vista con todos los escritorios
                    vista_escritorios()
            else:
                cambiar_escritorio(1 if self._rueda > 0 else -1)
            self._rueda, self._rueda_t = 0.0, ahora
        e.accept()
        return True

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
                for i, f in enumerate(m["filas_vol"]):
                    m["caja_vol"].insertWidget(i, f)  # antes del hueco final
                m["scroll_vol"].updateGeometry()
            m["filas_vol"][0].actualizar(*datos["general"])
            for f, (_x, vol, mute) in zip(m["filas_vol"][1:], apps):
                f.actualizar(vol, mute)
            m["seccion_vol"].setText(_("VOLUMEN") + f" · {datos['dispositivo'].upper()}")
            recortar(m["seccion_vol"], m["seccion_vol"].text(), ANCHO - 32)
        m["scroll_vol"].setVisible(bool(datos))
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
