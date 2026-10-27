"""Pack Ocio (Linux): los minijuegos."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import juegos
from idioma import _

WIDGETS = ('juegos',)


class VistaJuego(Dibujo):
    """El minijuego en marcha (juegos.py): le pasa el ratón y el teclado y lo redibuja
    cuando lo pide (cada frame mientras se mueve algo, cada segundo con el cronómetro)."""

    TECLAS = {Gdk.KEY_Left: "izquierda", Gdk.KEY_a: "izquierda", Gdk.KEY_Right: "derecha", Gdk.KEY_d: "derecha",
              Gdk.KEY_Up: "arriba", Gdk.KEY_w: "arriba", Gdk.KEY_Down: "abajo", Gdk.KEY_s: "abajo",
              Gdk.KEY_space: "espacio", Gdk.KEY_n: "n"}

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.poner_alto(80, 280)  # en una celda pequeña se dibuja en pequeño, sin cortar
        self.set_vexpand(True)
        self.set_can_focus(True)
        self.add_events(Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.KEY_RELEASE_MASK)
        self._timer = None
        self.connect("draw", self.dibujar)
        self.connect("button-press-event", self._pulsar)
        self.connect("button-release-event", self._soltar)
        self.connect("key-press-event", lambda _w, ev: self._tecla(ev, True))
        self.connect("key-release-event", lambda _w, ev: self._tecla(ev, False))
        self.connect("map", lambda _w: self._programar())
        cfg = app.config.setdefault("juegos", {})
        self.poner(cfg.get("actual", "buscaminas"))

    def poner(self, nombre):
        cfg = self.app.config.setdefault("juegos", {})
        cfg["actual"] = nombre
        self.juego = juegos.crear(nombre, cfg.setdefault(nombre, {}), self.app.guardar_config)
        self.queue_draw()
        self._programar()

    def nueva(self):
        self.juego.nueva()
        self.queue_draw()
        self._programar()

    def _programar(self):
        ms = self.juego.siguiente_frame()
        if ms and self._timer is None and self.get_mapped():
            self._timer = GLib.timeout_add(ms, self._frame)

    def _frame(self):
        self._timer = None
        self.queue_draw()
        self._programar()
        return False

    def _pulsar(self, _w, ev):
        tarjeta = self.get_ancestor(Tarjeta)
        if tarjeta and tarjeta.en_edicion():
            return False
        if ev.type != Gdk.EventType.BUTTON_PRESS:
            return ev.button == 1  # los dobles clics llegan además como un evento aparte
        if ev.button == 1:
            self.grab_focus()  # para las flechas y el espacio
        usado = self.juego.pulsar(ev.x, ev.y, ev.button)
        self.queue_draw()
        self._programar()
        return usado or ev.button == 1  # el clic derecho que no usa el juego abre el menú

    def _soltar(self, _w, ev):
        usado = self.juego.soltar(ev.x, ev.y, ev.button)
        self.queue_draw()
        self._programar()
        return usado

    def _tecla(self, ev, pulsada):
        nombre = self.TECLAS.get(Gdk.keyval_to_lower(ev.keyval))
        if nombre and self.juego.tecla(nombre, pulsada):
            self.queue_draw()
            self._programar()
            return True
        return False

    def dibujar(self, _w, cr):
        self.juego.dibujar(LienzoCairo(self, cr), paleta(), self.get_allocated_width(), self.get_allocated_height())


def construir(self, s):
    # Juegos: Buscaminas, 2048 y el dinosaurio de Chrome (se elige con el clic derecho).
    c = self.tarjeta("juegos", "Juegos")
    self.juego_vista = c.add_w(VistaJuego(self), expand=True)


def menu(self, tarjeta, menu):
    if tarjeta.clave == "juegos":
        sub = self.submenu(menu, "Juego")
        for clave, nombre in juegos.JUEGOS:
            self.item(sub, nombre, lambda c=clave: self.juego_vista.poner(c), self.juego_vista.juego.nombre == clave)
        self.item(menu, "Nueva partida", self.juego_vista.nueva)
        menu.append(Gtk.SeparatorMenuItem())
