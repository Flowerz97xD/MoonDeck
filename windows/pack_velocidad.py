"""Widget Test de velocidad (Windows): ping, bajada y subida con un velocímetro."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import velocimetro
from velocidad import TestVelocidad
from idioma import _

WIDGETS = ('velocidad',)


class Velocimetro(QWidget):
    """Test de velocidad como el velocímetro digital de un deportivo: arco de segmentos
    que se encienden, la cifra en el centro y la fase encima."""

    ESTIRA = True  # crece con la tarjeta (Tarjeta.add)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.valor = 0.0        # lo que marca ahora (se anima hacia el objetivo)
        self.objetivo = 0.0
        self.tope = 100
        self.texto = "—"        # la cifra del centro
        self.unidad = "Mbps"
        self.fase = ""          # rótulo de encima
        self.color = "azul"
        self.progreso = None    # 0-1 mientras mide (arco fino exterior)
        self.estilo = "deportivo"
        self.animacion = QTimer(self)
        self.animacion.setInterval(16)
        self.animacion.timeout.connect(self._animar)

    def sizeHint(self):
        return QSize(M.ANCHO - 32, 190)

    def poner(self, valor, tope, texto, fase, color="azul", progreso=None, unidad="Mbps"):
        self.objetivo = valor or 0.0
        self.tope, self.texto, self.fase, self.color, self.progreso, self.unidad = (
            tope, texto, fase, color, progreso, unidad)
        if abs(self.objetivo - self.valor) > self.tope * 1e-4:
            if not self.animacion.isActive():
                self.animacion.start()
        self.update()

    def _animar(self):
        self.valor += (self.objetivo - self.valor) * 0.14
        if abs(self.objetivo - self.valor) <= self.tope * 1e-4:
            self.valor = self.objetivo
            self.animacion.stop()
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        e = {"valor": self.valor, "tope": self.tope, "texto": self.texto, "fase": self.fase,
             "color": self.color, "progreso": self.progreso, "unidad": self.unidad}
        esferas.velocimetro(LienzoQt(self, p), paleta(), self.width(), self.height(), e, self.estilo)


class Metodos:
    """Se añaden a Monitor."""

    @staticmethod
    def fmt_mbps(v):
        return f"{v:.0f} Mbps" if v >= 100 else f"{v:.1f} Mbps"

    def iniciar_test(self):
        self.test.iniciar()
        self.t_velocidad.start()
        self.actualizar_velocidad()

    def actualizar_velocidad(self):
        t = self.test
        r = t.resultado
        if t.midiendo:
            p = t.parcial
            fase = {"ping": _("Midiendo ping…"), "bajada": _("Midiendo bajada…"),
                    "subida": _("Midiendo subida…")}.get(t.fase, _("Preparando…"))
            self.vel_estado.setText(fase)
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
            self.vel_resto.setText(" · ".join(x for x in partes if x) or " ")
            self.vel_boton.setEnabled(False)
            self.vel_boton.setText(_("Midiendo…"))
            return
        self.t_velocidad.stop()
        self._vel_tope = 0
        self.vel_boton.setEnabled(True)
        self.vel_boton.setText(_("Repetir test") if r else _("Iniciar test"))
        if r and r is not self.config.get("velocidad"):
            self.config["velocidad"] = r
            self.guardar_config()
        if r:
            self.vel_reloj.poner(r["bajada"], velocimetro.tope(r["bajada"]), self.fmt_cifra(r["bajada"]),
                                 _("Bajada").upper())
            self.vel_resto.setText(f"↑ {self.fmt_mbps(r['subida'])} · ping {r['ping']:.0f} ms")
        else:
            self.vel_reloj.poner(0, 100, "—", _("Bajada").upper())
            self.vel_resto.setText(_("↑ — · ping —"))
        if t.error:
            self.vel_estado.setText(t.error)
        else:
            self.vel_estado.setText(_("Último test: {fecha} · servidores de Cloudflare").format(fecha=r["fecha"]) if r else
                                    _("Mide ping, bajada y subida (unos 15 s)."))

    def cambiar_velocimetro(self, estilo):
        self.config["velocimetro"] = estilo
        self.vel_reloj.estilo = estilo
        self.vel_reloj.update()
        self.guardar_config()

    @staticmethod
    def fmt_cifra(v):
        if not v:
            return "0"
        return f"{v:.0f}" if v >= 100 else f"{v:.1f}"


def iniciar(self):
    self.test = TestVelocidad()
    self.test.resultado = self.config.get("velocidad")
    self.t_velocidad = QTimer(interval=250)  # solo corre mientras se mide
    self.t_velocidad.timeout.connect(self.actualizar_velocidad)


def construir(self, s):
    c = self.tarjeta("velocidad", "Test de velocidad")
    self.vel_reloj = c.add(Velocimetro())
    self.vel_reloj.estilo = self.config.get("velocimetro", "deportivo")
    self.vel_resto = c.add(etiqueta(), prescindible=2)
    self.vel_resto.setAlignment(Qt.AlignHCenter)
    self.vel_estado = c.add(etiqueta("", "dim"), prescindible=1)
    self.vel_estado.setWordWrap(True)
    self.vel_estado.setAlignment(Qt.AlignHCenter)
    self.vel_boton = QPushButton(_("Iniciar test"))
    self.vel_boton.setProperty("estilo", "principal")
    self.vel_boton.setCursor(Qt.PointingHandCursor)
    self.vel_boton.clicked.connect(self.iniciar_test)
    c.add(self.vel_boton)


def arrancar(self):
    self.actualizar_velocidad()


def menu(self, tarjeta, menu):
    sub = menu.addMenu(_("Estilo del velocímetro"))
    for clave, nombre in esferas.ESTILOS_VELOCIMETRO:
        a = sub.addAction(_(nombre), lambda _x=False, c=clave: self.cambiar_velocimetro(c))
        a.setCheckable(True)
        a.setChecked(self.vel_reloj.estilo == clave)
    menu.addSeparator()


def ajustes(self, caja):
    """Configuración > Widgets (self es la ventana)."""
    app = self.app
    lista = self.grupo(caja, "Test de velocidad")
    estilo = QComboBox()
    for clave, nombre in esferas.ESTILOS_VELOCIMETRO:
        estilo.addItem(_(nombre), clave)
    estilo.setCurrentIndex(max(0, estilo.findData(app.vel_reloj.estilo)))
    estilo.currentIndexChanged.connect(lambda i: app.cambiar_velocimetro(estilo.itemData(i)))
    self.fila(lista, "Estilo del velocímetro", estilo)
