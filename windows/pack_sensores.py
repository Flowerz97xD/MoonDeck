"""Widget Sensores (Windows): los sensores que elijas, por tipo."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
from idioma import _

WIDGETS = ('temperaturas',)


def fmt_sensor(tipo, valor, color=True):
    formato = TIPOS_SENSOR.get(tipo, (tipo, "{:.2f}"))[1]
    if formato == "rpm":
        return f"{valor:,.0f} RPM".replace(",", ".") if valor > 0 else _("parado")
    if formato == "bytes/s":
        return fmt_bytes(valor, True)
    texto = formato.format(valor)
    if color and tipo == "Temperature":
        return f'<span style="color:{color_temp(valor)}">{texto}</span>'
    return texto


def seleccion_auto(sensores):
    """Lo que se ve si no se ha elegido nada: temperaturas con sentido, y los
    ventiladores de las GPUs (paran a 0 RPM en reposo) y los que giran (los
    conectores vacíos de la placa marcan 0 siempre)."""
    temps, por_dispositivo, vistos = [], {}, set()
    for kind, hw, tipo, nombre, valor, ident in sensores:
        if tipo != "Temperature" or "distance" in nombre.lower() or not 5 < valor < 115:
            continue
        # Como mucho dos por dispositivo (la placa tiene muchos) y sin repetidos.
        if (hw, nombre) in vistos or por_dispositivo.get(hw, 0) >= 2:
            continue
        vistos.add((hw, nombre))
        por_dispositivo[hw] = por_dispositivo.get(hw, 0) + 1
        temps.append(ident)
    fans = [x[5] for x in sensores if x[2] == "Fan" and (x[0].startswith("Gpu") or x[4] > 0)]
    return temps[:12] + fans[:6]


class ListaSensores(QWidget):
    """Lista de sensores que se adapta al espacio: varias columnas si es ancha y, si
    aun así no caben, los que quepan y "… y N más" (en vez de aplastar las filas)."""

    FILA = 19
    ANCHO_COLUMNA = 250
    ANCHO_VALOR = 84

    def __init__(self):
        super().__init__()
        self.lineas = []   # ("seccion", texto) o ("sensor", nombre, valor, color)
        # Sin "alto para el ancho": Qt no deja bajar de ese alto, y en una celda pequeña
        # tiene que poder encoger (enseña "… y N más").
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_lineas(self, lineas):
        cambia_alto = len(lineas) != len(self.lineas)
        self.lineas = lineas
        if cambia_alto:
            self.updateGeometry()
        self.update()

    def columnas(self, ancho):
        return max(1, min(ancho // self.ANCHO_COLUMNA, len(self.lineas) or 1))

    def alto_para(self, ancho):
        return -(-len(self.lineas) // self.columnas(ancho)) * self.FILA

    def sizeHint(self):
        return QSize(M.ANCHO - 32, self.alto_para(M.ANCHO - 32))

    def minimumSizeHint(self):
        return QSize(100, self.FILA * 3)

    @staticmethod
    def huecos(lineas, por_columna):
        """Posición (hueco) de cada línea: un título nunca queda el último de una
        columna separado de sus sensores; pasa a la siguiente."""
        posiciones, hueco = [], 0
        for linea in lineas:
            if linea[0] == "seccion" and hueco % por_columna == por_columna - 1:
                hueco += 1
            posiciones.append(hueco)
            hueco += 1
        return posiciones, hueco

    def paintEvent(self, _e):
        p = QPainter(self)
        cols = self.columnas(self.width())
        maximo = max(1, self.height() // self.FILA)
        lineas = self.lineas
        # Columnas equilibradas: la altura mínima con la que todo cabe.
        por_columna = -(-len(lineas) // cols) or 1
        while por_columna < maximo and self.huecos(lineas, por_columna)[1] > cols * por_columna:
            por_columna += 1
        if por_columna > maximo or self.huecos(lineas, por_columna)[1] > cols * por_columna:
            por_columna = maximo
            while lineas and self.huecos(lineas, por_columna)[1] > cols * por_columna - 1:
                lineas = lineas[:-1]
            ocultas = sum(1 for x in self.lineas[len(lineas):] if x[0] == "sensor")
            lineas = lineas + [("mas", _("… y {n} más (amplía el widget)").format(n=ocultas))]
        posiciones, _x = self.huecos(lineas, por_columna)
        ancho_col = (self.width() - 16 * (cols - 1)) / cols
        normal = QFont(self.font())
        normal.setPointSizeF(9.5)
        seccion = QFont(normal)
        seccion.setPointSizeF(7.5)
        seccion.setBold(True)
        for i, linea in zip(posiciones, lineas):
            x = (i // por_columna) * (ancho_col + 16)
            y = (i % por_columna) * self.FILA
            caja = QRectF(x, y, ancho_col, self.FILA)
            if linea[0] == "seccion":
                p.setFont(seccion)
                p.setPen(QColor(M.C_TITULO))
                p.drawText(caja, Qt.AlignLeft | Qt.AlignBottom, linea[1])
            elif linea[0] == "mas":
                p.setFont(normal)
                p.setPen(QColor(M.C_SEC))
                p.drawText(caja.adjusted(0, 0, 400, 0), Qt.AlignLeft | Qt.AlignVCenter, linea[1])
            else:
                _x, nombre, valor, color = linea
                p.setFont(normal)
                p.setPen(QColor(color))
                p.drawText(caja, Qt.AlignRight | Qt.AlignVCenter, valor)
                p.setPen(QColor(M.C_NORMAL))
                ancho_nombre = int(ancho_col - self.ANCHO_VALOR)
                p.drawText(caja.adjusted(0, 0, -self.ANCHO_VALOR, 0), Qt.AlignLeft | Qt.AlignVCenter,
                           p.fontMetrics().elidedText(nombre, Qt.ElideRight, ancho_nombre))


class SelectorSensores(QDialog):
    """Ventana para marcar qué sensores se muestran, agrupados por dispositivo y tipo."""

    def __init__(self, sensores, seleccion, padre=None):
        super().__init__(padre)
        self.setWindowTitle(_("Elegir sensores"))
        self.setStyleSheet(ESTILO_DIALOGO)
        self.resize(600, 680)
        self.por_defecto = False
        caja = QVBoxLayout(self)
        caja.addWidget(QLabel(_("Marca los sensores que quieres ver en el widget Sensores "
                                "(hasta {n}).").format(n=MAX_SENSORES)))
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText(_("Buscar: «cpu», «voltaje», «fan», «nvme»…"))
        self.buscar.textChanged.connect(self.filtrar)
        caja.addWidget(self.buscar)

        self.arbol = QTreeWidget()
        self.arbol.setHeaderLabels([_("Sensor"), _("Valor")])
        self.arbol.setColumnWidth(0, 420)
        marcados = set(seleccion)
        dispositivos = {}
        for kind, hw, tipo, nombre, valor, ident in sensores:
            disp = dispositivos.get(hw)
            if disp is None:
                disp = dispositivos[hw] = QTreeWidgetItem(self.arbol, [hw])
                disp.setFlags(disp.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                disp.secciones = {}
            seccion_txt = _(TIPOS_SENSOR.get(tipo, (tipo,))[0])
            seccion = disp.secciones.get(seccion_txt)
            if seccion is None:
                seccion = disp.secciones[seccion_txt] = QTreeWidgetItem(disp, [seccion_txt])
                seccion.setFlags(seccion.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
            item = QTreeWidgetItem(seccion, [nombre, fmt_sensor(tipo, valor, color=False)])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked if ident in marcados else Qt.Unchecked)
            item.ident = ident
            item.busqueda = f"{hw} {seccion_txt} {tipo} {nombre}".lower()
        for disp in dispositivos.values():
            # Abiertos los grupos con algo marcado, para ver de un vistazo lo elegido.
            disp.setExpanded(disp.checkState(0) != Qt.Unchecked)
            for seccion in disp.secciones.values():
                seccion.setExpanded(seccion.checkState(0) != Qt.Unchecked)
        caja.addWidget(self.arbol, 1)

        botones = QHBoxLayout()
        for texto, fn in ((_("Por defecto"), self.restablecer), (_("Ninguno"), self.ninguno)):
            b = QPushButton(texto)
            b.clicked.connect(fn)
            botones.addWidget(b)
        botones.addStretch()
        cancelar = QPushButton(_("Cancelar"))
        cancelar.clicked.connect(self.reject)
        aceptar = QPushButton(_("Aceptar"))
        aceptar.setObjectName("aceptar")
        aceptar.clicked.connect(self.accept)
        botones.addWidget(cancelar)
        botones.addWidget(aceptar)
        caja.addLayout(botones)

    def hojas(self):
        for i in range(self.arbol.topLevelItemCount()):
            disp = self.arbol.topLevelItem(i)
            for j in range(disp.childCount()):
                seccion = disp.child(j)
                for k in range(seccion.childCount()):
                    yield seccion.child(k)

    def seleccion(self):
        return [h.ident for h in self.hojas() if h.checkState(0) == Qt.Checked][:MAX_SENSORES]

    def filtrar(self, texto):
        texto = texto.lower().strip()
        for h in self.hojas():
            h.setHidden(bool(texto) and texto not in h.busqueda)
        for i in range(self.arbol.topLevelItemCount()):
            disp = self.arbol.topLevelItem(i)
            for j in range(disp.childCount()):
                seccion = disp.child(j)
                visibles = any(not seccion.child(k).isHidden() for k in range(seccion.childCount()))
                seccion.setHidden(not visibles)
                seccion.setExpanded(bool(texto) or seccion.isExpanded())
            disp.setHidden(all(disp.child(j).isHidden() for j in range(disp.childCount())))
            disp.setExpanded(bool(texto) or disp.isExpanded())

    def ninguno(self):
        for h in self.hojas():
            h.setCheckState(0, Qt.Unchecked)

    def restablecer(self):
        self.por_defecto = True
        self.accept()


class Metodos:
    """Se añaden a Monitor."""

    def construir_sensores(self, s):
        """Decide qué sensores muestra el widget Sensores y en qué orden (por tipo)."""
        elegidos = self.config.get("sensores")
        if elegidos is None:
            elegidos = seleccion_auto(s["sensores"])
        tipos = {x[5]: x[2] for x in s["sensores"]}
        orden = list(dict.fromkeys(v[0] for v in TIPOS_SENSOR.values()))
        por_seccion = {}
        for ident in elegidos:
            if ident in tipos:
                seccion = TIPOS_SENSOR.get(tipos[ident], (tipos[ident],))[0]
                por_seccion.setdefault(seccion, []).append(ident)
        self.sens_secciones = [(sec, por_seccion[sec]) for sec in
                               sorted(por_seccion, key=lambda x: orden.index(x) if x in orden else 99)]
        self.pintar_sensores(s)

    def pintar_sensores(self, s):
        valores = {x[5]: x for x in s["sensores"]}
        lineas = []
        for seccion, idents in self.sens_secciones:
            if len(self.sens_secciones) > 1:
                lineas.append(("seccion", _(seccion).upper()))
            for ident in idents:
                x = valores.get(ident)
                if x:
                    _x, hw, tipo, nombre, valor, _x = x
                    color = color_temp(valor) if tipo == "Temperature" else M.C_CLARO
                    lineas.append(("sensor", f"{hw} · {nombre}", fmt_sensor(tipo, valor, color=False), color))
        if not lineas:
            lineas = [("mas", _("Ningún sensor elegido: clic derecho > «Elegir sensores…»"))]
        self.sens_lista.set_lineas(lineas)

    def elegir_sensores(self, padre=None):
        s = getattr(self, "ultimo", None)
        if not s:
            return
        actual = self.config.get("sensores")
        dialogo = SelectorSensores(s["sensores"], seleccion_auto(s["sensores"]) if actual is None else actual,
                                   padre)
        if dialogo.exec():
            self.config["sensores"] = None if dialogo.por_defecto else dialogo.seleccion()
            self.construir_sensores(s)
            self.aplicar(s)
            self.guardar_config()


def construir(self, s):
    # Los elegidos en "Elegir sensores…" (o una selección automática).
    c = self.tarjeta("temperaturas", "Sensores")
    if s["lhm_error"] and ES_WINDOWS:
        aviso = c.add(etiqueta(s["lhm_error"] + _(". Abre la app con iniciar.bat (como administrador)."), "dim"))
        aviso.setWordWrap(True)
    self.sens_lista = ListaSensores()
    c.add(self.sens_lista)
    c._estira = True  # la lista absorbe el alto sobrante
    self.construir_sensores(s)


def aplicar(self, s):
    self.pintar_sensores(s)


def acciones(self, menu, padre):
    menu.addAction(_("Elegir sensores…"), lambda: self.elegir_sensores(padre))


def menu(self, tarjeta, menu):
    menu.addAction(_("Elegir sensores…"), lambda: self.elegir_sensores(tarjeta.window()))
