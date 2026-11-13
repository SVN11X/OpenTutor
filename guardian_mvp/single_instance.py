"""Single running instance per Windows user session. Stdlib only."""
from __future__ import annotations

import os
import sys
import tempfile


class SingleInstance:
    def __init__(self, name: str = "OpenTutorGuardian") -> None:
        self.name = name
        self._handle = None
        self._lock_path = os.path.join(tempfile.gettempdir(), f"{name}.lock")
        self._held = False

    def acquire(self) -> bool:
        if self._held:
            return True
        self._held = self._acquire_win() if sys.platform == "win32" else self._acquire_file()
        return self._held

    def release(self) -> None:
        if not self._held:
            return
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None
        else:
            try:
                os.remove(self._lock_path)
            except OSError:
                pass
        self._held = False

    def __enter__(self) -> "SingleInstance":
        self.acquire()
        return self

    def __exit__(self, *_exc) -> None:
        self.release()

    def _acquire_win(self) -> bool:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.CreateMutexW(None, False, "Local\\" + self.name)
        if not handle:
            return False
        if ctypes.get_last_error() == 183 or kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        return True

    def _acquire_file(self) -> bool:
        try:
            os.close(os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return True
        except OSError:
            return False
