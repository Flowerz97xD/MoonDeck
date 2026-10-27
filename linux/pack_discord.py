"""Pack Discord (Linux): el canal de voz en el que estás."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
from discord_voz import CLIENT_ID_POR_DEFECTO, CLIENT_SECRET_POR_DEFECTO, Discord, abrir_discord
from idioma import _

WIDGETS = ('discord',)


def cargar_pixbuf(datos, tam):
    """Bytes de imagen -> pixbuf cuadrado de tam x tam (recortado al centro), o None."""
    if not datos:
        return None
    try:
        cargador = GdkPixbuf.PixbufLoader()
        cargador.write(datos)
        cargador.close()
        img = cargador.get_pixbuf()
    except GLib.Error:
        return None
    pw, ph = img.get_width(), img.get_height()
    lado = min(pw, ph)
    return img.new_subpixbuf((pw - lado) // 2, (ph - lado) // 2, lado, lado).scale_simple(
        tam, tam, GdkPixbuf.InterpType.BILINEAR)


class Avatar(Dibujo):
    """Avatar redondo; con un aro verde mientras la persona habla."""

    TAM = 26

    def __init__(self):
        super().__init__()
        self.set_size_request(self.TAM + 4, self.TAM + 4)
        self.set_valign(Gtk.Align.CENTER)
        self.pixbuf = None
        self.url = None
        self.hablando = False
        self.inicial = "?"
        self.connect("draw", self.dibujar)

    def poner(self, url, datos, inicial):
        self.inicial = (inicial or "?")[:1].upper()
        if url != self.url or (datos and not self.pixbuf):
            self.url = url
            self.pixbuf = cargar_pixbuf(datos, self.TAM * max(1, self.get_scale_factor()))
            self.queue_draw()

    def set_hablando(self, si):
        if si != self.hablando:
            self.hablando = si
            self.queue_draw()

    def dibujar(self, _w, cr):
        r = self.TAM / 2
        c = r + 2
        if self.hablando:
            cr.arc(c, c, r + 1.5, 0, 2 * math.pi)
            cr.set_source_rgb(*COLORES["verde"])
            cr.set_line_width(2.5)
            cr.stroke()
        cr.arc(c, c, r - (1 if self.hablando else 0), 0, 2 * math.pi)
        cr.clip()
        if self.pixbuf:
            escala = self.pixbuf.get_width() / self.TAM
            cr.translate(2, 2)
            cr.scale(1 / escala, 1 / escala)
            Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 0, 0)
            cr.paint()
        else:
            cr.set_source_rgb(*hex_rgb("5865f2"))  # azul de Discord
            cr.paint()
            lay = capa_texto(self, cr, self.inicial, 12, Pango.Weight.BOLD)
            pintar_texto(cr, lay, 2, 2, self.TAM, self.TAM, (1, 1, 1), 0.5)


class FilaDiscord(Gtk.Box):
    """Una persona del canal: avatar, nombre, micro/cascos y su volumen (solo para mí)."""

    def __init__(self, discord, uid, soy_yo):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.discord = discord
        self.uid = uid
        self._enviar = None
        self._actualizando = False
        arriba = caja(False, 8)
        self.avatar = Avatar()
        arriba.pack_start(self.avatar, False, False, 0)
        self.nombre = etiqueta("", "sub")
        arriba.pack_start(self.nombre, True, True, 0)
        self.i_micro = Gtk.Image.new_from_icon_name("microphone-disabled-symbolic", Gtk.IconSize.MENU)
        self.i_cascos = Gtk.Image.new_from_icon_name("audio-volume-muted-symbolic", Gtk.IconSize.MENU)
        self.i_micro.set_tooltip_text(_("Micrófono desactivado"))
        self.i_cascos.set_tooltip_text(_("Ensordecido"))
        for i in (self.i_micro, self.i_cascos):
            i.get_style_context().add_class("rojo")
            i.set_no_show_all(True)
            arriba.pack_start(i, False, False, 0)
        self.b_vol = None
        self.revelar = None
        if not soy_yo:
            self.b_vol = boton_icono("audio-volume-high-symbolic", Gtk.IconSize.MENU)
            self.b_vol.set_tooltip_text(_("Volumen de esta persona (solo para ti)"))
            self.b_vol.connect("clicked", lambda _b: self.revelar.set_reveal_child(not self.revelar.get_reveal_child()))
            arriba.pack_start(self.b_vol, False, False, 0)
        self.pack_start(arriba, False, False, 0)
        if not soy_yo:
            self.revelar = Gtk.Revealer()
            fila = caja(False, 6)
            fila.set_margin_start(34)
            self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 200, 1)
            self.slider.set_draw_value(False)
            self.slider.set_can_focus(False)
            self.slider.add_mark(100, Gtk.PositionType.BOTTOM, None)
            self.slider.connect("value-changed", self._cambio)
            fila.pack_start(self.slider, True, True, 0)
            self.valor = Gtk.Label(xalign=1)
            self.valor.get_style_context().add_class("dim")
            self.valor.set_size_request(38, -1)
            fila.pack_start(self.valor, False, False, 0)
            self.b_mute = boton_texto("Silenciar", "normal")
            self.b_mute.set_tooltip_text(_("Silenciar a esta persona solo para ti"))
            self.b_mute.connect("clicked", lambda _b: self.discord.silenciar_usuario(self.uid, not self._mute))
            fila.pack_start(self.b_mute, False, False, 0)
            self.revelar.add(fila)
            self.pack_start(self.revelar, False, False, 0)
        self._mute = False
        self.show_all()

    def _cambio(self, s):
        v = round(s.get_value())
        poner_texto(self.valor, f"{v} %")
        if self._actualizando:
            return
        # Al arrastrar, como mucho una orden cada 150 ms (Discord limita las peticiones).
        self._pendiente = v
        if not self._enviar:
            self._enviar = GLib.timeout_add(150, self._mandar)

    def _mandar(self):
        self._enviar = None
        self.discord.volumen_usuario(self.uid, self._pendiente)
        return False

    def actualizar(self, m, hablando, avatar):
        poner_texto(self.nombre, m["nombre"] + (_(" · bot") if m["bot"] else ""))
        clases(self.nombre, verde=hablando)
        self.avatar.poner(m["avatar"], avatar, m["nombre"])
        self.avatar.set_hablando(hablando)
        self.i_micro.set_visible(m["micro_off"] and not m["ensordecido"])
        self.i_cascos.set_visible(m["ensordecido"])
        if self.revelar:
            self._mute = m["silenciado_local"]
            self.b_mute.set_label(_("Activar") if self._mute else _("Silenciar"))
            clases(self.b_mute, marcado=self._mute)
            poner_icono(self.b_vol, "audio-volume-muted-symbolic" if self._mute else "audio-volume-high-symbolic",
                        Gtk.IconSize.MENU)
            if not self._enviar:
                self._actualizando = True
                self.slider.set_value(m["volumen"])
                self._actualizando = False
                poner_texto(self.valor, f"{round(m['volumen'])} %")


def guia_discord():
    """La guía paso a paso de Discord en GitHub (en español o en inglés)."""
    nombre = "DISCORD.md" if idioma.actual() == "es" else "DISCORD.en.md"
    return f"https://github.com/{REPO}/blob/main/docs/{nombre}"


class DialogoDiscord(Gtk.Dialog):
    """Conectar con Discord paso a paso: pide el Client ID y el Client Secret."""

    def __init__(self, client_id):
        super().__init__(title=_("Conectar con Discord"))
        self.set_default_size(560, -1)
        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        ok = self.add_button(_("Conectar"), Gtk.ResponseType.OK)
        ok.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)
        area = self.get_content_area()
        area.set_spacing(10)
        area.set_border_width(16)

        def texto(marcado, dim=False):
            lb = Gtk.Label(xalign=0, wrap=True, max_width_chars=64)
            lb.set_markup(marcado)
            if dim:
                lb.get_style_context().add_class("dim-label")
            area.pack_start(lb, False, False, 0)
            return lb

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
            texto(f"<b>{n}.</b>  {paso}")
        botones = caja(False, 6)
        for etiq, url in ((_("Abrir discord.com/developers"), "https://discord.com/developers/applications"),
                          (_("Ver la guía paso a paso"), guia_discord())):
            b = Gtk.Button(label=etiq)
            b.connect("clicked", lambda _b, u=url: abrir_web(u))
            botones.pack_start(b, False, False, 0)
        area.pack_start(botones, False, False, 0)
        rejilla = Gtk.Grid(column_spacing=10, row_spacing=8)
        rejilla.set_margin_top(6)
        self.id = Gtk.Entry(text=client_id, hexpand=True)
        self.id.set_placeholder_text(_("Un número largo, de OAuth2 > Client ID"))
        self.secreto = Gtk.Entry(visibility=False, hexpand=True, activates_default=True)
        self.secreto.set_placeholder_text(_("Vacío = el de la aplicación de MoonDeck") if CLIENT_SECRET_POR_DEFECTO
                                          else _("De OAuth2 > Reset Secret"))
        for fila, (nombre, campo) in enumerate((("Client ID", self.id), ("Client Secret", self.secreto))):
            rejilla.attach(Gtk.Label(label=nombre, xalign=0), 0, fila, 1, 1)
            rejilla.attach(campo, 1, fila, 1, 1)
        area.pack_start(rejilla, False, False, 0)
        texto(_("Se guardan solo en tu equipo."), dim=True)
        self.show_all()


class Metodos:
    """Se añaden a Monitor."""

    def _volumen_discord(self, slider, fn):
        v = round(slider.get_value())
        slider._valor.set_text(f"{v} %")
        if getattr(slider, "_actualizando", False):
            return
        slider._tocado = time.monotonic()
        slider._pendiente = v
        if not getattr(slider, "_enviar", None):
            def mandar():
                slider._enviar = None
                fn(slider._pendiente)
                return False
            slider._enviar = GLib.timeout_add(150, mandar)

    def conectar_discord(self):
        # La aplicación de serie solo sirve si este MoonDeck trae su secreto (versión para amigos).
        propio = self.discord.cfg.get("client_id")
        dlg = DialogoDiscord(propio or (CLIENT_ID_POR_DEFECTO if CLIENT_SECRET_POR_DEFECTO else ""))
        if dlg.run() == Gtk.ResponseType.OK:
            ident, secreto = dlg.id.get_text().strip(), dlg.secreto.get_text().strip()
            if secreto or (CLIENT_SECRET_POR_DEFECTO and ident in ("", CLIENT_ID_POR_DEFECTO)):
                self.discord.configurar(ident or CLIENT_ID_POR_DEFECTO, secreto)
        dlg.destroy()

    def menu_discord(self, menu):
        recientes = self.config.get("discord_recientes", [])
        if recientes and self.discord.estado == "conectado":
            sub = self.submenu(menu, "Entrar en un canal reciente")
            for r in recientes:
                self.item(sub, f"{r['nombre']} · {r['servidor']}" if r["servidor"] else r["nombre"],
                          lambda i=r["id"]: self.discord.entrar(i))
        self.item(menu, _("Conectar con Discord…") if self.discord.estado == "sin_config"
                  else "Cambiar Client ID / Secret…", self.conectar_discord)
        if self.discord.estado != "sin_config":
            self.item(menu, "Desconectar de Discord (olvidar la autorización)", self.discord.olvidar)
        menu.append(Gtk.SeparatorMenuItem())

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
        b = Gtk.Button()
        b.get_style_context().add_class("normal")
        b.set_can_focus(False)
        textos = caja(True, 0)
        nombre = etiqueta(f"🔊 {c['nombre']}" + (f" · {len(c['personas'])}" if c["personas"] else ""), "sub")
        nombre.get_style_context().add_class("negrita")
        textos.pack_start(nombre, False, False, 0)
        if c["personas"]:
            textos.pack_start(etiqueta(", ".join(c["personas"]), "dim"), False, False, 0)
        if con_servidor and c["servidor"]:
            textos.pack_start(etiqueta(c["servidor"], "dim"), False, False, 0)
        b.add(textos)
        b.connect("clicked", lambda _b, i=c["id"]: self.discord.entrar(i))
        b.show_all()
        return b

    def actualizar_discord(self):
        d = self.dc
        s = self.discord.instantanea()
        if s["version"] == d["version"]:
            return True
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
        poner_texto(d["aviso"], aviso)
        d["aviso"].set_visible(bool(aviso))
        d["conectar"].set_visible(estado in ("sin_config", "error"))
        d["abrir"].set_visible(estado == "desconectado")
        d["abrir"].set_sensitive(not self.discord_abriendo)
        en_canal = estado == "conectado" and bool(canal)

        # Sin canal: los canales con gente para entrar con un clic, o el último en el que estuve.
        canales = (s["canales_voz"] or []) if estado == "conectado" and not canal else []
        ids = [(c["id"], tuple(c["personas"])) for c in canales]
        if ids != d["canales_ids"]:
            d["canales_ids"] = ids
            for b in d["canales"].get_children():
                b.destroy()
            varios = len({c["guild_id"] for c in canales}) > 1
            botones = [self.boton_canal_discord(c, varios) for c in canales]
            for b in botones:
                d["canales"].pack_start(b, False, False, 0)
            # Si no caben, se quitan antes los vacíos (los últimos primero) y luego los demás.
            vacios = [b for b, c in zip(botones, canales) if not c["personas"]]
            llenos = [b for b, c in zip(botones, canales) if c["personas"]]
            d["tarjeta"].prescindibles_grupo("canales", vacios[::-1] + llenos[::-1], 1)
        d["canales"].set_visible(bool(canales))
        recientes = self.config.get("discord_recientes", [])
        ultimo = (estado == "conectado" and not canal and not self.config["discord"]["servidores"]
                  and bool(recientes))
        if ultimo:
            d["ultimo"].set_label(_("Entrar en {canal}").format(canal=recientes[0]["nombre"]))
        d["ultimo"].set_visible(ultimo)
        poner_texto(d["canal"], f"🔊 {canal['nombre']}" if en_canal else _("Sin canal de voz"))
        poner_texto(d["servidor"], canal["servidor"] if en_canal else "")
        d["servidor"].set_visible(en_canal and bool(canal["servidor"]))
        d["controles"].set_visible(estado == "conectado")
        d["salir"].set_sensitive(en_canal)
        if en_canal and canal["servidor"]:
            self.recordar_canal(canal)

        # Personas: las filas se rehacen solo si entra o sale alguien.
        miembros = s["miembros"] if en_canal else []
        ids = [m["id"] for m in miembros]
        if ids != d["ids"]:
            d["ids"] = ids
            for f in d["filas"].values():
                f.destroy()
            d["filas"] = {}
            for m in miembros:
                f = FilaDiscord(self.discord, m["id"], m["id"] == s["yo"])
                d["lista"].pack_start(f, False, False, 0)
                d["filas"][m["id"]] = f
            # Si no caben todos, se quitan los últimos de la lista.
            d["tarjeta"].prescindibles_grupo("miembros", list(d["filas"].values())[::-1], 1)
        for m in miembros:
            d["filas"][m["id"]].actualizar(m, m["id"] in s["hablando"], self.discord.avatares.get(m["avatar"]))
        d["lista"].set_visible(bool(miembros))

        a = s["ajustes"]
        clases(d["mute"], marcado=bool(a.get("mute")))
        d["mute"].set_label(_("Micro silenciado") if a.get("mute") else _("Silenciar"))
        clases(d["deaf"], marcado=bool(a.get("deaf")))
        d["deaf"].set_label(_("Ensordecido") if a.get("deaf") else _("Ensordecer"))
        for clave in ("entrada", "salida"):
            sl, val = d[clave]
            v = a.get(clave)
            if v is not None and time.monotonic() - sl._tocado > 1.5 and not getattr(sl, "_enviar", None):
                sl._actualizando = True
                sl.set_value(v)
                sl._actualizando = False
            val.set_text(f"{round(sl.get_value())} %")
        self.ajustar_alturas()
        return True


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
    d["canal"] = c.add_w(etiqueta("", "sub"))
    d["canal"].get_style_context().add_class("negrita")
    d["servidor"] = c.add_w(etiqueta("", "dim"))
    d["aviso"] = c.add_w(etiqueta("", "dim", envolver=True))
    d["conectar"] = c.add_w(boton_texto("Conectar con Discord…", "principal"))
    d["conectar"].connect("clicked", lambda _b: self.conectar_discord())
    d["abrir"] = c.add_w(boton_texto("Abrir Discord", "principal"))
    d["abrir"].connect("clicked", lambda _b: self.abrir_discord())
    d["canales"] = c.add_w(caja(True, 4))
    d["canales_ids"] = None
    d["ultimo"] = c.add_w(boton_texto("", "normal"))
    d["ultimo"].connect("clicked", lambda _b: self.entrar_ultimo_discord())
    d["lista"] = c.add_w(caja(True, 4))
    d["lista"].set_margin_top(4)
    d["controles"] = caja(True, 4)
    d["controles"].set_margin_top(6)
    for clave, texto, maximo, fn in (("entrada", "Micro", 100, self.discord.volumen_entrada),
                                     ("salida", "Salida", 200, self.discord.volumen_salida)):
        fila = caja(False, 6)
        lb = etiqueta(texto, "sub")
        lb.set_size_request(50, -1)
        lb.set_hexpand(False)
        fila.pack_start(lb, False, False, 0)
        sl = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, maximo, 1)
        sl.set_draw_value(False)
        sl.set_can_focus(False)
        sl._tocado = 0
        sl.connect("value-changed", lambda s, fn=fn: self._volumen_discord(s, fn))
        fila.pack_start(sl, True, True, 0)
        val = Gtk.Label(xalign=1)
        val.get_style_context().add_class("dim")
        val.set_size_request(38, -1)
        sl._valor = val
        fila.pack_start(val, False, False, 0)
        d[clave] = (sl, val)
        d["controles"].pack_start(fila, False, False, 0)
    botones = caja(False, 6)
    d["mute"] = boton_texto("Silenciar", "normal")
    d["deaf"] = boton_texto("Ensordecer", "normal")
    d["salir"] = boton_texto("Salir", "normal")
    d["salir"].get_style_context().add_class("rojo")
    d["mute"].connect("clicked", lambda _b: self.discord.silenciar(not self.discord.ajustes.get("mute")))
    d["deaf"].connect("clicked", lambda _b: self.discord.ensordecer(not self.discord.ajustes.get("deaf")))
    d["salir"].connect("clicked", lambda _b: self.discord.salir())
    for b in (d["mute"], d["deaf"], d["salir"]):
        botones.pack_start(b, True, True, 0)
    d["controles"].pack_start(botones, False, False, 0)
    c.add_w(d["controles"])
    d["tarjeta"] = c
    self.dc = d


def arrancar(self):
    GLib.timeout_add(150, self.actualizar_discord)  # rápido: quién habla


def visibles(self, claves):
    self.discord.permitir("discord" in claves)


def menu(self, tarjeta, menu):
    if tarjeta.clave == "discord":
        self.menu_discord(menu)


def ajustes(self, cont):
    """Configuración > Widgets (self es la ventana)."""
    app = self.app
    lista = self.grupo(cont, "Discord")
    o = app.config["discord"]
    al_abrir = Gtk.ComboBoxText()
    for clave, nombre in (("nada", "Solo mostrar los canales"), ("ultimo", "Entrar en el último canal"),
                          ("gente", "Entrar donde haya más gente")):
        al_abrir.append(clave, _(nombre))
    al_abrir.set_active_id(o["al_abrir"])
    al_abrir.connect("changed", lambda w: app.cambiar_discord(al_abrir=w.get_active_id()))
    self.fila(lista, "Al abrir Discord desde el widget", al_abrir)
    servidores = app.discord.instantanea()["servidores"]
    lista = self.grupo(cont, "Tu servidor de Discord",
                       "Sus canales de voz salen en el widget cuando no estás en ninguno; pulsa uno para entrar.")
    if not servidores:
        self.fila(lista, "Abre Discord para ver tus servidores", Gtk.Label())
    for g in servidores:
        sw = Gtk.Switch(active=g["id"] in o["servidores"])
        sw.connect("notify::active", lambda w, _p, i=g["id"]: app.cambiar_discord(
            servidores=[e for e in o["servidores"] if e != i] + ([i] if w.get_active() else [])))
        self.fila(lista, g["nombre"], sw)
