"""Eligible study seconds per local day, so the panel can show today's total after a restart.

Stored in the same SQLite file as the results. Only a date and a number of seconds, nothing about apps.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

_TABLE = """CREATE TABLE IF NOT EXISTS guardian_activity (
    day TEXT PRIMARY KEY,
    seconds REAL NOT NULL CHECK (seconds >= 0)
)"""


class ActivityLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as con, con:
            con.execute(_TABLE)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path), timeout=3)

    def add(self, day: date, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("seconds must not be negative")
        with closing(self._connect()) as con, con:
            con.execute(
                "INSERT INTO guardian_activity (day, seconds) VALUES (?, ?) "
                "ON CONFLICT(day) DO UPDATE SET seconds = seconds + excluded.seconds",
                (day.isoformat(), float(seconds)),
            )

    def seconds_on(self, day: date) -> float:
        with closing(self._connect()) as con:
            row = con.execute(
                "SELECT seconds FROM guardian_activity WHERE day = ?", (day.isoformat(),)
            ).fetchone()
        return 0.0 if row is None else float(row[0])
