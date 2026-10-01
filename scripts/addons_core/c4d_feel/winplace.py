"""Place new Blender windows centered on the main window's monitor (Windows only).

Blender's Python API can't position windows, so on Windows this finds the
new top-level window of this process and moves it with the Win32 API.
Other platforms: no-op.
"""

import os
import sys

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


def blender_windows():
    """Set of visible top-level window handles owned by this Blender process."""
    if sys.platform != "win32":
        return set()
    pid = os.getpid()
    found = set()

    def cb(hwnd, _lparam):
        owner = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and _user32.IsWindowVisible(hwnd):
            found.add(hwnd)
        return True

    _user32.EnumWindows(_EnumProc(cb), 0)
    return found


def open_floating_window(context, configure, width_frac=0.7, height_frac=0.75):
    """Open a new independent window (copy of an area), centered on screen,
    then call configure(window) to set its editor. Returns the window or None."""
    import bpy
    window = context.window or context.window_manager.windows[0]
    area = context.area if context.area and context.window else None
    if area is None:
        area = max(window.screen.areas, key=lambda a: a.width * a.height)
    before = set(context.window_manager.windows[:])
    os_before = blender_windows()
    with context.temp_override(window=window, screen=window.screen, area=area):
        bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
    new = [w for w in context.window_manager.windows if w not in before]
    if not new:
        return None
    new_window = new[0]

    def later():
        try:
            center_new_window(os_before, width_frac, height_frac)
            configure(new_window)
        except (ReferenceError, AttributeError, RuntimeError, OSError):
            pass
        return None
    bpy.app.timers.register(later, first_interval=0.05)
    return new_window


def center_new_window(before, width_frac=0.7, height_frac=0.75):
    """Center the window that appeared since `before` on the main window's monitor.

    Returns True when a window was moved."""
    if sys.platform != "win32":
        return False
    new = list(blender_windows() - set(before))
    if not new:
        return False
    hwnd = new[0]
    ref = next(iter(before), None) or hwnd
    monitor = _user32.MonitorFromWindow(ref, 2)  # MONITOR_DEFAULTTONEAREST
    info = _MONITORINFO()
    info.cbSize = ctypes.sizeof(_MONITORINFO)
    if not _user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return False
    work = info.rcWork
    mw, mh = work.right - work.left, work.bottom - work.top
    w, h = int(mw * width_frac), int(mh * height_frac)
    x = work.left + (mw - w) // 2
    y = work.top + (mh - h) // 2
    SWP_NOZORDER, SWP_SHOWWINDOW = 0x0004, 0x0040
    _user32.SetWindowPos(hwnd, None, x, y, w, h, SWP_NOZORDER | SWP_SHOWWINDOW)
    _user32.SetForegroundWindow(hwnd)
    return True
