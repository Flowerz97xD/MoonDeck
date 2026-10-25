"""Desenfoque de fondo ("cristal") para ventanas GTK3 en Wayland.

GTK3 no sabe pedir blur al compositor, así que se habla directamente con
libwayland-client vía ctypes. Se usa ext-background-effect-v1 (nativo de
COSMIC) y, si no existe, org_kde_kwin_blur.
"""

import ctypes
import ctypes.util

WL_MARSHAL_FLAG_DESTROY = 1


class wl_message(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p),
                ("signature", ctypes.c_char_p),
                ("types", ctypes.c_void_p)]


class wl_interface(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p),
                ("version", ctypes.c_int),
                ("method_count", ctypes.c_int),
                ("methods", ctypes.POINTER(wl_message)),
                ("event_count", ctypes.c_int),
                ("events", ctypes.POINTER(wl_message))]


GLOBAL_CB = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p,
                             ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32)
REMOVE_CB = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32)


class registry_listener(ctypes.Structure):
    _fields_ = [("global_", GLOBAL_CB), ("global_remove", REMOVE_CB)]


class _Protocols:
    """Definiciones wl_interface de los protocolos de blur."""

    def __init__(self, wl):
        self._keep = []
        surface = ctypes.c_void_p.in_dll(wl, "wl_surface_interface")
        surface_ptr = ctypes.addressof(surface)
        region_ptr = ctypes.addressof(ctypes.c_void_p.in_dll(wl, "wl_region_interface"))

        # ext-background-effect-v1
        self.ext_effect = wl_interface()
        self.ext_manager = wl_interface()
        self._fill(self.ext_effect, b"ext_background_effect_surface_v1", 1,
                   [(b"destroy", b"", []),
                    (b"set_blur_region", b"?o", [region_ptr])], [])
        self._fill(self.ext_manager, b"ext_background_effect_manager_v1", 1,
                   [(b"destroy", b"", []),
                    (b"get_background_effect", b"no",
                     [ctypes.addressof(self.ext_effect), surface_ptr])],
                   [(b"capabilities", b"u", [None])])

        # org_kde_kwin_blur
        self.kde_blur = wl_interface()
        self.kde_manager = wl_interface()
        self._fill(self.kde_blur, b"org_kde_kwin_blur", 1,
                   [(b"commit", b"", []),
                    (b"set_region", b"?o", [region_ptr]),
                    (b"release", b"", [])], [])
        self._fill(self.kde_manager, b"org_kde_kwin_blur_manager", 1,
                   [(b"create", b"no", [ctypes.addressof(self.kde_blur), surface_ptr]),
                    (b"unset", b"o", [surface_ptr])], [])

    def _messages(self, msgs):
        arr = (wl_message * max(len(msgs), 1))()
        for i, (name, sig, types) in enumerate(msgs):
            t = (ctypes.c_void_p * max(len(types), 1))(*types)
            self._keep.append(t)
            arr[i] = wl_message(name, sig, ctypes.cast(t, ctypes.c_void_p))
        self._keep.append(arr)
        return arr

    def _fill(self, iface, name, version, methods, events):
        iface.name = name
        iface.version = version
        iface.method_count = len(methods)
        iface.methods = self._messages(methods)
        iface.event_count = len(events)
        iface.events = self._messages(events)


def _ptr(gobj):
    get = ctypes.pythonapi.PyCapsule_GetPointer
    get.restype = ctypes.c_void_p
    get.argtypes = [ctypes.py_object, ctypes.c_char_p]
    return get(gobj.__gpointer__, None)


def superficie(gtk_window):
    """Puntero a la wl_surface de la ventana (cambia si GTK la rehace al ocultarla)."""
    try:
        gdk = ctypes.CDLL("libgdk-3.so.0")
        fn = gdk.gdk_wayland_window_get_wl_surface
        fn.restype = ctypes.c_void_p
        fn.argtypes = [ctypes.c_void_p]
        w = gtk_window.get_window()
        return fn(_ptr(w)) if w and "Wayland" in type(w).__name__ else None
    except (OSError, AttributeError, ValueError):
        return None


class Blur:
    """Aplica desenfoque detrás de una Gtk.Window ya realizada."""

    def __init__(self, gtk_window):
        self.ok = False
        self.effect = None
        self.kind = None
        self.surface = None
        try:
            self._setup(gtk_window)
        except (OSError, AttributeError, ValueError):
            self.ok = False

    def _setup(self, win):
        gdk = ctypes.CDLL("libgdk-3.so.0")
        wl = ctypes.CDLL(ctypes.util.find_library("wayland-client") or "libwayland-client.so.0")
        self.wl = wl
        for fn in ("gdk_wayland_window_get_wl_surface", "gdk_wayland_display_get_wl_display",
                   "gdk_wayland_display_get_wl_compositor"):
            getattr(gdk, fn).restype = ctypes.c_void_p
            getattr(gdk, fn).argtypes = [ctypes.c_void_p]
        wl.wl_proxy_marshal_flags.restype = ctypes.c_void_p
        wl.wl_proxy_get_version.restype = ctypes.c_uint32
        wl.wl_proxy_get_version.argtypes = [ctypes.c_void_p]
        wl.wl_proxy_create_wrapper.restype = ctypes.c_void_p
        wl.wl_proxy_create_wrapper.argtypes = [ctypes.c_void_p]
        wl.wl_display_create_queue.restype = ctypes.c_void_p
        wl.wl_display_create_queue.argtypes = [ctypes.c_void_p]
        wl.wl_proxy_set_queue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        wl.wl_proxy_add_listener.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        wl.wl_display_roundtrip_queue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        ptr = _ptr

        gdk_display = win.get_display()
        if "Wayland" not in type(gdk_display).__name__:
            return
        display = gdk.gdk_wayland_display_get_wl_display(ptr(gdk_display))
        self.surface = gdk.gdk_wayland_window_get_wl_surface(ptr(win.get_window()))
        self.compositor = gdk.gdk_wayland_display_get_wl_compositor(ptr(gdk_display))
        if not (display and self.surface and self.compositor):
            return

        self.p = _Protocols(wl)
        self.region_iface = ctypes.addressof(ctypes.c_void_p.in_dll(wl, "wl_region_interface"))
        registry_iface = ctypes.addressof(ctypes.c_void_p.in_dll(wl, "wl_registry_interface"))

        # Cola propia para no interferir con la de GDK.
        self.queue = wl.wl_display_create_queue(display)
        wrapper = wl.wl_proxy_create_wrapper(display)
        wl.wl_proxy_set_queue(wrapper, self.queue)
        registry = self._marshal(wrapper, 1, registry_iface, 0, None)  # wl_display.get_registry

        found = {}

        def on_global(_data, _reg, name, iface, version):
            found[iface.decode()] = name

        self._listener = registry_listener(GLOBAL_CB(on_global), REMOVE_CB(lambda *a: None))
        wl.wl_proxy_add_listener(registry, ctypes.byref(self._listener), None)
        wl.wl_display_roundtrip_queue(display, self.queue)

        def bind(name, iface):
            return wl.wl_proxy_marshal_flags(
                ctypes.c_void_p(registry), 0, ctypes.c_void_p(ctypes.addressof(iface)),
                ctypes.c_uint32(1), ctypes.c_uint32(0),
                ctypes.c_uint32(name), ctypes.c_char_p(iface.name), ctypes.c_uint32(1),
                ctypes.c_void_p(None))

        if "ext_background_effect_manager_v1" in found:
            mgr = bind(found["ext_background_effect_manager_v1"], self.p.ext_manager)
            self.effect = self._marshal(mgr, 1, ctypes.addressof(self.p.ext_effect),
                                        0, None, self.surface)
            self.kind = "ext"
        elif "org_kde_kwin_blur_manager" in found:
            mgr = bind(found["org_kde_kwin_blur_manager"], self.p.kde_manager)
            self.effect = self._marshal(mgr, 0, ctypes.addressof(self.p.kde_blur),
                                        0, None, self.surface)
            self.kind = "kde"
        self.ok = bool(self.effect)

    def _marshal(self, proxy, opcode, iface, flags, *args):
        version = self.wl.wl_proxy_get_version(proxy)
        cargs = [ctypes.c_void_p(a) if a is None or isinstance(a, int) else a for a in args]
        return self.wl.wl_proxy_marshal_flags(
            ctypes.c_void_p(proxy), ctypes.c_uint32(opcode), ctypes.c_void_p(iface),
            ctypes.c_uint32(version), ctypes.c_uint32(flags), *cargs)

    def set_region(self, rects):
        """rects: lista de (x, y, ancho, alto) en coordenadas de la superficie."""
        if not self.ok:
            return
        region = self._marshal(self.compositor, 1, self.region_iface, 0, None)  # create_region
        for x, y, w, h in rects:
            self._marshal(region, 1, 0, 0, *(ctypes.c_int32(int(v)) for v in (x, y, w, h)))
        if self.kind == "ext":
            self._marshal(self.effect, 1, 0, 0, region)
        else:
            self._marshal(self.effect, 1, 0, 0, region)
            self._marshal(self.effect, 0, 0, 0)  # commit
        self._marshal(region, 0, 0, WL_MARSHAL_FLAG_DESTROY)


def rounded_rects(x, y, w, h, r):
    """Aproxima un rectángulo redondeado con franjas horizontales."""
    rects = []
    for i in range(r):
        dy = r - i - 0.5
        inset = int(round(r - (r * r - dy * dy) ** 0.5))
        rects.append((x + inset, y + i, w - 2 * inset, 1))
        rects.append((x + inset, y + h - 1 - i, w - 2 * inset, 1))
    rects.append((x, y + r, w, h - 2 * r))
    return rects
