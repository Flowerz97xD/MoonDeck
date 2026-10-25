"""Lectura de hardware para Windows 11.

- CPU, RAM, discos y red: psutil (sin permisos especiales).
- GPUs NVIDIA: nvidia-smi (viene con el driver).
- Temperaturas, GPUs AMD/Intel, relojes y consumos: LibreHardwareMonitorLib.dll
  (necesita ejecutar como administrador y el driver PawnIO instalado).
- FPS: PresentMon.exe de Intel (necesita administrador).

En Linux también funciona (sin LibreHardwareMonitor) para poder probarlo.
"""

import os
import shutil
import subprocess
import sys
import threading
import time
from collections import deque

import psutil

from idioma import _

ES_WINDOWS = sys.platform == "win32"
LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")


class LibreHardwareMonitor:
    """Puente con LibreHardwareMonitorLib.dll vía pythonnet."""

    def __init__(self):
        self.ok = False
        self.error = None
        if not ES_WINDOWS:
            self.error = _("LibreHardwareMonitor solo funciona en Windows")
            return
        dll = os.path.join(LIB, "LibreHardwareMonitorLib.dll")
        if not os.path.exists(dll):
            self.error = _("Falta lib\\LibreHardwareMonitorLib.dll: ejecuta instalar.bat")
            return
        try:
            import clr  # pythonnet
            from System import AppDomain, ResolveEventHandler
            from System.Reflection import Assembly, AssemblyName

            # Sin el .config de LibreHardwareMonitor.exe no hay redirecciones de
            # versión: cargamos cualquier dependencia pedida desde lib\.
            def resolver(_sender, args):
                path = os.path.join(LIB, AssemblyName(args.Name).Name + ".dll")
                return Assembly.LoadFrom(path) if os.path.exists(path) else None

            self._resolver = ResolveEventHandler(resolver)
            AppDomain.CurrentDomain.AssemblyResolve += self._resolver
            clr.AddReference(dll)
            from LibreHardwareMonitor.Hardware import Computer

            c = Computer()
            c.IsCpuEnabled = True
            c.IsGpuEnabled = True
            c.IsMemoryEnabled = True
            c.IsStorageEnabled = True
            c.IsMotherboardEnabled = True
            c.Open()
            self.computer = c
            self.ok = True
        except Exception as e:  # noqa: BLE001 - cualquier fallo de .NET
            self.error = _("No se pudo cargar LibreHardwareMonitor: {error}").format(error=e)

    def read(self):
        """Lista de (tipo_hw, nombre_hw, tipo_sensor, nombre_sensor, valor, id).

        `id` es el identificador de LibreHardwareMonitor (p. ej. "/amdcpu/0/temperature/2"):
        no cambia entre reinicios, así que sirve para recordar qué sensores mostrar.
        """
        out = []
        if not self.ok:
            return out

        def visit(hw, kind):
            hw.Update()
            for s in hw.Sensors:
                if s.Value is not None:
                    out.append((kind, hw.Name, s.SensorType.ToString(), s.Name, float(s.Value),
                                s.Identifier.ToString()))
            for sub in hw.SubHardware:
                visit(sub, kind)

        for hw in self.computer.Hardware:
            try:
                visit(hw, hw.HardwareType.ToString())
            except Exception:  # noqa: BLE001 - un dispositivo no debe tumbar el resto
                continue
        return out

    def close(self):
        if self.ok:
            self.computer.Close()


def find(sensors, kind=None, stype=None, names=(), hw=None):
    """Primer valor que encaje; `names` en orden de preferencia (subcadenas)."""
    pool = [s for s in sensors
            if (kind is None or s[0].startswith(kind))
            and (stype is None or s[2] == stype)
            and (hw is None or s[1] == hw)]
    for n in names:
        for s in pool:
            if n.lower() in s[3].lower():
                return s[4]
    return pool[0][4] if pool and not names else None


NVIDIA_FIELDS = ("index,name,utilization.gpu,temperature.gpu,memory.used,memory.total,"
                 "power.draw,power.limit,fan.speed,clocks.gr")


def read_nvidia():
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    try:
        out = subprocess.run(
            [exe, f"--query-gpu={NVIDIA_FIELDS}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
            creationflags=0x08000000 if ES_WINDOWS else 0,  # CREATE_NO_WINDOW
        ).stdout.strip().splitlines()
    except (OSError, subprocess.TimeoutExpired):
        return []

    def num(x):
        try:
            return float(x)
        except ValueError:
            return None

    gpus = []
    for line in out:
        p = [s.strip() for s in line.split(",")]
        if len(p) < 10:
            continue
        used, total = num(p[4]), num(p[5])
        gpus.append({
            "id": f"nvidia{p[0]}", "name": p[1], "util": num(p[2]), "temp": num(p[3]),
            "vram": (used * 2**20, total * 2**20) if used is not None and total else None,
            "power": num(p[6]), "power_limit": num(p[7]),
            "fan": num(p[8]), "clock": num(p[9]),
        })
    return gpus


def lhm_gpus(sensors, skip_nvidia):
    gpus = []
    names = []
    for kind, hw, *_ in sensors:
        if kind.startswith("Gpu") and hw not in names:
            if skip_nvidia and kind == "GpuNvidia":
                continue
            names.append(hw)
    for i, hw in enumerate(names):
        def f(stype, *n):
            return find(sensors, stype=stype, names=n, hw=hw)
        used = f("SmallData", "Dedicated Memory Used", "Memory Used", "Shared Memory Used")
        total = f("SmallData", "Dedicated Memory Total", "Memory Total", "Shared Memory Total")
        gpus.append({
            "id": f"lhm{i}", "name": hw,
            "util": f("Load", "GPU Core", "D3D 3D"),
            "temp": f("Temperature", "GPU Core", "Hot Spot", "GPU"),
            "vram": (used * 2**20, total * 2**20) if used is not None and total else None,
            "power": f("Power", "GPU Package", "GPU Power", "GPU Core"),
            "power_limit": None,
            "fan": f("Control", "GPU Fan", "Fan"),
            "clock": f("Clock", "GPU Core"),
        })
    return gpus


class MedidorFPS:
    """FPS de la app en primer plano usando PresentMon (eventos ETW de Present()).

    PresentMon escribe una línea CSV por fotograma presentado; un hilo las lee y
    guarda los tiempos entre fotogramas de cada proceso.
    """

    SESION = "MoonDeckFPS"
    IGNORAR = ("dwm.exe", "pythonw.exe", "python.exe", "PresentMon.exe")
    # Apps de escritorio que también presentan fotogramas (vídeo, animaciones). Si
    # pasan a primer plano, p. ej. en el otro monitor, no le quitan el puesto a un
    # juego que siga activo; sin juegos abiertos sí se miden.
    ESCRITORIO = {
        "chrome.exe", "msedge.exe", "msedgewebview2.exe", "firefox.exe", "opera.exe",
        "opera_gx.exe", "brave.exe", "vivaldi.exe", "discord.exe", "spotify.exe",
        "explorer.exe", "steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe",
        "battle.net.exe", "eadesktop.exe", "obs64.exe", "ms-teams.exe", "teams.exe",
        "whatsapp.exe", "telegram.exe", "code.exe", "vlc.exe", "applicationframehost.exe",
    }

    def __init__(self, comando=None):
        self.ok = False
        self.error = None
        self.proc = None
        self.cuadros = {}   # pid -> deque[(inicio_ms, ms_entre_cuadros)]
        self.nombres = {}   # pid -> nombre del ejecutable
        self.visto = {}     # pid -> (último inicio_ms leído, hora local en que cambió)
        self.objetivo = None
        self.cerrando = False
        self.lock = threading.Lock()
        self.exe = os.path.join(LIB, "PresentMon.exe")
        if comando is None:
            if not ES_WINDOWS:
                self.error = _("PresentMon solo funciona en Windows")
                return
            if not os.path.exists(self.exe):
                self.error = _("Falta lib\\PresentMon.exe: vuelve a ejecutar instalar.bat")
                return
            comando = [self.exe, "--output_stdout", "--no_console_stats", "--stop_existing_session",
                       "--session_name", self.SESION,
                       "--no_track_display", "--no_track_gpu", "--no_track_input"]
            for nombre in self.IGNORAR:
                comando += ["--exclude", nombre]
        try:
            self.proc = subprocess.Popen(
                comando, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
                creationflags=0x08000000 if ES_WINDOWS else 0)
        except OSError as e:
            self.error = _("No se pudo iniciar PresentMon: {error}").format(error=e)
            return
        self.ok = True
        threading.Thread(target=self._leer, daemon=True).start()

    def _leer(self):
        cols = None
        for linea in self.proc.stdout:
            campos = linea.rstrip("\r\n").split(",")
            if cols is None:
                if "Application" not in campos:
                    continue
                cols = {c: i for i, c in enumerate(campos)}
                i_app, i_pid = cols["Application"], cols["ProcessID"]
                i_ms = cols.get("MsBetweenPresents", cols.get("FrameTime"))
                i_t = cols.get("CPUStartTime", cols.get("TimeInSeconds"))
                escala_t = 1000.0 if "TimeInSeconds" in cols and "CPUStartTime" not in cols else 1.0
                if i_ms is None:
                    self.error = _("PresentMon no da tiempos entre fotogramas")
                    return
                continue
            try:
                pid = int(campos[i_pid])
                ms = float(campos[i_ms])
                t = float(campos[i_t]) * escala_t if i_t is not None else time.monotonic() * 1000
            except (ValueError, IndexError):
                continue
            if ms <= 0:
                continue
            with self.lock:
                d = self.cuadros.get(pid)
                if d is None:
                    d = self.cuadros[pid] = deque()
                    self.nombres[pid] = campos[i_app]
                d.append((t, ms))
                # 10 s de historial por proceso para el 1% low.
                while d and d[0][0] < t - 10000:
                    d.popleft()
        if not self.cerrando and not self.error:
            self.error = _("PresentMon se cerró (¿falta permiso de administrador?)")
        self.ok = False

    @staticmethod
    def _pid_primer_plano():
        if not ES_WINDOWS:
            return None
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def leer(self):
        """{"app", "fps", "low1", "frametime"} de la app objetivo, o None si no hay ninguna."""
        if not self.ok:
            return None
        ahora = time.monotonic()
        with self.lock:
            # Quitar procesos que llevan 3 s sin presentar (por reloj local).
            activos = {}
            for pid, d in list(self.cuadros.items()):
                if not d:
                    continue
                if self.visto.get(pid, (None,))[0] != d[-1][0]:
                    self.visto[pid] = (d[-1][0], ahora)
                if ahora - self.visto[pid][1] > 3:
                    del self.cuadros[pid]
                    del self.visto[pid]
                    continue
                activos[pid] = d

            if not activos:
                self.objetivo = None
                return None
            def es_escritorio(pid):
                return self.nombres.get(pid, "").lower() in self.ESCRITORIO

            def cuadros_ultimo_seg(pid):
                return sum(1 for t, _ in activos[pid] if t >= activos[pid][-1][0] - 1000)

            juegos = [p for p in activos if not es_escritorio(p)]
            fg = self._pid_primer_plano()
            if fg in activos and (not es_escritorio(fg) or not juegos):
                self.objetivo = fg
            elif self.objetivo not in activos or (es_escritorio(self.objetivo) and juegos):
                self.objetivo = max(juegos or activos, key=cuadros_ultimo_seg)
            d = activos[self.objetivo]
            fin = d[-1][0]
            ultimo_seg = [ms for t, ms in d if t >= fin - 1000]
            todos = sorted(ms for _, ms in d)
            nombre = self.nombres.get(self.objetivo, "?")

        media = sum(ultimo_seg) / len(ultimo_seg)
        # 1% low: FPS medio del 1% de fotogramas más lentos de los últimos 10 s.
        peor = todos[-max(1, len(todos) // 100):]
        return {"app": nombre, "fps": 1000 / media, "frametime": media,
                "low1": 1000 / (sum(peor) / len(peor))}

    def close(self):
        self.cerrando = True
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        if ES_WINDOWS and os.path.exists(self.exe):
            # Cerrar la sesión ETW para no dejarla huérfana.
            subprocess.run([self.exe, "--terminate_existing_session", "--session_name", self.SESION],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=0x08000000, timeout=5)


class Sampler:
    """Recoge una instantánea de todo el hardware."""

    def __init__(self):
        self.lhm = LibreHardwareMonitor()
        self.fps = MedidorFPS()
        self.has_nvidia_smi = bool(read_nvidia())
        self.last_net = self._net_totals()
        self.last_disk = psutil.disk_io_counters()
        self.last_t = time.monotonic()
        psutil.cpu_percent(percpu=True)

    @staticmethod
    def _net_totals():
        rx = tx = 0
        for nic, c in psutil.net_io_counters(pernic=True).items():
            if nic != "lo" and "loopback" not in nic.lower():
                rx += c.bytes_recv
                tx += c.bytes_sent
        return rx, tx

    def sample(self):
        now = time.monotonic()
        dt = max(now - self.last_t, 1e-3)
        self.last_t = now
        sensors = self.lhm.read()

        s = {"lhm_error": self.lhm.error}
        s["cores"] = psutil.cpu_percent(percpu=True)
        s["cpu"] = sum(s["cores"]) / len(s["cores"])
        s["procs"] = len(psutil.pids())

        core_clocks = [v for k, _, t, n, v, _ in sensors if k == "Cpu" and t == "Clock" and n.startswith("Core #")]
        if core_clocks:
            s["freq"] = sum(core_clocks) / len(core_clocks)
        else:
            freq = psutil.cpu_freq()
            s["freq"] = freq.current if freq else None

        s["cpu_temp"] = find(sensors, "Cpu", "Temperature",
                             ("Tctl", "Package", "Core (Tctl", "Core Average", "Core"))
        s["cpu_power"] = find(sensors, "Cpu", "Power", ("Package",))

        # Todos los sensores, para el widget de sensores y su selector.
        todos = list(sensors)
        if not ES_WINDOWS:
            # En Linux (para probar): temperaturas y ventiladores de psutil.
            for tipo, lector in (("Temperature", "sensors_temperatures"), ("Fan", "sensors_fans")):
                for chip, entries in getattr(psutil, lector, dict)().items():
                    for i, e in enumerate(entries):
                        nombre = e.label or ("temp" if tipo == "Temperature" else "fan")
                        todos.append(("", chip, tipo, nombre, float(e.current), f"/linux/{chip}/{tipo}/{i}"))
            if s["cpu_temp"] is None and hasattr(psutil, "sensors_temperatures"):
                cpu = psutil.sensors_temperatures().get("k10temp") or psutil.sensors_temperatures().get("coretemp")
                s["cpu_temp"] = cpu[0].current if cpu else None
        s["sensores"] = todos
        s["temps"] = [x for x in todos if x[2] == "Temperature"]
        s["fans"] = [x for x in todos if x[2] == "Fan"]

        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        s["mem"] = (vm.total - vm.available, vm.total, vm.percent)
        s["swap"] = (sw.used, sw.total, sw.percent)

        nv = read_nvidia() if self.has_nvidia_smi else []
        s["gpus"] = nv + lhm_gpus(sensors, skip_nvidia=bool(nv))

        rx, tx = self._net_totals()
        s["net"] = ((rx - self.last_net[0]) / dt, (tx - self.last_net[1]) / dt)
        self.last_net = (rx, tx)

        d = psutil.disk_io_counters()
        if d and self.last_disk:
            s["disk_io"] = ((d.read_bytes - self.last_disk.read_bytes) / dt,
                            (d.write_bytes - self.last_disk.write_bytes) / dt)
        else:
            s["disk_io"] = (0, 0)
        self.last_disk = d

        parts = []
        for p in psutil.disk_partitions():
            if not p.fstype or "cdrom" in p.opts or p.device.startswith("/dev/loop") or "/snap/" in p.mountpoint:
                continue
            try:
                u = psutil.disk_usage(p.mountpoint)
            except OSError:
                continue
            parts.append((p.mountpoint, u.used, u.total, u.percent))
        s["parts"] = parts

        s["uptime"] = time.time() - psutil.boot_time()
        s["fps"] = self.fps.leer()
        s["fps_error"] = self.fps.error
        return s

    def close(self):
        self.fps.close()
        self.lhm.close()
