"""El tiempo de una ciudad con Open-Meteo (gratis, sin cuenta ni clave).

Se actualiza cada 15 minutos en un hilo; la interfaz lee el último resultado.
"""

import json
import threading
import time
import urllib.parse
import urllib.request

from idioma import _

AGENTE = "MoonDeck (widget del tiempo)"
CADA = 15 * 60

# Códigos WMO -> (texto, icono de día, icono de noche)
CODIGOS = {
    0: ("Despejado", "weather-clear", "weather-clear-night"),
    1: ("Casi despejado", "weather-few-clouds", "weather-few-clouds-night"),
    2: ("Parcialmente nublado", "weather-few-clouds", "weather-few-clouds-night"),
    3: ("Nublado", "weather-overcast", "weather-overcast"),
    45: ("Niebla", "weather-fog", "weather-fog"), 48: ("Niebla helada", "weather-fog", "weather-fog"),
    51: ("Llovizna débil", "weather-showers-scattered", "weather-showers-scattered"),
    53: ("Llovizna", "weather-showers-scattered", "weather-showers-scattered"),
    55: ("Llovizna intensa", "weather-showers", "weather-showers"),
    56: ("Llovizna helada", "weather-showers", "weather-showers"),
    57: ("Llovizna helada", "weather-showers", "weather-showers"),
    61: ("Lluvia débil", "weather-showers-scattered", "weather-showers-scattered"),
    63: ("Lluvia", "weather-showers", "weather-showers"), 65: ("Lluvia fuerte", "weather-showers", "weather-showers"),
    66: ("Lluvia helada", "weather-showers", "weather-showers"),
    67: ("Lluvia helada", "weather-showers", "weather-showers"),
    71: ("Nieve débil", "weather-snow", "weather-snow"), 73: ("Nieve", "weather-snow", "weather-snow"),
    75: ("Nieve fuerte", "weather-snow", "weather-snow"), 77: ("Granizo fino", "weather-snow", "weather-snow"),
    80: ("Chubascos", "weather-showers-scattered", "weather-showers-scattered"),
    81: ("Chubascos", "weather-showers", "weather-showers"),
    82: ("Chubascos fuertes", "weather-showers", "weather-showers"),
    85: ("Chubascos de nieve", "weather-snow", "weather-snow"),
    86: ("Chubascos de nieve", "weather-snow", "weather-snow"),
    95: ("Tormenta", "weather-storm", "weather-storm"),
    96: ("Tormenta con granizo", "weather-storm", "weather-storm"),
    99: ("Tormenta con granizo", "weather-storm", "weather-storm"),
}

# Barbate (Cádiz): un guiño a la tierra del creador. Cada uno elige la suya en Configuración.
CIUDAD_POR_DEFECTO = {"nombre": "Barbate", "region": "Cádiz, España", "lat": 36.19237, "lon": -5.92186}


def describir(codigo, de_dia=True):
    texto, dia, noche = CODIGOS.get(codigo, ("—", "weather-overcast", "weather-overcast"))
    return texto, dia if de_dia else noche


def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def buscar_ciudades(texto):
    """[{"nombre", "region", "lat", "lon"}] que coinciden con `texto` (puede lanzar OSError)."""
    q = urllib.parse.urlencode({"name": texto, "count": 8, "language": "es", "format": "json"})
    datos = _get(f"https://geocoding-api.open-meteo.com/v1/search?{q}")
    return [{"nombre": r["name"],
             "region": ", ".join(x for x in (r.get("admin1"), r.get("country")) if x),
             "lat": r["latitude"], "lon": r["longitude"]} for r in datos.get("results", [])]


class Tiempo:
    def __init__(self, ciudad=None):
        self.ciudad = ciudad or dict(CIUDAD_POR_DEFECTO)
        self.datos = None
        self.error = None
        self.version = 0
        self._despertar = threading.Event()
        threading.Thread(target=self._bucle, daemon=True).start()

    def cambiar_ciudad(self, ciudad):
        self.ciudad = ciudad
        self.datos = None
        self.version += 1
        self._despertar.set()

    def _bucle(self):
        while True:
            try:
                self._leer()
                self.error = None
                espera = CADA
            except (OSError, ValueError, KeyError) as e:
                self.error = _("No se pudo leer el tiempo: {error}").format(error=e)
                espera = 120  # sin internet: se reintenta antes
            self.version += 1
            self._despertar.wait(espera)
            self._despertar.clear()

    def _leer(self):
        c = self.ciudad
        q = urllib.parse.urlencode({
            "latitude": c["lat"], "longitude": c["lon"], "timezone": "auto", "forecast_days": 6,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,"
                       "wind_speed_10m,is_day",
            "hourly": "temperature_2m,weather_code,precipitation_probability,is_day",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                     "sunrise,sunset",
        })
        d = _get(f"https://api.open-meteo.com/v1/forecast?{q}")
        cur, h, dia = d["current"], d["hourly"], d["daily"]
        ahora = cur["time"][:13]  # "2026-10-25T14"
        inicio = next((i for i, t in enumerate(h["time"]) if t[:13] >= ahora), 0)
        horas = [{"hora": h["time"][i][11:13], "temp": h["temperature_2m"][i], "codigo": h["weather_code"][i],
                  "lluvia": h["precipitation_probability"][i], "dia": bool(h["is_day"][i])}
                 for i in range(inicio + 1, min(inicio + 13, len(h["time"])))]
        dias = [{"fecha": dia["time"][i], "codigo": dia["weather_code"][i], "max": dia["temperature_2m_max"][i],
                 "min": dia["temperature_2m_min"][i], "lluvia": dia["precipitation_probability_max"][i]}
                for i in range(len(dia["time"]))]
        self.datos = {
            "temp": cur["temperature_2m"], "sensacion": cur["apparent_temperature"],
            "humedad": cur["relative_humidity_2m"], "viento": cur["wind_speed_10m"],
            "codigo": cur["weather_code"], "dia": bool(cur["is_day"]),
            "salida": dia["sunrise"][0][11:16], "puesta": dia["sunset"][0][11:16],
            "horas": horas, "dias": dias, "leido": time.strftime("%H:%M"),
        }
