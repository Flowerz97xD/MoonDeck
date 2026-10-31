"""Pack Ocio (Linux): los minijuegos."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import juegos
import minijuegos
from esferas import con_alfa, px_que_quepa
from idioma import _

WIDGETS = ('juegos',)


class VistaJuego(Dibujo):
    """El minijuego en marcha (juegos.py): le pasa el ratón y el teclado y lo redibuja
    cuando lo pide (cada frame mientras se mueve algo, cada segundo con el cronómetro).
    Mientras algo se mueve, los frames van al ritmo de la pantalla (el reloj de frames de GTK):
    con un temporizador, aunque sea a 60 fps, no casan con los refrescos y a ratos uno se ve
    dos veces y otro ninguna (tirones en lo que va rápido)."""

    RAPIDO = 100  # ms: si el juego quiere frames más seguidos, al ritmo de la pantalla

    TECLAS = {Gdk.KEY_Left: "izquierda", Gdk.KEY_a: "izquierda", Gdk.KEY_Right: "derecha", Gdk.KEY_d: "derecha",
              Gdk.KEY_Up: "arriba", Gdk.KEY_w: "arriba", Gdk.KEY_Down: "abajo", Gdk.KEY_s: "abajo",
              Gdk.KEY_space: "espacio", Gdk.KEY_n: "n"}

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.poner_alto(80, 280)  # en una celda pequeña se dibuja en pequeño, sin cortar
        self.set_vexpand(True)
        self.set_can_focus(True)
        self.add_events(Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.KEY_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK)  # algunos juegos siguen el ratón
        self._timer = None
        self._tic = None          # el aviso del reloj de frames, mientras algo se mueve
        self._ultimo = 0.0        # cuándo fue el último frame que se pidió
        self._t_frame = None      # la hora del frame que se va a dibujar
        self._hora_dibujada = 0.0
        self.connect("draw", self.dibujar)
        self.connect("button-press-event", self._pulsar)
        self.connect("button-release-event", self._soltar)
        self.connect("motion-notify-event", self._mover)
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
        if not ms or not self.get_mapped():
            return
        if ms < self.RAPIDO:
            if self._tic is None:
                self._tic = self.add_tick_callback(self._latido)
        elif self._timer is None and self._tic is None:
            self._timer = GLib.timeout_add(ms, self._frame)

    def _latido(self, _w, reloj_frames):
        """Cada refresco de la pantalla: se dibuja el frame siguiente si el juego lo quiere."""
        ms = self.juego.siguiente_frame()
        if not ms or ms >= self.RAPIDO or not self.get_mapped():
            self._tic = None
            GLib.idle_add(self._programar)  # (el temporizador, si ahora va más despacio)
            return GLib.SOURCE_REMOVE
        ahora = reloj_frames.get_frame_time()
        t = ahora / 1e6  # el mismo reloj que time.perf_counter (el monótono)
        try:
            periodo = reloj_frames.get_refresh_info(ahora)[0] / 1e6 or 1 / 60
        except Exception:  # noqa: BLE001
            periodo = 1 / 60
        if t - self._ultimo >= ms / 1000 - periodo * 0.5:  # el juego no quiere tantos (p. ej. 30 fps)
            self._ultimo = t
            self._t_frame = t + periodo  # cuando se verá
            self.queue_draw()
        return GLib.SOURCE_CONTINUE

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

    def _mover(self, _w, ev):
        if self.juego.mover(ev.x, ev.y):
            self.queue_draw()
            self._programar()
        return False

    def _tecla(self, ev, pulsada):
        nombre = self.TECLAS.get(Gdk.keyval_to_lower(ev.keyval))
        if nombre and self.juego.tecla(nombre, pulsada):
            self.queue_draw()
            self._programar()
            return True
        return False

    def dibujar(self, _w, cr):
        # La hora del frame (cuando se verá): todo avanza a pasos iguales. Nunca hacia atrás.
        t, self._t_frame = self._t_frame, None
        t = max(t or 0.0, time.perf_counter(), self._hora_dibujada)
        self._hora_dibujada = t
        juegos.poner_frame(t)
        try:
            self.juego.dibujar(LienzoCairo(self, cr), paleta(), self.get_allocated_width(), self.get_allocated_height())
        finally:
            juegos.poner_frame(None)


class SelectorJuegos:
    """Lo que sale al pulsar el título del widget: los juegos en fichas con su dibujo, el récord
    y las monedas que dan; un clic en una lo pone. Abajo, "Nueva partida". Es un menú de GTK
    con las fichas en cuadrícula: así se coloca, se cierra y va con el teclado como los demás."""

    COLUMNAS = 3
    FICHA = 112          # ancho de cada ficha (alto un poco más, por los textos)

    def __init__(self, vista):
        self.vista = vista
        self.menu = Gtk.Menu()
        filas = -(-len(juegos.JUEGOS) // self.COLUMNAS)
        for i, (clave, nombre) in enumerate(juegos.JUEGOS):
            item = Gtk.MenuItem()
            ficha = Gtk.DrawingArea()
            ficha.set_size_request(self.FICHA, round(self.FICHA * 1.18))
            ficha.connect("draw", self._dibujar, clave, nombre)
            item.add(ficha)
            item.connect("activate", lambda _i, c=clave: vista.poner(c))
            fila, col = divmod(i, self.COLUMNAS)
            self.menu.attach(item, col, col + 1, fila, fila + 1)
        nueva = Gtk.MenuItem(label="↻  " + _("Nueva partida"))
        nueva.get_child().set_xalign(0.5)
        nueva.connect("activate", lambda _i: vista.nueva())
        self.menu.attach(nueva, 0, self.COLUMNAS, filas, filas + 1)
        self.menu.show_all()

    def abrir(self, debajo_de, ev):
        self.menu.popup_at_widget(debajo_de, Gdk.Gravity.SOUTH_WEST, Gdk.Gravity.NORTH_WEST, ev)

    def _texto_record(self, clave):
        guardado = self.vista.app.config.get("juegos", {}).get(clave, {})
        if clave == "buscaminas":
            tiempos = guardado.get("records", {}).values()
            return _("Mejor: {n} s").format(n=min(tiempos)) if tiempos else ""
        record = guardado.get("record", 0)
        return _("Récord: {n}").format(n=record) if record else ""

    def _dibujar(self, ficha, cr, clave, nombre):
        l, pal = LienzoCairo(ficha, cr), paleta()
        w, h = ficha.get_allocated_width(), ficha.get_allocated_height()
        if clave == self.vista.juego.nombre:  # el que está puesto: con un borde
            l.rect(0, 0, w, h, 10, pal["azul"])
        # Fondo propio en todas: los colores van con el tema de MoonDeck, el menú con el del sistema
        l.rect(2, 2, w - 4, h - 4, 8, (0.97, 0.97, 0.98) if tema_claro() else (0.11, 0.12, 0.15))
        l.rect(2, 2, w - 4, h - 4, 8, con_alfa(pal["tenue"], 0.06))
        icono = w * 0.5
        minijuegos.dibujar_icono(clave, l, (w - icono) / 2, 8, icono, pal)
        texto = _(nombre)
        l.texto(texto, 4, 12 + icono, w - 8, 18, px_que_quepa(l, texto, w - 10, 13, "negrita"), pal["texto"], "negrita")
        record = self._texto_record(clave)
        if record:
            l.texto(record, 4, 30 + icono, w - 8, 15, 10.5, pal["gris"])
        if juegos.AL_GANAR is not None:  # las monedas, solo si hay mascota que las guarde
            monedas = _("hasta {n}").format(n=minijuegos.MONEDAS.get(clave, 0))
            tw, _th = l.medir(monedas, 10.5)
            mx = (w - tw - 14) / 2
            l.circulo(mx + 5, h - 12, 5, (1.0, 0.78, 0.2))
            l.circulo(mx + 5, h - 12, 2.6, (0.95, 0.62, 0.1))
            l.texto(monedas, mx + 14, h - 20, tw, 16, 10.5, pal["amarillo"], "normal", 0.0)
        return False


def titulo(self, tarjeta, ev):
    """Clic en el título de Juegos: el selector de juegos con fichas, en vez de una lista."""
    if tarjeta.clave == "juegos":
        self.selector_juegos = SelectorJuegos(self.juego_vista)  # (sin referencia, Python lo borraría)
        self.selector_juegos.abrir(tarjeta.lb_titulo, ev)
        return True
    return None


def construir(self, s):
    # Juegos: los minijuegos de juegos.py y minijuegos.py (se eligen con el clic en el título o el derecho).
    c = self.tarjeta("juegos", "Juegos")
    self.juego_vista = c.add_w(VistaJuego(self), expand=True)


def menu(self, tarjeta, menu):
    if tarjeta.clave == "juegos":
        # Los juegos, a la vista (sin submenú): se elige con un clic, también desde el título
        for clave, nombre in juegos.JUEGOS:
            self.item(menu, nombre, lambda c=clave: self.juego_vista.poner(c), self.juego_vista.juego.nombre == clave)
        menu.append(Gtk.SeparatorMenuItem())
        self.item(menu, "Nueva partida", self.juego_vista.nueva)
        menu.append(Gtk.SeparatorMenuItem())
