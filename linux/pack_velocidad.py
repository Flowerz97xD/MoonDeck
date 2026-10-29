"""Widget Test de velocidad (Linux): ping, bajada y subida con un velocímetro."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import velocimetro
from velocidad import TestVelocidad
from idioma import _

WIDGETS = ('velocidad',)


class Velocimetro(Dibujo):
    """Test de velocidad como el velocímetro digital de un deportivo: arco de segmentos
    que se encienden, la cifra en el centro y la fase encima."""

    def __init__(self):
        super().__init__()
        self.poner_alto(56, 190)
        self.set_vexpand(True)
        self.valor = 0.0        # lo que marca ahora (se anima hacia el objetivo)
        self.objetivo = 0.0
        self.tope = 100
        self.texto = "—"        # la cifra del centro
        self.unidad = "Mbps"
        self.fase = ""          # rótulo de encima
        self.color = "azul"
        self.progreso = None    # 0-1 mientras mide (arco fino exterior)
        self.estilo = "deportivo"
        self._animando = None
        self.connect("draw", self.dibujar)

    def poner(self, valor, tope, texto, fase, color="azul", progreso=None, unidad="Mbps"):
        cambia = (texto, fase, color, progreso, tope, unidad) != (self.texto, self.fase, self.color,
                                                                  self.progreso, self.tope, self.unidad)
        self.objetivo = valor or 0.0
        self.tope, self.texto, self.fase, self.color, self.progreso, self.unidad = (
            tope, texto, fase, color, progreso, unidad)
        if abs(self.objetivo - self.valor) > self.tope * 1e-4 and not self._animando:
            self._animando = GLib.timeout_add(16, self._animar)
        elif cambia:
            self.queue_draw()

    def _animar(self):
        self.valor += (self.objetivo - self.valor) * 0.14
        if abs(self.objetivo - self.valor) <= self.tope * 1e-4:
            self.valor = self.objetivo
            self._animando = None
        self.queue_draw()
        return self._animando is not None

    def dibujar(self, _w, cr):
        e = {"valor": self.valor, "tope": self.tope, "texto": self.texto, "fase": self.fase,
             "color": self.color, "progreso": self.progreso, "unidad": self.unidad}
        esferas.velocimetro(LienzoCairo(self, cr), paleta(), self.get_allocated_width(),
                            self.get_allocated_height(), e, self.estilo)


class Metodos:
    """Se añaden a Monitor."""

    @staticmethod
    def fmt_mbps(v):
        return f"{v:.0f} Mbps" if v >= 100 else f"{v:.1f} Mbps"

    def iniciar_test(self):
        self.test.iniciar()
        if not self.t_velocidad:
            self.t_velocidad = GLib.timeout_add(250, self.actualizar_velocidad)
        self.actualizar_velocidad()

    def actualizar_velocidad(self):
        t = self.test
        r = t.resultado
        if t.midiendo:
            p = t.parcial
            fase = {"ping": _("Midiendo ping…"), "bajada": _("Midiendo bajada…"),
                    "subida": _("Midiendo subida…")}.get(t.fase, _("Preparando…"))
            poner_texto(self.vel_estado, fase)
            # La escala crece si hace falta (como el cambio de rango de un velocímetro), nunca encoge.
            self._vel_tope = max(getattr(self, "_vel_tope", 0) or 0,
                                 velocimetro.tope(t.actual if t.fase in ("bajada", "subida") else 0,
                                                  p.get("bajada")))
            if t.fase == "ping" or not t.fase:
                self.vel_reloj.poner(0, self._vel_tope, "…", _("PING"), "amarillo", t.progreso, "ms")
            else:
                self.vel_reloj.poner(t.actual or 0, self._vel_tope, self.fmt_cifra(t.actual),
                                     (_("Bajada") if t.fase == "bajada" else _("Subida")).upper(),
                                     "azul" if t.fase == "bajada" else "morado", t.progreso)
            partes = [f"↓ {self.fmt_mbps(p['bajada'])}" if "bajada" in p else None,
                      f"ping {p['ping']:.0f} ms" if "ping" in p else None]
            poner_texto(self.vel_resto, " · ".join(x for x in partes if x) or " ")
            self.vel_boton.set_sensitive(False)
            self.vel_boton.set_label(_("Midiendo…"))
            return True
        self.t_velocidad = None
        self._vel_tope = 0
        self.vel_boton.set_sensitive(True)
        self.vel_boton.set_label(_("Repetir test") if r else _("Iniciar test"))
        if r and r is not self.config.get("velocidad"):
            self.config["velocidad"] = r
            self.guardar_config()
        if r:
            self.vel_reloj.poner(r["bajada"], velocimetro.tope(r["bajada"]), self.fmt_cifra(r["bajada"]),
                                 _("Bajada").upper())
            poner_texto(self.vel_resto, f"↑ {self.fmt_mbps(r['subida'])} · ping {r['ping']:.0f} ms")
        else:
            self.vel_reloj.poner(0, 100, "—", _("Bajada").upper())
            poner_texto(self.vel_resto, _("↑ — · ping —"))
        if t.error:
            poner_texto(self.vel_estado, t.error)
        else:
            poner_texto(self.vel_estado, _("Último test: {fecha} · servidores de Cloudflare").format(fecha=r["fecha"]) if r else
                        _("Mide ping, bajada y subida (unos 15 s)."))
        return False

    def cambiar_velocimetro(self, estilo):
        self.config["velocimetro"] = estilo
        self.vel_reloj.estilo = estilo
        self.vel_reloj.queue_draw()
        self.guardar_config()

    @staticmethod
    def fmt_cifra(v):
        if not v:
            return "0"
        return f"{v:.0f}" if v >= 100 else f"{v:.1f}"


def iniciar(self):
    self.test = TestVelocidad()
    self.test.resultado = self.config.get("velocidad")
    self.t_velocidad = None  # solo corre mientras se mide


def construir(self, s):
    c = self.tarjeta("velocidad", "Test de velocidad")
    self.vel_reloj = c.add_w(Velocimetro(), expand=True)
    self.vel_reloj.estilo = self.config.get("velocimetro", "deportivo")
    self.vel_resto = c.add_w(etiqueta(), prescindible=2)
    self.vel_resto.set_xalign(0.5)
    self.vel_estado = c.add_w(etiqueta("", "dim", envolver=True), prescindible=1)
    self.vel_estado.set_justify(Gtk.Justification.CENTER)
    self.vel_estado.set_xalign(0.5)
    self.vel_boton = c.add_w(boton_texto("Iniciar test", "principal"))
    self.vel_boton.connect("clicked", lambda _b: self.iniciar_test())


def arrancar(self):
    self.actualizar_velocidad()


def menu(self, tarjeta, menu):
    sub = self.submenu(menu, "Estilo del velocímetro")
    for clave, nombre in esferas.ESTILOS_VELOCIMETRO:
        self.item(sub, nombre, lambda c=clave: self.cambiar_velocimetro(c), self.vel_reloj.estilo == clave)
    menu.append(Gtk.SeparatorMenuItem())


def ajustes(self, cont):
    """Configuración > Widgets (self es la ventana)."""
    app = self.app
    lista = self.grupo(cont, "Test de velocidad")
    estilo = Gtk.ComboBoxText()
    for clave, nombre in esferas.ESTILOS_VELOCIMETRO:
        estilo.append(clave, _(nombre))
    estilo.set_active_id(app.vel_reloj.estilo)
    estilo.connect("changed", lambda w: app.cambiar_velocimetro(w.get_active_id()))
    self.fila(lista, "Estilo del velocímetro", estilo)
