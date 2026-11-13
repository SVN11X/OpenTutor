"""Persist the user's explicit study session, schedule and pending quiz across restarts.

Stored in the same SQLite file as the results, in one row. Stdlib only. Privacy: only the fields of
SessionState are stored, never window titles, URLs or keystrokes. A pending quiz survives even when the
session has ended or expired, so a reboot never loses an unanswered exam. A session.json written by an
earlier version is imported once and renamed to session.json.migrated.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 1
log = logging.getLogger(__name__)

_TABLE = """CREATE TABLE IF NOT EXISTS guardian_session (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    schema_version INTEGER NOT NULL,
    active INTEGER NOT NULL CHECK (active IN (0, 1)),
    until TEXT,
    paused_until TEXT,
    topic TEXT NOT NULL,
    source TEXT NOT NULL,
    pending INTEGER NOT NULL CHECK (pending IN (0, 1)),
    windows_json TEXT NOT NULL
)"""
_COLUMNS = "schema_version, active, until, paused_until, topic, source, pending, windows_json"
_UPSERT = f"INSERT OR REPLACE INTO guardian_session (id, {_COLUMNS}) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)"


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
    def __init__(self, path: Path, legacy_json: Path | None = None) -> None:
        self.path = Path(path)
        self.legacy_json = Path(legacy_json) if legacy_json else None

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self.path), timeout=3)
        try:
            con.execute(_TABLE)
        except sqlite3.Error:
            con.close()  # do not leak a handle on a corrupt file
            raise
        return con

    def has_saved_state(self) -> bool:
        try:
            with closing(self._connect()) as con:
                return con.execute("SELECT 1 FROM guardian_session WHERE id = 1").fetchone() is not None
        except sqlite3.Error:
            return False

    def save(self, state: SessionState) -> None:
        if not _aware(state.until) or not _aware(state.paused_until):
            raise ValueError("Session datetimes must be timezone-aware")
        if not state.active and not state.pending and not state.windows:
            self.clear()
            return
        row = (
            SCHEMA_VERSION,
            int(state.active),
            state.until.isoformat() if state.until else None,
            state.paused_until.isoformat() if state.paused_until else None,
            state.topic,
            state.source,
            int(state.pending),
            json.dumps([list(w) for w in state.windows]),
        )
        with closing(self._connect()) as con, con:
            con.execute(_UPSERT, row)

    def clear(self) -> None:
        try:
            with closing(self._connect()) as con, con:
                con.execute("DELETE FROM guardian_session")
        except sqlite3.Error as err:
            log.warning("Could not clear the saved session: %s", err)

    def load(self, now: datetime) -> SessionState:
        """Never raises. Bad or foreign data gives INACTIVE; an expired session keeps pending and windows."""
        self._import_legacy()
        try:
            with closing(self._connect()) as con:
                row = con.execute(f"SELECT {_COLUMNS} FROM guardian_session WHERE id = 1").fetchone()
        except sqlite3.Error as err:
            log.warning("Ignoring unreadable session store (%s): %s", type(err).__name__, err)
            return INACTIVE
        if row is None:
            return INACTIVE
        try:
            version, active, until_s, paused_s, topic, source, pending, windows_json = row
            if version != SCHEMA_VERSION:
                return INACTIVE
            state = _state_from_fields(
                active, until_s, paused_s, topic, source, pending, json.loads(windows_json)
            )
        except (ValueError, TypeError) as err:
            log.warning("Ignoring invalid saved session (%s): %s", type(err).__name__, err)
            return INACTIVE
        return self._apply_expiry(state, now)

    def _apply_expiry(self, state: SessionState, now: datetime) -> SessionState:
        active, until, paused = state.active, state.until, state.paused_until
        if active and (until is None or until <= now):
            active, until, paused = False, None, None  # expired: nothing resumes by itself
        if not active:
            kept = SessionState(False, None, None, state.topic, state.source, state.pending, state.windows)
            if kept == INACTIVE:
                self.clear()
                return INACTIVE
            self.save(kept)
            return kept
        if paused is not None and paused <= now:
            paused = None
        return SessionState(True, until, paused, state.topic, state.source, state.pending, state.windows)

    def _import_legacy(self) -> None:
        """One-time import of session.json from versions before SQLite. Never overwrites a saved row."""
        if self.legacy_json is None or not self.legacy_json.exists():
            return
        try:
            if not self.has_saved_state():
                data = json.loads(self.legacy_json.read_text(encoding="utf-8"))
                if data.get("schema_version") != SCHEMA_VERSION:
                    raise ValueError("unsupported legacy schema")
                state = _state_from_fields(
                    data["active"],
                    data.get("until"),
                    data.get("paused_until"),
                    data["topic"],
                    data["source"],
                    data.get("pending", False),
                    data.get("windows", []),
                )
                if state != INACTIVE:
                    self.save(state)
            os.replace(self.legacy_json, self.legacy_json.with_name(self.legacy_json.name + ".migrated"))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as err:
            log.warning("Legacy session.json not imported (%s): %s", type(err).__name__, err)
            try:
                os.replace(self.legacy_json, self.legacy_json.with_name(self.legacy_json.name + ".corrupt"))
            except OSError:
                pass


def _state_from_fields(active, until_s, paused_s, topic, source, pending, windows_raw) -> SessionState:
    if active not in (0, 1, True, False) or pending not in (0, 1, True, False):
        raise TypeError("flags must be boolean")
    if not isinstance(topic, str) or not isinstance(source, str):
        raise TypeError("topic and source must be text")
    return SessionState(
        bool(active),
        _parse(until_s),
        _parse(paused_s),
        topic,
        source,
        bool(pending),
        _parse_windows(windows_raw),
    )


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
