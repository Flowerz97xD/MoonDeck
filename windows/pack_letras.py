"""Pack Letras (Windows): la letra de lo que suena, sincronizada como en Spotify (letras.py)."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
import letras
import time
from idioma import _

WIDGETS = ('letras',)


class VistaLetra(QWidget):
    """La letra sincronizada de lo que suena, como en Spotify: centrada, con la frase actual
    resaltada en el medio; al cambiar de frase la lista se desliza suave y el resaltado se
    funde de una a otra. Con un clic en una frase la canción salta ahí."""

    ESTIRA = True
    FLUIDO, REPOSO = 16, 80   # ms entre fotogramas: mientras se mueve / quieta
    DURACION = 0.7            # segundos que tarda en deslizarse a la frase siguiente

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.letras = letras.Letras()
        self.setMinimumHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.sesion = None     # lo que suena (dict de Reproductores)
        self.estado = None     # "ok", "buscando", "sin_letra" o None (no suena nada)
        self.frases = []
        self.pista = None      # (n.º, de cuántas, canción) si suena un disco entero
        self.cabecera = self.contrapeso = self.titulo = None  # los pone construir()
        self.actual = self.anterior = -1
        self.bloques = []      # (y, alto, renglones) de cada frase, para el ancho actual
        self._medida = None
        self.desplazado = 0.0  # y de la parte de arriba
        self._desde = 0.0      # animación: de dónde sale, cuándo empezó y su avance (0-1)
        self._inicio = 0.0
        self.avance = 1.0
        self.timer = QTimer(self, interval=self.REPOSO)
        self.timer.timeout.connect(self.tic)

    def sizeHint(self):
        return QSize(M.ANCHO - 32, 240)

    def showEvent(self, e):
        super().showEvent(e)
        self.timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    def _fuente(self, actual=False):
        f = QFont(self.font())
        f.setPointSizeF(12.5 * M.ESCALA)
        f.setWeight(QFont.Bold if actual else QFont.DemiBold)
        return f

    def posicion(self):
        d = self.sesion
        pos = d["pos"] + (time.monotonic() - d["momento"] if d["reproduciendo"] else 0)
        return min(pos, d["dur"]) if d["dur"] > 0 else pos

    def tic(self):
        lista = self.app.reproductores.leer()
        d = next((x for x in lista if x["reproduciendo"]), lista[0] if lista else None)
        self.sesion = d
        if not d:
            frases, estado, pista = [], None, None
        else:
            estado, frases, pista = self.letras.pedir(d["titulo"], d["artista"], d["dur"], self.posicion())
            frases = frases or []
        cambio = estado != self.estado
        if pista != self.pista:
            self.pista = pista
            self._poner_cabecera()
        self.estado = estado
        if frases != self.frases:
            self.frases, self._medida = frases, None
            self.actual = self.anterior = -1
            self.avance, cambio = 1.0, True
            self._medir()
            self.desplazado = self._objetivo()
        if frases:
            pos = self.posicion() + 0.25  # un pelín antes, que el ojo va detrás
            actual = -1
            for i, (t, _f) in enumerate(frases):
                if t > pos:
                    break
                actual = i
            if actual != self.actual:
                self.anterior, self.actual = self.actual, actual
                self._desde, self._inicio, self.avance = self.desplazado, time.monotonic(), 0.0
            self._medir()
            if self.avance < 1:
                self.avance = min(1.0, (time.monotonic() - self._inicio) / self.DURACION)
                t = self.avance
                suave = 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2  # acelera y frena
                self.desplazado = self._desde + (self._objetivo() - self._desde) * suave
                cambio = True
        self.timer.setInterval(self.FLUIDO if self.avance < 1 else self.REPOSO)
        if cambio:
            self.update()

    def _medir(self):
        ancho = max(40, self.width() - 16)
        if self._medida == (ancho, M.ESCALA):
            return
        self._medida = (ancho, M.ESCALA)
        fm = QFontMetricsF(self._fuente(True))
        self.bloques, y = [], 0.0
        for _t, frase in self.frases:
            renglones, linea = [], ""
            for palabra in frase.split():
                prueba = f"{linea} {palabra}".strip()
                if linea and fm.horizontalAdvance(prueba) > ancho:
                    renglones.append(linea)
                    linea = palabra
                else:
                    linea = prueba
            renglones.append(linea)
            alto = len(renglones) * fm.lineSpacing()
            self.bloques.append((y, alto, renglones))
            y += alto + fm.lineSpacing() * 0.6

    def _objetivo(self):
        """La frase actual, en el centro."""
        if not self.bloques:
            return 0.0
        y, alto, _r = self.bloques[max(self.actual, 0)]
        return y + alto / 2 - self.height() / 2

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._poner_cabecera()
        self._medida = None
        if self.frases:
            self._medir()
            self.desplazado = self._objetivo()

    def _brillo(self, i):
        """Cuánto resalta la frase i (0-1): la actual sube y la anterior baja mientras se desliza."""
        t = self.avance
        if i == self.actual:
            return t
        if i == self.anterior:
            return 1 - t
        return 0.0

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        if self.estado != "ok":
            textos = {None: _("No está sonando nada."), "buscando": _("Buscando la letra…"),
                      "sin_letra": _("No hay letra sincronizada para lo que suena.")}
            p.setPen(QColor(M.C_SEC))
            p.drawText(QRectF(self.rect()).adjusted(8, 0, -8, 0), Qt.AlignCenter | Qt.TextWordWrap,
                       textos.get(self.estado, ""))
            return
        alto_vista, ancho = self.height(), self.width()
        fundido = min(110.0, alto_vista * 0.36)  # arriba y abajo la letra se desvanece, poco a poco
        texto, sec = QColor(M.C_TEXTO), QColor(M.C_SEC)
        for i, (y, alto, renglones) in enumerate(self.bloques):
            arriba = y - self.desplazado
            if arriba + alto < 0 or arriba > alto_vista:
                continue
            brillo = self._brillo(i)
            base = 0.45 if i < self.actual else 0.75
            c = QColor.fromRgbF(*(a + (b - a) * brillo for a, b in zip(sec.getRgbF()[:3], texto.getRgbF()[:3])))
            centro = arriba + alto / 2
            borde = max(0.0, min(1.0, centro / fundido, (alto_vista - centro) / fundido))
            borde = borde * borde * (3 - 2 * borde)  # curva suave: se va apagando antes y sin corte
            c.setAlphaF((base + (1 - base) * brillo) * borde)
            p.setPen(c)
            p.setFont(self._fuente(brillo > 0.5))
            fm = QFontMetricsF(p.font())
            for j, renglon in enumerate(renglones):
                x = (ancho - fm.horizontalAdvance(renglon)) / 2
                p.drawText(QPointF(x, arriba + j * fm.lineSpacing() + fm.ascent()), renglon)

    def _poner_cabecera(self):
        """Con un disco entero, qué canción suena ("2/16 · CANDY"), junto al título de la tarjeta."""
        if not self.cabecera:
            return
        self.cabecera.setVisible(bool(self.pista))
        self.contrapeso.setFixedWidth(self.titulo.sizeHint().width() if self.titulo.isVisible() else 0)
        if self.pista:
            n, total, cancion = self.pista
            texto = f"{n}/{total} · {cancion}"
            ancho = max(40, self.width() - 2 * self.contrapeso.width() - 12)
            self.cabecera.setText(self.cabecera.fontMetrics().elidedText(texto, Qt.ElideRight, ancho))
            self.cabecera.setToolTip(texto)

    def _tarjeta(self):
        w = self.parentWidget()
        while w and not isinstance(w, Tarjeta):
            w = w.parentWidget()
        return w

    def mousePressEvent(self, e):
        tarjeta = self._tarjeta()
        d = self.sesion
        if (e.button() != Qt.LeftButton or (tarjeta and tarjeta.en_edicion()) or self.estado != "ok"
                or not d or not d["buscar"]):
            e.ignore()
            return
        y = e.position().y() + self.desplazado
        for i, (arriba, alto, _r) in enumerate(self.bloques):
            if arriba - 4 <= y <= arriba + alto + 4:
                self.app.reproductores.buscar(d["id"], max(0.0, self.frases[i][0] - 0.1))
                return
        e.ignore()

    def enterEvent(self, e):
        super().enterEvent(e)
        puede = self.estado == "ok" and self.sesion and self.sesion["buscar"]
        self.setCursor(Qt.PointingHandCursor if puede else Qt.ArrowCursor)


def construir(self, s):
    # Letra: la de lo que suena, sincronizada (LRCLIB)
    c = self.tarjeta("letras", "Letras")
    self.letra_vista = VistaLetra(self)
    c.add(self.letra_vista)
    c._estira = True
    # Con un disco entero, qué canción suena: en la cabecera, centrada respecto a la tarjeta
    # (a la derecha, un hueco del ancho del título hace de contrapeso)
    v = self.letra_vista
    v.cabecera = c.poner_esquina(etiqueta("", "titulo"))  # con la letra del título, para que sea de su línea
    v.cabecera.setStyleSheet("font-weight: normal;")
    v.cabecera.setAlignment(Qt.AlignCenter)
    v.contrapeso = QWidget()
    fila = c._esquina
    fila.addWidget(v.contrapeso)
    fila.setStretch(0, 0)
    fila.setStretch(1, 1)
    v.titulo = c.lb_titulo
