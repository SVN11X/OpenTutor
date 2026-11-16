"""The owner's settings: what Guardian asks, how often, and how insistently. Same SQLite file, stdlib only.

One row per field with a JSON value, so a new field never needs a migration. A missing or invalid value
falls back to its default with a warning, so a damaged file can never stop the agent from starting.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

from .i18n import t

log = logging.getLogger(__name__)

SOURCES = ("practice", "reviewed", "ollama")
LANGUAGES = ("es", "en")
QUESTION_SETS = {"gcp-pde": "Google Cloud Professional Data Engineer"}
DOMAIN_IDS = (1, 2, 3, 4, 5)
INTERVAL_BOUNDS = (2, 240)  # minutes

_TABLE = """CREATE TABLE IF NOT EXISTS guardian_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
)"""


@dataclass(frozen=True)
class Settings:
    question_set: str = "gcp-pde"
    source: str = "practice"
    language: str = "es"  # language of the bank questions, not of the interface
    domains: tuple[int, ...] = ()  # empty means every exam domain
    interval_min: int = 10
    interval_max: int = 25
    bank_path: str = ""  # empty means GUARDIAN_GCP_BANK or the folder next to the repository
    all_day: bool = False
    insistent: bool = True
    model: str = "qwen3.5:4b"
    guide_done: bool = False  # the owner hid the first-steps card


DEFAULTS = Settings()


def validate(settings: Settings) -> Settings:
    """Return the settings with domains sorted, or raise ValueError with a message for the owner."""
    if settings.question_set not in QUESTION_SETS:
        raise ValueError(t("settings_store.unknown_question_set"))
    if settings.source not in SOURCES:
        raise ValueError(t("settings_store.unknown_source"))
    if settings.language not in LANGUAGES:
        raise ValueError(t("settings_store.unknown_language"))
    if any(type(d) is not int or d not in DOMAIN_IDS for d in settings.domains):
        raise ValueError(t("settings_store.invalid_domain"))
    low, high = INTERVAL_BOUNDS
    if type(settings.interval_min) is not int or type(settings.interval_max) is not int:
        raise ValueError(t("settings_store.minutes_not_integers"))
    if not low <= settings.interval_min <= settings.interval_max <= high:
        raise ValueError(t("settings_store.minutes_out_of_range", low=low, high=high))
    if not isinstance(settings.bank_path, str) or not isinstance(settings.model, str):
        raise ValueError(t("settings_store.invalid_text"))
    if not all(isinstance(v, bool) for v in (settings.all_day, settings.insistent, settings.guide_done)):
        raise ValueError(t("settings_store.invalid_value"))
    return replace(settings, domains=tuple(sorted(set(settings.domains))))


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self.path), timeout=3)
        try:
            con.execute(_TABLE)
        except sqlite3.Error:
            con.close()
            raise
        return con

    def load(self) -> Settings:
        """Never raises. Each field that is missing or invalid keeps its default."""
        try:
            with closing(self._connect()) as con:
                rows = dict(con.execute("SELECT key, value_json FROM guardian_settings").fetchall())
        except sqlite3.Error as err:
            log.warning("Settings unreadable, using defaults (%s): %s", type(err).__name__, err)
            return DEFAULTS
        parsed = {}
        for field in fields(Settings):
            if field.name not in rows:
                continue
            try:
                value = json.loads(rows[field.name])
                parsed[field.name] = tuple(value) if field.name == "domains" else value
            except (ValueError, TypeError) as err:
                log.warning("Ignoring saved setting %s: %s", field.name, err)
        try:
            return validate(replace(DEFAULTS, **parsed))
        except (ValueError, TypeError) as err:
            log.warning("Saved settings invalid, keeping the valid fields: %s", err)
        settings = DEFAULTS
        for name, value in parsed.items():
            try:
                settings = validate(replace(settings, **{name: value}))
            except (ValueError, TypeError) as err:
                log.warning("Ignoring saved setting %s: %s", name, err)
        return settings

    def save(self, settings: Settings) -> Settings:
        """Validate and store every field. Raises ValueError before writing anything invalid."""
        settings = validate(settings)
        values = asdict(settings)
        values["domains"] = list(settings.domains)
        with closing(self._connect()) as con, con:
            con.executemany(
                "INSERT INTO guardian_settings (key, value_json) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json",
                [(key, json.dumps(value)) for key, value in values.items()],
            )
        return settings
