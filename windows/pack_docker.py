"""Widget Docker (Windows): tus contenedores, con su estado; pararlos y arrancarlos."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import contenedores
from idioma import _

WIDGETS = ('docker',)


class FilaDocker(QWidget):
    """Un contenedor: punto de color, nombre y, a la derecha, tiempo, CPU y RAM."""

    def __init__(self, app, nombre):
        super().__init__()
        self.app, self.nombre = app, nombre
        self.color = "verde"
        fila = QHBoxLayout(self)
        fila.setContentsMargins(16, 0, 0, 0)  # sitio para el punto
        fila.setSpacing(8)
        self.lb_nombre = etiqueta("", "sub")
        recortar(self.lb_nombre, nombre, M.ANCHO - 160)
        fila.addWidget(self.lb_nombre, 1)
        self.lb_datos = etiqueta("", "dim")
        fila.addWidget(self.lb_datos)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(COLORES[self.color])
        p.drawEllipse(QPointF(5, self.height() / 2), 4, 4)

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.app.docker_sel = self.nombre  # el menú de la tarjeta trae parar, iniciar…
        e.ignore()

    def actualizar(self, c):
        color = contenedores.color(c)
        if color != self.color:
            self.color = color
            self.update()
        partes = [contenedores.hace(c["desde"])] + ([c["cpu"], c["ram"]] if c["estado"] == "running" else [])
        self.lb_datos.setText(" · ".join(x for x in partes if x))


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
                menu.addAction(_("Parar {nombre}").format(nombre=nombre), lambda: self.docker.accion(nombre, "stop"))
                menu.addAction(_("Reiniciar {nombre}").format(nombre=nombre),
                               lambda: self.docker.accion(nombre, "restart"))
            else:
                menu.addAction(_("Iniciar {nombre}").format(nombre=nombre), lambda: self.docker.accion(nombre, "start"))
            menu.addSeparator()

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
        dk["aviso"].setText(aviso)
        dk["aviso"].setVisible(bool(aviso))
        nombres = [c["nombre"] for c in s["contenedores"]]
        if nombres != dk["orden"]:
            dk["orden"] = nombres
            for f in dk["filas"].values():
                f.deleteLater()
            dk["filas"] = {n: FilaDocker(self, n) for n in nombres}
            for n in nombres:
                dk["caja"].addWidget(dk["filas"][n])
            dk["tarjeta"].prescindibles_grupo("contenedores", [dk["filas"][n] for n in nombres][::-1], 1)
        for c in s["contenedores"]:
            dk["filas"][c["nombre"]].actualizar(c)
        dk["lista"].setVisible(bool(nombres))
        dk["todo"].setText(_("Parar todos") if any(c["estado"] == "running" for c in s["contenedores"])
                           else _("Iniciar todos"))
        dk["todo"].setVisible(bool(nombres))
        self.ajustar_alturas()


def iniciar(self):
    if not hasattr(self, "docker"):  # lo comparte con el widget Immich
        self.docker = contenedores.Docker()
    self.docker_sel = None  # contenedor sobre el que se abrió el menú


def construir(self, s):
    # Docker: los contenedores, con su estado.
    c = self.tarjeta("docker", "Docker")
    dk = {"version": None, "filas": {}, "orden": None}
    dk["aviso"] = c.add(etiqueta("", "dim"))
    dk["aviso"].setWordWrap(True)
    dk["lista"] = QWidget()
    dk["caja"] = QVBoxLayout(dk["lista"])
    dk["caja"].setContentsMargins(0, 0, 0, 0)
    dk["caja"].setSpacing(6)
    c.add(dk["lista"])
    dk["todo"] = c.add(QPushButton())
    dk["todo"].setCursor(Qt.PointingHandCursor)
    dk["todo"].clicked.connect(self.alternar_docker)
    dk["tarjeta"] = c
    self.dk = dk


def arrancar(self):
    self.t_docker = QTimer()  # Monitor no es un QObject: el temporizador va sin padre
    self.t_docker.timeout.connect(self.actualizar_docker)
    self.t_docker.start(1000)


def visibles(self, claves):
    self.docker.permitir(bool(claves & {"docker", "immich"}))  # Immich: su IA


def menu(self, tarjeta, menu):
    self.menu_docker(menu)
