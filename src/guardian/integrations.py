"""Honest health of the services Guardian can use. Local probes only, no telemetry.

States: ok, degraded, incompatible, disconnected, unavailable.
FocoLocal has no IPC yet (see docs/contracts.md), so it reports ``unavailable``.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass

OLLAMA_URL = "http://127.0.0.1:11434/api/tags"

LABELS = {
    "ok": ("●", "OK"),
    "degraded": ("◐", "degradado"),
    "incompatible": ("✖", "no compatible"),
    "disconnected": ("○", "desconectado"),
    "unavailable": ("◌", "no disponible"),
}


@dataclass(frozen=True)
class Health:
    name: str
    state: str

    def text(self) -> str:
        icon, word = LABELS[self.state]
        return f"{self.name}: {icon} {word}"


def probe_http(name: str, url: str, timeout: float = 1.5) -> Health:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return Health(name, "ok" if 200 <= resp.status < 300 else "degraded")
    except urllib.error.HTTPError as err:
        return Health(name, "incompatible" if err.code in (404, 405) else "degraded")
    except (urllib.error.URLError, OSError, ValueError):
        return Health(name, "disconnected")


def check_all(*, bank_ok: bool) -> list[Health]:
    """Blocking (up to ~3 s): call it from a worker thread, never from the UI thread."""
    return [
        Health("Preguntas locales", "ok" if bank_ok else "degraded"),
        probe_http("Ollama", OLLAMA_URL),
        Health("FocoLocal", "unavailable"),
    ]
