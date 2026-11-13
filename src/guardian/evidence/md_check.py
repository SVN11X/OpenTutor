"""Deterministic Markdown rubric (rubric md-1). The file is read as text and never rendered or run.

failed: a hard rule broke. needs_review: hard rules hold but required terms are missing.
passed: every rule holds. Like the other validators, passed is evidence and not leisure credit.
"""

from __future__ import annotations

import re
from pathlib import Path

from .pptx_check import Check, Result

RUBRIC_VERSION = "md-1"
MAX_BYTES = 2 * 1024 * 1024
MIN_WORDS_PER_SECTION = 10
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
# Phrases ignore case, but TODO, TBD and FIXME count only in capitals: "todo" is a normal Spanish word.
_PLACEHOLDER = re.compile(r"(?i:lorem\s+ipsum|click to edit)|\b(?:TODO|TBD|FIXME)\b")
_WORD = re.compile(r"\w+")


def _fail(name: str, detail: str) -> Result:
    return Result("failed", (Check(name, False, detail),), kind="md")


def _sections(text: str) -> list[tuple[str, str]]:
    """Headings with the text under them. Lines inside code fences are never headings."""
    sections: list[tuple[str, list[str]]] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        match = None if in_fence else _HEADING.match(line)
        if match:
            sections.append((match.group(2).strip(), []))
        elif sections:
            sections[-1][1].append(line)
    return [(title, "\n".join(body)) for title, body in sections]


def check_markdown(
    path: Path | str, *, expected_sections: int | None = None, required_terms: tuple[str, ...] = ()
) -> Result:
    path = Path(path)
    if path.suffix.lower() not in (".md", ".markdown"):
        return _fail("extension", "La extensión debe ser .md o .markdown")
    try:
        if path.stat().st_size > MAX_BYTES:
            return _fail("readable", "El archivo supera 2 MB")
        raw = path.read_bytes()
        if b"\x00" in raw:
            return _fail("readable", "No es un archivo de texto")
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _fail("readable", "El archivo debe estar en UTF-8")
    except OSError as err:
        return _fail("readable", f"No se pudo leer: {err.strerror or err}")

    sections = _sections(text)
    titles = tuple(title for title, _ in sections)
    words = _WORD.findall(text)
    blob = text.casefold()
    checks: list[Check] = [Check("readable", True)]
    count_ok = expected_sections is None or len(sections) >= expected_sections
    checks.append(
        Check(
            "section_count",
            count_ok,
            f"{len(sections)} secciones"
            + ("" if count_ok else f", se esperaban al menos {expected_sections}"),
        )
    )
    empty = [t for t, body in sections if not _WORD.search(body)]
    checks.append(Check("no_empty_sections", not empty, f"vacías: {empty}" if empty else ""))
    placeholders = sorted({m.group(0).upper() for m in _PLACEHOLDER.finditer(text)})
    checks.append(
        Check("no_placeholder_text", not placeholders, f"se encontró: {placeholders}" if placeholders else "")
    )
    folded = [t.casefold() for t in titles]
    checks.append(Check("no_duplicate_headings", len(set(folded)) == len(folded)))
    needed = MIN_WORDS_PER_SECTION * max(1, expected_sections or 1)
    checks.append(Check("min_words", len(words) >= needed, f"{len(words)} palabras, mínimo {needed}"))
    missing = [t for t in required_terms if not re.search(rf"\b{re.escape(t.casefold())}\b", blob)]
    checks.append(Check("required_terms", not missing, f"faltan: {missing}" if missing else ""))

    hard = [c for c in checks if c.name != "required_terms"]
    if not all(c.ok for c in hard):
        status = "failed"
    elif missing:
        status = "needs_review"
    else:
        status = "passed"
    vocab = tuple(sorted({w.casefold() for w in words if len(w) >= 4})[:500])
    return Result(
        status,
        tuple(checks),
        rubric_version=RUBRIC_VERSION,
        titles=titles,
        vocabulary=vocab,
        full_text=blob[:200_000],
        kind="md",
        unit_count=len(sections),
    )
