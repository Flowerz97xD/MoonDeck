"""Widget Immich (Windows): espacio, biblioteca, tareas y la IA de tu servidor Immich.

La IA se apaga parando su contenedor: si hay Docker, lo usa sin necesitar el widget Docker."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import contenedores
from immich import URL_POR_DEFECTO as IMMICH_URL, Immich, tam_legible
from idioma import _

WIDGETS = ('immich',)


class DialogoImmich(QDialog):
    """La dirección de Immich y una clave de API."""

    def __init__(self, url, clave, padre=None):
        super().__init__(padre)
        self.setWindowTitle(_("Conectar con Immich"))
        self.setStyleSheet(ESTILO_DIALOGO)
        self.resize(480, 0)
        caja = QVBoxLayout(self)
        ayuda = QLabel(_("En Immich: tu foto (arriba a la derecha) > <b>Ajustes de la cuenta</b> > <b>Claves de API</b> "
                         "> <b>Nueva clave de API</b>. Copia la clave y pégala aquí."))
        ayuda.setWordWrap(True)
        caja.addWidget(ayuda)
        for etiq, attr, valor, oculto in (("Dirección", "url", url, False), ("Clave de API", "clave", clave, True)):
            caja.addWidget(QLabel(_(etiq)))
            e = QLineEdit(valor)
            if oculto:
                e.setEchoMode(QLineEdit.Password)
            setattr(self, attr, e)
            caja.addWidget(e)
        botones = QHBoxLayout()
        botones.addStretch(1)
        for texto, fn, principal in ((_("Cancelar"), self.reject, False), (_("Conectar"), self.accept, True)):
            b = QPushButton(texto)
            b.clicked.connect(fn)
            if principal:
                b.setProperty("estilo", "principal")
                b.setDefault(True)
            botones.addWidget(b)
        caja.addLayout(botones)


class Metodos:
    """Se añaden a Monitor."""

    def abrir_immich(self):
        QDesktopServices.openUrl(QUrl(self.immich.url()))

    def conectar_immich(self, padre=None):
        dlg = DialogoImmich(self.immich.cfg.get("url") or IMMICH_URL, self.immich.cfg.get("clave", ""), padre)
        if dlg.exec() == QDialog.Accepted:
            self.immich.configurar(dlg.url.text(), dlg.clave.text())

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
            im["ia"].setText(_("Apagar la IA") if ml["estado"] == "running" else _("Encender la IA"))
        im["ia"].setVisible(bool(ml))
        estado, d = s["estado"], s["datos"]
        aviso = {"sin_config": _("Conecta el widget con tu Immich (clave de API de administrador)."),
                 "conectando": _("Conectando con Immich…")}.get(estado, "")
        if estado == "error":
            aviso = {"clave": _("Immich no acepta la clave de API."),
                     "conexion": _("No se puede conectar con Immich ({url}).").format(url=self.immich.url())
                     }.get(s["error"], _("Error de Immich: {error}").format(error=s["error"]))
        im["aviso"].setText(aviso)
        im["aviso"].setVisible(bool(aviso))
        im["conectar"].setVisible(estado in ("sin_config", "error"))
        ok = estado == "ok"
        disco = d.get("disco") if ok else None
        if disco:
            recortar(im["disco"], _("Disco: {usado} de {total}").format(
                usado=tam_legible(disco["usado"]), total=tam_legible(disco["total"])), M.ANCHO - 32)
            im["barra"].set(disco["pct"])
        for clave in ("disco", "barra"):
            poner_visible(im[clave], bool(disco))
        for clave, texto in (("fotos", "{n} fotos · {tam}"), ("videos", "{n} vídeos · {tam}")):
            n, uso = d.get(clave) if ok else None, d.get(f"uso_{clave}") if ok else None
            if n is not None:
                cifra = f"{n:,}".replace(",", ".")
                recortar(im[clave], _(texto).format(n=cifra, tam=tam_legible(uso)) if uso is not None
                         else _(texto.split(" · ")[0]).format(n=cifra), M.ANCHO - 32)
            poner_visible(im[clave], n is not None)
        usuarios = d.get("usuarios", []) if ok else []
        if [u["nombre"] for u in usuarios] != im["usuarios"]:
            im["usuarios"] = [u["nombre"] for u in usuarios]
            while im["caja_usuarios"].count():
                im["caja_usuarios"].takeAt(0).widget().deleteLater()
            for _u in usuarios:
                im["caja_usuarios"].addWidget(etiqueta("", "dim"))
        for i, u in enumerate(usuarios):
            im["caja_usuarios"].itemAt(i).widget().setText(f"{u['nombre']}: {tam_legible(u['uso'])}")
        poner_visible(im["lista_usuarios"], len(usuarios) > 1)  # con un solo usuario no aporta nada
        tareas = d.get("tareas") if ok else None
        if tareas is not None:
            lineas = [(_("{nombre}: {n} en marcha, {m} en espera") if activas else _("{nombre}: {m} en espera"))
                      .format(nombre=_(nombre), n=activas, m=esperando) for nombre, activas, esperando in tareas[:4]]
            im["tareas"].setText("\n".join(lineas) or _("Sin tareas pendientes"))
        poner_visible(im["tareas"], tareas is not None)
        im["pie"].setText(_("Immich {version} · en línea").format(version=d.get("version", "")) if ok else "")
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
    im["disco"] = c.add(etiqueta("", "sub"))
    im["barra"] = c.add(Barra())
    im["fotos"] = c.add(etiqueta("", "sub"), prescindible=4)
    im["videos"] = c.add(etiqueta("", "sub"), prescindible=4)
    im["lista_usuarios"] = QWidget()
    im["caja_usuarios"] = QVBoxLayout(im["lista_usuarios"])
    im["caja_usuarios"].setContentsMargins(0, 0, 0, 0)
    im["caja_usuarios"].setSpacing(2)
    c.add(im["lista_usuarios"], prescindible=3)
    im["tareas"] = c.add(etiqueta("", "dim"), prescindible=2)
    im["tareas"].setWordWrap(True)
    im["pie"] = c.add(etiqueta("", "dim"), prescindible=5)
    im["ia"] = c.add(QPushButton())
    im["ia"].setCursor(Qt.PointingHandCursor)
    im["ia"].clicked.connect(self.alternar_ia)
    im["aviso"] = c.add(etiqueta("", "dim"))
    im["aviso"].setWordWrap(True)
    im["conectar"] = c.add(QPushButton(_("Conectar con Immich…")))
    im["conectar"].setProperty("estilo", "principal")
    im["conectar"].setCursor(Qt.PointingHandCursor)
    im["conectar"].clicked.connect(lambda: self.conectar_immich(c.window()))
    self.im = im


def arrancar(self):
    self.t_immich = QTimer()  # Monitor no es un QObject: el temporizador va sin padre
    self.t_immich.timeout.connect(self.actualizar_immich)
    self.t_immich.start(1000)


def visibles(self, claves):
    self.immich.permitir("immich" in claves)
    self.docker.permitir(bool(claves & {"docker", "immich"}))  # Immich: su IA


def menu(self, tarjeta, menu):
    menu.addAction(_("Abrir Immich"), self.abrir_immich)
    menu.addAction(_("Conectar con Immich…"), lambda: self.conectar_immich(tarjeta.window()))
    menu.addSeparator()
