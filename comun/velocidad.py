"""Test de velocidad de internet contra los servidores de Cloudflare
(los mismos que usa speed.cloudflare.com). Solo usa la librería estándar.

Ping: mediana de lo que tarda en abrirse una conexión TCP (un viaje de ida y
vuelta, como el ping clásico; un ICMP de verdad necesitaría administrador).
Bajada y subida: varias conexiones a la vez durante unos segundos; se mide
lo transferido entre el tiempo transcurrido.
"""

import http.client
import socket
import statistics
import threading
import time

from idioma import _

HOST = "speed.cloudflare.com"
# Sin presentarse como un navegador, Cloudflare rechaza las descargas de 10 MB o más
# (responde 429 "Too Many Requests" con un solo byte).
CABECERAS = {"User-Agent": "Mozilla/5.0 (compatible; MoonDeck)", "Referer": f"https://{HOST}/"}


class TestVelocidad:
    HILOS = 4
    DURACION_BAJADA = 8.0       # segundos
    DURACION_SUBIDA = 6.0
    MAX_BAJADA = 400 * 2**20    # para no gastar demasiados datos en conexiones muy rápidas
    MAX_SUBIDA = 120 * 2**20
    TROZO_SUBIDA = 1 * 2**20

    def __init__(self):
        self.fase = None        # None (parado), "ping", "bajada" o "subida"
        self.progreso = 0.0     # 0-1 dentro de la fase
        self.actual = None      # Mbps en directo durante la fase
        self.resultado = None   # {"ping", "bajada", "subida", "fecha"}
        self.parcial = {}       # lo ya medido del test en marcha ("ping", "bajada")
        self._rechazo = None    # código HTTP si Cloudflare no ha dejado medir
        self.error = None
        self._hilo = None

    @property
    def midiendo(self):
        return self._hilo is not None and self._hilo.is_alive()

    def iniciar(self):
        if self.midiendo:
            return
        self.error = None
        self.parcial = {}
        self._hilo = threading.Thread(target=self._ejecutar, daemon=True)
        self._hilo.start()

    def _ejecutar(self):
        try:
            ping = self.parcial["ping"] = self._ping()
            bajada = self.parcial["bajada"] = self._medir("bajada", self._trabajo_bajada,
                                                          self.DURACION_BAJADA, self.MAX_BAJADA)
            subida = self._medir("subida", self._trabajo_subida, self.DURACION_SUBIDA, self.MAX_SUBIDA)
            self.resultado = {"ping": ping, "bajada": bajada, "subida": subida,
                              "fecha": time.strftime("%d/%m %H:%M")}
        except Exception as e:  # noqa: BLE001 - sin internet, cortafuegos...
            self.error = _("No se pudo completar el test: {error}").format(error=e)
        finally:
            self.fase = None
            self.actual = None

    def _ping(self):
        self.fase, self.progreso = "ping", 0.0
        direccion = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)[0][4]  # DNS fuera de la medida
        tiempos = []
        for i in range(8):
            t = time.perf_counter()
            with socket.create_connection(direccion[:2], timeout=5):
                tiempos.append((time.perf_counter() - t) * 1000)
            self.progreso = (i + 1) / 8
        return statistics.median(tiempos)

    def _medir(self, fase, trabajo, duracion, maximo):
        self.fase, self.progreso, self.actual = fase, 0.0, None
        self._rechazo = None
        total = [0]
        lock = threading.Lock()
        fin = threading.Event()

        def sumar(n):
            with lock:
                total[0] += n
                if total[0] >= maximo:
                    fin.set()

        inicio = time.perf_counter()
        hilos = [threading.Thread(target=trabajo, args=(sumar, fin), daemon=True) for _x in range(self.HILOS)]
        for h in hilos:
            h.start()
        while not fin.is_set():
            transcurrido = time.perf_counter() - inicio
            if transcurrido >= duracion:
                fin.set()
                break
            self.progreso = transcurrido / duracion
            if transcurrido > 0.5:
                self.actual = total[0] * 8 / transcurrido / 1e6
            time.sleep(0.2)
        transcurrido = time.perf_counter() - inicio
        for h in hilos:
            h.join(timeout=3)
        if total[0] == 0:
            if self._rechazo:
                raise ConnectionError(_("Cloudflare no deja medir ahora mismo (respuesta {codigo}); "
                                        "prueba dentro de un rato.").format(codigo=self._rechazo))
            raise ConnectionError(_("no se pudo medir la bajada") if fase == "bajada"
                                  else _("no se pudo medir la subida"))
        return total[0] * 8 / transcurrido / 1e6

    def _trabajo_bajada(self, sumar, fin):
        tam = 25 * 2**20
        con = http.client.HTTPSConnection(HOST, timeout=10)
        try:
            while not fin.is_set():
                con.request("GET", f"/__down?bytes={tam}", headers=CABECERAS)
                r = con.getresponse()
                if r.status != 200:
                    # Rechazado (p. ej. 429): no cuenta como datos. Se prueba con trozos más pequeños.
                    r.read()
                    self._rechazo = r.status
                    if tam <= 2**20:
                        return
                    tam //= 4
                    time.sleep(0.2)
                    continue
                while not fin.is_set():
                    trozo = r.read(64 * 1024)
                    if not trozo:
                        break
                    sumar(len(trozo))
        except OSError:
            pass  # una conexión que falla no invalida las demás
        finally:
            con.close()

    def _trabajo_subida(self, sumar, fin):
        datos = b"0" * self.TROZO_SUBIDA
        con = http.client.HTTPSConnection(HOST, timeout=10)
        try:
            while not fin.is_set():
                con.request("POST", "/__up", body=datos,
                            headers=dict(CABECERAS, **{"Content-Type": "application/octet-stream"}))
                r = con.getresponse()
                r.read()
                if r.status != 200:
                    self._rechazo = r.status
                    return
                sumar(len(datos))
        except OSError:
            pass
        finally:
            con.close()
