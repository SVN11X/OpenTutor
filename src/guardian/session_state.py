"""Persist the user's explicit study session, schedule and pending quiz across restarts.

Stdlib only. Privacy: only the fields of SessionState are stored. No window
titles, no URLs, no keystrokes. A pending quiz survives even when the session
itself has ended or expired, so a reboot never loses an unanswered exam.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 1
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionState:
    active: bool = False
    until: datetime | None = None
    paused_until: datetime | None = None
    topic: str = "Google Cloud"
    source: str = "bank-only"
    pending: bool = False
    windows: tuple[tuple[str, str], ...] = ()  # authorized study hours, local HH:MM


INACTIVE = SessionState()


def _aware(value: datetime | None) -> bool:
    return value is None or value.tzinfo is not None


class SessionStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def save(self, state: SessionState) -> None:
        if not _aware(state.until) or not _aware(state.paused_until):
            raise ValueError("Session datetimes must be timezone-aware")
        if not state.active and not state.pending and not state.windows:
            self.clear()
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "active": state.active,
            "until": state.until.isoformat() if state.until else None,
            "paused_until": state.paused_until.isoformat() if state.paused_until else None,
            "topic": state.topic,
            "source": state.source,
            "pending": state.pending,
            "windows": [list(w) for w in state.windows],
        }
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def clear(self) -> None:
        try:
            self.path.unlink()
        except OSError as err:
            log.warning("Could not remove %s: %s", self.path.name, err)

    def load(self, now: datetime) -> SessionState:
        """Never raises. Bad or foreign data gives INACTIVE; an expired session keeps pending/windows."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("schema_version") != SCHEMA_VERSION:
                return INACTIVE
            active, topic, source = data["active"], data["topic"], data["source"]
            pending = data.get("pending", False)
            if (
                not all(isinstance(v, bool) for v in (active, pending))
                or not isinstance(topic, str)
                or not isinstance(source, str)
            ):
                return INACTIVE
            windows = _parse_windows(data.get("windows", []))
            until = _parse(data.get("until"))
            paused = _parse(data.get("paused_until"))
        except FileNotFoundError:
            return INACTIVE
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as err:
            log.warning("Ignoring unreadable session file (%s): %s", type(err).__name__, err)
            return INACTIVE
        if active and (until is None or until <= now):
            active, until, paused = False, None, None  # expired: nothing resumes by itself
        if not active:
            kept = SessionState(False, None, None, topic, source, pending, windows)
            if kept == INACTIVE:
                self.clear()
                return INACTIVE
            self.save(kept)
            return kept
        if paused is not None and paused <= now:
            paused = None
        return SessionState(True, until, paused, topic, source, pending, windows)


def _parse(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("datetime must be a string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("naive datetime")
    return parsed


def parse_schedule(text: str) -> tuple[tuple[str, str], ...]:
    """'09:00-12:00, 14:00-17:00' -> windows. Empty text means no schedule. Raises ValueError."""
    windows = []
    for part in filter(None, (p.strip() for p in text.split(","))):
        start, sep, end = part.partition("-")
        if not sep:
            raise ValueError(f"Horario inválido: {part!r}. Use HH:MM-HH:MM")
        windows.append((start.strip(), end.strip()))
    return _parse_windows([list(w) for w in windows])


def _parse_windows(raw: object) -> tuple[tuple[str, str], ...]:
    from .core import within_study_window

    if not isinstance(raw, list):
        raise TypeError("windows must be a list")
    windows = []
    for item in raw:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("bad window")
        windows.append((item[0], item[1]))
    within_study_window(datetime(2000, 1, 1), windows)  # validates HH:MM, raises ValueError
    return tuple(windows)
