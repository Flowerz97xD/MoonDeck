"""Pack Escritorio (Linux): el lanzador de aplicaciones."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import lanzador
from idioma import _

WIDGETS = ('apps',)


class VistaApps(Dibujo):
    """Lanzador: los iconos de las apps que elige el usuario; un clic las abre. Con el clic
    derecho sobre un icono, el menú de la tarjeta trae quitarlo o moverlo."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.encima = None        # icono bajo el ratón
        self.menu_indice = None   # icono sobre el que se abrió el menú
        self._iconos = {}         # (id, color, escala) -> superficie de cairo
        self._alto = None
        self.add_events(Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw", self.dibujar)
        self.connect("size-allocate", lambda _w, r: self._ajustar(r.width))
        self.connect("motion-notify-event", self._mover)
        self.connect("leave-notify-event", lambda *_a: self._poner_encima(None))
        self.connect("button-press-event", self._pulsar)
        self.set_vexpand(True)  # ocupa toda la celda: los iconos se centran en ella
        self.poner_alto(lanzador.TAM)

    def apps(self):
        return self.app.config.setdefault("apps", [])

    def cambiado(self):
        self.app.guardar_config()
        self._ajustar(self.get_allocated_width())
        self.queue_draw()

    def _ajustar(self, ancho):
        _pos, alto = lanzador.rejilla(len(self.apps()), ancho)
        alto = max(lanzador.TAM, alto)
        if alto != self._alto:
            self._alto = alto
            self.poner_alto(alto)

    def _indice(self, x, y):
        pos, _alto = lanzador.rejilla(len(self.apps()), self.get_allocated_width(), self.get_allocated_height())
        return next((i for i, (ix, iy) in enumerate(pos)
                     if ix <= x < ix + lanzador.TAM and iy <= y < iy + lanzador.TAM), None)

    def _poner_encima(self, i):
        if i != self.encima:
            self.encima = i
            self.queue_draw()

    def _mover(self, _w, ev):
        self._poner_encima(self._indice(ev.x, ev.y))

    def _pulsar(self, _w, ev):
        tarjeta = self.get_ancestor(Tarjeta)
        if (tarjeta and tarjeta.en_edicion()) or ev.type != Gdk.EventType.BUTTON_PRESS:
            return False
        i = self._indice(ev.x, ev.y)
        if ev.button == 3:
            self.menu_indice = i
            return False  # el menú de la tarjeta
        if ev.button == 1 and i is not None:
            self.abrir(self.apps()[i])
            return True
        return False

    def abrir(self, a):
        try:
            Gio.DesktopAppInfo.new(a["id"]).launch([], None)
        except (TypeError, GLib.Error) as e:
            log("No se pudo abrir", a["id"], e)

    def _icono(self, a, color):
        escala = self.get_scale_factor()
        clave = (a["id"], color, escala)
        if clave not in self._iconos:
            pb = None
            info = Gio.DesktopAppInfo.new(a["id"]) if a["id"] else None
            gicon = info.get_icon() if info else None
            tema = Gtk.IconTheme.get_default()
            for g in (gicon, Gio.ThemedIcon.new("application-x-executable")):
                if not g:
                    continue
                datos = tema.lookup_by_gicon_for_scale(g, lanzador.TAM, escala, Gtk.IconLookupFlags.FORCE_SIZE)
                try:
                    pb = datos.load_icon() if datos else None
                except GLib.Error:
                    pb = None
                if pb:
                    break
            if pb and color:
                if not pb.get_has_alpha():
                    pb = pb.add_alpha(False, 0, 0, 0)
                w, h, fila = pb.get_width(), pb.get_height(), pb.get_rowstride()
                crudo = pb.get_pixels()
                rgba = b"".join(crudo[y * fila:y * fila + w * 4] for y in range(h))
                datos = lanzador.tenir_icono(rgba, color)
                pb = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(datos), GdkPixbuf.Colorspace.RGB, True, 8,
                                                     w, h, w * 4)
            self._iconos[clave] = Gdk.cairo_surface_create_from_pixbuf(pb, escala, None) if pb else None
        return self._iconos[clave]

    def dibujar(self, _w, cr):
        apps = self.apps()
        ancho = self.get_allocated_width()
        if not apps:
            lay = capa_texto(self, cr, _("Clic derecho > Añadir aplicación…"), 12)
            pintar_texto(cr, lay, 0, 0, ancho, self.get_allocated_height(), M.GRIS, 0.5, 0.5, recortar=True)
            return
        modo = self.app.config.get("apps_color", "original")
        color = {"acento": COLORES["azul"], "texto": M.BLANCO}.get(modo)
        pos, _alto = lanzador.rejilla(len(apps), ancho, self.get_allocated_height())
        t = lanzador.TAM
        for i, (a, (x, y)) in enumerate(zip(apps, pos)):
            if i == self.encima:
                cr.set_source_rgba(*M.TENUE[:3], 0.14)
                rect_redondeado(cr, x - 3, y - 3, t + 6, t + 6, 9)
                cr.fill()
            sup = self._icono(a, color)
            if sup:
                cr.set_source_surface(sup, x, y)
                cr.paint()


class SelectorApps(Gtk.Dialog):
    """Elegir apps instaladas (las de los menús del sistema) para el lanzador."""

    def __init__(self, ya):
        super().__init__(title=_("Añadir aplicación"))
        self.set_default_size(420, 520)
        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        self.add_button(_("Añadir"), Gtk.ResponseType.OK).get_style_context().add_class("suggested-action")
        cont = self.get_content_area()
        cont.set_spacing(8)
        for lado in ("start", "end", "top", "bottom"):
            getattr(cont, f"set_margin_{lado}")(10)
        self.buscar = Gtk.SearchEntry()
        self.buscar.connect("search-changed", lambda _e: self.lista.invalidate_filter())
        cont.pack_start(self.buscar, False, False, 0)
        self.lista = Gtk.ListBox(selection_mode=Gtk.SelectionMode.MULTIPLE)
        self.lista.set_activate_on_single_click(False)
        self.lista.connect("row-activated", lambda *_a: self.response(Gtk.ResponseType.OK))
        self.lista.set_filter_func(lambda fila: self.buscar.get_text().lower() in fila.nombre.lower())
        apps = sorted((a for a in Gio.AppInfo.get_all() if a.should_show() and a.get_id() not in ya),
                      key=lambda a: a.get_display_name().lower())
        for a in apps:
            fila = Gtk.ListBoxRow()
            fila.id, fila.nombre = a.get_id(), a.get_display_name()
            f = caja(False, 10)
            for lado in ("start", "end", "top", "bottom"):
                getattr(f, f"set_margin_{lado}")(4)
            img = Gtk.Image.new_from_gicon(a.get_icon(), Gtk.IconSize.DND) if a.get_icon() else Gtk.Image()
            f.pack_start(img, False, False, 0)
            f.pack_start(Gtk.Label(label=fila.nombre, xalign=0), True, True, 0)
            fila.add(f)
            self.lista.add(fila)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.add(self.lista)
        cont.pack_start(scroll, True, True, 0)
        self.show_all()

    def elegidas(self):
        return [{"id": f.id, "nombre": f.nombre} for f in self.lista.get_selected_rows()]


class Metodos:
    """Se añaden a Monitor."""

    def menu_apps(self, menu):
        v = self.apps_vista
        apps = v.apps()
        i, v.menu_indice = v.menu_indice, None
        self.item(menu, "Añadir aplicación…", self.anadir_apps)
        if i is not None and i < len(apps):
            self.item(menu, _("Quitar {app}").format(app=apps[i]["nombre"]), lambda: self.mover_app(i, None))
            if i > 0:
                self.item(menu, "Mover a la izquierda", lambda: self.mover_app(i, i - 1))
            if i < len(apps) - 1:
                self.item(menu, "Mover a la derecha", lambda: self.mover_app(i, i + 1))
        sub = self.submenu(menu, "Color de los iconos")
        for clave, nombre in lanzador.COLORES_ICONOS:
            self.item(sub, nombre, lambda c=clave: self.color_apps(c), self.config.get("apps_color", "original") == clave)
        menu.append(Gtk.SeparatorMenuItem())

    def anadir_apps(self):
        apps = self.apps_vista.apps()
        dlg = SelectorApps({a["id"] for a in apps})
        if dlg.run() == Gtk.ResponseType.OK:
            apps.extend(dlg.elegidas())
            self.apps_vista.cambiado()
            self.ajustar_alturas()
        dlg.destroy()

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


def construir(self, s):
    # Aplicaciones: un lanzador con los iconos que elija el usuario.
    c = self.tarjeta("apps", "Aplicaciones")
    self.apps_vista = c.add_w(VistaApps(self), expand=True)


def menu(self, tarjeta, menu):
    if tarjeta.clave == "apps":
        self.menu_apps(menu)


def ajustes(self, cont):
    """Configuración > Widgets (self es la ventana)."""
    app = self.app
    lista = self.grupo(cont, "Aplicaciones", "Añade apps con el clic derecho en el widget de aplicaciones.")
    color = Gtk.ComboBoxText()
    for clave, nombre in lanzador.COLORES_ICONOS:
        color.append(clave, _(nombre))
    color.set_active_id(app.config.get("apps_color", "original"))
    color.connect("changed", lambda w: app.color_apps(w.get_active_id()))
    self.fila(lista, "Color de los iconos", color, "Los del tema se adaptan al cambiar de tema")
