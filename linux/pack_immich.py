"""Widget Immich (Linux): espacio, biblioteca, tareas y la IA de tu servidor Immich.

La IA se apaga parando su contenedor: si hay Docker, lo usa sin necesitar el widget Docker."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import contenedores
from immich import URL_POR_DEFECTO as IMMICH_URL, Immich, tam_legible
from idioma import _

WIDGETS = ('immich',)


class DialogoImmich(Gtk.Dialog):
    """La dirección de Immich y una clave de API."""

    def __init__(self, url, clave):
        super().__init__(title=_("Conectar con Immich"))
        self.set_default_size(480, -1)
        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        self.add_button(_("Conectar"), Gtk.ResponseType.OK).get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)
        area = self.get_content_area()
        area.set_spacing(8)
        area.set_border_width(16)
        ayuda = Gtk.Label(xalign=0, wrap=True, max_width_chars=60)
        ayuda.set_markup(_("En Immich: tu foto (arriba a la derecha) > <b>Ajustes de la cuenta</b> > <b>Claves de API</b> "
                           "> <b>Nueva clave de API</b>. Copia la clave y pégala aquí."))
        area.pack_start(ayuda, False, False, 0)
        for etiq, attr, valor, oculto in (("Dirección", "url", url, False), ("Clave de API", "clave", clave, True)):
            area.pack_start(Gtk.Label(label=_(etiq), xalign=0), False, False, 0)
            e = Gtk.Entry(text=valor, visibility=not oculto, activates_default=True)
            setattr(self, attr, e)
            area.pack_start(e, False, False, 0)
        self.show_all()


class Metodos:
    """Se añaden a Monitor."""

    def abrir_immich(self):
        Gio.AppInfo.launch_default_for_uri(self.immich.url(), None)
        return True

    def conectar_immich(self):
        dlg = DialogoImmich(self.immich.cfg.get("url") or IMMICH_URL, self.immich.cfg.get("clave", ""))
        if dlg.run() == Gtk.ResponseType.OK:
            self.immich.configurar(dlg.url.get_text(), dlg.clave.get_text())
        dlg.destroy()

    def alternar_ia(self):
        """Para o arranca el contenedor de la IA de Immich (y la activa o desactiva en Immich)."""
        ml = contenedores.buscar(self.docker.instantanea()["contenedores"], "immich-machine-learning")
        if not ml:
            return
        encendida = ml["estado"] == "running"
        self.docker.accion(ml["nombre"], "stop" if encendida else "start")
        self.immich.poner_ia(not encendida)

    def actualizar_immich(self):
        im = self.im
        s = self.immich.instantanea()
        dk = self.docker.instantanea()
        if (s["version"], dk["version"]) == im["version"]:
            return
        im["version"] = (s["version"], dk["version"])
        ml = contenedores.buscar(dk["contenedores"], "immich-machine-learning")
        if ml:
            encendida = ml["estado"] == "running"
            im["ia"].set_label(_("Apagar la IA") if encendida else _("Encender la IA"))
            clases(im["ia"], marcado=not encendida)
        im["ia"].set_visible(bool(ml))
        estado, d = s["estado"], s["datos"]
        aviso = {"sin_config": _("Conecta el widget con tu Immich (clave de API de administrador)."),
                 "conectando": _("Conectando con Immich…")}.get(estado, "")
        if estado == "error":
            aviso = {"clave": _("Immich no acepta la clave de API."),
                     "conexion": _("No se puede conectar con Immich ({url}).").format(url=self.immich.url())
                     }.get(s["error"], _("Error de Immich: {error}").format(error=s["error"]))
        poner_texto(im["aviso"], aviso)
        im["aviso"].set_visible(bool(aviso))
        im["conectar"].set_visible(estado in ("sin_config", "error"))
        ok = estado == "ok"
        disco = d.get("disco") if ok else None
        if disco:
            poner_texto(im["disco"], _("Disco: {usado} de {total}").format(
                usado=tam_legible(disco["usado"]), total=tam_legible(disco["total"])))
            im["barra"].set(disco["pct"])
        for clave in ("disco", "barra"):
            poner_visible(im[clave], bool(disco))
        for clave, texto in (("fotos", "{n} fotos · {tam}"), ("videos", "{n} vídeos · {tam}")):
            n, uso = d.get(clave) if ok else None, d.get(f"uso_{clave}") if ok else None
            if n is not None:
                cifra = f"{n:,}".replace(",", ".")
                poner_texto(im[clave], _(texto).format(n=cifra, tam=tam_legible(uso)) if uso is not None
                            else _(texto.split(" · ")[0]).format(n=cifra))
            poner_visible(im[clave], n is not None)
        usuarios = d.get("usuarios", []) if ok else []
        if [u["nombre"] for u in usuarios] != im["usuarios"]:
            im["usuarios"] = [u["nombre"] for u in usuarios]
            for w in im["lista_usuarios"].get_children():
                w.destroy()
            for u in usuarios:
                im["lista_usuarios"].pack_start(etiqueta("", "dim"), False, False, 0)
            im["lista_usuarios"].show_all()
        for lb, u in zip(im["lista_usuarios"].get_children(), usuarios):
            poner_texto(lb, f"{u['nombre']}: {tam_legible(u['uso'])}")
        poner_visible(im["lista_usuarios"], len(usuarios) > 1)  # con un solo usuario no aporta nada
        tareas = d.get("tareas") if ok else None
        if tareas is not None:
            lineas = [(_("{nombre}: {n} en marcha, {m} en espera") if activas else _("{nombre}: {m} en espera"))
                      .format(nombre=_(nombre), n=activas, m=esperando) for nombre, activas, esperando in tareas[:4]]
            poner_texto(im["tareas"], "\n".join(lineas) or _("Sin tareas pendientes"))
        poner_visible(im["tareas"], tareas is not None)
        poner_texto(im["pie"], _("Immich {version} · en línea").format(version=d.get("version", "")) if ok else "")
        poner_visible(im["pie"], ok)
        self.ajustar_alturas()


def iniciar(self):
    if not hasattr(self, "docker"):  # lo comparte con el widget Docker
        self.docker = contenedores.Docker()
    self.immich = Immich(CARPETA)


def construir(self, s):
    # Immich: espacio, lo que ocupa la biblioteca y las tareas en cola.
    c = self.tarjeta("immich", "Immich")
    im = {"version": None, "usuarios": None}
    im["disco"] = c.add_w(etiqueta("", "sub"))
    im["barra"] = c.add_w(Barra())
    im["fotos"] = c.add_w(etiqueta("", "sub"), prescindible=4)
    im["videos"] = c.add_w(etiqueta("", "sub"), prescindible=4)
    im["lista_usuarios"] = c.add_w(caja(True, 2), prescindible=3)
    im["tareas"] = c.add_w(etiqueta("", "dim", envolver=True), prescindible=2)
    im["pie"] = c.add_w(etiqueta("", "dim"), prescindible=5)
    im["ia"] = c.add_w(boton_texto("", "normal"))
    im["ia"].connect("clicked", lambda _b: self.alternar_ia())
    im["aviso"] = c.add_w(etiqueta("", "dim", envolver=True))
    im["conectar"] = c.add_w(boton_texto("Conectar con Immich…", "principal"))
    im["conectar"].connect("clicked", lambda _b: self.conectar_immich())
    self.im = im


def arrancar(self):
    GLib.timeout_add(1000, lambda: self.actualizar_immich() or True)


def visibles(self, claves):
    self.immich.permitir("immich" in claves)
    self.docker.permitir(bool(claves & {"docker", "immich"}))  # Immich: su IA


def menu(self, tarjeta, menu):
    self.item(menu, "Abrir Immich", self.abrir_immich)
    self.item(menu, "Conectar con Immich…", self.conectar_immich)
    menu.append(Gtk.SeparatorMenuItem())
