"""Pack Ocio (Windows): los minijuegos."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import juegos
import minijuegos
from esferas import con_alfa, px_que_quepa
from idioma import _

WIDGETS = ('juegos',)


class Refresco(QObject):
    """Avisa en cada refresco (vsync) de la pantalla donde está el juego, desde un hilo que espera
    al refresco de verdad (D3DKMTWaitForVerticalBlankEvent). Con un temporizador, aunque sea a
    60 fps, los frames no casan con los refrescos de la pantalla: a ratos uno se ve dos veces y
    otro ninguna, y lo que se mueve rápido va a tirones. Si no se puede (sin Direct3D, en una
    máquina virtual...), ok es False y se usa el temporizador."""

    latido = Signal(float, float)   # cuándo ha sido el refresco y cada cuánto hay uno (s)

    class _Abrir(ctypes.Structure):
        _fields_ = [("hDc", ctypes.c_void_p), ("hAdapter", ctypes.c_uint), ("luid_bajo", ctypes.c_uint32),
                    ("luid_alto", ctypes.c_int32), ("VidPnSourceId", ctypes.c_uint)]

    class _Esperar(ctypes.Structure):
        _fields_ = [("hAdapter", ctypes.c_uint), ("hDevice", ctypes.c_uint), ("VidPnSourceId", ctypes.c_uint)]

    class _InfoMonitor(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint32), ("rcMonitor", ctypes.c_long * 4), ("rcWork", ctypes.c_long * 4),
                    ("dwFlags", ctypes.c_uint32), ("szDevice", ctypes.c_wchar * 32)]

    def __init__(self):
        super().__init__()
        self.ok = sys.platform == "win32" and hasattr(ctypes.windll.gdi32, "D3DKMTWaitForVerticalBlankEvent")
        self.pantalla = None          # \\.\DISPLAYn de la ventana del juego
        self.activo = threading.Event()
        self.vivo = True
        if self.ok:
            threading.Thread(target=self._bucle, daemon=True, name="vsync").start()

    def pantalla_de(self, hwnd):
        """La pantalla (nombre de GDI) donde está la ventana."""
        user32 = ctypes.windll.user32
        user32.MonitorFromWindow.restype = ctypes.c_void_p
        user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        info = self._InfoMonitor()
        info.cbSize = ctypes.sizeof(info)
        if user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(info)):
            self.pantalla = info.szDevice

    def _abrir(self, pantalla):
        gdi32 = ctypes.windll.gdi32
        gdi32.CreateDCW.restype = ctypes.c_void_p
        gdi32.CreateDCW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p]
        gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
        hdc = gdi32.CreateDCW(pantalla, None, None, None)
        if not hdc:
            return None
        abrir = self._Abrir(hDc=hdc)
        estado = gdi32.D3DKMTOpenAdapterFromHdc(ctypes.byref(abrir))
        gdi32.DeleteDC(hdc)
        if estado != 0:
            return None
        return self._Esperar(hAdapter=abrir.hAdapter, hDevice=0, VidPnSourceId=abrir.VidPnSourceId)

    def _cerrar(self, espera):
        if espera:
            cerrar = ctypes.c_uint(espera.hAdapter)
            ctypes.windll.gdi32.D3DKMTCloseAdapter(ctypes.byref(cerrar))

    def _bucle(self):
        gdi32 = ctypes.windll.gdi32
        espera, abierta, antes, periodo, fallos = None, None, 0.0, 1 / 60, 0
        while self.vivo:
            if not self.activo.wait(0.5):
                continue
            if self.pantalla != abierta:
                self._cerrar(espera)
                abierta, espera = self.pantalla, self._abrir(self.pantalla) if self.pantalla else None
            if espera is None or gdi32.D3DKMTWaitForVerticalBlankEvent(ctypes.byref(espera)) != 0:
                fallos += 1
                if fallos > 20:     # no va: que siga el temporizador
                    self.ok = False
                    self._cerrar(espera)
                    return
                time.sleep(0.016)
                abierta = None
                continue
            fallos = 0
            ahora = time.perf_counter()
            if 0.002 < ahora - antes < 0.1:  # cada cuánto refresca (suavizado)
                periodo += (ahora - antes - periodo) * 0.1
            antes = ahora
            if self.activo.is_set():
                self.latido.emit(ahora, periodo)


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
        self.setMouseTracking(True)  # algunos juegos siguen el ratón (Atrapa la comida, Faltas)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        # Preciso: el normal de Windows va a saltos de ~16 ms y un frame de 16 ms salía de 16 o de 31
        self.timer.setTimerType(Qt.PreciseTimer)
        self._ultimo = 0.0
        self.timer.timeout.connect(self._frame)
        self._t_frame = None      # cuándo se verá el frame que se va a dibujar
        self._hora_dibujada = 0.0
        self._mirar_pantalla = 0.0
        self.refresco = Refresco()
        self.refresco.latido.connect(self._latido)
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
        if self.refresco.ok:
            if ms and self.isVisible():
                if not self.refresco.pantalla:
                    self.refresco.pantalla_de(int(self.window().winId()))
                self.refresco.activo.set()
            else:
                self.refresco.activo.clear()
            return
        if ms and not self.timer.isActive() and self.isVisible():
            # A ritmo fijo: lo que ha tardado el frame anterior se descuenta de la espera
            pasado = (time.perf_counter() - self._ultimo) * 1000
            self.timer.start(max(1, round(ms - pasado)) if pasado < ms else 1 if pasado < 2 * ms else ms)

    def _frame(self):
        self._ultimo = time.perf_counter()
        self.update()
        self._programar()

    def animando(self):
        return self.refresco.ok and self.refresco.activo.is_set()

    def _redibujar(self):
        """Tras un clic, una tecla o mover el ratón. Si el juego ya se mueve al ritmo de la
        pantalla, lo dibuja el siguiente refresco: dibujar ahora metería un frame a destiempo
        (con el ratón, cientos por segundo) y eso se ve como un tirón."""
        animando = self.animando()
        self._programar()
        if not animando:
            self.update()

    def _latido(self, t, periodo):
        """Un refresco de la pantalla: se dibuja el frame que se verá en el siguiente."""
        ms = self.juego.siguiente_frame()
        if not ms or not self.isVisible():
            self.refresco.activo.clear()
            if not self.refresco.ok:  # el hilo se ha rendido: al temporizador
                self._programar()
            return
        if t - self._ultimo < ms / 1000 - periodo * 0.5:  # el juego no quiere tantos (p. ej. 30 fps)
            return
        self._ultimo = t
        self._t_frame = t + periodo
        # Ya mismo y solo él: con update() saldría en el siguiente repintado de la ventana junto
        # con todo lo que esté pendiente (gráficas, reloj, la mascota...) y el frame llegaría tarde
        self.repaint()
        if t - self._mirar_pantalla > 1:  # por si la ventana se ha ido a otra pantalla
            self._mirar_pantalla = t
            self.refresco.pantalla_de(int(self.window().winId()))

    def showEvent(self, e):
        super().showEvent(e)
        self._programar()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.refresco.activo.clear()

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
        self._redibujar()
        if not (usado or boton == 1):
            e.ignore()  # el clic derecho que no usa el juego abre el menú de la tarjeta

    def mouseDoubleClickEvent(self, e):
        self.mousePressEvent(e)  # en Qt el segundo clic rápido llega como doble clic

    def mouseReleaseEvent(self, e):
        boton = self.BOTONES.get(e.button())
        pos = e.position()
        if not boton or not self.juego.soltar(pos.x(), pos.y(), boton):
            e.ignore()
        self._redibujar()

    def mouseMoveEvent(self, e):
        pos = e.position()
        if self.juego.mover(pos.x(), pos.y()):
            self._redibujar()

    def _tecla(self, e, pulsada):
        nombre = self.TECLAS.get(e.key())
        if e.isAutoRepeat() and nombre in ("espacio", "arriba", "abajo"):
            return  # mantener pulsado no repite el salto
        if nombre and self.juego.tecla(nombre, pulsada):
            self._redibujar()
        else:
            e.ignore()

    def keyPressEvent(self, e):
        self._tecla(e, True)

    def keyReleaseEvent(self, e):
        self._tecla(e, False)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # La hora del frame: cuando se verá (si llega tarde, la de ahora), sin volver nunca atrás
        t, self._t_frame = self._t_frame, None
        t = max(t or 0.0, time.perf_counter(), self._hora_dibujada)
        self._hora_dibujada = t
        juegos.poner_frame(t)
        try:
            self.juego.dibujar(LienzoQt(self, p), paleta(), self.width(), self.height())
        finally:
            juegos.poner_frame(None)


class SelectorJuegos(QWidget):
    """Lo que sale al pulsar el título del widget: los juegos en fichas con su dibujo, el récord
    y las monedas que dan; un clic en una lo pone. Abajo, "Nueva partida"."""

    COLUMNAS = 3
    FICHA = 112          # ancho de cada ficha (alto un poco más, por los textos)
    HUECO = 8
    PIE = 40             # la fila de abajo (Nueva partida)

    def __init__(self, vista):
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.vista = vista
        self.encima = None
        self.zonas = []     # (x, y, w, h, clave o "nueva")
        filas = -(-len(juegos.JUEGOS) // self.COLUMNAS)
        self.alto_ficha = round(self.FICHA * 1.18)
        self.setFixedSize(self.HUECO + self.COLUMNAS * (self.FICHA + self.HUECO),
                          self.HUECO + filas * (self.alto_ficha + self.HUECO) + self.PIE)

    def abrir(self, punto):
        """En `punto` (abajo a la izquierda del título), sin salirse de la pantalla."""
        pantalla = QGuiApplication.screenAt(punto) or QGuiApplication.primaryScreen()
        zona = pantalla.availableGeometry()
        x = min(max(punto.x(), zona.left()), zona.right() - self.width())
        y = punto.y() if punto.y() + self.height() <= zona.bottom() else max(zona.top(), punto.y() - self.height() - 30)
        self.move(x, y)
        self.show()

    def _texto_record(self, clave):
        guardado = self.vista.app.config.get("juegos", {}).get(clave, {})
        if clave == "buscaminas":
            tiempos = guardado.get("records", {}).values()
            return _("Mejor: {n} s").format(n=min(tiempos)) if tiempos else ""
        record = guardado.get("record", 0)
        return _("Récord: {n}").format(n=record) if record else ""

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        l, pal = LienzoQt(self, p), paleta()
        claro = tema_claro()
        fondo = (0.97, 0.97, 0.98, 0.98) if claro else (0.11, 0.12, 0.15, 0.97)
        l.rect(0.5, 0.5, self.width() - 1, self.height() - 1, 12, con_alfa(pal["tenue"], 0.18))
        l.rect(1.5, 1.5, self.width() - 3, self.height() - 3, 11, fondo)
        actual = self.vista.juego.nombre
        con_monedas = juegos.AL_GANAR is not None  # solo si hay mascota que las guarde
        self.zonas = []
        for i, (clave, nombre) in enumerate(juegos.JUEGOS):
            x = self.HUECO + (i % self.COLUMNAS) * (self.FICHA + self.HUECO)
            y = self.HUECO + (i // self.COLUMNAS) * (self.alto_ficha + self.HUECO)
            w, h = self.FICHA, self.alto_ficha
            self.zonas.append((x, y, w, h, clave))
            if clave == actual:
                l.rect(x - 2, y - 2, w + 4, h + 4, 12, pal["azul"])  # el que está puesto: con un borde
                l.rect(x, y, w, h, 10, fondo)
            l.rect(x, y, w, h, 10, con_alfa(pal["tenue"], 0.13 if self.encima == clave else 0.06))
            icono = w * 0.5
            minijuegos.dibujar_icono(clave, l, x + (w - icono) / 2, y + 8, icono, pal)
            texto = _(nombre)
            l.texto(texto, x + 4, y + 12 + icono, w - 8, 18, px_que_quepa(l, texto, w - 10, 13, "negrita"),
                    pal["texto"], "negrita")
            record = self._texto_record(clave)
            if record:
                l.texto(record, x + 4, y + 30 + icono, w - 8, 15, 10.5, pal["gris"])
            if con_monedas:
                monedas = _("hasta {n}").format(n=minijuegos.MONEDAS.get(clave, 0))
                tw, _th = l.medir(monedas, 10.5)
                mx = x + (w - tw - 14) / 2
                l.circulo(mx + 5, y + h - 12, 5, (1.0, 0.78, 0.2))
                l.circulo(mx + 5, y + h - 12, 2.6, (0.95, 0.62, 0.1))
                l.texto(monedas, mx + 14, y + h - 20, tw, 16, 10.5, pal["amarillo"], "normal", 0.0)
        # Nueva partida
        bw, bh = 150, 28
        bx, by = (self.width() - bw) / 2, self.height() - self.PIE + (self.PIE - bh) / 2 - 4
        self.zonas.append((bx, by, bw, bh, "nueva"))
        l.rect(bx, by, bw, bh, bh / 2, con_alfa(pal["azul"], 0.55 if self.encima == "nueva" else 0.35))
        l.texto("↻  " + _("Nueva partida"), bx, by, bw, bh, 12.5, pal["texto"], "negrita")

    def _zona(self, pos):
        for x, y, w, h, clave in self.zonas:
            if x <= pos.x() <= x + w and y <= pos.y() <= y + h:
                return clave
        return None

    def mouseMoveEvent(self, e):
        encima = self._zona(e.position())
        if encima != self.encima:
            self.encima = encima
            self.setCursor(Qt.PointingHandCursor if encima else Qt.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, e):
        clave = self._zona(e.position())
        if clave == "nueva":
            self.vista.nueva()
        elif clave:
            self.vista.poner(clave)
        if clave:
            self.close()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()


def titulo(self, tarjeta, punto):
    """Clic en el título de Juegos: el selector de juegos con fichas, en vez de una lista."""
    if tarjeta.clave == "juegos":
        self.selector_juegos = SelectorJuegos(self.juego_vista)  # (sin referencia, Python lo borraría)
        self.selector_juegos.abrir(punto)
        return True
    return None


def construir(self, s):
    # Juegos: los minijuegos de juegos.py y minijuegos.py (se eligen con el clic en el título o el derecho).
    c = self.tarjeta("juegos", "Juegos")
    self.juego_vista = VistaJuego(self)
    c.add(self.juego_vista)
    c._estira = True


def menu(self, tarjeta, menu):
    if tarjeta.clave == "juegos":
        # Los juegos, a la vista (sin submenú): se elige con un clic, también desde el título
        for clave, nombre in juegos.JUEGOS:
            a = menu.addAction(_(nombre), lambda _x=False, c=clave: self.juego_vista.poner(c))
            a.setCheckable(True)
            a.setChecked(self.juego_vista.juego.nombre == clave)
        menu.addSeparator()
        menu.addAction(_("Nueva partida"), self.juego_vista.nueva)
        menu.addSeparator()
