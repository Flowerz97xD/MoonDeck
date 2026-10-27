"""Pack Ocio (Windows): los minijuegos."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import juegos
from idioma import _

WIDGETS = ('juegos',)


class VistaJuego(QWidget):
    """El minijuego en marcha (juegos.py): le pasa el ratón y el teclado y lo redibuja
    cuando lo pide (cada frame mientras se mueve algo, cada segundo con el cronómetro)."""

    ESTIRA = True  # crece con la tarjeta (Tarjeta.add)

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
        return QSize(M.ANCHO - 32, 280)

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


def construir(self, s):
    # Juegos: Buscaminas, 2048 y el dinosaurio de Chrome (se elige con el clic derecho).
    c = self.tarjeta("juegos", "Juegos")
    self.juego_vista = VistaJuego(self)
    c.add(self.juego_vista)
    c._estira = True


def menu(self, tarjeta, menu):
    if tarjeta.clave == "juegos":
        sub = menu.addMenu(_("Juego"))
        for clave, nombre in juegos.JUEGOS:
            a = sub.addAction(_(nombre), lambda _x=False, c=clave: self.juego_vista.poner(c))
            a.setCheckable(True)
            a.setChecked(self.juego_vista.juego.nombre == clave)
        menu.addAction(_("Nueva partida"), self.juego_vista.nueva)
        menu.addSeparator()
