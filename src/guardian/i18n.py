"""User-facing text lives in locales/es.json, apart from the code, as AGENTS.md asks.

Keys are dotted by module, for example "tray.open". A missing key raises KeyError instead of showing a
key or an empty label, and tests/test_i18n.py checks that every key used in the code exists and that no
text in the file is left unused.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

LOCALE_DIR = Path(__file__).resolve().parent / "locales"
LANGUAGE = "es"


@cache
def messages(language: str = LANGUAGE) -> dict[str, str]:
    with open(LOCALE_DIR / f"{language}.json", encoding="utf-8") as handle:
        return json.load(handle)


def t(key: str, **values: object) -> str:
    """The text for key, with its {name} placeholders filled from values."""
    text = messages()[key]
    return text.format(**values) if values else text
