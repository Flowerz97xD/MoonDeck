"""Widget Sensores (Linux): los sensores que elijas, por tipo."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
from idioma import _

WIDGETS = ('temperaturas',)


def fmt_sensor(tipo, valor):
    formato = TIPOS_SENSOR.get(tipo, (tipo, "{:.2f}"))[1]
    if formato == "rpm":
        return f"{valor:,.0f} RPM".replace(",", ".") if valor > 0 else _("parado")
    if formato == "bytes/s":
        return fmt_bytes(valor, True)
    return formato.format(valor)


def seleccion_auto(sensores):
    """Lo que se ve si no se ha elegido nada: temperaturas con sentido, y los
    ventiladores de las GPUs (paran en reposo) y los que giran."""
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
    fans += [x[5] for x in sensores if x[2] == "Control" and x[0].startswith("Gpu")]
    return temps[:12] + fans[:6]


class ListaSensores(Dibujo):
    """Lista de sensores que se adapta al espacio: varias columnas si es ancha y, si
    aun así no caben, los que quepan y "… y N más" (en vez de aplastar las filas)."""

    FILA = 19
    ANCHO_COLUMNA = 250
    ANCHO_VALOR = 84

    def __init__(self):
        super().__init__()
        self.lineas = []   # ("seccion", texto) o ("sensor", nombre, valor, color)
        self.set_vexpand(True)
        self.connect("draw", self.dibujar)

    def set_lineas(self, lineas):
        cambia_alto = len(lineas) != len(self.lineas)
        self.lineas = lineas
        if cambia_alto:
            self.queue_resize()
        self.queue_draw()

    def columnas(self, ancho):
        return max(1, min(ancho // self.ANCHO_COLUMNA, len(self.lineas) or 1))

    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_get_preferred_width(self):
        return 100, M.ANCHO - 32

    def do_get_preferred_height_for_width(self, ancho):
        return self.FILA * 3, max(self.FILA * 3, -(-len(self.lineas) // self.columnas(ancho)) * self.FILA)

    def do_get_preferred_height(self):
        return self.do_get_preferred_height_for_width(M.ANCHO - 32)

    @staticmethod
    def huecos(lineas, por_columna):
        """Posición de cada línea: un título nunca queda el último de una columna."""
        posiciones, hueco = [], 0
        for linea in lineas:
            if linea[0] == "seccion" and hueco % por_columna == por_columna - 1:
                hueco += 1
            posiciones.append(hueco)
            hueco += 1
        return posiciones, hueco

    def dibujar(self, _w, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        cols = self.columnas(w)
        maximo = max(1, h // self.FILA)
        lineas = self.lineas
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
        ancho_col = (w - 16 * (cols - 1)) / cols
        for i, linea in zip(posiciones, lineas):
            x = (i // por_columna) * (ancho_col + 16)
            y = (i % por_columna) * self.FILA
            if linea[0] == "seccion":
                lay = capa_texto(self, cr, linea[1], 10, Pango.Weight.BOLD)
                pintar_texto(cr, lay, x, y, ancho_col, self.FILA, M.TITULO, v_al=0.9)
            elif linea[0] == "mas":
                lay = capa_texto(self, cr, linea[1], 12.5)
                pintar_texto(cr, lay, x, y, w - x, self.FILA, M.GRIS, recortar=True)
            else:
                _x, nombre, valor, color = linea
                lay = capa_texto(self, cr, valor, 12.5)
                pintar_texto(cr, lay, x, y, ancho_col, self.FILA, hex_rgb(color), 1.0)
                lay = capa_texto(self, cr, nombre, 12.5)
                # Corte por el medio: se ve el dispositivo y el nombre del sensor.
                pintar_texto(cr, lay, x, y, ancho_col - self.ANCHO_VALOR, self.FILA, M.NORMAL,
                             recortar="medio")


class SelectorSensores(Gtk.Dialog):
    """Ventana para marcar qué sensores se muestran, agrupados por dispositivo y tipo."""

    # Columnas del modelo
    TEXTO, VALOR, MARCA, MEDIO, IDENT, BUSCA, VISIBLE = range(7)

    def __init__(self, sensores, seleccion):
        super().__init__(title=_("Elegir sensores"))
        self.set_default_size(600, 680)
        self.get_style_context().add_class("selector")
        self.add_button(_("Por defecto"), 1)
        self.add_button(_("Ninguno"), 2)
        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        aceptar = self.add_button(_("Aceptar"), Gtk.ResponseType.OK)
        aceptar.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)
        area = self.get_content_area()
        area.set_spacing(8)
        area.set_border_width(10)
        area.pack_start(Gtk.Label(label=_("Marca los sensores que quieres ver en el widget Sensores "
                                                  "(hasta {n}).").format(n=MAX_SENSORES), xalign=0), False, False, 0)
        self.buscar = Gtk.SearchEntry()
        self.buscar.set_placeholder_text(_("Buscar: «cpu», «voltaje», «fan», «nvme»…"))
        self.buscar.connect("search-changed", lambda e: self.filtrar(e.get_text()))
        area.pack_start(self.buscar, False, False, 0)

        self.modelo = Gtk.TreeStore(str, str, bool, bool, str, str, bool)
        marcados = set(seleccion)
        dispositivos = {}
        for kind, hw, tipo, nombre, valor, ident in sensores:
            if hw not in dispositivos:
                dispositivos[hw] = (self.modelo.append(None, [hw, "", False, False, "", hw.lower(), True]), {})
            disp, secciones = dispositivos[hw]
            seccion_txt = _(TIPOS_SENSOR.get(tipo, (tipo,))[0])
            if seccion_txt not in secciones:
                secciones[seccion_txt] = self.modelo.append(disp, [seccion_txt, "", False, False, "", "", True])
            self.modelo.append(secciones[seccion_txt], [
                nombre, fmt_sensor(tipo, valor), ident in marcados, False, ident,
                f"{hw} {seccion_txt} {tipo} {nombre}".lower(), True])
        self.recalcular_padres()

        self.filtro = self.modelo.filter_new()
        self.filtro.set_visible_column(self.VISIBLE)
        self.arbol = Gtk.TreeView(model=self.filtro)
        self.arbol.set_headers_visible(True)
        marca = Gtk.CellRendererToggle()
        marca.connect("toggled", self.marcar)
        col = Gtk.TreeViewColumn(_("Sensor"))
        col.pack_start(marca, False)
        col.add_attribute(marca, "active", self.MARCA)
        col.add_attribute(marca, "inconsistent", self.MEDIO)
        texto = Gtk.CellRendererText(ellipsize=Pango.EllipsizeMode.END)
        col.pack_start(texto, True)
        col.add_attribute(texto, "text", self.TEXTO)
        col.set_expand(True)
        self.arbol.append_column(col)
        valor = Gtk.CellRendererText(xalign=1.0)
        self.arbol.append_column(Gtk.TreeViewColumn(_("Valor"), valor, text=self.VALOR))
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.add(self.arbol)
        area.pack_start(scroll, True, True, 0)
        # Abiertos los grupos con algo marcado, para ver de un vistazo lo elegido.
        self.expandir_marcados()
        self.show_all()

    def hojas(self, it=None):
        it = self.modelo.iter_children(it)
        while it:
            if self.modelo.iter_has_child(it):
                yield from self.hojas(it)
            elif self.modelo[it][self.IDENT]:
                yield it
            it = self.modelo.iter_next(it)

    def recalcular_padres(self, it=None):
        """Marca de los grupos: llena si todo está marcado, a medias si solo algo."""
        estados = []
        hijo = self.modelo.iter_children(it)
        while hijo:
            if self.modelo.iter_has_child(hijo):
                estados.append(self.recalcular_padres(hijo))
            else:
                estados.append("si" if self.modelo[hijo][self.MARCA] else "no")
            hijo = self.modelo.iter_next(hijo)
        if it is None:
            return None
        estado = "si" if all(e == "si" for e in estados) else "no" if all(e == "no" for e in estados) else "medio"
        self.modelo[it][self.MARCA] = estado == "si"
        self.modelo[it][self.MEDIO] = estado == "medio"
        return estado

    def marcar(self, _r, ruta_filtro):
        it = self.filtro.convert_iter_to_child_iter(self.filtro.get_iter(ruta_filtro))
        nuevo = not self.modelo[it][self.MARCA] or self.modelo[it][self.MEDIO]
        if self.modelo.iter_has_child(it):
            for h in self.hojas(it):
                if self.modelo[h][self.VISIBLE]:
                    self.modelo[h][self.MARCA] = nuevo
        else:
            self.modelo[it][self.MARCA] = nuevo
        self.recalcular_padres()

    def expandir_marcados(self):
        def recorrer(it):
            while it:
                if self.modelo.iter_has_child(it) and (self.modelo[it][self.MARCA] or self.modelo[it][self.MEDIO]):
                    ok, f = self.filtro.convert_child_iter_to_iter(it)
                    if ok:
                        self.arbol.expand_row(self.filtro.get_path(f), False)
                    recorrer(self.modelo.iter_children(it))
                it = self.modelo.iter_next(it)
        recorrer(self.modelo.get_iter_first())

    def filtrar(self, texto):
        texto = texto.lower().strip()

        def recorrer(it):
            alguno = False
            while it:
                if self.modelo.iter_has_child(it):
                    v = recorrer(self.modelo.iter_children(it))
                else:
                    v = not texto or texto in self.modelo[it][self.BUSCA]
                self.modelo[it][self.VISIBLE] = v
                alguno = alguno or v
                it = self.modelo.iter_next(it)
            return alguno
        recorrer(self.modelo.get_iter_first())
        self.filtro.refilter()
        if texto:
            self.arbol.expand_all()

    def ninguno(self):
        for h in self.hojas():
            self.modelo[h][self.MARCA] = False
        self.recalcular_padres()

    def seleccion(self):
        return [self.modelo[h][self.IDENT] for h in self.hojas() if self.modelo[h][self.MARCA]][:MAX_SENSORES]


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
                    color = color_temp(valor) if tipo == "Temperature" else temas.a_hex(M.CLARO)
                    lineas.append(("sensor", f"{hw} · {nombre}", fmt_sensor(tipo, valor), color))
        if not lineas:
            lineas = [("mas", _("Ningún sensor elegido: clic derecho > «Elegir sensores…»"))]
        self.sens_lista.set_lineas(lineas)

    def elegir_sensores(self):
        s = getattr(self, "ultimo", None)
        if not s:
            return
        actual = self.config.get("sensores")
        dialogo = SelectorSensores(s["sensores"], seleccion_auto(s["sensores"]) if actual is None else actual)
        while True:
            r = dialogo.run()
            if r == 2:
                dialogo.ninguno()
                continue
            break
        if r in (Gtk.ResponseType.OK, 1):
            self.config["sensores"] = None if r == 1 else dialogo.seleccion()
            self.construir_sensores(s)
            self.aplicar(s)
            self.guardar_config()
        dialogo.destroy()


def construir(self, s):
    # Los elegidos en "Elegir sensores…" (o una selección automática).
    c = self.tarjeta("temperaturas", "Sensores")
    self.sens_lista = c.add_w(ListaSensores(), expand=True)
    self.construir_sensores(s)


def aplicar(self, s):
    self.pintar_sensores(s)


def acciones(self, menu):
    self.item(menu, "Elegir sensores…", self.elegir_sensores)


def menu(self, tarjeta, menu):
    self.item(menu, "Elegir sensores…", self.elegir_sensores)
