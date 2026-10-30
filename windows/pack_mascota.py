"""Pack Mascota (Windows): un tamagotchi en pixel art que vive en el escritorio (mascota.py).

Reacciona a lo que pasa en el PC: baila con la música (la reconoce con letras.py), come palomitas
con los vídeos, suda si el PC va caliente, saca un mando si juegas y se pone los auriculares en
Discord. Los fondos de fuera muestran el tiempo de verdad (el del widget del tiempo). Las monedas
salen de cada día juntos y de los minijuegos (pack Juegos, si está) y se gastan en su tienda.
"""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import letras
import mascota
from sensores import MedidorFPS
import time
from idioma import _

WIDGETS = ('mascota',)


class VistaMascota(QWidget):
    """La mascota (mascota.py) en su tarjeta: la anima mientras se ve y le pasa los clics."""

    ESTIRA = True

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)  # para la mano al pasar por encima de la mascota
        self._acariciando = None    # dónde iba el ratón en la última caricia (botón pulsado)
        self.timer = QTimer(self, interval=100)
        self.timer.timeout.connect(self._tic)

    def _tic(self):
        # Mientras se juega en la misma ventana, a la mitad (5 por segundo): dibujarla cuesta y le
        # quita tiempo a los frames del juego
        juego = getattr(self.app, "juego_vista", None)
        if juego and hasattr(juego, "animando") and juego.animando() and juego.window() is self.window():
            self._tics = getattr(self, "_tics", 0) + 1
            if self._tics % 2:
                return
        self.update()

    def sizeHint(self):
        return QSize(M.ANCHO - 32, 260)

    def showEvent(self, e):
        super().showEvent(e)
        self.timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self.app.mascota.dibujar(LienzoQt(self, p), paleta(), self.width(), self.height(),
                                 self.app.mascota_contexto, time.monotonic())

    def mousePressEvent(self, e):
        tarjeta = self.parentWidget()
        while tarjeta and not isinstance(tarjeta, Tarjeta):
            tarjeta = tarjeta.parentWidget()
        if e.button() != Qt.LeftButton or (tarjeta and tarjeta.en_edicion()):
            e.ignore()
            return
        accion = self.app.mascota.pulsar(e.position().x(), e.position().y())
        if accion is None and self.app.mascota.en_mascota(e.position().x(), e.position().y()):
            # Una caricia (y si arrastra por encima, más): no mueve la ventana
            self._acariciando = e.position()
            self.app.mascota.acariciar()
            self.setCursor(Qt.ClosedHandCursor)
            self.update()
            return
        if accion == "adoptar":
            personalizar_mascota(self.app, self.window())
        elif accion == "tienda":
            DialogoTienda(self.app.mascota, self.window()).exec()
        elif accion is None:
            e.ignore()
        self.update()

    def mouseMoveEvent(self, e):
        m, x, y = self.app.mascota, e.position().x(), e.position().y()
        if self._acariciando is not None and e.buttons() & Qt.LeftButton:
            # Acariciar es pasar la mano por encima: una caricia por cada trocito de recorrido
            if m.en_mascota(x, y) and (e.position() - self._acariciando).manhattanLength() > 18:
                self._acariciando = e.position()
                m.acariciar()
            return
        sobre_boton = any(bx <= x <= bx + bw and by <= y <= by + bh for bx, by, bw, bh, _a in m.botones)
        self.setCursor(Qt.PointingHandCursor if sobre_boton else
                       Qt.OpenHandCursor if m.en_mascota(x, y) else Qt.ArrowCursor)

    def mouseReleaseEvent(self, e):
        if self._acariciando is None:
            e.ignore()
            return
        self._acariciando = None
        self.setCursor(Qt.OpenHandCursor)


class LienzoMascota(QWidget):
    """Vista previa de la mascota en el diálogo de personalizar."""

    def __init__(self, dialogo):
        super().__init__()
        self.dlg = dialogo
        self.setFixedSize(150, 150)
        self.timer = QTimer(self, interval=150)
        self.timer.timeout.connect(self.update)
        self.timer.start()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        l = LienzoQt(self, p)
        d = self.dlg
        suelo = mascota.dibujar_fondo(l, 0, 0, 150, 150, d.fondo.currentData() if d.fondo else None, time.monotonic())
        if not suelo:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#262a33"))
            p.drawRoundedRect(QRectF(self.rect()), 10, 10)
        px = 6 if suelo else 8
        pie = suelo + px * 1.5 if suelo else (150 + 16 * px) / 2
        expresion = "parpadeo" if int(time.monotonic() * 2) % 9 == 0 else "feliz"
        mascota.dibujar_mascota(l, (150 - 16 * px) / 2, pie - 16 * px, px, d.especie,
                                d.colores, expresion, [k for k, ch in d.casillas.items() if ch.isChecked()],
                                t=time.monotonic(), pelaje=d.pelaje.currentData() if d.pelaje else None)


class DialogoMascota(QDialog):
    """Adoptar (la primera vez) o personalizar: nombre, especie, colores y complementos."""

    def __init__(self, m, padre=None):
        super().__init__(padre)
        self.m = m
        adoptar = not m.adoptada
        self.setWindowTitle(_("Adopta tu mascota") if adoptar else _("Personalizar mascota"))
        self.setStyleSheet(ESTILO_DIALOGO)
        d = m.d
        self.especie = d.get("especie", "gato")
        self.colores = list(d.get("colores") or mascota.COLORES[self.especie])
        caja = QHBoxLayout(self)
        izq = QVBoxLayout()
        self.casillas = {}
        self.fondo = self.pelaje = None
        izq.addWidget(LienzoMascota(self), 0, Qt.AlignHCenter)
        izq.addStretch()
        caja.addLayout(izq)
        der = QVBoxLayout()
        der.addWidget(QLabel(_("Nombre")))
        self.nombre = QLineEdit(d.get("nombre", ""))
        self.nombre.setPlaceholderText(_("Pixel"))
        self.nombre.setMaxLength(16)
        der.addWidget(self.nombre)
        der.addWidget(QLabel(_("Especie")))
        self.combo = QComboBox()
        for clave, nombre in mascota.ESPECIES:
            self.combo.addItem(_(nombre), clave)
        self.combo.setCurrentIndex(max(0, self.combo.findData(self.especie)))
        self.combo.currentIndexChanged.connect(self._especie)
        der.addWidget(self.combo)
        der.addWidget(QLabel(_("Colores")))
        fila = QHBoxLayout()
        self.botones_color = []
        for i, nombre in enumerate((_("Cuerpo"), _("Manchas"), _("Ojos"))):
            b = QPushButton(nombre)
            b.clicked.connect(lambda _x=False, i=i: self._color(i))
            fila.addWidget(b)
            self.botones_color.append(b)
        der.addLayout(fila)
        defecto = QPushButton(_("Colores de la especie"))
        defecto.clicked.connect(lambda: self._especie(self.combo.currentIndex()))
        der.addWidget(defecto)
        der.addWidget(QLabel(_("Fondo")))
        self.fondo = QComboBox()
        for clave, nombre, _precio in mascota.FONDOS:
            if clave in m.fondos():
                self.fondo.addItem(_(nombre), clave)
        self.fondo.setCurrentIndex(max(0, self.fondo.findData(d.get("fondo", "jardin" if adoptar else "ninguno"))))
        der.addWidget(self.fondo)
        pelajes = [k for k in mascota.PELAJES if m.tiene(k)]
        if pelajes:  # los especiales de la tienda
            der.addWidget(QLabel(_("Pelaje")))
            self.pelaje = QComboBox()
            self.pelaje.addItem(_("Sus colores"), None)
            for clave, nombre, _precio, _para in mascota.ESPECIALES:
                if clave in pelajes:
                    self.pelaje.addItem(_(nombre), clave)
            self.pelaje.setCurrentIndex(max(0, self.pelaje.findData(d.get("pelaje"))))
            der.addWidget(self.pelaje)
        if d.get("complementos"):
            der.addWidget(QLabel(_("Complementos")))
            for clave, nombre, _precio in mascota.COMPLEMENTOS:
                if clave in d["complementos"]:
                    ch = QCheckBox(_(nombre))
                    ch.setChecked(clave in d.get("puestos", []))
                    self.casillas[clave] = ch
                    der.addWidget(ch)
        elif not adoptar:
            nota = QLabel(_("Los complementos se compran en la tienda (clic derecho › Tienda) con las "
                            "monedas que ganas en los minijuegos."))
            nota.setWordWrap(True)
            nota.setStyleSheet("color: #8b94a4;")
            der.addWidget(nota)
        der.addStretch()
        botones = QHBoxLayout()
        botones.addStretch()
        cancelar = QPushButton(_("Cancelar"))
        cancelar.clicked.connect(self.reject)
        aceptar = QPushButton(_("Adoptar") if adoptar else _("Guardar"))
        aceptar.setObjectName("aceptar")
        aceptar.clicked.connect(self.accept)
        botones.addWidget(cancelar)
        botones.addWidget(aceptar)
        der.addLayout(botones)
        caja.addLayout(der, 1)
        self.resize(480, 330)
        self._pintar_botones()

    def _especie(self, i):
        self.especie = self.combo.itemData(i)
        self.colores = list(mascota.COLORES[self.especie])
        self._pintar_botones()

    def _color(self, i):
        c = QColorDialog.getColor(QColor(self.colores[i]), self, _("Elige un color"))
        if c.isValid():
            self.colores[i] = c.name()
            self._pintar_botones()

    def _pintar_botones(self):
        for b, c in zip(self.botones_color, self.colores):
            claro = QColor(c).lightnessF() > 0.6
            b.setStyleSheet(f"background: {c}; color: {'#1b1e25' if claro else 'white'};")

    def guardar(self):
        nombre = self.nombre.text().strip()
        if self.m.adoptada:
            if self.pelaje:
                self.m.d["pelaje"] = self.pelaje.currentData()
            self.m.personalizar(nombre, self.especie, self.colores,
                                [k for k, ch in self.casillas.items() if ch.isChecked()], self.fondo.currentData())
        else:
            self.m.adoptar(nombre, self.especie, self.colores)
            self.m.d["fondo"] = self.fondo.currentData()
            self.m.al_guardar()


class Vitrina(QWidget):
    """La imagen de una tarjeta de la tienda, animada: un fondo, la mascota con un complemento
    o un pelaje puesto, un objeto o una comida."""

    def __init__(self, ancho, alto, fondo=None, complemento=None, especie="gato", colores=None, objeto=None,
                 pelaje=None):
        super().__init__()
        self.fondo, self.complemento, self.especie = fondo, complemento, especie
        self.colores = colores or mascota.COLORES[especie]
        self.objeto, self.pelaje = objeto, pelaje
        self.setFixedSize(ancho, alto)
        self.timer = QTimer(self, interval=120)
        self.timer.timeout.connect(self.update)

    def showEvent(self, e):
        super().showEvent(e)
        self.timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        l = LienzoQt(self, p)
        w, h, t = self.width(), self.height(), time.monotonic()
        suelo = mascota.dibujar_fondo(l, 0, 0, w, h, self.fondo, t) if self.fondo else None
        if not suelo:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 10))
            p.drawRoundedRect(QRectF(self.rect()), 10, 10)
        if self.objeto:
            px = max(2, int(min(w, h) * 0.7 / 8))
            mascota.dibujar_objeto(l, (w - 8 * px) / 2, (h - 8 * px) / 2, px, self.objeto)
        if self.complemento is not None or self.pelaje:
            px = max(2, int(h * (0.72 if suelo else 0.92) / 16) // 2 * 2)  # par: nítida a 32 x 32
            pie = suelo + px * 1.5 if suelo else (h + 16 * px) / 2
            mascota.dibujar_mascota(l, (w - 16 * px) / 2, pie - 16 * px, px, self.especie, self.colores, "feliz",
                                    [self.complemento] if self.complemento else [], t=t, pelaje=self.pelaje)


# Rareza por precio, como en las tiendas de los juegos: (desde, nombre, color)
RAREZAS = ((0, "Común", "#9aa3b2"), (15, "Rara", "#4d9dff"), (30, "Épica", "#b36bff"), (50, "Legendaria", "#ffc23d"))


def rareza(precio):
    nombre, color = RAREZAS[0][1:]
    for desde, n, c in RAREZAS:
        if precio >= desde:
            nombre, color = n, c
    return nombre, color


class DialogoTienda(QDialog):
    """La tienda de la mascota, como la de un videojuego: pestañas por tipo y una cuadrícula
    de tarjetas con su imagen animada, la rareza y el precio. Lo que ya tienes se usa desde aquí."""

    PESTANAS = (("comida", "Comida"), ("complementos", "Complementos"), ("fondos", "Fondos"),
                ("especiales", "Especiales"))
    COLUMNAS = 4

    def __init__(self, m, padre=None):
        super().__init__(padre)
        self.m = m
        self.setWindowTitle(_("Tienda"))
        self.setStyleSheet(ESTILO_DIALOGO + """
            QScrollArea { border: none; background: transparent; }
            QFrame#tarjeta { background: #232733; border-radius: 12px; border: 1px solid #2f3442; }
            QFrame#tarjeta:hover { border: 1px solid #4d8dff; }
            QPushButton#pestana { background: transparent; color: #aab3c2; padding: 8px 14px; border-radius: 8px;
                                  font-weight: 600; }
            QPushButton#pestana:checked { background: #2c313b; color: white; }
            QLabel#monedas { background: #3a2f12; color: #ffd257; border-radius: 12px; padding: 4px 12px;
                             font-weight: 700; }
            QLabel#nombre { color: white; font-weight: 600; }
            QLabel#detalle { color: #8b94a4; font-size: 8pt; }
            QPushButton#comprar { background: #ffc23d; color: #241a05; font-weight: 700; padding: 6px 8px; }
            QPushButton#comprar:disabled { background: #3a3f4b; color: #7d8696; }
            QPushButton#usar { background: #2c313b; color: white; padding: 6px 8px; }
            QPushButton#usado { background: #1f3b2a; color: #6fe39a; padding: 6px 8px; }
        """)
        caja = QVBoxLayout(self)
        caja.setSpacing(10)
        cab = QHBoxLayout()
        titulo = QLabel(_("Tienda"))
        titulo.setStyleSheet("font-size: 16pt; font-weight: 700; color: white;")
        cab.addWidget(titulo)
        cab.addStretch()
        self.monedas = QLabel()
        self.monedas.setObjectName("monedas")
        cab.addWidget(self.monedas)
        caja.addLayout(cab)
        ayuda = QLabel(_("Las monedas se ganan cada día que pasáis juntos y en los minijuegos (widget Juegos)."))
        ayuda.setObjectName("detalle")
        caja.addWidget(ayuda)
        fila = QHBoxLayout()
        fila.setSpacing(4)
        self.botones_pestana = {}
        for clave, nombre in self.PESTANAS:
            b = QPushButton(_(nombre))
            b.setObjectName("pestana")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _x=False, c=clave: self.mostrar(c))
            fila.addWidget(b)
            self.botones_pestana[clave] = b
        fila.addStretch()
        caja.addLayout(fila)
        self.aviso = QLabel()
        self.aviso.setStyleSheet("color: #ff6b6b;")
        self.aviso.hide()
        caja.addWidget(self.aviso)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        caja.addWidget(self.scroll, 1)
        self.resize(820, 620)
        self.pestana = "complementos"
        self.mostrar(self.pestana)

    def mostrar(self, pestana, aviso=""):
        self.pestana = pestana
        for clave, b in self.botones_pestana.items():
            b.setChecked(clave == pestana)
        d = self.m.d
        self.monedas.setText(f"🪙 {d.get('monedas', 0)} / {mascota.MAX_MONEDAS}")
        self.aviso.setText(aviso)
        self.aviso.setVisible(bool(aviso))
        posicion = self.scroll.verticalScrollBar().value() if pestana == getattr(self, "_ultima", None) else 0
        self._ultima = pestana
        cont = QWidget()
        cont.setObjectName("rejilla")
        cont.setStyleSheet("QWidget#rejilla { background: transparent; }")  # solo ella: no a sus botones
        rejilla = QGridLayout(cont)
        rejilla.setSpacing(10)
        rejilla.setContentsMargins(0, 0, 8, 0)
        for i, tarjeta in enumerate(self._tarjetas(pestana)):
            rejilla.addWidget(tarjeta, i // self.COLUMNAS, i % self.COLUMNAS)
        rejilla.setRowStretch(rejilla.rowCount(), 1)
        self.scroll.setWidget(cont)
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(posicion))

    def _tarjetas(self, pestana):
        m, d = self.m, self.m.d
        especie, colores = d.get("especie", "gato"), d.get("colores")
        nombres = dict((k, _(n)) for k, n in mascota.NECESIDADES)
        if pestana == "comida":
            for clave, nombre, precio, efecto in mascota.COMIDAS:
                detalle = " · ".join(f"{nombres[k]} +{v}" for k, v in efecto.items())
                yield self._tarjeta(_(nombre), detalle, precio, clave, Vitrina(150, 112, objeto=clave))
        elif pestana == "complementos":
            for clave, nombre, precio in mascota.COMPLEMENTOS:
                estado = None
                if clave in d.get("complementos", []):
                    estado = "puesto" if clave in d.get("puestos", []) else "guardado"
                yield self._tarjeta(_(nombre), "", precio, clave,
                                    Vitrina(150, 112, None, clave, especie, colores, pelaje=d.get("pelaje")), estado)
        elif pestana == "fondos":
            for clave, nombre, precio in mascota.FONDOS:
                estado = ("puesto" if d.get("fondo") == clave else "guardado") if clave in m.fondos() else None
                yield self._tarjeta(_(nombre), "", precio, clave, Vitrina(150, 112, fondo=clave), estado)
        else:
            for clave, nombre, precio, para in mascota.ESPECIALES:
                estado = None
                if m.tiene(clave):
                    estado = ("puesto" if d.get("pelaje") == clave else "guardado") if clave in mascota.PELAJES \
                        else "objeto"
                imagen = (Vitrina(150, 112, None, None, especie, colores, pelaje=clave) if clave in mascota.PELAJES
                          else Vitrina(150, 112, objeto=clave))
                yield self._tarjeta(_(nombre), _(para), precio, clave, imagen, estado)

    def _tarjeta(self, nombre, detalle, precio, clave, imagen, estado=None):
        """estado: None (se puede comprar), "puesto" / "guardado" (lo tiene: se pone o se quita)
        u "objeto" (lo tiene y no hay nada que elegir)."""
        tarjeta = QFrame()
        tarjeta.setObjectName("tarjeta")
        caja = QVBoxLayout(tarjeta)
        caja.setContentsMargins(10, 10, 10, 10)
        caja.setSpacing(6)
        nombre_r, color_r = rareza(precio)
        etiqueta_r = QLabel(_("Gratis") if not precio else _(nombre_r))
        etiqueta_r.setStyleSheet(f"color: {color_r}; font-size: 7.5pt; font-weight: 700; letter-spacing: 1px;")
        caja.addWidget(etiqueta_r)
        caja.addWidget(imagen, 0, Qt.AlignHCenter)
        lb = QLabel(nombre)
        lb.setObjectName("nombre")
        lb.setWordWrap(True)
        caja.addWidget(lb)
        sub = QLabel(detalle)
        sub.setObjectName("detalle")
        sub.setWordWrap(True)
        sub.setVisible(bool(detalle))
        caja.addWidget(sub)
        caja.addStretch()
        if estado is None:
            b = QPushButton(f"🪙 {precio}")
            b.setObjectName("comprar")
            b.setEnabled(self.m.d.get("monedas", 0) >= precio)
            b.clicked.connect(lambda _x=False, c=clave: self._comprar(c))
        elif estado == "objeto":
            b = QPushButton("✓ " + _("Lo tienes"))
            b.setObjectName("usado")
            b.setEnabled(False)
        else:
            puesto = estado == "puesto"
            texto = {"complementos": (_("Quitárselo"), _("Ponérselo")), "fondos": (_("En uso"), _("Usar")),
                     "especiales": (_("Quitárselo"), _("Ponérselo"))}[self.pestana]
            b = QPushButton(("✓ " if puesto and self.pestana == "fondos" else "") + texto[0 if puesto else 1])
            b.setObjectName("usado" if puesto else "usar")
            b.setEnabled(not (puesto and self.pestana == "fondos"))
            b.clicked.connect(lambda _x=False, c=clave, s=puesto: self._usar(c, not s))
        b.setCursor(Qt.PointingHandCursor)
        caja.addWidget(b)
        return tarjeta

    def _comprar(self, clave):
        self.mostrar(self.pestana, self.m.comprar(clave) or "")

    def _usar(self, clave, poner):
        self.m.usar(clave, poner)
        self.mostrar(self.pestana)


def personalizar_mascota(app, padre=None):
    dlg = DialogoMascota(app.mascota, padre)
    if dlg.exec():
        dlg.guardar()


# Lo que suena en estas apps es música; en el navegador, solo si el widget Letras reconoce la canción
APPS_MUSICA = {"Spotify", "Apple Music", "TIDAL", "Deezer", "Reproductor multimedia"}


def que_suena(app):
    """(música, vídeo): si lo que se reproduce es una canción (baila) u otra cosa (lo mira)."""
    d = next((x for x in app.reproductores.leer() if x["reproduciendo"]), None)
    if not d:
        return False, False
    if d["app"] in APPS_MUSICA:
        return True, False
    pos = d["pos"] + time.monotonic() - d["momento"]
    # El buscador de letras del pack Letras (comparten lo ya buscado); sin él, uno propio
    vista = getattr(app, "letra_vista", None)
    buscador = vista.letras if vista else app.mascota_letras
    estado, _f, _p = buscador.pedir(d["titulo"], d["artista"], d["dur"], pos)
    if estado == "buscando":  # aún no se sabe: sigue como estaba
        antes = app.mascota_contexto.get("musica", False)
        return antes, not antes
    return estado == "ok", estado != "ok"


def avanzar_mascota(app):
    """Cada pocos segundos: el tiempo pasa para la mascota, aunque su tarjeta no se vea."""
    m, ctx = app.mascota, app.mascota_contexto
    ctx["musica"], ctx["video"] = que_suena(app)
    # El tiempo de verdad de tu ciudad (widget del tiempo): los fondos de fuera lo muestran
    datos = getattr(getattr(app, "tiempo", None), "datos", None)
    ctx["clima"] = ({"codigo": datos.get("codigo"), "salida": datos.get("salida"), "puesta": datos.get("puesta")}
                    if datos else None)
    discord = getattr(app, "discord", None)
    try:
        s = discord.instantanea() if discord else None
        ctx["discord"] = bool(s and s["estado"] == "conectado" and s["canal"])
    except Exception:  # noqa: BLE001 - sin el pack Discord o a medio conectar
        ctx["discord"] = False
    for aviso in m.avanzar(ctx):
        if app.config.get("mascota_avisos", True):
            app.tray.showMessage(m.d["nombre"], aviso, QSystemTrayIcon.Information, 6000)


def construir(self, s):
    # Mascota: un tamagotchi que reacciona al PC; los minijuegos le dan monedas
    self.mascota = mascota.Mascota(self.config.setdefault("mascota", {}), self.guardar_config)
    self.mascota_contexto = {}
    self.mascota_letras = letras.Letras()
    try:  # las partidas ganadas dan monedas (si está el pack Juegos)
        import juegos
        import minijuegos
        juegos.AL_GANAR = self.mascota.anadir_monedas
        minijuegos.DIBUJAR_MASCOTA = self.mascota.dibujar_sola  # en Atrapa la comida juega ella
    except ImportError:
        pass
    c = self.tarjeta("mascota", "Mascota")
    self.mascota_vista = VistaMascota(self)
    c.add(self.mascota_vista)
    c._estira = True
    self.t_mascota = QTimer(interval=5000)
    self.t_mascota.timeout.connect(lambda: avanzar_mascota(self))
    self.t_mascota.start()
    QTimer.singleShot(1500, lambda: avanzar_mascota(self))


def aplicar(self, s):
    # La mascota suda si el PC va caliente y mira la pantalla si hay un juego en marcha
    gpus = [g["temp"] for g in s.get("gpus", []) if g.get("temp") is not None]
    self.mascota_contexto["calor"] = (s.get("cpu_temp") or 0) >= 85 or any(t >= 83 for t in gpus)
    # Sin juegos, el medidor de FPS mide el navegador o el reproductor (un vídeo también pinta
    # fotogramas): eso no es jugar, es ver un vídeo
    fps = s.get("fps")
    self.mascota_contexto["jugando"] = jugando(fps)


# Además de las de MedidorFPS.ESCRITORIO: también pintan fotogramas y no son juegos
NO_JUEGOS = {"python.exe", "pythonw.exe", "moondeck.exe", "claude.exe", "steelseriesgg.exe", "radeonsoftware.exe",
             "amdrsserv.exe", "nvidia overlay.exe", "wallpaper32.exe", "wallpaper64.exe", "lively.exe"}


def jugando(fps):
    """¿Hay un juego delante? Lo que presenta fotogramas tiene que ser la ventana que tienes
    delante: si no, cualquier app animada de fondo (la de Claude, el software de la gráfica...)
    contaba como un juego y la mascota sacaba el mando con Spotify abierto."""
    if not fps:
        return False
    app = fps["app"].lower()
    if app in MedidorFPS.ESCRITORIO or app in NO_JUEGOS:
        return False
    try:
        import psutil
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return psutil.Process(pid.value).name().lower() == app
    except Exception:  # noqa: BLE001 - el proceso se ha cerrado justo ahora
        return False


def menu(self, tarjeta, menu):
    if tarjeta.clave == "mascota":
        m = self.mascota
        if m.adoptada:
            menu.addAction(_("Personalizar…"), lambda: personalizar_mascota(self, tarjeta.window()))
            menu.addAction(_("Tienda…"), lambda: DialogoTienda(m, tarjeta.window()).exec())
            a = menu.addAction(_("Avisos de la mascota"))
            a.setCheckable(True)
            a.setChecked(self.config.get("mascota_avisos", True))
            a.toggled.connect(lambda v: (self.config.__setitem__("mascota_avisos", v), self.guardar_config()))

            def de_nuevo():
                r = QMessageBox.question(tarjeta.window(), _("Empezar de nuevo"),
                                         _("¿Despedirte de {nombre} y adoptar otra mascota?").format(nombre=m.d["nombre"]))
                if r == QMessageBox.Yes:
                    m.d.clear()
                    self.guardar_config()
            menu.addAction(_("Empezar de nuevo…"), de_nuevo)
        else:
            menu.addAction(_("Adoptar…"), lambda: personalizar_mascota(self, tarjeta.window()))
        menu.addSeparator()
