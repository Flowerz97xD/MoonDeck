"""Escritorios virtuales por el protocolo estándar de Wayland ext-workspace-v1 (COSMIC,
KDE, niri…). Un cliente mínimo en Python puro, con su propia conexión al compositor:
un hilo escucha qué escritorios hay y cuál está activo, y `cambiar(±1)` pasa al
siguiente o al anterior.

Si el compositor no ofrece el protocolo, `disponible` queda en False y no hace nada.
"""

import os
import shutil
import socket
import subprocess
import struct
import threading

# Peticiones y eventos (su número es el orden en que salen en el XML del protocolo).
DISPLAY, REGISTRO, SINCRONIZAR = 1, 2, 3
GESTOR_COMMIT = 0
GESTOR_EV_GRUPO, GESTOR_EV_ESCRITORIO = 0, 1
GRUPO_EV_ENTRA, GRUPO_EV_SALE, GRUPO_EV_QUITADO = 3, 4, 5
ESC_EV_NOMBRE, ESC_EV_COORDENADAS, ESC_EV_ESTADO, ESC_EV_QUITADO = 1, 2, 3, 5
ESC_ACTIVAR = 1
ACTIVO, OCULTO = 1, 4


def _cadena(datos, i):
    n = struct.unpack_from("<I", datos, i)[0]
    return datos[i + 4:i + 4 + n - 1].decode(errors="replace"), i + 4 + (n + 3) // 4 * 4


def vista_general():
    """Abre la vista con todos los escritorios (la de COSMIC; en KDE, su "Vista general")."""
    for orden in (["cosmic-workspaces"],
                  ["qdbus", "org.kde.kglobalaccel", "/component/kwin", "invokeShortcut", "Overview"]):
        if shutil.which(orden[0]):
            try:
                subprocess.Popen(orden, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
                return True
            except OSError:
                continue
    return False


class Escritorios:
    def __init__(self):
        self.disponible = False
        self.lock = threading.Lock()
        self._sock = None
        self._gestor = None
        self._grupos = {}        # id del grupo -> [ids de escritorio, en orden de llegada]
        self._escritorios = {}   # id -> {"nombre", "coord", "estado", "orden"}
        self._siguiente_orden = 0
        threading.Thread(target=self._bucle, daemon=True).start()

    # --- protocolo ---------------------------------------------------------------

    def _enviar(self, obj, op, args=b""):
        with self.lock:
            self._sock.sendall(struct.pack("<IHH", obj, op, 8 + len(args)) + args)

    def _bucle(self):
        ruta = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
        if not ruta.startswith("/"):
            ruta = os.path.join(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"), ruta)
        try:
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.connect(ruta)
            self._enviar(DISPLAY, 1, struct.pack("<I", REGISTRO))      # get_registry
            self._enviar(DISPLAY, 0, struct.pack("<I", SINCRONIZAR))   # sync
            buf = b""
            while True:
                trozo = self._sock.recv(65536)
                if not trozo:
                    break
                buf += trozo
                while len(buf) >= 8:
                    obj, op, largo = struct.unpack_from("<IHH", buf)
                    if len(buf) < largo:
                        break
                    self._evento(obj, op, buf[8:largo])
                    buf = buf[largo:]
        except (OSError, struct.error):
            pass
        self.disponible = False

    def _evento(self, obj, op, d):
        if obj == REGISTRO and op == 0:  # global: (name, interfaz, versión)
            nombre = struct.unpack_from("<I", d)[0]
            interfaz, i = _cadena(d, 4)
            if interfaz == "ext_workspace_manager_v1" and not self._gestor:
                self._gestor = 4
                texto = interfaz.encode() + b"\0"
                texto += b"\0" * (-len(texto) % 4)
                self._enviar(REGISTRO, 0, struct.pack("<I", nombre) + struct.pack("<I", len(interfaz) + 1) + texto
                             + struct.pack("<II", 1, self._gestor))  # bind
                self.disponible = True
            return
        if obj == self._gestor:
            nuevo = struct.unpack_from("<I", d)[0] if op in (GESTOR_EV_GRUPO, GESTOR_EV_ESCRITORIO) else None
            if op == GESTOR_EV_GRUPO:
                self._grupos[nuevo] = []
            elif op == GESTOR_EV_ESCRITORIO:
                self._escritorios[nuevo] = {"nombre": "", "coord": None, "estado": 0, "orden": self._siguiente_orden}
                self._siguiente_orden += 1
            return
        if obj in self._grupos:
            if op in (GRUPO_EV_ENTRA, GRUPO_EV_SALE):
                esc = struct.unpack_from("<I", d)[0]
                lista = self._grupos[obj]
                if op == GRUPO_EV_ENTRA and esc not in lista:
                    lista.append(esc)
                elif op == GRUPO_EV_SALE and esc in lista:
                    lista.remove(esc)
            elif op == GRUPO_EV_QUITADO:
                del self._grupos[obj]
            return
        e = self._escritorios.get(obj)
        if e is None:
            return
        if op == ESC_EV_NOMBRE:
            e["nombre"] = _cadena(d, 0)[0]
        elif op == ESC_EV_COORDENADAS:
            n = struct.unpack_from("<I", d)[0]
            e["coord"] = struct.unpack_from(f"<{n // 4}I", d, 4)
        elif op == ESC_EV_ESTADO:
            e["estado"] = struct.unpack_from("<I", d)[0]
        elif op == ESC_EV_QUITADO:
            del self._escritorios[obj]
            for lista in self._grupos.values():
                if obj in lista:
                    lista.remove(obj)

    # --- uso ------------------------------------------------------------------------

    def cambiar(self, paso):
        """Pasa al escritorio siguiente (+1) o anterior (-1) del grupo del escritorio
        activo (el de la pantalla). En el primero o el último no hace nada."""
        if not self.disponible:
            return False
        todos = dict(self._escritorios)  # copias: el hilo lector los va cambiando
        for lista in [list(v) for v in list(self._grupos.values())]:
            esc = [i for i in lista if i in todos and not todos[i]["estado"] & OCULTO]
            esc.sort(key=lambda i: (todos[i]["coord"] or (), todos[i]["orden"]))
            activos = [k for k, i in enumerate(esc) if todos[i]["estado"] & ACTIVO]
            if not activos:
                continue
            destino = activos[0] + paso
            if 0 <= destino < len(esc):
                try:
                    self._enviar(esc[destino], ESC_ACTIVAR)
                    self._enviar(self._gestor, GESTOR_COMMIT)
                except OSError:
                    return False
                return True
            return False
        return False
