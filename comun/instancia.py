"""Que solo haya un MoonDeck abierto: un candado sobre un archivo de la carpeta de configuración.
El sistema lo suelta solo al cerrarse la app (aunque sea de golpe). Si se abre otra vez, la
nueva deja un aviso (moondeck.mostrar) para que la que ya está abierta se muestre, y se cierra."""

import os
import sys
import time

_abierto = []  # el archivo del candado, abierto mientras dure la app


def unica(carpeta, espera=10.0):
    """True si esta es la única. Si hay otra, espera un poco (al actualizar, la anterior aún se
    está cerrando) y, si sigue abierta, devuelve False."""
    f = open(os.path.join(carpeta, "moondeck.lock"), "a+")
    fin = time.monotonic() + espera
    avisado = False
    while True:
        try:
            if sys.platform == "win32":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _abierto.append(f)
            return True
        except OSError:
            if not avisado:  # que la abierta se muestre ya (si se está cerrando, no pasa nada)
                avisado = True
                try:
                    open(os.path.join(carpeta, "moondeck.mostrar"), "w").close()
                except OSError:
                    pass
            if time.monotonic() > fin:
                f.close()
                return False
            time.sleep(0.3)


def quieren_verme(carpeta):
    """True (una vez) si otra apertura ha pedido que esta se muestre."""
    ruta = os.path.join(carpeta, "moondeck.mostrar")
    if not os.path.exists(ruta):
        return False
    try:
        os.remove(ruta)
    except OSError:
        pass
    return True
