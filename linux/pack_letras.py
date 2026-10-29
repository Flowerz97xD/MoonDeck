"""Pack Letras (Linux): la letra de lo que suena, sincronizada como en Spotify (letras.py)."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import letras
import time
from idioma import _

WIDGETS = ('letras',)


class VistaLetra(Dibujo):
    """La letra sincronizada de lo que suena, como en Spotify: centrada, con la frase actual
    resaltada en el medio; al cambiar de frase la lista se desliza suave y el resaltado se
    funde de una a otra. Con un clic en una frase la canción salta ahí."""

    FLUIDO, REPOSO = 16, 80   # ms entre fotogramas: mientras se mueve / quieta
    DURACION = 0.7            # segundos que tarda en deslizarse a la frase siguiente
    PX = 16.5                 # tamaño de la letra

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.letras = letras.Letras()
        self.poner_alto(90, 240)
        self.set_vexpand(True)
        self.sesion = None     # lo que suena (dict de Reproductores)
        self.estado = None     # "ok", "buscando", "sin_letra" o None (no suena nada)
        self.frases = []
        self.pista = None      # (n.º, de cuántas, canción) si suena un disco entero
        self.cabecera = None   # la pone construir()
        self.actual = self.anterior = -1
        self.bloques = []      # (y, alto) de cada frase, para el ancho actual
        self._medida = None
        self.desplazado = 0.0  # y de la parte de arriba
        self._desde = 0.0      # animación: de dónde sale, cuándo empezó y su avance (0-1)
        self._inicio = 0.0
        self.avance = 1.0
        self._timer = None
        self._ms = self.REPOSO
        self.connect("draw", self.dibujar)
        self.connect("map", lambda _w: self._programar(self.REPOSO))
        self.connect("unmap", lambda _w: self._programar(None))
        self.connect("size-allocate", self._al_cambiar_tamano)
        self.connect("button-press-event", self._pulsar)
        self.connect("enter-notify-event", self._entrar)

    def _programar(self, ms):
        """Cada cuánto se mira lo que suena (None: parado, mientras no se ve)."""
        if ms == self._ms and self._timer is not None:
            return
        if self._timer is not None:
            GLib.source_remove(self._timer)
            self._timer = None
        self._ms = ms
        if ms:
            self._timer = GLib.timeout_add(ms, self.tic)

    def _capa(self, texto, actual=False):
        lay = self.create_pango_layout(texto)
        fd = self.get_pango_context().get_font_description().copy()
        fd.set_absolute_size(self.PX * M.ESCALA * Pango.SCALE)
        fd.set_weight(Pango.Weight.BOLD if actual else Pango.Weight.SEMIBOLD)
        lay.set_font_description(fd)
        lay.set_width(int(max(40, self.get_allocated_width() - 16) * Pango.SCALE))
        lay.set_wrap(Pango.WrapMode.WORD_CHAR)
        lay.set_alignment(Pango.Alignment.CENTER)
        return lay

    def posicion(self):
        d = self.sesion
        pos = d["pos"] + (time.monotonic() - d["momento"] if d["reproduciendo"] else 0)
        return min(pos, d["dur"]) if d["dur"] > 0 else pos

    def tic(self):
        lista = self.app.reproductores.leer()
        d = next((x for x in lista if x["reproduciendo"]), lista[0] if lista else None)
        self.sesion = d
        if not d:
            frases, estado, pista = [], None, None
        else:
            estado, frases, pista = self.letras.pedir(d["titulo"], d["artista"], d["dur"], self.posicion())
            frases = frases or []
        cambio = estado != self.estado
        if pista != self.pista:
            self.pista = pista
            self._poner_cabecera()
        self.estado = estado
        if frases != self.frases:
            self.frases, self._medida = frases, None
            self.actual = self.anterior = -1
            self.avance, cambio = 1.0, True
            self._medir()
            self.desplazado = self._objetivo()
        if frases:
            pos = self.posicion() + 0.25  # un pelín antes, que el ojo va detrás
            actual = -1
            for i, (t, _f) in enumerate(frases):
                if t > pos:
                    break
                actual = i
            if actual != self.actual:
                self.anterior, self.actual = self.actual, actual
                self._desde, self._inicio, self.avance = self.desplazado, time.monotonic(), 0.0
            self._medir()
            if self.avance < 1:
                self.avance = min(1.0, (time.monotonic() - self._inicio) / self.DURACION)
                t = self.avance
                suave = 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2  # acelera y frena
                self.desplazado = self._desde + (self._objetivo() - self._desde) * suave
                cambio = True
        if cambio:
            self.queue_draw()
        ms = self.FLUIDO if self.avance < 1 else self.REPOSO
        if ms != self._ms:
            self._programar(ms)
            return False  # sigue el temporizador nuevo
        return True

    def _medir(self):
        ancho = max(40, self.get_allocated_width() - 16)
        if self._medida == (ancho, M.ESCALA):
            return
        self._medida = (ancho, M.ESCALA)
        separacion = self._capa("Ag", True).get_pixel_size()[1] * 0.6
        self.bloques, y = [], 0.0
        for _t, frase in self.frases:
            alto = self._capa(frase, True).get_pixel_size()[1]
            self.bloques.append((y, alto))
            y += alto + separacion

    def _objetivo(self):
        """La frase actual, en el centro."""
        if not self.bloques:
            return 0.0
        y, alto = self.bloques[max(self.actual, 0)]
        return y + alto / 2 - self.get_allocated_height() / 2

    def _al_cambiar_tamano(self, _w, _a):
        if self.frases and self._medida != (max(40, self.get_allocated_width() - 16), M.ESCALA):
            self._medir()
            self.desplazado = self._objetivo()

    def _brillo(self, i):
        """Cuánto resalta la frase i (0-1): la actual sube y la anterior baja mientras se desliza."""
        t = self.avance
        if i == self.actual:
            return t
        if i == self.anterior:
            return 1 - t
        return 0.0

    def dibujar(self, _w, cr):
        ancho, alto_vista = self.get_allocated_width(), self.get_allocated_height()
        if self.estado != "ok":
            textos = {None: _("No está sonando nada."), "buscando": _("Buscando la letra…"),
                      "sin_letra": _("No hay letra sincronizada para lo que suena.")}
            lay = capa_texto(self, cr, textos.get(self.estado, ""), 13)
            lay.set_width(int(max(1, ancho - 16) * Pango.SCALE))
            lay.set_wrap(Pango.WrapMode.WORD_CHAR)
            lay.set_alignment(Pango.Alignment.CENTER)
            pintar_texto(cr, lay, 8, 0, ancho - 16, alto_vista, M.GRIS)
            return
        self._medir()
        fundido = min(110.0, alto_vista * 0.36)  # arriba y abajo la letra se desvanece, poco a poco
        for i, (y, alto) in enumerate(self.bloques):
            arriba = y - self.desplazado
            if arriba + alto < 0 or arriba > alto_vista:
                continue
            brillo = self._brillo(i)
            base = 0.45 if i < self.actual else 0.75
            color = [a + (b - a) * brillo for a, b in zip(M.GRIS, M.BLANCO)]
            centro = arriba + alto / 2
            borde = max(0.0, min(1.0, centro / fundido, (alto_vista - centro) / fundido))
            borde = borde * borde * (3 - 2 * borde)  # curva suave: se va apagando antes y sin corte
            cr.set_source_rgba(*color, (base + (1 - base) * brillo) * borde)
            cr.move_to(8, arriba)
            PangoCairo.show_layout(cr, self._capa(self.frases[i][1], brillo > 0.5))

    def _poner_cabecera(self):
        """Con un disco entero, qué canción suena ("2/16 · CANDY"), junto al título de la tarjeta."""
        if not self.cabecera:
            return
        self.cabecera.set_visible(bool(self.pista))
        if self.pista:
            n, total, cancion = self.pista
            texto = f"{n}/{total} · {cancion}"
            poner_texto(self.cabecera, texto)
            self.cabecera.set_tooltip_text(texto)

    def _puede_saltar(self):
        return self.estado == "ok" and self.sesion and self.sesion["buscar"]

    def _pulsar(self, _w, ev):
        tarjeta = self.get_ancestor(Tarjeta)
        if ev.button != 1 or (tarjeta and tarjeta.en_edicion()) or not self._puede_saltar():
            return False
        y = ev.y + self.desplazado
        for i, (arriba, alto) in enumerate(self.bloques):
            if arriba - 4 <= y <= arriba + alto + 4:
                if ev.type == Gdk.EventType.BUTTON_PRESS:
                    self.app.reproductores.buscar(self.sesion["id"], max(0.0, self.frases[i][0] - 0.1))
                return True
        return False  # entre frases: se arrastra la tarjeta

    def _entrar(self, _w, _ev):
        ventana = self.get_window()
        if ventana:
            ventana.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), "pointer")
                               if self._puede_saltar() else None)


def construir(self, s):
    # Letra: la de lo que suena, sincronizada (LRCLIB)
    c = self.tarjeta("letras", "Letras")
    self.letra_vista = v = c.add_w(VistaLetra(self), expand=True)
    # Con un disco entero, qué canción suena: en la cabecera, centrada respecto a la tarjeta
    # (a la derecha, un hueco del ancho del título hace de contrapeso)
    v.cabecera = etiqueta("", "titulo")  # con la letra del título, para que sea de su línea
    v.cabecera.set_xalign(0.5)
    atributos = Pango.AttrList()
    atributos.insert(Pango.attr_weight_new(Pango.Weight.NORMAL))
    v.cabecera.set_attributes(atributos)
    v.cabecera.set_no_show_all(True)
    contrapeso = Gtk.Box()
    contrapeso.show()
    grupo = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)  # sin título (oculto) no cuenta: hueco de 0
    grupo.add_widget(c.lb_titulo)
    grupo.add_widget(contrapeso)
    v._grupo = grupo  # que no se libere
    cab = caja(False, 6)
    c.contenido.remove(c.lb_titulo)
    c.lb_titulo.set_hexpand(False)
    c.lb_titulo.set_ellipsize(Pango.EllipsizeMode.NONE)  # entero: el hueco mide lo mismo que él
    for w, estira in ((c.lb_titulo, False), (v.cabecera, True), (contrapeso, False)):
        cab.pack_start(w, estira, estira, 0)
    cab.show()
    c.contenido.pack_start(cab, False, False, 0)
    c.contenido.reorder_child(cab, 0)
