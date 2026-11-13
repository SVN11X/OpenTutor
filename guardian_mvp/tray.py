"""System tray icon for the resident agent. Win32 via ctypes, no third-party deps.

The icon lives in its own thread with a hidden window and message loop, so it
keeps working while the Tk panel is hidden. Menu clicks are delivered to
``on_command`` from that thread: callers must hand them to the UI thread
(for example through a queue polled with ``root.after``).
"""
from __future__ import annotations

import sys
import threading
from typing import Callable

# (command, label). The order is the menu order. "emergency" is always visible.
MENU_ITEMS: tuple[tuple[str, str], ...] = (
    ("open", "Abrir panel"),
    ("start", "Iniciar sesión"),
    ("pause", "Pausar"),
    ("stop", "Terminar"),
    ("emergency", "Emergencia"),
    ("exit", "Salir"),
)
_FIRST_ID = 1000


class TrayIcon:
    """Tray icon. ``start()`` returns False when the platform has no tray."""

    def __init__(self, on_command: Callable[[str], None], tooltip: str = "OpenTutor Guardian") -> None:
        self._on_command = on_command
        self._tooltip = tooltip[:127]
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._ok = False
        self._hwnd = 0

    def start(self) -> bool:
        if sys.platform != "win32":
            return False
        self._thread = threading.Thread(target=self._run, name="guardian-tray", daemon=True)
        self._thread.start()
        self._ready.wait(5)
        return self._ok

    def stop(self) -> None:
        if sys.platform == "win32" and self._hwnd:
            import ctypes
            ctypes.windll.user32.PostMessageW(self._hwnd, 0x0010, 0, 0)  # WM_CLOSE
            if self._thread is not None:
                self._thread.join(2)

    # ---- Win32 internals -------------------------------------------------
    def _run(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32, shell32, kernel32 = ctypes.windll.user32, ctypes.windll.shell32, ctypes.windll.kernel32
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                        ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                        ("hIcon", wintypes.HANDLE), ("hCursor", wintypes.HANDLE),
                        ("hbrBackground", wintypes.HANDLE), ("lpszMenuName", wintypes.LPCWSTR),
                        ("lpszClassName", wintypes.LPCWSTR)]

        class GUID(ctypes.Structure):
            _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]

        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                        ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT),
                        ("hIcon", wintypes.HANDLE), ("szTip", wintypes.WCHAR * 128),
                        ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                        ("szInfo", wintypes.WCHAR * 256), ("uTimeout", wintypes.UINT),
                        ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                        ("guidItem", GUID), ("hBalloonIcon", wintypes.HANDLE)]

        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = LRESULT
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                           ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                           wintypes.HWND, wintypes.HANDLE, wintypes.HINSTANCE, wintypes.LPVOID]
        user32.LoadIconW.restype = wintypes.HANDLE
        user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
        user32.CreatePopupMenu.restype = wintypes.HANDLE
        user32.AppendMenuW.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
        user32.TrackPopupMenu.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                          ctypes.c_int, wintypes.HWND, wintypes.LPVOID]
        user32.DestroyMenu.argtypes = [wintypes.HANDLE]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
        kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

        WM_APP_TRAY, WM_CLOSE, WM_DESTROY, WM_NULL = 0x8001, 0x0010, 0x0002, 0x0000
        WM_LBUTTONDBLCLK, WM_RBUTTONUP = 0x0203, 0x0205
        NIM_ADD, NIM_DELETE = 0, 2
        taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
        icon = user32.LoadIconW(None, ctypes.cast(ctypes.c_void_p(32512), wintypes.LPCWSTR))  # IDI_APPLICATION

        def nid() -> NOTIFYICONDATAW:
            data = NOTIFYICONDATAW()
            data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            data.hWnd = self._hwnd
            data.uID = 1
            data.uFlags = 0x1 | 0x2 | 0x4  # NIF_MESSAGE | NIF_ICON | NIF_TIP
            data.uCallbackMessage = WM_APP_TRAY
            data.hIcon = icon
            data.szTip = self._tooltip
            return data

        def show_menu() -> None:
            menu = user32.CreatePopupMenu()
            for i, (_cmd, label) in enumerate(MENU_ITEMS):
                user32.AppendMenuW(menu, 0, _FIRST_ID + i, label)
            point = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            user32.SetForegroundWindow(self._hwnd)  # required so the menu closes on outside click
            choice = user32.TrackPopupMenu(menu, 0x0100 | 0x0002, point.x, point.y, 0, self._hwnd, None)  # RETURNCMD|RIGHTBUTTON
            user32.PostMessageW(self._hwnd, WM_NULL, 0, 0)
            user32.DestroyMenu(menu)
            if choice:
                self._emit(MENU_ITEMS[choice - _FIRST_ID][0])

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_APP_TRAY:
                if lparam == WM_RBUTTONUP:
                    show_menu()
                elif lparam == WM_LBUTTONDBLCLK:
                    self._emit("open")
                return 0
            if msg == taskbar_created:  # Explorer restarted: re-add the icon
                shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid()))
                return 0
            if msg == WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid()))
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        proc = WNDPROC(wndproc)  # keep a reference for the thread lifetime
        wc = WNDCLASSW()
        wc.lpfnWndProc = proc
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = "OpenTutorGuardianTray"
        if not user32.RegisterClassW(ctypes.byref(wc)):
            self._ready.set()
            return
        self._hwnd = user32.CreateWindowExW(0, wc.lpszClassName, "Guardian tray", 0, 0, 0, 0, 0,
                                            None, None, wc.hInstance, None)
        self._ok = bool(self._hwnd) and bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid())))
        self._ready.set()
        if not self._ok:
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        self._hwnd = 0

    def _emit(self, command: str) -> None:
        try:
            self._on_command(command)
        except Exception:  # a UI handler error must never kill the tray thread
            pass
