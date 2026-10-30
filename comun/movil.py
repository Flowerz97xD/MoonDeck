"""Móvil: tu Android en el escritorio con scrcpy (github.com/Genymobile/scrcpy).

Cada app se abre en su propia ventana, en una pantalla virtual del móvil (la de verdad
sigue libre), o se controla el móvil entero. Lo lento (adb, leer las apps) va en hilos:
la interfaz mira el estado cuando quiera.
"""

import os
import re
import shutil
import subprocess
import threading
import time

from idioma import _

WEB_SCRCPY = "https://github.com/Genymobile/scrcpy/releases/latest"
MAX_FAVORITAS = 8
ANCHO_VENTANA = 900  # px del lado largo de las ventanas de scrcpy


def buscar_scrcpy():
    """La ruta de scrcpy: el del sistema o el suelto de ~/.local/bin (el de GitHub)."""
    for ruta in (shutil.which("scrcpy"), os.path.expanduser("~/.local/bin/scrcpy")):
        if ruta and os.access(ruta, os.X_OK):
            return ruta
    return None


def _ejecutar(orden, timeout=10, env=None):
    r = subprocess.run(orden, capture_output=True, text=True, timeout=timeout, env=env)
    return r.stdout + r.stderr


def leer_lista_apps(texto):
    """Las apps de "scrcpy --list-apps": [(paquete, nombre, del sistema)]. Los nombres largos
    dejan el paquete en la línea siguiente."""
    apps, pendiente = [], None
    for linea in texto.splitlines():
        m = re.match(r"^ ([*-]) (.*)$", linea)
        if m:
            partes = re.split(r"\s{2,}", m.group(2).strip())
            if len(partes) >= 2:
                apps.append((partes[-1], " ".join(partes[:-1]), m.group(1) == "*"))
            else:
                pendiente = (partes[0], m.group(1) == "*")
        elif pendiente and re.match(r"^\s+[\w.]+$", linea):
            apps.append((linea.strip(), pendiente[0], pendiente[1]))
            pendiente = None
    return sorted(apps, key=lambda a: a[1].lower())


class Movil:
    """estado: "sin_scrcpy", "viejo" (scrcpy < 3), "sin_movil", "sin_permiso" (falta la regla
    de udev), "sin_autorizar" (falta aceptar el aviso en el móvil) o "listo"."""

    def __init__(self, datos, al_guardar, carpeta):
        """datos: el dict de la configuración (se modifica aquí); al_guardar: guarda la config."""
        self.d = datos
        self.al_guardar = al_guardar
        self.log = os.path.join(carpeta, "scrcpy.log")
        self.estado = None
        self.serie = None
        self.nombre = ""
        self.error = ""          # el último fallo al abrir algo
        self.leyendo = False     # leyendo las apps
        self.procesos = {}       # "todo" o el paquete -> Popen
        self._scrcpy = None      # (ruta, versión, opciones de su --help)
        self._comprobando = False

    # --- en segundo plano -------------------------------------------------------

    def comprobar(self):
        """Mira (en un hilo) si hay scrcpy y un móvil conectado."""
        if not self._comprobando:
            self._comprobando = True
            threading.Thread(target=self._comprobar, daemon=True).start()

    def _comprobar(self):
        try:
            self._mirar()
        except (OSError, subprocess.SubprocessError) as e:
            self.error = str(e)
        finally:
            self._comprobando = False

    def _mirar(self):
        ruta = buscar_scrcpy()
        if not ruta:
            self.estado = "sin_scrcpy"
            return
        if not self._scrcpy or self._scrcpy[0] != ruta:
            m = re.search(r"scrcpy (\d+)", _ejecutar([ruta, "--version"]))
            self._scrcpy = (ruta, int(m.group(1)) if m else 0, _ejecutar([ruta, "--help"]))
        if self._scrcpy[1] < 3:  # sin pantallas virtuales
            self.estado = "viejo"
            return
        estado, serie = "sin_movil", None
        for linea in _ejecutar([self.adb(), "devices"], env=self.entorno()).splitlines()[1:]:
            partes = linea.split(None, 1)
            if len(partes) < 2:
                continue
            if partes[1].startswith("device"):
                estado, serie = "listo", partes[0]
                break
            if "no permissions" in partes[1]:
                estado = "sin_permiso"
            elif partes[1].startswith("unauthorized") and estado == "sin_movil":
                estado = "sin_autorizar"
        if serie and serie != self.serie:
            self.serie = serie
            self.nombre = self._nombre(serie)
            if self.d.get("serie") != serie or not self.d.get("apps"):
                self.leer_apps()
        self.estado = estado
        for clave, p in list(self.procesos.items()):
            if p.poll() is not None:
                del self.procesos[clave]
                if p.returncode and time.monotonic() - p.inicio < 15:  # no llegó a abrirse
                    self.error = self._ultimo_error() or _("scrcpy se ha cerrado.")

    def _nombre(self, serie):
        """El nombre que le has puesto al móvil (o su modelo)."""
        for orden in (["settings", "get", "global", "device_name"], ["getprop", "ro.product.marketname"],
                      ["getprop", "ro.product.model"]):
            nombre = _ejecutar([self.adb(), "-s", serie, "shell", *orden], env=self.entorno()).strip()
            if nombre and nombre != "null" and "\n" not in nombre:
                return nombre
        return serie

    def leer_apps(self):
        """Lee (en un hilo) las apps del móvil con sus nombres. Tarda unos segundos."""
        if self.leyendo or not self.serie:
            return
        self.leyendo = True

        def trabajo():
            try:
                texto = _ejecutar([self._scrcpy[0], "-s", self.serie, "--list-apps"], timeout=90,
                                  env=self.entorno())
                apps = leer_lista_apps(texto)
                if apps:
                    self.d["serie"] = self.serie
                    self.d["apps"] = [list(a) for a in apps]
                    self.al_guardar()
                else:
                    self.error = _("No se pudieron leer las apps del móvil.")
            except (OSError, subprocess.SubprocessError) as e:
                self.error = str(e)
            finally:
                self.leyendo = False
        threading.Thread(target=trabajo, daemon=True).start()

    # --- scrcpy y adb ------------------------------------------------------------

    def adb(self):
        """El adb que trae scrcpy (el de GitHub lo lleva al lado) o el del sistema."""
        junto = os.path.join(os.path.dirname(os.path.realpath(self._scrcpy[0])), "adb")
        return junto if os.access(junto, os.X_OK) else (shutil.which("adb") or "adb")

    def entorno(self):
        return dict(os.environ, ADB=self.adb())

    def _ultimo_error(self):
        try:
            with open(self.log, encoding="utf-8", errors="replace") as f:
                errores = [l.strip() for l in f if "ERROR" in l]
        except OSError:
            return ""
        return errores[-1].split("ERROR:", 1)[-1].strip() if errores else ""

    def abrir(self, paquete=None, nombre=None):
        """Una app en su propia ventana (pantalla virtual) o, sin paquete, el móvil entero."""
        if self.estado != "listo":
            return
        clave = paquete or "todo"
        viejo = self.procesos.pop(clave, None)
        if viejo and viejo.poll() is None:
            viejo.terminate()  # se vuelve a abrir: así sale delante
        orden = [self._scrcpy[0], "-s", self.serie, f"--max-size={ANCHO_VENTANA}", "--stay-awake",
                 f"--window-title={nombre or self.nombre}"]
        if "--hwdec" in self._scrcpy[2]:
            # Por software: con algunas gráficas (NVIDIA) la de hardware deja la ventana en negro
            orden.append("--hwdec=disabled")
        if not self.d.get("sonido", True):
            orden.append("--no-audio")
        if paquete:
            orden += ["--new-display", f"--start-app={paquete}"]
            usos = self.d.setdefault("usos", {})
            usos[paquete] = usos.get(paquete, 0) + 1
            self.al_guardar()
        elif self.d.get("apagar_pantalla", False):
            orden.append("--turn-screen-off")
        self.error = ""
        with open(self.log, "w", encoding="utf-8") as salida:
            p = subprocess.Popen(orden, stdout=salida, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                 env=self.entorno(), start_new_session=True)
        p.inicio = time.monotonic()
        self.procesos[clave] = p

    # --- favoritas ---------------------------------------------------------------

    def apps(self, sistema=False):
        return [tuple(a) for a in self.d.get("apps", []) if sistema or not a[2]]

    def favorita(self, paquete):
        return paquete in self.d.get("favoritas", [])

    def alternar_favorita(self, paquete):
        favs = self.d.setdefault("favoritas", [])
        if paquete in favs:
            favs.remove(paquete)
        else:
            favs.append(paquete)
        self.al_guardar()

    def destacadas(self):
        """Las del widget: tus favoritas y, si quedan huecos, las que más abres."""
        nombres = {a[0]: a[1] for a in self.d.get("apps", [])}
        favs = [p for p in self.d.get("favoritas", []) if p in nombres]
        usos = self.d.get("usos", {})
        mas_usadas = sorted((p for p in usos if p in nombres and p not in favs), key=lambda p: -usos[p])
        return [(p, nombres[p]) for p in (favs + mas_usadas)[:MAX_FAVORITAS]]
