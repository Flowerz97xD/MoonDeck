"""Pack Escritorio (Windows): el lanzador de aplicaciones."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import lanzador
from idioma import _

WIDGETS = ('apps',)


class VistaApps(QWidget):
    """Lanzador: los iconos de las apps que elige el usuario; un clic las abre. Con el clic
    derecho sobre un icono, el menú de la tarjeta trae quitarlo o moverlo."""

    ESTIRA = True  # crece con la tarjeta (Tarjeta.add)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.encima = None        # icono bajo el ratón
        self.menu_indice = None   # icono sobre el que se abrió el menú
        self._iconos = {}         # (id, color, escala) -> QPixmap
        self._alto = None
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # los iconos se centran en la celda
        self.setMinimumHeight(lanzador.TAM)

    def apps(self):
        return self.app.config.setdefault("apps", [])

    def cambiado(self):
        self.app.guardar_config()
        self._ajustar()
        self.update()

    def _ajustar(self):
        _pos, alto = lanzador.rejilla(len(self.apps()), self.width())
        alto = max(lanzador.TAM, alto)
        if alto != self._alto:
            self._alto = alto
            self.setMinimumHeight(alto)
            self.updateGeometry()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._ajustar()

    def _indice(self, pos):
        rejilla, _alto = lanzador.rejilla(len(self.apps()), self.width(), self.height())
        return next((i for i, (ix, iy) in enumerate(rejilla)
                     if ix <= pos.x() < ix + lanzador.TAM and iy <= pos.y() < iy + lanzador.TAM), None)

    def _poner_encima(self, i):
        if i != self.encima:
            self.encima = i
            self.setCursor(Qt.PointingHandCursor if i is not None else Qt.ArrowCursor)
            self.update()

    def mouseMoveEvent(self, e):
        self._poner_encima(self._indice(e.position()))
        e.ignore()

    def leaveEvent(self, e):
        self._poner_encima(None)

    def _tarjeta(self):
        w = self.parentWidget()
        while w and not isinstance(w, Tarjeta):
            w = w.parentWidget()
        return w

    def mousePressEvent(self, e):
        tarjeta = self._tarjeta()
        i = self._indice(e.position())
        if tarjeta and tarjeta.en_edicion():
            e.ignore()
        elif e.button() == Qt.RightButton:
            self.menu_indice = i
            e.ignore()  # el menú de la tarjeta
        elif e.button() == Qt.LeftButton and i is not None:
            self.abrir(self.apps()[i])
        else:
            e.ignore()

    def abrir(self, a):
        try:
            os.startfile(a["id"])
        except OSError as e:
            print("No se pudo abrir", a["id"], e, file=sys.stderr)

    def _icono(self, a, color):
        escala = self.devicePixelRatioF()
        clave = (a["id"], color, escala)
        if clave not in self._iconos:
            lado = round(lanzador.TAM * escala)
            pm = QFileIconProvider().icon(QFileInfo(a["id"])).pixmap(lado, lado)
            if not pm.isNull() and (pm.width() != lado or pm.height() != lado):
                pm = pm.scaled(lado, lado, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if not pm.isNull() and color:
                img = pm.toImage().convertToFormat(QImage.Format_RGBA8888)
                w, h, fila = img.width(), img.height(), img.bytesPerLine()
                crudo = bytes(img.constBits())
                rgba = b"".join(crudo[y * fila:y * fila + w * 4] for y in range(h))
                datos = lanzador.tenir_icono(rgba, color)
                pm = QPixmap.fromImage(QImage(datos, w, h, w * 4, QImage.Format_RGBA8888).copy())
            pm.setDevicePixelRatio(escala)
            self._iconos[clave] = None if pm.isNull() else pm
        return self._iconos[clave]

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        apps = self.apps()
        if not apps:
            p.setPen(QColor(M.C_SEC))
            f = QFont(self.font())
            f.setPixelSize(round(12 * M.ESCALA))
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter, _("Clic derecho > Añadir aplicación…"))
            return
        modo = self.app.config.get("apps_color", "original")
        color = {"acento": rgb(acento()), "texto": rgb(QColor(M.C_TEXTO))}.get(modo)
        rejilla, _alto = lanzador.rejilla(len(apps), self.width(), self.height())
        t = lanzador.TAM
        for i, (a, (x, y)) in enumerate(zip(apps, rejilla)):
            if i == self.encima:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(*M.TENUE, 36))
                p.drawRoundedRect(QRectF(x - 3, y - 3, t + 6, t + 6), 9, 9)
            pm = self._icono(a, color)
            if pm:
                p.drawPixmap(QPointF(x, y), pm)


class SelectorApps(QDialog):
    """Elegir apps del menú Inicio (o cualquier .exe) para el lanzador."""

    def __init__(self, ya, padre=None):
        super().__init__(padre)
        self.setWindowTitle(_("Añadir aplicación"))
        self.setStyleSheet(ESTILO_DIALOGO + "QListWidget { background: #20232b; color: #e6e9ef; "
                           "border: 1px solid #3a3f4b; border-radius: 6px; } QListWidget::item { padding: 4px; }")
        self.resize(440, 540)
        self.extra = []
        caja = QVBoxLayout(self)
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText(_("Buscar…"))
        self.buscar.textChanged.connect(self.filtrar)
        caja.addWidget(self.buscar)
        self.lista = QListWidget()
        self.lista.setSelectionMode(QListWidget.ExtendedSelection)
        self.lista.setIconSize(QSize(24, 24))
        self.lista.itemDoubleClicked.connect(lambda _i: self.accept())
        iconos = QFileIconProvider()
        for a in lanzador.apps_windows():
            if a["id"] in ya:
                continue
            item = QListWidgetItem(iconos.icon(QFileInfo(a["id"])), a["nombre"])
            item.setData(Qt.UserRole, a)
            self.lista.addItem(item)
        caja.addWidget(self.lista, 1)
        botones = QHBoxLayout()
        exe = QPushButton(_("Elegir un programa (.exe)…"))
        exe.clicked.connect(self.elegir_exe)
        botones.addWidget(exe)
        botones.addStretch(1)
        for texto, fn, principal in ((_("Cancelar"), self.reject, False), (_("Añadir"), self.accept, True)):
            b = QPushButton(texto)
            b.clicked.connect(fn)
            if principal:
                b.setProperty("estilo", "principal")
                b.setDefault(True)
            botones.addWidget(b)
        caja.addLayout(botones)

    def filtrar(self, texto):
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            item.setHidden(texto.lower() not in item.text().lower())

    def elegir_exe(self):
        ruta, _x = QFileDialog.getOpenFileName(self, _("Elegir un programa (.exe)…"), os.environ.get("ProgramFiles", ""),
                                               _("Programas (*.exe)"))
        if ruta:
            ruta = os.path.normpath(ruta)
            self.extra.append({"id": ruta, "nombre": os.path.splitext(os.path.basename(ruta))[0]})
            self.accept()

    def elegidas(self):
        return [i.data(Qt.UserRole) for i in self.lista.selectedItems()] + self.extra


class Metodos:
    """Se añaden a Monitor."""

    def menu_apps(self, menu, padre=None):
        v = self.apps_vista
        apps = v.apps()
        i, v.menu_indice = v.menu_indice, None
        menu.addAction(_("Añadir aplicación…"), lambda: self.anadir_apps(padre))
        if i is not None and i < len(apps):
            menu.addAction(_("Quitar {app}").format(app=apps[i]["nombre"]), lambda: self.mover_app(i, None))
            if i > 0:
                menu.addAction(_("Mover a la izquierda"), lambda: self.mover_app(i, i - 1))
            if i < len(apps) - 1:
                menu.addAction(_("Mover a la derecha"), lambda: self.mover_app(i, i + 1))
        sub = menu.addMenu(_("Color de los iconos"))
        for clave, nombre in lanzador.COLORES_ICONOS:
            a = sub.addAction(_(nombre), lambda _x=False, c=clave: self.color_apps(c))
            a.setCheckable(True)
            a.setChecked(self.config.get("apps_color", "original") == clave)
        menu.addSeparator()

    def anadir_apps(self, padre=None):
        apps = self.apps_vista.apps()
        dlg = SelectorApps({a["id"] for a in apps}, padre)
        if dlg.exec() == QDialog.Accepted:
            apps.extend(dlg.elegidas())
            self.apps_vista.cambiado()
            self.ajustar_alturas()

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
    self.apps_vista = VistaApps(self)
    c.add(self.apps_vista)


def menu(self, tarjeta, menu):
    if tarjeta.clave == "apps":
        self.menu_apps(menu, tarjeta.window())


def ajustes(self, caja):
    """Configuración > Widgets (self es la ventana)."""
    app = self.app
    lista = self.grupo(caja, "Aplicaciones", "Añade apps con el clic derecho en el widget de aplicaciones.")
    color = QComboBox()
    for clave, nombre in lanzador.COLORES_ICONOS:
        color.addItem(_(nombre), clave)
    color.setCurrentIndex(max(0, color.findData(app.config.get("apps_color", "original"))))
    color.currentIndexChanged.connect(lambda i: app.color_apps(color.itemData(i)))
    self.fila(lista, "Color de los iconos", color, "Los del tema se adaptan al cambiar de tema")
