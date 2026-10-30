"""Pack Móvil (Linux): tu Android en el escritorio con scrcpy (movil.py).

Arriba, el móvil entero (control total); debajo, tus apps favoritas, cada una en su ventana
(en una pantalla virtual: el móvil sigue libre); y "Todas las apps…" con un buscador.
"""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import colorsys
import zlib
import movil
from idioma import _

WIDGETS = ('movil',)

COLUMNAS = 4


class Inicial(Dibujo):
    """Un círculo de color con la inicial de la app (scrcpy no da los iconos)."""

    def __init__(self, paquete, nombre, tam):
        super().__init__()
        self.letra = (nombre.strip()[:1] or "?").upper()
        tono = zlib.crc32(paquete.encode()) % 360 / 360  # cada app, siempre su color
        self.color = colorsys.hls_to_rgb(tono, 0.5, 0.55)
        self.tam = tam
        self.set_size_request(tam, tam)
        self.set_halign(Gtk.Align.CENTER)
        self.connect("draw", self.dibujar)

    def dibujar(self, _w, cr):
        l = LienzoCairo(self, cr)
        r = self.tam / 2
        l.circulo(r, r, r, self.color)
        l.texto(self.letra, 0, 0, self.tam, self.tam, self.tam * 0.45, (1, 1, 1), "negrita")


def boton_app(app, paquete, nombre):
    b = Gtk.Button()
    b.set_relief(Gtk.ReliefStyle.NONE)
    b.get_style_context().add_class("plano")
    b.set_can_focus(False)
    b.set_tooltip_text(nombre)
    dentro = caja(True, 3)
    dentro.pack_start(Inicial(paquete, nombre, 38), False, False, 0)
    lb = etiqueta("", "dim")
    lb.set_text(nombre)  # sin traducir: es el nombre de la app
    lb.set_xalign(0.5)
    dentro.pack_start(lb, False, False, 0)
    b.add(dentro)
    b.connect("clicked", lambda _b: app.movil.abrir(paquete, nombre))
    return b


class DialogoApps(Gtk.Dialog):
    """Todas las apps del móvil, con buscador: clic para abrirla y ★ para tenerla en el widget."""

    def __init__(self, app, padre=None):
        super().__init__(title=_("Apps del móvil"), transient_for=padre)
        self.app = app
        self.m = app.movil
        self.set_default_size(420, 560)
        self.add_button(_("Cerrar"), Gtk.ResponseType.CLOSE)
        area = self.get_content_area()
        area.set_spacing(8)
        area.set_border_width(12)
        self.buscar = Gtk.SearchEntry()
        self.buscar.set_placeholder_text(_("Buscar app"))
        self.buscar.connect("search-changed", lambda _e: self.lista.invalidate_filter())
        self.buscar.connect("activate", lambda _e: self._abrir_primera())
        area.pack_start(self.buscar, False, False, 0)
        self.sistema = Gtk.CheckButton(label=_("Mostrar también las del sistema"))
        self.sistema.connect("toggled", lambda _c: self.llenar())
        area.pack_start(self.sistema, False, False, 0)
        self.aviso = Gtk.Label(xalign=0, no_show_all=True, wrap=True)
        self.aviso.get_style_context().add_class("dim-label")
        area.pack_start(self.aviso, False, False, 0)
        self.lista = Gtk.ListBox()
        self.lista.set_filter_func(self._filtro)
        self.lista.connect("row-activated", lambda _l, fila: self._abrir(fila))
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.lista)
        area.pack_start(scroll, True, True, 0)
        self.llenar()
        self.show_all()
        self.buscar.grab_focus()
        if self.m.leyendo or not self.m.apps(True):
            GLib.timeout_add(500, self._esperar)

    def _esperar(self):
        """Mientras se leen las apps del móvil: cuando acabe, se rellena."""
        if self.m.leyendo:
            return True
        self.llenar()
        return False

    def llenar(self):
        for fila in self.lista.get_children():
            self.lista.remove(fila)
        apps = self.m.apps(self.sistema.get_active())
        texto = (_("Leyendo las apps del móvil…") if self.m.leyendo else
                 self.m.error or _("Conecta el móvil para ver sus apps.") if not apps else "")
        self.aviso.set_text(texto)
        self.aviso.set_visible(bool(texto))
        for paquete, nombre, _sistema in apps:
            fila = Gtk.ListBoxRow()
            fila.paquete, fila.nombre = paquete, nombre
            fila.busqueda = nombre.lower()
            linea = caja(False, 10)
            linea.set_border_width(5)
            linea.pack_start(Inicial(paquete, nombre, 30), False, False, 0)
            textos = caja(True)
            lb = Gtk.Label(label=nombre, xalign=0, ellipsize=Pango.EllipsizeMode.END)
            sub = Gtk.Label(label=paquete, xalign=0, ellipsize=Pango.EllipsizeMode.END)
            sub.get_style_context().add_class("dim-label")
            textos.pack_start(lb, False, False, 0)
            textos.pack_start(sub, False, False, 0)
            linea.pack_start(textos, True, True, 0)
            estrella = Gtk.Button(relief=Gtk.ReliefStyle.NONE, can_focus=False, valign=Gtk.Align.CENTER)
            self._pintar_estrella(estrella, paquete)
            estrella.connect("clicked", lambda b, p=paquete: self._favorita(b, p))
            linea.pack_end(estrella, False, False, 0)
            fila.add(linea)
            self.lista.add(fila)
        self.lista.show_all()

    def _pintar_estrella(self, boton, paquete):
        fav = self.m.favorita(paquete)
        boton.set_image(Gtk.Image.new_from_icon_name("starred-symbolic" if fav else "non-starred-symbolic",
                                                     Gtk.IconSize.BUTTON))
        boton.set_tooltip_text(_("Quitar del widget") if fav else _("Poner en el widget"))

    def _favorita(self, boton, paquete):
        self.m.alternar_favorita(paquete)
        self._pintar_estrella(boton, paquete)
        refrescar_movil(self.app)

    def _filtro(self, fila):
        texto = self.buscar.get_text().strip().lower()
        return not texto or all(t in fila.busqueda for t in texto.split())

    def _abrir(self, fila):
        self.m.abrir(fila.paquete, fila.nombre)
        self.response(Gtk.ResponseType.CLOSE)

    def _abrir_primera(self):
        fila = next((f for f in self.lista.get_children() if f.get_child_visible()), None)
        if fila:
            self._abrir(fila)


def ventana_de(w):
    padre = w.get_toplevel() if w else None
    return padre if isinstance(padre, Gtk.Window) else None


def abrir_lista(app, padre=None):
    dlg = DialogoApps(app, padre)
    dlg.run()
    dlg.destroy()


AVISOS = {
    "sin_scrcpy": "Para ver el móvil hace falta scrcpy 3 o más moderno.",
    "viejo": "Tu scrcpy es antiguo: hace falta la versión 3 o más moderna.",
    "sin_movil": "Conecta el móvil por USB con la depuración USB activada.",
    "sin_permiso": "Linux no deja usar el móvil: falta la regla de udev de Android.",
    "sin_autorizar": "Acepta en el móvil el aviso «¿Permitir la depuración USB?».",
}


def refrescar_movil(self):
    """Pone la tarjeta según el estado del móvil."""
    v, m = self.movil_vista, self.movil
    estado = m.estado
    if estado is None:
        return
    listo = estado == "listo"
    aviso = m.error if listo else _(AVISOS[estado])
    poner_texto(v["aviso"], aviso)
    poner_visible(v["aviso"], bool(aviso))
    poner_visible(v["descargar"], estado in ("sin_scrcpy", "viejo"))
    poner_visible(v["equipo"], listo)
    if listo:
        v["equipo"].set_label(m.nombre)
    destacadas = m.destacadas() if listo else []
    if destacadas != v["destacadas"]:
        v["destacadas"] = destacadas
        for hijo in v["rejilla"].get_children():
            v["rejilla"].remove(hijo)
        for i, (paquete, nombre) in enumerate(destacadas):
            b = boton_app(self, paquete, nombre)
            b.show_all()  # la rejilla no lo hace por ellos: no se enseña con show_all (set_no_show_all)
            v["rejilla"].attach(b, i % COLUMNAS, i // COLUMNAS, 1, 1)
        for i in range(len(destacadas), COLUMNAS):  # huecos: con pocas apps, cada una en su cuarto
            hueco = Gtk.Box()
            hueco.show()
            v["rejilla"].attach(hueco, i, 0, 1, 1)
    poner_visible(v["rejilla"], bool(destacadas))
    poner_visible(v["pista"], listo and not destacadas)
    poner_visible(v["todas"], listo)


def tic_movil(self):
    if self.movil_tarjeta in self.visibles():  # oculto, no se pregunta nada al móvil
        self.movil.comprobar()
        refrescar_movil(self)
    return True


def construir(self, s):
    # Móvil: tu Android con scrcpy (sus apps en ventanas o el control total)
    self.movil = movil.Movil(self.config.setdefault("movil", {}), self.guardar_config, CARPETA)
    c = self.movil_tarjeta = self.tarjeta("movil", "Móvil")
    v = self.movil_vista = {"destacadas": None}
    v["aviso"] = c.add_w(etiqueta("", "dim", envolver=True))
    v["descargar"] = c.add_w(boton_texto("Descargar scrcpy", "principal"))
    v["descargar"].connect("clicked", lambda _b: abrir_web(movil.WEB_SCRCPY))
    v["equipo"] = c.add_w(boton_texto("", "principal"))
    v["equipo"].set_image(Gtk.Image.new_from_icon_name("smartphone-symbolic", Gtk.IconSize.BUTTON))
    v["equipo"].set_always_show_image(True)
    v["equipo"].set_tooltip_text(_("Controlar todo el móvil"))
    v["equipo"].connect("clicked", lambda _b: self.movil.abrir())
    v["rejilla"] = c.add_w(Gtk.Grid(column_homogeneous=True, row_spacing=4, column_spacing=2))
    v["pista"] = c.add_w(etiqueta("Pon tus apps en el widget con la ★ de «Todas las apps…».", "dim",
                                  envolver=True), prescindible=1)
    v["todas"] = c.add_w(boton_texto("Todas las apps…", "normal"))
    v["todas"].connect("clicked", lambda _b: abrir_lista(self, ventana_de(c)))
    for w in v.values():
        if isinstance(w, Gtk.Widget):
            w.set_no_show_all(True)  # se ven según el estado del móvil (refrescar_movil)


def arrancar(self):
    tic_movil(self)
    GLib.timeout_add(1000, lambda: refrescar_movil(self) and False)  # tras la primera comprobación
    GLib.timeout_add(3000, lambda: tic_movil(self))


def menu(self, tarjeta, menu):
    if tarjeta.clave == "movil":
        m = self.movil
        d = m.d

        def alternar(clave, defecto):
            d[clave] = not d.get(clave, defecto)
            self.guardar_config()
        self.item(menu, "Leer otra vez las apps del móvil", m.leer_apps)
        self.item(menu, "Apagar la pantalla del móvil al controlarlo",
                  lambda: alternar("apagar_pantalla", False), d.get("apagar_pantalla", False))
        self.item(menu, "Sonido del móvil en el PC", lambda: alternar("sonido", True), d.get("sonido", True))
        menu.append(Gtk.SeparatorMenuItem())
