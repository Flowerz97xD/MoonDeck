"""Widget Docker (Linux): tus contenedores, con su estado; pararlos y arrancarlos."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import contenedores
from idioma import _

WIDGETS = ('docker',)


class FilaDocker(Gtk.EventBox):
    """Un contenedor: punto de color, nombre y, a la derecha, tiempo, CPU y RAM."""

    def __init__(self, app, nombre):
        super().__init__()
        self.app, self.nombre = app, nombre
        self.color = "verde"
        fila = caja(False, 8)
        self.punto = Gtk.DrawingArea()
        self.punto.set_size_request(10, 10)
        self.punto.set_valign(Gtk.Align.CENTER)
        self.punto.connect("draw", self._punto)
        fila.pack_start(self.punto, False, False, 0)
        self.lb_nombre = etiqueta(nombre, "sub")
        fila.pack_start(self.lb_nombre, True, True, 0)
        self.lb_datos = Gtk.Label(xalign=1)
        self.lb_datos.get_style_context().add_class("dim")
        fila.pack_start(self.lb_datos, False, False, 0)
        self.add(fila)
        self.connect("button-press-event", self._pulsar)
        self.show_all()

    def _punto(self, _w, cr):
        cr.arc(5, 5, 4, 0, 2 * math.pi)
        cr.set_source_rgb(*COLORES[self.color])
        cr.fill()

    def _pulsar(self, _w, ev):
        if ev.button == 3:
            self.app.docker_sel = self.nombre  # el menú de la tarjeta trae parar, iniciar…
        return False

    def actualizar(self, c):
        color = contenedores.color(c)
        if color != self.color:
            self.color = color
            self.punto.queue_draw()
        partes = [contenedores.hace(c["desde"])] + ([c["cpu"], c["ram"]] if c["estado"] == "running" else [])
        poner_texto(self.lb_datos, " · ".join(p for p in partes if p))


class Metodos:
    """Se añaden a Monitor."""

    def alternar_docker(self):
        """Para todos los contenedores en marcha o vuelve a arrancar los que se pararon así."""
        lista = self.docker.instantanea()["contenedores"]
        en_marcha = [c["nombre"] for c in lista if c["estado"] == "running"]
        if en_marcha:
            self.config["docker_parados"] = en_marcha
            self.docker.accion(en_marcha, "stop")
        else:
            nombres = {c["nombre"] for c in lista}
            self.docker.accion([n for n in self.config.pop("docker_parados", []) if n in nombres]
                               or list(nombres), "start")
        self.guardar_config()

    def menu_docker(self, menu):
        nombre, self.docker_sel = self.docker_sel, None
        c = next((c for c in self.docker.instantanea()["contenedores"] if c["nombre"] == nombre), None)
        if c:
            if c["estado"] == "running":
                self.item(menu, _("Parar {nombre}").format(nombre=nombre), lambda: self.docker.accion(nombre, "stop"))
                self.item(menu, _("Reiniciar {nombre}").format(nombre=nombre),
                          lambda: self.docker.accion(nombre, "restart"))
            else:
                self.item(menu, _("Iniciar {nombre}").format(nombre=nombre), lambda: self.docker.accion(nombre, "start"))
            menu.append(Gtk.SeparatorMenuItem())

    def actualizar_docker(self):
        dk = self.dk
        s = self.docker.instantanea()
        if s["version"] == dk["version"]:
            return
        dk["version"] = s["version"]
        aviso = {"cargando": _("Leyendo los contenedores…"), "sin_docker": _("Docker no está instalado."),
                 "sin_permiso": _("Sin permiso para usar Docker: cierra sesión y vuelve a entrar (grupo docker)."),
                 "parado": _("Docker no está en marcha.")}.get(s["estado"], "")
        if s["estado"] == "ok" and not s["contenedores"]:
            aviso = _("No hay contenedores.")
        poner_texto(dk["aviso"], aviso)
        dk["aviso"].set_visible(bool(aviso))
        nombres = [c["nombre"] for c in s["contenedores"]]
        if nombres != dk["orden"]:
            dk["orden"] = nombres
            for f in dk["filas"].values():
                f.destroy()
            dk["filas"] = {n: FilaDocker(self, n) for n in nombres}
            for n in nombres:
                dk["lista"].pack_start(dk["filas"][n], False, False, 0)
            dk["tarjeta"].prescindibles_grupo("contenedores", [dk["filas"][n] for n in nombres][::-1], 1)
        for c in s["contenedores"]:
            dk["filas"][c["nombre"]].actualizar(c)
        dk["lista"].set_visible(bool(nombres))
        dk["todo"].set_label(_("Parar todos") if any(c["estado"] == "running" for c in s["contenedores"])
                             else _("Iniciar todos"))
        dk["todo"].set_visible(bool(nombres))
        self.ajustar_alturas()


def iniciar(self):
    if not hasattr(self, "docker"):  # lo comparte con el widget Immich
        self.docker = contenedores.Docker()
    self.docker_sel = None  # contenedor sobre el que se abrió el menú


def construir(self, s):
    # Docker: los contenedores, con su estado.
    c = self.tarjeta("docker", "Docker")
    dk = {"version": None, "filas": {}, "orden": None}
    dk["aviso"] = c.add_w(etiqueta("", "dim", envolver=True))
    dk["lista"] = c.add_w(caja(True, 6))
    dk["todo"] = c.add_w(boton_texto("", "normal"))
    dk["todo"].connect("clicked", lambda _b: self.alternar_docker())
    dk["tarjeta"] = c
    self.dk = dk


def arrancar(self):
    GLib.timeout_add(1000, lambda: self.actualizar_docker() or True)


def visibles(self, claves):
    self.docker.permitir(bool(claves & {"docker", "immich"}))  # Immich: su IA


def menu(self, tarjeta, menu):
    self.menu_docker(menu)
