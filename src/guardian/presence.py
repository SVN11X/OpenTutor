"""What Windows reports about the user's presence, so the clock counts only real study time.

Only state flags are read: seconds since the last input, session lock, suspension and whether a
full-screen app or presentation mode is on. Never the screen, window titles, URLs or keys.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

log = logging.getLogger(__name__)

IDLE_LIMIT_SEC = 180

# SHQueryUserNotificationState results. Store apps in full screen report QUNS_APP.
_QUNS_NOT_PRESENT, _QUNS_BUSY, _QUNS_D3D_FULL_SCREEN, _QUNS_PRESENTATION = 1, 2, 3, 4
_QUNS_APP = 7
FULLSCREEN, PRESENTATION = "fullscreen", "presentation"


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def is_user_active(idle_limit_sec: int = IDLE_LIMIT_SEC) -> bool:
    """True when the last keyboard or mouse input is recent. Off Windows it is always True (demo only)."""
    if sys.platform != "win32":
        return True
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return False
    now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
    idle_ms = (now - info.dwTime) & 0xFFFFFFFF
    return idle_ms < idle_limit_sec * 1000


def busy_from_state(state: int) -> str | None:
    """Map a SHQueryUserNotificationState value to the reason a quiz must wait, or None."""
    if state in (_QUNS_BUSY, _QUNS_D3D_FULL_SCREEN, _QUNS_APP):
        return FULLSCREEN
    if state == _QUNS_PRESENTATION:
        return PRESENTATION
    return None


def busy_reason() -> str | None:
    """Why an insistent quiz should wait now: a full-screen app or presentation mode, else None.

    Fails open: if Windows cannot answer, the quiz is shown, because hiding it forever would be worse.
    """
    if sys.platform != "win32":
        return None
    state = ctypes.c_int(0)
    try:
        result = ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state))
    except (OSError, AttributeError) as err:
        log.debug("SHQueryUserNotificationState unavailable: %s", err)
        return None
    if result != 0:
        log.debug("SHQueryUserNotificationState failed with HRESULT %#x", result & 0xFFFFFFFF)
        return None
    return busy_from_state(state.value)


class Presence:
    """Suspension and lock flags, fed by Windows messages that the tray window receives."""

    def __init__(self) -> None:
        self.suspended = False
        self.locked = False

    def on_event(self, event: str) -> bool:
        """Apply 'suspend', 'resume', 'lock' or 'unlock'. Returns False for an unknown event."""
        if event == "suspend":
            self.suspended = True
        elif event == "resume":
            self.suspended = False
        elif event == "lock":
            self.locked = True
        elif event == "unlock":
            self.locked = False
        else:
            return False
        return True

    def paused_reason(self, active: bool) -> str | None:
        """Why the clock is not counting, in the user's words, or None when it counts."""
        if self.suspended:
            return "equipo en suspensión"
        if self.locked:
            return "pantalla bloqueada"
        if not active:
            return "sin actividad"
        return None
