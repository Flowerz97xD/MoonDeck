"""Widget FPS (Windows): los FPS del juego en primer plano, con PresentMon."""

from __main__ import *  # noqa: F403 - las piezas de monitor.py (etiqueta, Tarjeta, Dibujo...)
import __main__ as M  # lo que cambia mientras corre (colores del tema, ANCHO...)
from idioma import _

WIDGETS = ('fps',)


def construir(self, s):
    self.fps = None
    if ES_WINDOWS:
        c = self.tarjeta("fps", "FPS")
        self.fps = {"big": c.add(etiqueta("", "grande")), "app": c.add(etiqueta()),
                    "sub": c.add(etiqueta("", "dim")),
                    "graf": c.add(Grafica(["verde", "naranja"], maximo=None), prescindible=9)}
        c.add(leyenda(("FPS", "verde"), ("1% low", "naranja")), prescindible=1)
        self.fps["sub"].setWordWrap(True)


def aplicar(self, s):
    if self.fps:
        f = s["fps"]
        if f:
            self.fps["big"].setText(f"{f['fps']:.0f} FPS")
            self.fps["app"].setText(f["app"])
            self.fps["sub"].setText(f"1% low {f['low1']:.0f} FPS · frametime {f['frametime']:.1f} ms")
            self.fps["graf"].push(f["fps"], f["low1"])
        else:
            self.fps["big"].setText("—")
            self.fps["app"].setText(_("Sin juegos ni apps 3D activos"))
            self.fps["sub"].setText(s["fps_error"] or _("Abre un juego para medir sus FPS."))
            self.fps["graf"].push(0, 0)
