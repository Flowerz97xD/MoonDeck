"""Idiomas de MoonDeck: los textos se escriben en español en el código y se traducen
con _("texto"). Las traducciones están en lang_<código>.py (TEXTOS = {"español": "traducción"});
lo que falte sale en español. También fechas, meses y días de la semana de cada idioma.
"""

import importlib
import locale
import os
import sys

IDIOMAS = (("es", "Español"), ("en", "English"), ("de", "Deutsch"), ("zh", "中文"), ("ru", "Русский"))
_actual = "es"
_tabla = {}


def detectar():
    """El idioma del sistema si es uno de los nuestros; si no, inglés."""
    candidatos = [os.environ.get(v, "") for v in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")]
    if sys.platform == "win32":
        try:
            import ctypes
            candidatos.insert(0, locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), ""))
        except (OSError, AttributeError):
            pass
    try:
        candidatos.append(locale.getlocale()[0] or "")
    except ValueError:
        pass
    for c in candidatos:
        for parte in c.split(":"):
            codigo = parte[:2].lower()
            if codigo in dict(IDIOMAS):
                return codigo
    return "en"


def poner(codigo):
    """Cambia el idioma (hay que hacerlo antes de crear la interfaz)."""
    global _actual, _tabla
    _actual = codigo if codigo in dict(IDIOMAS) else "en"
    _tabla = {}
    if _actual != "es":
        try:
            _tabla = importlib.import_module(f"lang_{_actual}").TEXTOS
        except ImportError:
            _tabla = {}


def actual():
    return _actual


def _(texto):
    return _tabla.get(texto, texto)


# --- fechas ---------------------------------------------------------------------

_MESES = {
    "es": ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
           "noviembre", "diciembre"),
    "en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"),
    "de": ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
           "November", "Dezember"),
    "zh": tuple(f"{i}月" for i in range(1, 13)),
    "ru": ("январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь",
           "ноябрь", "декабрь"),
}
_MESES_DE = {  # ruso: "25 октября" (genitivo)
    "ru": ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
           "ноября", "декабря"),
}
_DIAS = {  # lunes = 0
    "es": ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    "de": ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"),
    "zh": ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"),
    "ru": ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"),
}
_CORTOS = {
    "es": ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"),
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    "de": ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"),
    "zh": ("周一", "周二", "周三", "周四", "周五", "周六", "周日"),
    "ru": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"),
}
_INICIALES = {
    "es": "LMXJVSD", "en": "MTWTFSS", "de": "MDMDFSS", "zh": "一二三四五六日", "ru": "ПВСЧПСВ",
}


def nombre_mes(mes):
    return _MESES[_actual][mes - 1]


def dia_semana(i):
    return _DIAS[_actual][i]


def dia_corto(i):
    return _CORTOS[_actual][i]


def inicial_dia(i):
    return _INICIALES[_actual][i]


def titulo_mes(anio, mes):
    """ "Octubre 2026", "October 2026", "2026年10月"..."""
    if _actual == "zh":
        return f"{anio}年{mes}月"
    m = nombre_mes(mes)
    return f"{m[:1].upper()}{m[1:]} {anio}"


def fecha_larga(d):
    dia, mes = dia_semana(d.weekday()), d.month
    if _actual == "es":
        return f"{dia}, {d.day} de {nombre_mes(mes)} de {d.year}"
    if _actual == "en":
        return f"{dia}, {nombre_mes(mes)} {d.day}, {d.year}"
    if _actual == "de":
        return f"{dia}, {d.day}. {nombre_mes(mes)} {d.year}"
    if _actual == "zh":
        return f"{d.year}年{mes}月{d.day}日 {dia}"
    return f"{dia}, {d.day} {_MESES_DE['ru'][mes - 1]} {d.year}"
