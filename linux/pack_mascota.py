"""Pack Mascota (Linux): un tamagotchi en pixel art que vive en el escritorio (mascota.py).

Reacciona a lo que pasa en el PC: baila con la música (la reconoce con letras.py), come palomitas
con los vídeos, suda si el PC va caliente, saca un mando si juegas y se pone los auriculares en
Discord. Los fondos de fuera muestran el tiempo de verdad (el del widget del tiempo). Las monedas
salen de cada día juntos y de los minijuegos (pack Juegos, si está) y se gastan en su tienda.
"""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import letras
import mascota
import os
import time
from idioma import _

WIDGETS = ('mascota',)


def animar(w, ms):
    """Redibuja w cada ms mientras se ve."""
    w._animacion = None

    def empezar(_w):
        if w._animacion is None:
            w._animacion = GLib.timeout_add(ms, lambda: w.queue_draw() or True)

    def parar(_w):
        if w._animacion is not None:
            GLib.source_remove(w._animacion)
            w._animacion = None
    w.connect("map", empezar)
    w.connect("unmap", parar)


def ventana_de(w):
    padre = w.get_toplevel() if w else None
    return padre if isinstance(padre, Gtk.Window) else None


class VistaMascota(Dibujo):
    """La mascota (mascota.py) en su tarjeta: la anima mientras se ve y le pasa los clics."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.poner_alto(120, 260)
        self.set_vexpand(True)
        self._acariciando = None  # dónde iba el ratón en la última caricia (botón pulsado)
        self._cursor = None
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)
        animar(self, 100)
        self.connect("draw", self.dibujar)
        self.connect("button-press-event", self._pulsar)
        self.connect("button-release-event", self._soltar)
        self.connect("motion-notify-event", self._mover)

    def _poner_cursor(self, nombre):
        ventana = self.get_window()
        if ventana and nombre != self._cursor:
            self._cursor = nombre
            ventana.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), nombre))

    def dibujar(self, _w, cr):
        self.app.mascota.dibujar(LienzoCairo(self, cr), paleta(), self.get_allocated_width(),
                                 self.get_allocated_height(), self.app.mascota_contexto, time.monotonic())

    def _pulsar(self, _w, ev):
        tarjeta = self.get_ancestor(Tarjeta)
        if ev.button != 1 or (tarjeta and tarjeta.en_edicion()):
            return False
        if ev.type != Gdk.EventType.BUTTON_PRESS:
            return True  # los dobles clics llegan además como un evento aparte
        accion = self.app.mascota.pulsar(ev.x, ev.y)
        if accion is None and self.app.mascota.en_mascota(ev.x, ev.y):
            # Una caricia (y si arrastra por encima, más): no mueve la ventana
            self._acariciando = (ev.x, ev.y)
            self.app.mascota.acariciar()
            self._poner_cursor("grabbing")
            self.queue_draw()
            return True
        if accion == "adoptar":
            personalizar_mascota(self.app, ventana_de(self))
        elif accion == "tienda":
            abrir_tienda(self.app.mascota, ventana_de(self))
        self.queue_draw()
        return accion is not None  # fuera de los botones se arrastra la tarjeta

    def _mover(self, _w, ev):
        m = self.app.mascota
        if self._acariciando is not None:
            # Acariciar es pasar la mano por encima: una caricia por cada trocito de recorrido
            if m.en_mascota(ev.x, ev.y) and (abs(ev.x - self._acariciando[0]) +
                                             abs(ev.y - self._acariciando[1])) > 18:
                self._acariciando = (ev.x, ev.y)
                m.acariciar()
            return True
        sobre_boton = any(bx <= ev.x <= bx + bw and by <= ev.y <= by + bh for bx, by, bw, bh, _a in m.botones)
        self._poner_cursor("pointer" if sobre_boton else "grab" if m.en_mascota(ev.x, ev.y) else "default")
        return False

    def _soltar(self, _w, ev):
        if self._acariciando is None:
            return False
        self._acariciando = None
        self._poner_cursor("grab")
        return True


class LienzoMascota(Dibujo):
    """Vista previa de la mascota en el diálogo de personalizar."""

    def __init__(self, dialogo):
        super().__init__()
        self.dlg = dialogo
        self.set_size_request(150, 150)
        self.set_halign(Gtk.Align.CENTER)
        animar(self, 150)
        self.connect("draw", self.dibujar)

    def dibujar(self, _w, cr):
        l = LienzoCairo(self, cr)
        d = self.dlg
        suelo = mascota.dibujar_fondo(l, 0, 0, 150, 150, d.fondo.get_active_id() if d.fondo else None,
                                      time.monotonic())
        if not suelo:
            l.rect(0, 0, 150, 150, 10, hex_rgb("#262a33"))
        px = 6 if suelo else 8
        pie = suelo + px * 1.5 if suelo else (150 + 16 * px) / 2
        expresion = "parpadeo" if int(time.monotonic() * 2) % 9 == 0 else "feliz"
        mascota.dibujar_mascota(l, (150 - 16 * px) / 2, pie - 16 * px, px, d.especie,
                                d.colores, expresion, [k for k, ch in d.casillas.items() if ch.get_active()],
                                t=time.monotonic(), pelaje=d.pelaje_elegido())


def rgba_de(hex_):
    c = Gdk.RGBA()
    c.parse(hex_)
    return c


def hex_de(rgba):
    return "#{:02x}{:02x}{:02x}".format(*(round(v * 255) for v in (rgba.red, rgba.green, rgba.blue)))


class DialogoMascota(Gtk.Dialog):
    """Adoptar (la primera vez) o personalizar: nombre, especie, colores y complementos."""

    def __init__(self, m, padre=None):
        adoptar = not m.adoptada
        super().__init__(title=_("Adopta tu mascota") if adoptar else _("Personalizar mascota"), transient_for=padre)
        self.m = m
        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        ok = self.add_button(_("Adoptar") if adoptar else _("Guardar"), Gtk.ResponseType.OK)
        ok.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)
        d = m.d
        self.especie = d.get("especie", "gato")
        self.colores = list(d.get("colores") or mascota.COLORES[self.especie])
        self.casillas = {}
        self.fondo = self.pelaje = None
        area = self.get_content_area()
        area.set_border_width(14)
        fila = caja(False, 16)
        area.pack_start(fila, True, True, 0)
        izq = caja(True)
        izq.pack_start(LienzoMascota(self), False, False, 0)
        fila.pack_start(izq, False, False, 0)
        der = caja(True, 6)
        fila.pack_start(der, True, True, 0)

        def titulo(texto):
            lb = Gtk.Label(label=texto, xalign=0)
            lb.set_margin_top(4)
            der.pack_start(lb, False, False, 0)

        titulo(_("Nombre"))
        self.nombre = Gtk.Entry(text=d.get("nombre", ""), max_length=16, activates_default=True)
        self.nombre.set_placeholder_text(_("Pixel"))
        der.pack_start(self.nombre, False, False, 0)
        titulo(_("Especie"))
        self.combo = Gtk.ComboBoxText()
        for clave, nombre in mascota.ESPECIES:
            self.combo.append(clave, _(nombre))
        self.combo.set_active_id(self.especie)
        self.combo.connect("changed", lambda _c: self._especie())
        der.pack_start(self.combo, False, False, 0)
        titulo(_("Colores"))
        colores = caja(False, 8)
        self.botones_color = []
        for i, nombre in enumerate((_("Cuerpo"), _("Manchas"), _("Ojos"))):
            b = Gtk.ColorButton(title=_("Elige un color"))
            b.connect("color-set", lambda b, i=i: self._color(i, b))
            una = caja(True, 2)
            una.pack_start(b, False, False, 0)
            una.pack_start(Gtk.Label(label=nombre), False, False, 0)
            colores.pack_start(una, False, False, 0)
            self.botones_color.append(b)
        der.pack_start(colores, False, False, 0)
        defecto = Gtk.Button(label=_("Colores de la especie"), halign=Gtk.Align.START)
        defecto.connect("clicked", lambda _b: self._especie())
        der.pack_start(defecto, False, False, 0)
        titulo(_("Fondo"))
        self.fondo = Gtk.ComboBoxText()
        for clave, nombre, _precio in mascota.FONDOS:
            if clave in m.fondos():
                self.fondo.append(clave, _(nombre))
        if not self.fondo.set_active_id(d.get("fondo", "jardin" if adoptar else "ninguno")):
            self.fondo.set_active(0)
        der.pack_start(self.fondo, False, False, 0)
        pelajes = [k for k in mascota.PELAJES if m.tiene(k)]
        if pelajes:  # los especiales de la tienda
            titulo(_("Pelaje"))
            self.pelaje = Gtk.ComboBoxText()
            self.pelaje.append("", _("Sus colores"))
            for clave, nombre, _precio, _para in mascota.ESPECIALES:
                if clave in pelajes:
                    self.pelaje.append(clave, _(nombre))
            if not self.pelaje.set_active_id(d.get("pelaje") or ""):
                self.pelaje.set_active(0)
            der.pack_start(self.pelaje, False, False, 0)
        if d.get("complementos"):
            titulo(_("Complementos"))
            for clave, nombre, _precio in mascota.COMPLEMENTOS:
                if clave in d["complementos"]:
                    ch = Gtk.CheckButton(label=_(nombre))
                    ch.set_active(clave in d.get("puestos", []))
                    self.casillas[clave] = ch
                    der.pack_start(ch, False, False, 0)
        elif not adoptar:
            nota = Gtk.Label(label=_("Los complementos se compran en la tienda (clic derecho › Tienda) con las "
                                     "monedas que ganas en los minijuegos."), xalign=0, wrap=True, max_width_chars=40)
            nota.get_style_context().add_class("dim-label")
            nota.set_margin_top(6)
            der.pack_start(nota, False, False, 0)
        self.set_default_size(480, 330)
        self._pintar_botones()
        self.show_all()

    def pelaje_elegido(self):
        return (self.pelaje.get_active_id() or None) if self.pelaje else None

    def _especie(self):
        self.especie = self.combo.get_active_id()
        self.colores = list(mascota.COLORES[self.especie])
        self._pintar_botones()

    def _color(self, i, boton):
        self.colores[i] = hex_de(boton.get_rgba())

    def _pintar_botones(self):
        for b, c in zip(self.botones_color, self.colores):
            b.set_rgba(rgba_de(c))

    def guardar(self):
        nombre = self.nombre.get_text().strip()
        if self.m.adoptada:
            if self.pelaje:
                self.m.d["pelaje"] = self.pelaje_elegido()
            self.m.personalizar(nombre, self.especie, self.colores,
                                [k for k, ch in self.casillas.items() if ch.get_active()], self.fondo.get_active_id())
        else:
            self.m.adoptar(nombre, self.especie, self.colores)
            self.m.d["fondo"] = self.fondo.get_active_id()
            self.m.al_guardar()


class Vitrina(Dibujo):
    """La imagen de una tarjeta de la tienda, animada: un fondo, la mascota con un complemento
    o un pelaje puesto, un objeto o una comida."""

    def __init__(self, ancho, alto, fondo=None, complemento=None, especie="gato", colores=None, objeto=None,
                 pelaje=None):
        super().__init__()
        self.fondo, self.complemento, self.especie = fondo, complemento, especie
        self.colores = colores or mascota.COLORES[especie]
        self.objeto, self.pelaje = objeto, pelaje
        self.set_size_request(ancho, alto)
        self.set_halign(Gtk.Align.CENTER)
        animar(self, 120)
        self.connect("draw", self.dibujar)

    def dibujar(self, _w, cr):
        l = LienzoCairo(self, cr)
        w, h, t = self.get_allocated_width(), self.get_allocated_height(), time.monotonic()
        suelo = mascota.dibujar_fondo(l, 0, 0, w, h, self.fondo, t) if self.fondo else None
        if not suelo:
            l.rect(0, 0, w, h, 10, (1, 1, 1, 0.04))
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


CSS_TIENDA = b"""
.tienda-tarjeta { background-color: rgba(127, 127, 127, 0.10); border-radius: 12px;
                  border: 1px solid rgba(127, 127, 127, 0.22); padding: 10px; }
.tienda-tarjeta:hover { border-color: #4d8dff; }
.tienda-monedas { background-color: #3a2f12; color: #ffd257; border-radius: 12px; padding: 4px 12px; font-weight: 700; }
.tienda-titulo { font-size: 16pt; font-weight: 700; }
.tienda-nombre { font-weight: 600; }
.tienda-rareza { font-size: 7.5pt; font-weight: 700; letter-spacing: 1px; }
.tienda-detalle { font-size: 8pt; }
.tienda-aviso { color: #ff6b6b; }
button.tienda-comprar { background-image: none; background-color: #ffc23d; color: #241a05; font-weight: 700; }
button.tienda-comprar:disabled { background-color: rgba(127, 127, 127, 0.25); color: rgba(127, 127, 127, 0.9); }
button.tienda-usado { background-image: none; background-color: #1f3b2a; color: #6fe39a; }
"""
_ESTILO_TIENDA = None


class DialogoTienda(Gtk.Dialog):
    """La tienda de la mascota, como la de un videojuego: pestañas por tipo y una cuadrícula
    de tarjetas con su imagen animada, la rareza y el precio. Lo que ya tienes se usa desde aquí."""

    PESTANAS = (("comida", "Comida"), ("complementos", "Complementos"), ("fondos", "Fondos"),
                ("especiales", "Especiales"))
    COLUMNAS = 4

    def __init__(self, m, padre=None):
        super().__init__(title=_("Tienda"), transient_for=padre)
        self.m = m
        global _ESTILO_TIENDA
        if _ESTILO_TIENDA is None:  # una vez: cada proveedor que se añade se queda en la pantalla
            _ESTILO_TIENDA = Gtk.CssProvider()
            _ESTILO_TIENDA.load_from_data(CSS_TIENDA)
            Gtk.StyleContext.add_provider_for_screen(self.get_screen(), _ESTILO_TIENDA,
                                                     Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.add_button(_("Cerrar"), Gtk.ResponseType.CLOSE)
        area = self.get_content_area()
        area.set_spacing(10)
        area.set_border_width(14)
        cab = caja(False, 8)
        titulo = Gtk.Label(label=_("Tienda"), xalign=0)
        titulo.get_style_context().add_class("tienda-titulo")
        cab.pack_start(titulo, True, True, 0)
        self.monedas = Gtk.Label()
        self.monedas.get_style_context().add_class("tienda-monedas")
        cab.pack_end(self.monedas, False, False, 0)
        area.pack_start(cab, False, False, 0)
        ayuda = Gtk.Label(label=_("Las monedas se ganan cada día que pasáis juntos y en los minijuegos (widget Juegos)."),
                          xalign=0, wrap=True)
        ayuda.get_style_context().add_class("dim-label")
        area.pack_start(ayuda, False, False, 0)
        fila = caja(False)
        fila.get_style_context().add_class("linked")
        self.botones_pestana = {}
        grupo = None
        for clave, nombre in self.PESTANAS:
            b = Gtk.RadioButton.new_with_label_from_widget(grupo, _(nombre))
            b.set_mode(False)  # como un botón, sin el círculo
            b.connect("toggled", lambda b, c=clave: b.get_active() and self.mostrar(c))
            fila.pack_start(b, False, False, 0)
            self.botones_pestana[clave] = b
            grupo = grupo or b
        area.pack_start(fila, False, False, 0)
        self.aviso = Gtk.Label(xalign=0, no_show_all=True)
        self.aviso.get_style_context().add_class("tienda-aviso")
        area.pack_start(self.aviso, False, False, 0)
        self.scroll = Gtk.ScrolledWindow(vexpand=True)
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        area.pack_start(self.scroll, True, True, 0)
        self.set_default_size(820, 620)
        self.pestana = None
        self.show_all()
        self.botones_pestana["complementos"].set_active(True)  # y la muestra

    def mostrar(self, pestana, aviso=""):
        posicion = self.scroll.get_vadjustment().get_value() if pestana == self.pestana else 0
        self.pestana = pestana
        d = self.m.d
        self.monedas.set_text(f"🪙 {d.get('monedas', 0)} / {mascota.MAX_MONEDAS}")
        self.aviso.set_text(aviso)
        self.aviso.set_visible(bool(aviso))
        rejilla = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True, valign=Gtk.Align.START,
                              min_children_per_line=self.COLUMNAS, max_children_per_line=self.COLUMNAS,
                              column_spacing=10, row_spacing=10)
        rejilla.set_margin_end(8)
        for tarjeta in self._tarjetas(pestana):
            rejilla.add(tarjeta)
        for hijo in self.scroll.get_children():
            self.scroll.remove(hijo)
        self.scroll.add(rejilla)
        self.scroll.show_all()
        GLib.idle_add(lambda: self.scroll.get_vadjustment().set_value(posicion) and False)

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
        tarjeta = caja(True, 6)
        tarjeta.get_style_context().add_class("tienda-tarjeta")
        nombre_r, color_r = rareza(precio)
        etiqueta_r = Gtk.Label(xalign=0)
        etiqueta_r.set_markup(f"<span foreground='{color_r}'>"
                              f"{GLib.markup_escape_text(_('Gratis') if not precio else _(nombre_r))}</span>")
        etiqueta_r.get_style_context().add_class("tienda-rareza")
        tarjeta.pack_start(etiqueta_r, False, False, 0)
        tarjeta.pack_start(imagen, False, False, 0)
        lb = Gtk.Label(label=nombre, xalign=0, wrap=True, max_width_chars=14)
        lb.get_style_context().add_class("tienda-nombre")
        tarjeta.pack_start(lb, False, False, 0)
        if detalle:
            sub = Gtk.Label(label=detalle, xalign=0, wrap=True, max_width_chars=18)
            for c in ("tienda-detalle", "dim-label"):
                sub.get_style_context().add_class(c)
            tarjeta.pack_start(sub, False, False, 0)
        if estado is None:
            b = Gtk.Button(label=f"🪙 {precio}")
            b.get_style_context().add_class("tienda-comprar")
            b.set_sensitive(self.m.d.get("monedas", 0) >= precio)
            b.connect("clicked", lambda _b, c=clave: self._comprar(c))
        elif estado == "objeto":
            b = Gtk.Button(label="✓ " + _("Lo tienes"), sensitive=False)
            b.get_style_context().add_class("tienda-usado")
        else:
            puesto = estado == "puesto"
            texto = {"complementos": (_("Quitárselo"), _("Ponérselo")), "fondos": (_("En uso"), _("Usar")),
                     "especiales": (_("Quitárselo"), _("Ponérselo"))}[self.pestana]
            b = Gtk.Button(label=("✓ " if puesto and self.pestana == "fondos" else "") + texto[0 if puesto else 1])
            if puesto:
                b.get_style_context().add_class("tienda-usado")
            b.set_sensitive(not (puesto and self.pestana == "fondos"))
            b.connect("clicked", lambda _b, c=clave, s=puesto: self._usar(c, not s))
        b.set_valign(Gtk.Align.END)
        tarjeta.pack_end(b, False, False, 0)
        return tarjeta

    def _comprar(self, clave):
        self.mostrar(self.pestana, self.m.comprar(clave) or "")

    def _usar(self, clave, poner):
        self.m.usar(clave, poner)
        self.mostrar(self.pestana)


def abrir_tienda(m, padre=None):
    dlg = DialogoTienda(m, padre)
    dlg.run()
    dlg.destroy()


def personalizar_mascota(app, padre=None):
    dlg = DialogoMascota(app.mascota, padre)
    if dlg.run() == Gtk.ResponseType.OK:
        dlg.guardar()
    dlg.destroy()


def avisar(titulo, texto):
    """Una notificación del escritorio (en Windows es el globo de la bandeja)."""
    try:
        Gio.bus_get_sync(Gio.BusType.SESSION, None).call(
            "org.freedesktop.Notifications", "/org/freedesktop/Notifications", "org.freedesktop.Notifications",
            "Notify", GLib.Variant("(susssasa{sv}i)", ("MoonDeck", 0, "utilities-system-monitor", titulo, texto,
                                                         [], {}, 6000)),
            None, Gio.DBusCallFlags.NONE, -1, None, None, None)
    except GLib.Error:
        pass  # sin servidor de notificaciones


# Lo que suena en estas apps es música; en el navegador, solo si el widget Letras reconoce la canción
APPS_MUSICA = {"Spotify", "TIDAL", "Deezer", "Rhythmbox", "Elisa", "Strawberry", "Lollypop", "Amberol",
               "Clementine", "Audacious", "Tauon"}


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


# En la línea de órdenes de un juego: el "reaper" de Steam vive lo que dura el juego,
# y lo de steamapps/common (el juego, Proton) solo corre con uno abierto
SENALES_JUEGO = (b"SteamLaunch", b"/steamapps/common/", b"lutris-wrapper")


def hay_juego():
    """Si hay un juego en marcha (en Windows lo dice el medidor de FPS)."""
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                orden = f.read(4096)
        except OSError:
            continue  # se ha cerrado o no es nuestro
        if any(s in orden for s in SENALES_JUEGO) or orden.startswith(b"gamescope"):
            return True
    return False


def avanzar_mascota(app):
    """Cada pocos segundos: el tiempo pasa para la mascota, aunque su tarjeta no se vea."""
    m, ctx = app.mascota, app.mascota_contexto
    ctx["musica"], ctx["video"] = que_suena(app)
    ctx["jugando"] = hay_juego()
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
            avisar(m.d["nombre"], aviso)
    return True


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
    self.mascota_vista = c.add_w(VistaMascota(self), expand=True)
    GLib.timeout_add(5000, lambda: avanzar_mascota(self))
    GLib.timeout_add(1500, lambda: avanzar_mascota(self) and False)


def aplicar(self, s):
    # La mascota suda si el PC va caliente
    gpus = [g["temp"] for g in s.get("gpus", []) if g.get("temp") is not None]
    self.mascota_contexto["calor"] = (s.get("cpu_temp") or 0) >= 85 or any(t >= 83 for t in gpus)


def menu(self, tarjeta, menu):
    if tarjeta.clave == "mascota":
        m = self.mascota
        padre = ventana_de(tarjeta)
        if m.adoptada:
            self.item(menu, "Personalizar…", lambda: personalizar_mascota(self, padre))
            self.item(menu, "Tienda…", lambda: abrir_tienda(m, padre))

            def avisos():
                self.config["mascota_avisos"] = not self.config.get("mascota_avisos", True)
                self.guardar_config()
            self.item(menu, "Avisos de la mascota", avisos, self.config.get("mascota_avisos", True))

            def de_nuevo():
                dlg = Gtk.MessageDialog(transient_for=padre, message_type=Gtk.MessageType.QUESTION,
                                        buttons=Gtk.ButtonsType.YES_NO, text=_("Empezar de nuevo"))
                dlg.format_secondary_text(_("¿Despedirte de {nombre} y adoptar otra mascota?").format(
                    nombre=m.d["nombre"]))
                if dlg.run() == Gtk.ResponseType.YES:
                    m.d.clear()
                    self.guardar_config()
                dlg.destroy()
            self.item(menu, "Empezar de nuevo…", de_nuevo)
        else:
            self.item(menu, "Adoptar…", lambda: personalizar_mascota(self, padre))
        menu.append(Gtk.SeparatorMenuItem())
