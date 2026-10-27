"""Widget de Docker: los contenedores con su estado, CPU y RAM, usando el comando `docker`
(igual en Linux que en Windows con Docker Desktop). Un hilo los lee cada pocos segundos;
la interfaz usa `instantanea()` y `accion()` para iniciar, parar o reiniciar.
"""

import datetime
import json
import shutil
import subprocess
import sys
import threading

SIN_VENTANA = 0x08000000 if sys.platform == "win32" else 0  # que no salga una consola en Windows


def _docker(*args, timeout=20):
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout,
                          creationflags=SIN_VENTANA)


class Docker:
    def __init__(self):
        self.lock = threading.Lock()
        self.estado = "cargando"   # "sin_docker", "sin_permiso", "parado", "ok"
        self.contenedores = []     # [{"nombre", "estado", "salud", "tiempo", "cpu", "ram"}]
        self.version = 0
        self._despertar = threading.Event()
        self._activo = threading.Event()
        threading.Thread(target=self._bucle, daemon=True).start()

    def permitir(self, si):
        """Con el widget oculto no consulta nada."""
        (self._activo.set if si else self._activo.clear)()

    def _cambio(self, **campos):
        with self.lock:
            for k, v in campos.items():
                setattr(self, k, v)
            self.version += 1

    def _bucle(self):
        while True:
            self._activo.wait()
            try:
                self._leer()
            except (OSError, subprocess.SubprocessError, ValueError):
                self._cambio(estado="parado", contenedores=[])
            self._despertar.wait(5)
            self._despertar.clear()

    def _leer(self):
        if not shutil.which("docker"):
            self._cambio(estado="sin_docker", contenedores=[])
            return
        r = _docker("ps", "-a", "--format", "{{json .}}")
        if r.returncode:
            error = r.stderr.lower()
            self._cambio(estado="sin_permiso" if "permission denied" in error else "parado", contenedores=[])
            return
        lista = []
        for linea in r.stdout.splitlines():
            c = json.loads(linea)
            texto = c.get("Status", "")
            salud = ("sano" if "(healthy)" in texto else "enfermo" if "(unhealthy)" in texto
                     else "arrancando" if "starting" in texto else None)
            lista.append({"id": c.get("ID"), "nombre": c.get("Names", "?"), "estado": c.get("State", ""),
                          "salud": salud, "desde": None, "cpu": None, "ram": None})
        # Desde cuándo está en marcha (o parado), para contarlo en el idioma de la app.
        r = _docker("inspect", "-f", "{{.Id}} {{.State.StartedAt}} {{.State.FinishedAt}}", *[c["id"] for c in lista]) \
            if lista else None
        if r and not r.returncode:
            fechas = {}
            for linea in r.stdout.splitlines():
                ident, inicio, fin = (linea.split() + ["", ""])[:3]
                fechas[ident[:12]] = (inicio, fin)
            for c in lista:
                inicio, fin = fechas.get((c["id"] or "")[:12], ("", ""))
                c["desde"] = _fecha(inicio if c["estado"] == "running" else fin)
        if any(c["estado"] == "running" for c in lista):
            r = _docker("stats", "--no-stream", "--format", "{{json .}}")
            if not r.returncode:
                stats = {}
                for linea in r.stdout.splitlines():
                    s = json.loads(linea)
                    stats[s.get("Name")] = s
                for c in lista:
                    s = stats.get(c["nombre"])
                    if s:
                        c["cpu"] = s.get("CPUPerc")
                        c["ram"] = (s.get("MemUsage") or "").split(" / ")[0]
        orden = {"running": 0, "restarting": 1, "paused": 2}
        lista.sort(key=lambda c: (orden.get(c["estado"], 3), c["nombre"]))
        self._cambio(estado="ok", contenedores=lista)

    def accion(self, nombre, orden):
        """orden: "start", "stop" o "restart" (en segundo plano)."""
        def hacer():
            try:
                _docker(orden, nombre, timeout=120)
            except (OSError, subprocess.SubprocessError):
                pass
            self._despertar.set()
        threading.Thread(target=hacer, daemon=True).start()

    def instantanea(self):
        with self.lock:
            return {"version": self.version, "estado": self.estado,
                    "contenedores": [dict(c) for c in self.contenedores]}


def _fecha(texto):
    """Fecha de Docker (RFC 3339 con nanosegundos) a datetime con zona; None si no hay."""
    if not texto or texto.startswith("0001"):
        return None
    try:
        return datetime.datetime.fromisoformat(texto[:19] + "+00:00")
    except ValueError:
        return None


def hace(fecha):
    """Tiempo desde `fecha`, corto: "45 s", "6 min", "3 h", "2 d"."""
    if not fecha:
        return ""
    s = max(0, (datetime.datetime.now(datetime.timezone.utc) - fecha).total_seconds())
    for tope, div, unidad in ((60, 1, "s"), (3600, 60, "min"), (86400, 3600, "h"), (float("inf"), 86400, "d")):
        if s < tope:
            return f"{int(s // div)} {unidad}"


def color(c):
    """Color del punto: verde (sano o en marcha), amarillo (arrancando), rojo (parado o mal)."""
    if c["estado"] == "running":
        return "amarillo" if c["salud"] == "arrancando" else "rojo" if c["salud"] == "enfermo" else "verde"
    return "amarillo" if c["estado"] in ("restarting", "paused") else "rojo"
