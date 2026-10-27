"""Pack Discord (Windows): el canal de voz en el que estás."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
from discord_voz import CLIENT_ID_POR_DEFECTO, CLIENT_SECRET_POR_DEFECTO, Discord, abrir_discord
from idioma import _

WIDGETS = ('discord',)


def pixmap_redondo(datos, tam, dpr):
    img = QPixmap()
    final = QPixmap(int(tam * dpr), int(tam * dpr))
    final.setDevicePixelRatio(dpr)
    final.fill(Qt.transparent)
    if not datos or not img.loadFromData(datos):
        return None
    p = QPainter(final)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    ruta = QPainterPath()
    ruta.addEllipse(QRectF(0, 0, tam, tam))
    p.setClipPath(ruta)
    img = img.scaled(int(tam * dpr), int(tam * dpr), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    img.setDevicePixelRatio(dpr)
    p.drawPixmap(QPointF(0, 0), img)
    p.end()
    return final


class Avatar(QWidget):
    """Avatar redondo; con un aro verde mientras la persona habla."""

    TAM = 26

    def __init__(self):
        super().__init__()
        self.setFixedSize(self.TAM + 4, self.TAM + 4)
        self.url = None
        self.pix = None
        self.hablando = False
        self.inicial = "?"

    def poner(self, url, datos, inicial):
        self.inicial = (inicial or "?")[:1].upper()
        if url != self.url or (datos and not self.pix):
            self.url = url
            self.pix = pixmap_redondo(datos, self.TAM, self.devicePixelRatioF())
            self.update()

    def set_hablando(self, si):
        if si != self.hablando:
            self.hablando = si
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.TAM / 2 + 2, self.TAM / 2 + 2)
        if self.pix:
            p.drawPixmap(QPointF(2, 2), self.pix)
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#5865f2"))  # azul de Discord
            p.drawEllipse(c, self.TAM / 2, self.TAM / 2)
            f = QFont(self.font())
            f.setPixelSize(12)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("white"))
            p.drawText(QRectF(2, 2, self.TAM, self.TAM), Qt.AlignCenter, self.inicial)
        if self.hablando:
            p.setPen(QPen(COLORES["verde"], 2.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, self.TAM / 2 + 0.8, self.TAM / 2 + 0.8)


class FilaDiscord(QWidget):
    """Una persona del canal: avatar, nombre, micro/cascos y su volumen (solo para mí)."""

    def __init__(self, discord, uid, soy_yo):
        super().__init__()
        self.discord = discord
        self.uid = uid
        self._mute = False
        self._pendiente = None
        self._actualizando = False
        self._enviar = QTimer(self, singleShot=True, interval=150)  # Discord limita las peticiones
        self._enviar.timeout.connect(lambda: self.discord.volumen_usuario(self.uid, self._pendiente))
        caja = QVBoxLayout(self)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(2)
        arriba = QHBoxLayout()
        arriba.setSpacing(8)
        self.avatar = Avatar()
        arriba.addWidget(self.avatar)
        self.nombre = etiqueta("", "sub")
        arriba.addWidget(self.nombre, 1)
        self.estado = etiqueta("", "sub")
        arriba.addWidget(self.estado)
        self.b_vol = None
        if not soy_yo:
            self.b_vol = boton_icono("volumen", 10)
            self.b_vol.setToolTip(_("Volumen de esta persona (solo para ti)"))
            self.b_vol.clicked.connect(lambda: self.abajo.setVisible(not self.abajo.isVisible()))
            arriba.addWidget(self.b_vol)
        caja.addLayout(arriba)
        if not soy_yo:
            self.abajo = QWidget()
            fila = QHBoxLayout(self.abajo)
            fila.setContentsMargins(34, 0, 0, 0)
            fila.setSpacing(6)
            self.slider = QSlider(Qt.Horizontal)
            self.slider.setRange(0, 200)
            self.slider.setCursor(Qt.PointingHandCursor)
            self.slider.valueChanged.connect(self._cambio)
            fila.addWidget(self.slider, 1)
            self.valor = etiqueta("", "dim")
            self.valor.setFixedWidth(40)
            self.valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            fila.addWidget(self.valor)
            self.b_mute = QPushButton(_("Silenciar"))
            self.b_mute.setCheckable(True)
            self.b_mute.setCursor(Qt.PointingHandCursor)
            self.b_mute.setToolTip(_("Silenciar a esta persona solo para ti"))
            self.b_mute.clicked.connect(lambda: self.discord.silenciar_usuario(self.uid, not self._mute))
            fila.addWidget(self.b_mute)
            self.abajo.hide()
            caja.addWidget(self.abajo)

    def _cambio(self, v):
        self.valor.setText(f"{v} %")
        if not self._actualizando:
            self._pendiente = v
            self._enviar.start()

    def actualizar(self, m, hablando, avatar):
        recortar(self.nombre, m["nombre"] + (_(" · bot") if m["bot"] else ""), M.ANCHO - 140)
        self.nombre.setStyleSheet(f"color: {COLORES['verde'].name()};" if hablando else "")
        self.avatar.poner(m["avatar"], avatar, m["nombre"])
        self.avatar.set_hablando(hablando)
        rojo = COLORES["rojo"].name()
        self.estado.setText(f'<span style="color:{rojo}">🎧 ✕</span>' if m["ensordecido"] else
                            f'<span style="color:{rojo}">🎙 ✕</span>' if m["micro_off"] else "")
        if self.b_vol:
            self._mute = m["silenciado_local"]
            self.b_mute.setChecked(self._mute)
            self.b_mute.setText(_("Activar") if self._mute else _("Silenciar"))
            poner_icono(self.b_vol, "silencio" if self._mute else "volumen", 10)
            if not self._enviar.isActive() and not self.slider.isSliderDown():
                self._actualizando = True
                self.slider.setValue(round(m["volumen"]))
                self._actualizando = False
                self.valor.setText(f"{round(m['volumen'])} %")


def guia_discord():
    """La guía paso a paso de Discord en GitHub (en español o en inglés)."""
    nombre = "DISCORD.md" if idioma.actual() == "es" else "DISCORD.en.md"
    return f"https://github.com/{REPO}/blob/main/docs/{nombre}"


class DialogoDiscord(QDialog):
    """Conectar con Discord paso a paso: pide el Client ID y el Client Secret."""

    def __init__(self, client_id, padre=None):
        super().__init__(padre)
        self.setWindowTitle(_("Conectar con Discord"))
        self.setStyleSheet(ESTILO_DIALOGO)
        self.resize(580, 420)
        caja = QVBoxLayout(self)

        def texto(html, sub=False):
            lb = QLabel(html)
            lb.setWordWrap(True)
            if sub:
                lb.setStyleSheet("color: #8b94a4;")
            caja.addWidget(lb)

        texto(_("Discord solo deja controlar la voz a aplicaciones registradas. Crea la tuya "
                "(gratis, una sola vez, unos 3 minutos):"))
        if CLIENT_SECRET_POR_DEFECTO:
            texto(_("<b>¿Te han invitado como tester de la aplicación de MoonDeck?</b> Acepta la invitación, "
                    "deja el Client Secret vacío y pulsa Conectar."))
        pasos = (
            _("Abre <b>discord.com/developers</b> y pulsa <b>New Application</b> (el nombre da igual)."),
            _("En <b>OAuth2</b>, copia el <b>Client ID</b>; pulsa <b>Reset Secret</b> y copia el <b>Client Secret</b>."),
            _("En la misma página, en <b>Redirects</b>: <b>Add Redirect</b>, escribe <tt>http://localhost</tt> "
              "y pulsa <b>Save Changes</b>."),
            _("Pega aquí los dos datos y pulsa <b>Conectar</b>. Con Discord abierto, acepta <b>Autorizar</b>."),
        )
        for n, paso in enumerate(pasos, 1):
            texto(f"<b>{n}.</b>&nbsp; {paso}")
        enlaces = QHBoxLayout()
        for etiq, url in ((_("Abrir discord.com/developers"), "https://discord.com/developers/applications"),
                          (_("Ver la guía paso a paso"), guia_discord())):
            b = QPushButton(etiq)
            b.clicked.connect(lambda _x=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            enlaces.addWidget(b)
        enlaces.addStretch()
        caja.addLayout(enlaces)
        rejilla = QGridLayout()
        self.id = QLineEdit(client_id)
        self.id.setPlaceholderText(_("Un número largo, de OAuth2 > Client ID"))
        self.secreto = QLineEdit()
        self.secreto.setEchoMode(QLineEdit.Password)
        self.secreto.setPlaceholderText(_("Vacío = el de la aplicación de MoonDeck") if CLIENT_SECRET_POR_DEFECTO
                                        else _("De OAuth2 > Reset Secret"))
        for fila, (nombre, campo) in enumerate((("Client ID", self.id), ("Client Secret", self.secreto))):
            rejilla.addWidget(QLabel(nombre), fila, 0)
            rejilla.addWidget(campo, fila, 1)
        caja.addLayout(rejilla)
        texto(_("Se guardan solo en tu equipo."), sub=True)
        botones = QHBoxLayout()
        botones.addStretch()
        cancelar = QPushButton(_("Cancelar"))
        cancelar.clicked.connect(self.reject)
        ok = QPushButton(_("Conectar"))
        ok.setObjectName("aceptar")
        ok.clicked.connect(self.accept)
        botones.addWidget(cancelar)
        botones.addWidget(ok)
        caja.addLayout(botones)


class Metodos:
    """Se añaden a Monitor."""

    def conectar_discord(self, padre=None):
        # La aplicación de serie solo sirve si este MoonDeck trae su secreto (versión para amigos).
        propio = self.discord.cfg.get("client_id")
        dlg = DialogoDiscord(propio or (CLIENT_ID_POR_DEFECTO if CLIENT_SECRET_POR_DEFECTO else ""), padre)
        if dlg.exec():
            ident, secreto = dlg.id.text().strip(), dlg.secreto.text().strip()
            if secreto or (CLIENT_SECRET_POR_DEFECTO and ident in ("", CLIENT_ID_POR_DEFECTO)):
                self.discord.configurar(ident or CLIENT_ID_POR_DEFECTO, secreto)

    def menu_discord(self, menu, padre=None):
        recientes = self.config.get("discord_recientes", [])
        if recientes and self.discord.estado == "conectado":
            sub = menu.addMenu(_("Entrar en un canal reciente"))
            for r in recientes:
                sub.addAction(f"{r['nombre']} · {r['servidor']}" if r["servidor"] else r["nombre"],
                              lambda _=False, i=r["id"]: self.discord.entrar(i))
        menu.addAction(_("Conectar con Discord…") if self.discord.estado == "sin_config"
                       else "Cambiar Client ID / Secret…", lambda: self.conectar_discord(padre))
        if self.discord.estado != "sin_config":
            menu.addAction(_("Desconectar de Discord (olvidar la autorización)"), self.discord.olvidar)
        menu.addSeparator()

    def recordar_canal(self, canal):
        recientes = [r for r in self.config.get("discord_recientes", []) if r["id"] != canal["id"]]
        recientes.insert(0, {"id": canal["id"], "nombre": canal["nombre"], "servidor": canal["servidor"],
                             "guild_id": canal.get("guild_id")})
        if recientes[:8] != self.config.get("discord_recientes"):
            self.config["discord_recientes"] = recientes[:8]
            self.guardar_config()

    def vigilar_discord(self):
        self.discord.vigilar(self.config["discord"]["servidores"])

    def cambiar_discord(self, **cambios):
        self.config["discord"].update(cambios)
        self.guardar_config()
        self.vigilar_discord()
        self.dc["version"] = None

    def abrir_discord(self):
        self.discord_no_instalado = not abrir_discord()
        if not self.discord_no_instalado:
            self.discord_abriendo = time.monotonic()
            self.discord._despertar.set()
        self.dc["version"] = None

    def entrar_ultimo_discord(self):
        recientes = self.config.get("discord_recientes", [])
        if recientes:
            self.discord.entrar(recientes[0]["id"])

    def al_conectar_discord(self, s):
        """Tras abrir Discord desde el widget: entra en el último canal o donde haya gente."""
        if not self.discord_abriendo or time.monotonic() - self.discord_abriendo > 120:
            self.discord_abriendo = 0
            return
        if s["estado"] != "conectado" or (s["canales_voz"] is None and self.config["discord"]["servidores"]):
            return  # aún arrancando o sin haber mirado los canales
        self.discord_abriendo = 0
        accion = self.config["discord"]["al_abrir"]
        if s["canal"]:
            return
        if accion == "ultimo":
            self.entrar_ultimo_discord()
        elif accion == "gente":
            canales = [c for c in s["canales_voz"] or [] if c["personas"]]
            if canales:
                self.discord.entrar(max(canales, key=lambda c: len(c["personas"]))["id"])

    def boton_canal_discord(self, c, con_servidor):
        b = QPushButton()
        b.setProperty("estilo", "dispositivo")
        b.setCursor(Qt.PointingHandCursor)
        textos = QVBoxLayout(b)
        textos.setContentsMargins(8, 5, 8, 5)
        textos.setSpacing(0)
        nombre = etiqueta("", "sub")
        nombre.setStyleSheet("font-weight: 600;")
        recortar(nombre, f"🔊 {c['nombre']}" + (f" · {len(c['personas'])}" if c["personas"] else ""), M.ANCHO - 48)
        textos.addWidget(nombre)
        lineas = ([", ".join(c["personas"])] if c["personas"] else []) + \
                 ([c["servidor"]] if con_servidor and c["servidor"] else [])
        for texto in lineas:
            lb = etiqueta("", "dim")
            recortar(lb, texto, M.ANCHO - 48)
            textos.addWidget(lb)
        for lb in b.findChildren(QLabel):
            lb.setAttribute(Qt.WA_TransparentForMouseEvents)
        b.setMinimumHeight(textos.sizeHint().height())
        b.clicked.connect(lambda _=False, i=c["id"]: self.discord.entrar(i))
        return b

    def actualizar_discord(self):
        d = self.dc
        s = self.discord.instantanea()
        if s["version"] == d["version"]:
            return
        d["version"] = s["version"]
        estado, canal = s["estado"], s["canal"]
        textos = {
            "sin_config": _("Conecta el widget con tu cuenta para ver y controlar tu canal de voz."),
            "desconectado": _("Discord no está abierto."),
            "conectando": _("Conectando con Discord…"),
            "autorizando": _("Mira Discord: te está pidiendo que autorices el widget."),
        }
        aviso = s["error"] if estado == "error" else textos.get(estado, "")
        if estado == "desconectado" and self.discord_abriendo:
            aviso = _("Abriendo Discord…")
        elif estado == "desconectado" and self.discord_no_instalado:
            aviso = _("No encuentro Discord instalado.")
        elif estado == "conectado" and not canal:
            aviso = (_("Elige tu servidor de Discord en Configuración > Widgets.")
                     if not self.config["discord"]["servidores"] else
                     _("Buscando canales…") if s["canales_voz"] is None else
                     _("Nadie en voz ahora mismo.") if not any(c["personas"] for c in s["canales_voz"]) else "")
        elif estado == "conectado" and s["error"]:
            aviso = s["error"]
        self.al_conectar_discord(s)
        d["aviso"].setText(aviso)
        d["aviso"].setVisible(bool(aviso))
        d["conectar"].setVisible(estado in ("sin_config", "error"))
        d["abrir"].setVisible(estado == "desconectado")
        d["abrir"].setEnabled(not self.discord_abriendo)
        en_canal = estado == "conectado" and bool(canal)

        # Sin canal: los canales de voz de mi servidor para entrar con un clic.
        canales = (s["canales_voz"] or []) if estado == "conectado" and not canal else []
        ids = [(c["id"], tuple(c["personas"])) for c in canales]
        if ids != d["canales_ids"]:
            d["canales_ids"] = ids
            while d["caja_canales"].count():
                d["caja_canales"].takeAt(0).widget().deleteLater()
            varios = len({c["guild_id"] for c in canales}) > 1
            botones = [self.boton_canal_discord(c, varios) for c in canales]
            for b in botones:
                d["caja_canales"].addWidget(b)
            # Si no caben, se quitan antes los vacíos (los últimos primero) y luego los demás.
            vacios = [b for b, c in zip(botones, canales) if not c["personas"]]
            llenos = [b for b, c in zip(botones, canales) if c["personas"]]
            d["tarjeta"].prescindibles_grupo("canales", vacios[::-1] + llenos[::-1], 1)
        d["canales"].setVisible(bool(canales))
        recientes = self.config.get("discord_recientes", [])
        ultimo = (estado == "conectado" and not canal and not self.config["discord"]["servidores"]
                  and bool(recientes))
        if ultimo:
            d["ultimo"].setText(_("Entrar en {canal}").format(canal=recientes[0]["nombre"]))
        d["ultimo"].setVisible(ultimo)
        recortar(d["canal"], f"🔊 {canal['nombre']}" if en_canal else _("Sin canal de voz"), M.ANCHO - 32)
        recortar(d["servidor"], canal["servidor"] if en_canal else "", M.ANCHO - 32)
        d["servidor"].setVisible(en_canal and bool(canal["servidor"]))
        d["controles"].setVisible(estado == "conectado")
        d["salir"].setEnabled(en_canal)
        if en_canal and canal["servidor"]:
            self.recordar_canal(canal)
        miembros = s["miembros"] if en_canal else []
        ids = [m["id"] for m in miembros]
        if ids != d["ids"]:
            d["ids"] = ids
            for f in d["filas"].values():
                f.deleteLater()
            d["filas"] = {}
            for m in miembros:
                f = FilaDiscord(self.discord, m["id"], m["id"] == s["yo"])
                d["caja_lista"].addWidget(f)
                d["filas"][m["id"]] = f
            # Si no caben todos, se quitan los últimos de la lista.
            d["tarjeta"].prescindibles_grupo("miembros", list(d["filas"].values())[::-1], 1)
        for m in miembros:
            d["filas"][m["id"]].actualizar(m, m["id"] in s["hablando"], self.discord.avatares.get(m["avatar"]))
        d["lista"].setVisible(bool(miembros))
        a = s["ajustes"]
        d["mute"].setChecked(bool(a.get("mute")))
        d["mute"].setText(_("Micro silenciado") if a.get("mute") else _("Silenciar"))
        d["deaf"].setChecked(bool(a.get("deaf")))
        d["deaf"].setText(_("Ensordecido") if a.get("deaf") else _("Ensordecer"))
        for clave in ("entrada", "salida"):
            sl, val, envio = d[clave]
            v = a.get(clave)
            if v is not None and time.monotonic() - getattr(sl, "_tocado", 0) > 1.5 and not envio.isActive() \
                    and not sl.isSliderDown():
                sl._actualizando = True
                sl.setValue(round(v))
                sl._actualizando = False
            val.setText(f"{sl.value()} %")
        self.ajustar_alturas()


def iniciar(self):
    self.discord = Discord(CARPETA)
    self.config["discord"] = dict(DISCORD_POR_DEFECTO, **self.config.get("discord", {}))
    self.discord_no_instalado = False
    self.discord_abriendo = 0  # cuándo se pulsó "Abrir Discord" (para lo que haya que hacer al conectar)
    self.vigilar_discord()


def construir(self, s):
    # Discord: el canal de voz en el que estoy
    c = self.tarjeta("discord", "Discord")
    d = {"version": None, "filas": {}, "ids": None}
    d["canal"] = c.add(etiqueta("", "sub"))
    d["canal"].setStyleSheet("font-weight: 600;")
    d["servidor"] = c.add(etiqueta("", "dim"))
    d["aviso"] = c.add(etiqueta("", "dim"))
    d["aviso"].setWordWrap(True)
    d["conectar"] = c.add(QPushButton(_("Conectar con Discord…")))
    d["conectar"].setProperty("estilo", "principal")
    d["conectar"].setCursor(Qt.PointingHandCursor)
    d["conectar"].clicked.connect(lambda: self.conectar_discord(c.window()))
    d["abrir"] = c.add(QPushButton(_("Abrir Discord")))
    d["abrir"].setProperty("estilo", "principal")
    d["abrir"].setCursor(Qt.PointingHandCursor)
    d["abrir"].clicked.connect(self.abrir_discord)
    d["canales"] = QWidget()
    d["caja_canales"] = QVBoxLayout(d["canales"])
    d["caja_canales"].setContentsMargins(0, 0, 0, 0)
    d["caja_canales"].setSpacing(4)
    d["canales_ids"] = None
    c.add(d["canales"])
    d["ultimo"] = c.add(QPushButton())
    d["ultimo"].setCursor(Qt.PointingHandCursor)
    d["ultimo"].clicked.connect(self.entrar_ultimo_discord)
    d["lista"] = QWidget()
    d["caja_lista"] = QVBoxLayout(d["lista"])
    d["caja_lista"].setContentsMargins(0, 4, 0, 0)
    d["caja_lista"].setSpacing(4)
    c.add(d["lista"])
    d["controles"] = QWidget()
    cc = QVBoxLayout(d["controles"])
    cc.setContentsMargins(0, 6, 0, 0)
    cc.setSpacing(4)
    for clave, texto, maximo, fn in (("entrada", "Micro", 100, self.discord.volumen_entrada),
                                     ("salida", "Salida", 200, self.discord.volumen_salida)):
        fila = QHBoxLayout()
        lb = etiqueta(texto, "sub")
        lb.setFixedWidth(50)
        fila.addWidget(lb)
        sl = QSlider(Qt.Horizontal)
        sl.setRange(0, maximo)
        sl.setCursor(Qt.PointingHandCursor)
        val = etiqueta("", "dim")
        val.setFixedWidth(40)
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        envio = QTimer(sl, singleShot=True, interval=150)
        envio.timeout.connect(lambda sl=sl, fn=fn: fn(sl.value()))
        sl.valueChanged.connect(lambda v, sl=sl, val=val, envio=envio: (
            val.setText(f"{v} %"), None if getattr(sl, "_actualizando", False) else
            (setattr(sl, "_tocado", time.monotonic()), envio.start())))
        fila.addWidget(sl, 1)
        fila.addWidget(val)
        d[clave] = (sl, val, envio)
        cc.addLayout(fila)
    botones = QHBoxLayout()
    botones.setSpacing(6)
    d["mute"], d["deaf"], d["salir"] = QPushButton(_("Silenciar")), QPushButton(_("Ensordecer")), QPushButton(_("Salir"))
    for b in (d["mute"], d["deaf"]):
        b.setCheckable(True)
    d["mute"].clicked.connect(lambda: self.discord.silenciar(not self.discord.ajustes.get("mute")))
    d["deaf"].clicked.connect(lambda: self.discord.ensordecer(not self.discord.ajustes.get("deaf")))
    d["salir"].clicked.connect(self.discord.salir)
    for b in (d["mute"], d["deaf"], d["salir"]):
        b.setCursor(Qt.PointingHandCursor)
        botones.addWidget(b)
    cc.addLayout(botones)
    c.add(d["controles"])
    d["tarjeta"] = c
    self.dc = d


def arrancar(self):
    self.t_discord = QTimer(interval=150)  # rápido: quién habla
    self.t_discord.timeout.connect(self.actualizar_discord)
    self.t_discord.start()


def visibles(self, claves):
    self.discord.permitir("discord" in claves)


def menu(self, tarjeta, menu):
    if tarjeta.clave == "discord":
        self.menu_discord(menu, tarjeta.window())


def ajustes(self, caja):
    """Configuración > Widgets (self es la ventana)."""
    app = self.app
    lista = self.grupo(caja, "Discord")
    o = app.config["discord"]
    al_abrir = QComboBox()
    for clave, nombre in (("nada", "Solo mostrar los canales"), ("ultimo", "Entrar en el último canal"),
                          ("gente", "Entrar donde haya más gente")):
        al_abrir.addItem(_(nombre), clave)
    al_abrir.setCurrentIndex(max(0, al_abrir.findData(o["al_abrir"])))
    al_abrir.currentIndexChanged.connect(lambda i: app.cambiar_discord(al_abrir=al_abrir.itemData(i)))
    self.fila(lista, "Al abrir Discord desde el widget", al_abrir)
    servidores = app.discord.instantanea()["servidores"]
    lista = self.grupo(caja, "Tu servidor de Discord",
                       "Sus canales de voz salen en el widget cuando no estás en ninguno; pulsa uno para entrar.")
    if not servidores:
        self.fila(lista, "Abre Discord para ver tus servidores", QLabel())
    for g in servidores:
        ch = QCheckBox()
        ch.setChecked(g["id"] in o["servidores"])
        ch.toggled.connect(lambda v, i=g["id"]: app.cambiar_discord(
            servidores=[e for e in o["servidores"] if e != i] + ([i] if v else [])))
        self.fila(lista, g["nombre"], ch)
