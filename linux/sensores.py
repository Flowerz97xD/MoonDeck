"""Lectura de hardware en Linux.

- CPU, RAM, discos y red: psutil.
- Temperaturas, ventiladores, voltajes, consumos...: /sys/class/hwmon (sin permisos).
- GPUs NVIDIA: nvidia-smi (viene con el driver).
- GPUs AMD: sysfs del driver amdgpu (uso, VRAM, temperatura, consumo, reloj).

Cada sensor es una tupla (tipo_hw, nombre_hw, tipo_sensor, nombre_sensor, valor, id)
con los mismos tipos que LibreHardwareMonitor en la versión de Windows, para que
el widget Sensores y su selector funcionen igual.
"""

import glob
import os
import re
import shlex
import shutil
import subprocess
import time

import psutil

from idioma import _


def leer(ruta, defecto=None):
    try:
        with open(ruta) as f:
            return f.read().strip()
    except OSError:
        return defecto


def leer_num(ruta):
    v = leer(ruta)
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None


def modelo_cpu():
    try:
        with open("/proc/cpuinfo") as f:
            for linea in f:
                if linea.startswith("model name"):
                    return linea.split(":", 1)[1].strip()
    except OSError:
        pass
    return "CPU"


def cpu_corto(nombre):
    """ "AMD Ryzen 7 7800X3D 8-Core Processor" -> "Ryzen 7 7800X3D" (para la lista de sensores)."""
    corto = re.sub(r"\s+\d+-Core Processor|\s+Processor|\(R\)|\(TM\)|\s+CPU\b.*|^AMD\s+|^Intel\s+", "", nombre)
    corto = re.sub(r"\s+with Radeon.*", "", corto).strip()
    return corto or nombre


def nombres_pci():
    """{"0000:01:00.0": "NVIDIA GeForce RTX 4070", ...} de las tarjetas gráficas (lspci)."""
    nombres = {}
    if not shutil.which("lspci"):
        return nombres
    try:
        salida = subprocess.run(["lspci", "-D", "-mm"], capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.TimeoutExpired):
        return nombres
    for linea in salida.splitlines():
        try:
            campos = shlex.split(linea)  # ranura "clase" "fabricante" "modelo" -rXX ...
        except ValueError:
            continue
        if len(campos) < 4 or not any(x in campos[1] for x in ("VGA", "3D", "Display")):
            continue
        fabricante, modelo = campos[2], campos[3]
        # "AD104 [GeForce RTX 4070]" -> "GeForce RTX 4070"
        if "[" in modelo and modelo.endswith("]"):
            modelo = modelo[modelo.rindex("[") + 1:-1]
        corto = {"Advanced Micro Devices, Inc. [AMD/ATI]": "AMD", "NVIDIA Corporation": "NVIDIA",
                 "Intel Corporation": "Intel"}.get(fabricante, fabricante.split()[0])
        nombres[campos[0]] = f"{corto} {modelo}"
    return nombres


# Chips de hwmon -> (tipo de hardware, nombre visible)
CHIPS = {
    "k10temp": ("Cpu", None), "coretemp": ("Cpu", None), "zenpower": ("Cpu", None),
    "nvme": ("Storage", None), "drivetemp": ("Storage", None),
    "amdgpu": ("GpuAmd", None), "nouveau": ("GpuNvidia", None), "i915": ("GpuIntel", None),
    "xe": ("GpuIntel", None),
    "spd5118": ("Memory", "RAM"), "jc42": ("Memory", "RAM"),
    "r8169": ("Network", "Ethernet"), "igc": ("Network", "Ethernet"), "e1000e": ("Network", "Ethernet"),
    "mt7921": ("Network", "Wi-Fi"), "mt7922": ("Network", "Wi-Fi"), "iwlwifi": ("Network", "Wi-Fi"),
    "ath": ("Network", "Wi-Fi"), "rtw": ("Network", "Wi-Fi"),
    "nct6": ("Motherboard", "Placa base"), "it87": ("Motherboard", "Placa base"),
    "asus": ("Motherboard", "Placa base"), "gigabyte": ("Motherboard", "Placa base"),
    "f718": ("Motherboard", "Placa base"), "w83": ("Motherboard", "Placa base"),
    "acpitz": ("Motherboard", "ACPI"), "thinkpad": ("Motherboard", "ThinkPad"),
    "BAT": ("Battery", "Batería"),
}

# Prefijo de fichero -> (tipo de sensor, divisor, nombre por defecto)
TIPOS_FICHERO = (
    ("temp", "_input", "Temperature", 1000, "Temperatura"),
    ("fan", "_input", "Fan", 1, "Ventilador"),
    ("pwm", "", "Control", 255 / 100, "Ventilador"),
    ("in", "_input", "Voltage", 1000, "Voltaje"),
    ("curr", "_input", "Current", 1000, "Corriente"),
    ("power", "_average", "Power", 1e6, "Consumo"),
    ("power", "_input", "Power", 1e6, "Consumo"),
    ("energy", "_input", "Energy", 3600, "Energía"),   # µJ -> mWh
    ("freq", "_input", "Clock", 1e6, "Reloj"),         # Hz -> MHz
    ("humidity", "_input", "Humidity", 1000, "Humedad"),
)


class Hwmon:
    """Recorre /sys/class/hwmon una vez y luego solo lee los valores."""

    def __init__(self, cpu, pci):
        self.ficheros = []   # (ruta, tipo_hw, nombre_hw, tipo, nombre, divisor, id)
        vistos = {}
        for h in sorted(glob.glob("/sys/class/hwmon/hwmon*"), key=lambda p: int(p.rsplit("hwmon", 1)[1])):
            chip = leer(f"{h}/name", "?")
            dispositivo = os.path.realpath(f"{h}/device") if os.path.exists(f"{h}/device") else h
            tipo_hw, nombre_hw = next((v for k, v in CHIPS.items() if chip.startswith(k)), ("Other", chip))
            nombre_hw = _(nombre_hw) if nombre_hw else nombre_hw  # "Placa base", "Batería"...
            if tipo_hw == "Cpu":
                nombre_hw = cpu_corto(cpu)
            elif chip in ("nvme", "drivetemp"):
                nombre_hw = leer(f"{dispositivo}/model") or leer(f"{dispositivo}/device/model") or _("Disco")
            elif tipo_hw.startswith("Gpu"):
                nombre_hw = pci.get(os.path.basename(dispositivo), chip)
            # Varios del mismo nombre (dos módulos de RAM, dos SSD iguales): "#2", "#3"...
            n = vistos.get(nombre_hw, 0) + 1
            vistos[nombre_hw] = n
            if n > 1:
                nombre_hw = f"{nombre_hw} #{n}"
            # El número hwmonN cambia entre reinicios: el id usa el chip y el dispositivo.
            base = f"/hwmon/{chip}/{os.path.basename(dispositivo)}"
            hechos = set()
            for prefijo, sufijo, tipo, divisor, defecto in TIPOS_FICHERO:
                patron = f"{h}/{prefijo}[0-9]*{sufijo}"
                for ruta in sorted(glob.glob(patron)):
                    nombre_fich = os.path.basename(ruta)
                    clave = nombre_fich[:len(nombre_fich) - len(sufijo)] if sufijo else nombre_fich
                    if not clave[len(prefijo):].isdigit() or clave in hechos:
                        continue
                    hechos.add(clave)
                    etiqueta = leer(f"{h}/{clave}_label")
                    if not etiqueta:
                        num = clave[len(prefijo):]
                        etiqueta = f"{_(defecto)} {num}" if prefijo != "pwm" else _("Control ventilador {n}").format(n=num)
                    self.ficheros.append((ruta, tipo_hw, nombre_hw, tipo, etiqueta, divisor, f"{base}/{clave}"))

    def leer(self):
        out = []
        for ruta, tipo_hw, nombre_hw, tipo, etiqueta, divisor, ident in self.ficheros:
            v = leer_num(ruta)
            if v is None:
                continue
            out.append((tipo_hw, nombre_hw, tipo, etiqueta, v / divisor, ident))
        return out


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
                 "power.draw,power.limit,fan.speed,clocks.gr,clocks.mem,utilization.memory")


def read_nvidia():
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    try:
        out = subprocess.run(
            [exe, f"--query-gpu={NVIDIA_FIELDS}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
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
        if len(p) < 12:
            continue
        used, total = num(p[4]), num(p[5])
        name = p[1] if p[1].startswith("NVIDIA") else f"NVIDIA {p[1]}"
        gpus.append({
            "id": f"nvidia{p[0]}", "name": name, "util": num(p[2]), "temp": num(p[3]),
            "vram": (used * 2**20, total * 2**20) if used is not None and total else None,
            "power": num(p[6]), "power_limit": num(p[7]),
            "fan": num(p[8]), "clock": num(p[9]), "mem_clock": num(p[10]), "mem_util": num(p[11]),
        })
    return gpus


def sensores_nvidia(gpus):
    """Las lecturas de nvidia-smi como sensores, para poder elegirlas en el widget."""
    out = []
    for g in gpus:
        base = f"/{g['id']}"
        for tipo, nombre, valor, ident in (
                ("Temperature", "GPU Core", g["temp"], "temperature/0"),
                ("Load", "GPU Core", g["util"], "load/0"),
                ("Load", "GPU Memory Controller", g["mem_util"], "load/1"),
                ("Control", "GPU Fan", g["fan"], "control/0"),
                ("Power", "GPU Package", g["power"], "power/0"),
                ("Clock", "GPU Core", g["clock"], "clock/0"),
                ("Clock", "GPU Memory", g["mem_clock"], "clock/1"),
                ("SmallData", "GPU Memory Used", g["vram"][0] / 2**20 if g["vram"] else None, "smalldata/0"),
                ("SmallData", "GPU Memory Total", g["vram"][1] / 2**20 if g["vram"] else None, "smalldata/1")):
            if valor is not None:
                out.append(("GpuNvidia", g["name"], tipo, nombre, valor, f"{base}/{ident}"))
    return out


class GpusAmd:
    """GPUs AMD (dedicadas o integradas) a través de sysfs."""

    def __init__(self, pci):
        self.tarjetas = []   # (id, nombre, ruta del dispositivo, ruta hwmon)
        for card in sorted(glob.glob("/sys/class/drm/card[0-9]*")):
            if "-" in os.path.basename(card):
                continue
            dev = os.path.realpath(f"{card}/device")
            if leer(f"{dev}/vendor") != "0x1002" or not os.path.exists(f"{dev}/gpu_busy_percent"):
                continue
            hw = next(iter(glob.glob(f"{dev}/hwmon/hwmon*")), None)
            nombre = pci.get(os.path.basename(dev), "AMD Radeon")
            self.tarjetas.append((f"amd{len(self.tarjetas)}", nombre, dev, hw))

    def leer(self):
        gpus = []
        for ident, nombre, dev, hw in self.tarjetas:
            usada, total = leer_num(f"{dev}/mem_info_vram_used"), leer_num(f"{dev}/mem_info_vram_total")
            temp = leer_num(f"{hw}/temp1_input") if hw else None
            potencia = None
            if hw:
                potencia = leer_num(f"{hw}/power1_average") or leer_num(f"{hw}/power1_input")
            limite = leer_num(f"{hw}/power1_cap") if hw else None
            reloj = leer_num(f"{hw}/freq1_input") if hw else None
            pwm = leer_num(f"{hw}/pwm1") if hw else None
            gpus.append({
                "id": ident, "name": nombre, "util": leer_num(f"{dev}/gpu_busy_percent"),
                "temp": temp / 1000 if temp is not None else None,
                "vram": (usada, total) if usada is not None and total else None,
                "power": potencia / 1e6 if potencia is not None else None,
                "power_limit": limite / 1e6 if limite else None,
                "fan": pwm / 2.55 if pwm is not None else None,
                "clock": reloj / 1e6 if reloj is not None else None,
            })
        return gpus


class Sampler:
    """Recoge una instantánea de todo el hardware."""

    def __init__(self):
        self.cpu = modelo_cpu()
        pci = nombres_pci()
        self.hwmon = Hwmon(self.cpu, pci)
        self.amd = GpusAmd(pci)
        self.has_nvidia_smi = bool(read_nvidia())
        self.lhm = self   # misma interfaz que la versión de Windows (lhm.ok / lhm.error)
        self.ok, self.error = True, None
        self.last_net = self._net_totals()
        self.last_disk = psutil.disk_io_counters()
        self.last_t = time.monotonic()
        psutil.cpu_percent(percpu=True)
        self.relojes = sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"),
                              key=lambda p: int(p.split("/cpu")[2].split("/")[0]))

    @staticmethod
    def _net_totals():
        rx = tx = 0
        for nic, c in psutil.net_io_counters(pernic=True).items():
            if nic != "lo" and not nic.startswith(("veth", "docker", "br-", "virbr")):
                rx += c.bytes_recv
                tx += c.bytes_sent
        return rx, tx

    def sample(self):
        now = time.monotonic()
        dt = max(now - self.last_t, 1e-3)
        self.last_t = now
        sensors = self.hwmon.leer()

        s = {"lhm_error": None}
        s["cores"] = psutil.cpu_percent(percpu=True)
        s["cpu"] = sum(s["cores"]) / len(s["cores"])
        s["procs"] = len(psutil.pids())

        relojes = [leer_num(r) for r in self.relojes]
        relojes = [r / 1000 for r in relojes if r]
        if relojes:
            s["freq"] = sum(relojes) / len(relojes)
        else:
            freq = psutil.cpu_freq()
            s["freq"] = freq.current if freq else None

        s["cpu_temp"] = find(sensors, "Cpu", "Temperature", ("Tctl", "Package", "Tdie", "Core"))
        if s["cpu_temp"] is None:
            s["cpu_temp"] = find(sensors, "Cpu", "Temperature")
        # En los Ryzen con gráfica integrada, el "PPT" de amdgpu es el consumo del paquete.
        s["cpu_power"] = find(sensors, "GpuAmd", "Power", ("PPT",))

        # CPU: carga y reloj de cada hilo, como en LibreHardwareMonitor.
        corto = cpu_corto(self.cpu)
        extra = [("Cpu", corto, "Load", "CPU Total", s["cpu"], "/cpu/load/0")]
        extra += [("Cpu", corto, "Load", f"CPU Core #{i + 1}", v, f"/cpu/load/{i + 1}")
                  for i, v in enumerate(s["cores"])]
        extra += [("Cpu", corto, "Clock", f"Core #{i + 1}", v, f"/cpu/clock/{i}")
                  for i, v in enumerate(relojes)]

        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        s["mem"] = (vm.total - vm.available, vm.total, vm.percent)
        s["swap"] = (sw.used, sw.total, sw.percent)
        mem = _("Memoria")
        extra += [("Memory", mem, "Load", mem, vm.percent, "/ram/load/0"),
                  ("Memory", mem, "Data", _("Memoria usada"), (vm.total - vm.available) / 2**30, "/ram/data/0"),
                  ("Memory", mem, "Data", _("Memoria libre"), vm.available / 2**30, "/ram/data/1")]

        nv = read_nvidia() if self.has_nvidia_smi else []
        s["gpus"] = nv + self.amd.leer()
        todos = sensors + sensores_nvidia(nv) + extra
        s["sensores"] = todos
        s["temps"] = [x for x in todos if x[2] == "Temperature"]
        s["fans"] = [x for x in todos if x[2] == "Fan"]

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

        parts, vistos = [], set()
        for p in psutil.disk_partitions():
            if (not p.fstype or p.fstype in ("squashfs", "iso9660", "tmpfs", "overlay")
                    or p.device.startswith("/dev/loop") or "/snap/" in p.mountpoint
                    or p.device in vistos):
                continue
            vistos.add(p.device)  # btrfs monta el mismo disco varias veces
            try:
                u = psutil.disk_usage(p.mountpoint)
            except OSError:
                continue
            parts.append((p.mountpoint, u.used, u.total, u.percent))
        s["parts"] = parts

        s["uptime"] = time.time() - psutil.boot_time()
        s["fps"] = None
        s["fps_error"] = None
        return s

    def close(self):
        pass
