"""Read-only adapter for the local GCP Data Engineer Fieldnotes question bank.

Never copy/modify source questions, images or answer keys. Only questions
explicitly reviewed and gradable in the source are candidates for scoring.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Sequence
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

from .core import Question

log = logging.getLogger(__name__)

BANK_ENV = "GUARDIAN_GCP_BANK"
BANK_DIR = "GCP_Data_Engineer_Fieldnotes"
BANK_FILE = Path("content") / "imported.json"
TRANSLATION_GLOB = "imported-d*.json"
PROMPT_LIMIT = 8000
OPTION_LIMIT = 4000


def find_bank_path(explicit: Path | str | None = None) -> Path | None:
    """Prefer explicit location, then local override, then sibling repository."""
    locations = []
    if explicit is not None:
        locations.append(Path(explicit))
    elif os.environ.get(BANK_ENV):
        locations.append(Path(os.environ[BANK_ENV]))
    else:
        # Typical Windows layout: C:/my_drive/Portafolio/{OpenTutor,GCP_...}
        locations.extend(
            [
                Path(__file__).resolve().parents[3] / BANK_DIR,
                Path.cwd().parent / BANK_DIR,
            ]
        )
    for location in locations:
        if location.suffix.lower() == ".json":
            candidates = [location]
        else:  # the repository folder, or its content folder chosen by mistake
            candidates = [location / BANK_FILE, location / BANK_FILE.name]
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
    return None


class _PlainTextParser(HTMLParser):
    """Collects character data only. Block tags become spaces so words never glue together."""

    BLOCK_TAGS = frozenset({"p", "br", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.BLOCK_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BLOCK_TAGS:
            self.parts.append(" ")


def _plain_text(html: str) -> str:
    """HTML to plain text: tags dropped, entities unescaped, whitespace collapsed."""
    parser = _PlainTextParser()
    parser.feed(html)
    parser.close()
    return " ".join("".join(parser.parts).split())


def _load_translations(bank_file: Path) -> dict[str, dict]:
    """Merge every es/imported-d*.json next to the bank into {question id: {field path: entry}}."""
    folder = bank_file.parent / "es"
    files = sorted(folder.glob(TRANSLATION_GLOB))
    if not files:
        log.warning("No Fieldnotes translation files in %s; questions stay in English", folder)
        return {}
    merged: dict[str, dict] = {}
    for file in files:
        try:
            with open(file, encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                raise ValueError("translation is not a JSON object")
        except (OSError, ValueError) as err:
            log.warning("Skipping Fieldnotes translation file %s (%s)", file, type(err).__name__)
            continue
        for question_id, entries in payload.items():
            if isinstance(entries, dict):
                merged.setdefault(question_id, {}).update(entries)
    return merged


def _translated(entries: dict, path: str, original: object) -> str | None:
    """Plain-text Spanish text for a field, or None when it is missing, stale or not text."""
    if not isinstance(original, str) or not isinstance(entries.get(path), dict):
        return None
    entry = entries[path]
    fingerprint = hashlib.sha256(original.encode("utf-8")).hexdigest()[:12]
    if entry.get("src") != fingerprint or not isinstance(entry.get("es"), str):
        return None
    return _plain_text(entry["es"])


def _spanish_prompt_options(entries: dict, item: dict) -> tuple[str, tuple[str, str, str, str]] | None:
    """Spanish prompt and options, or None unless every piece is current and within the limits."""
    # The bank fingerprints the html fields, which differ from text in about two thirds of the items.
    prompt = _translated(entries, "html", item.get("html"))
    if prompt is None or not prompt.strip() or len(prompt) > PROMPT_LIMIT:
        return None
    options = []
    for i, choice in enumerate(item["choices"]):
        original = choice.get("html") if isinstance(choice, dict) else None
        text = _translated(entries, f"choices.{i}.html", original)
        if text is None or not text.strip() or len(text) > OPTION_LIMIT:
            return None
        options.append(text)
    # A translation that Question would reject is as unusable as a stale one.
    return None if len(set(options)) != 4 else (prompt, tuple(options))


def _spanish_explanation(entries: dict, item: dict) -> str | None:
    """Current Spanish explanation, or None to keep today's English fallback chain."""
    for path in ("sourceExplanation", "explanation"):
        text = _translated(entries, path, item.get(path))
        if text is not None and text.strip():
            return text
    return None


@lru_cache(maxsize=4)
def _load_questions(
    path: str,
    mtime_ns: int,
    size: int,
    reviewed_only: bool,
    domains: tuple[int, ...] = (),
    language: str = "en",
) -> tuple[Question, ...]:
    """Cache by file metadata; skip incomplete/unreviewed/image questions and other domains."""
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("questions"), list):
        raise ValueError("Formato del banco Fieldnotes inválido")

    translations = _load_translations(Path(path)) if language == "es" else {}
    result = []
    for item in payload["questions"]:
        if not isinstance(item, dict):
            continue
        if domains:
            domain = item.get("domain")
            if not isinstance(domain, int) or domain not in domains:
                continue
        if reviewed_only and (item.get("status") != "reviewed" or item.get("gradable") is not True):
            continue
        if item.get("hasImages") or item.get("missingDiagram") or item.get("required") != 1:
            continue  # The current MVP has no images or multi-select controls.
        choices = item.get("choices")
        answer = item.get("answer")
        if not isinstance(choices, list) or len(choices) != 4:
            continue
        if not isinstance(answer, list) or len(answer) != 1:
            continue
        letters = [choice.get("letter") if isinstance(choice, dict) else None for choice in choices]
        if letters != ["A", "B", "C", "D"] or answer[0] not in letters:
            continue
        prompt = item.get("text")
        options = [choice.get("text") for choice in choices]
        explanation = item.get("explanation") or item.get("sourceExplanation")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > PROMPT_LIMIT:
            continue
        if any(not isinstance(opt, str) or not opt.strip() or len(opt) > OPTION_LIMIT for opt in options):
            continue
        if not isinstance(explanation, str) or not explanation.strip():
            # Do not manufacture a source-supported explanation.
            explanation = "Pregunta revisada en Fieldnotes; consulta allí la fundamentación."
        raw_id = item.get("id")
        uid = raw_id if isinstance(raw_id, str) and raw_id else ""
        entries = translations.get(uid, {}) if uid else {}
        spanish = _spanish_prompt_options(entries, item) if entries else None
        if spanish is not None:
            # Only a fully current translation switches the question; a stale one keeps it in English.
            prompt, options = spanish
            spanish_explanation = _spanish_explanation(entries, item)
            if spanish_explanation is not None:
                explanation = spanish_explanation
        if not reviewed_only:
            explanation = "Clave original sin verificar; no garantiza validez. " + explanation
        try:
            result.append(Question(prompt, tuple(options), letters.index(answer[0]), explanation, uid=uid))
        except ValueError:
            continue
    return tuple(result)


def load_pool(
    bank_path: Path | str | None = None,
    *,
    reviewed_only: bool = True,
    domains: Sequence[int] = (),
    language: str = "es",
) -> list[Question]:
    """Every usable question of the bank. Read-only, never writes to Fieldnotes."""
    path = find_bank_path(bank_path)
    if path is None:
        return []
    info = path.stat()
    questions = _load_questions(
        str(path), info.st_mtime_ns, info.st_size, reviewed_only, tuple(domains), language
    )
    return list(questions)


def _is_domain_entry(entry: object) -> bool:
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("id"), int)
        and isinstance(entry.get("name"), str)
        and isinstance(entry.get("weight"), int)
    )


def domain_names(bank_path: Path | str | None = None) -> list[tuple[int, str, int]]:
    """Domain catalog (id, name, weight) sorted by id; [] without a bank or catalog file."""
    path = find_bank_path(bank_path)
    if path is None:
        return []
    domains_file = path.parent / "domains.json"
    if not domains_file.is_file():
        return []
    try:
        with open(domains_file, encoding="utf-8") as handle:
            payload = json.load(handle)
        result = [
            (entry["id"], entry["name"], entry["weight"]) for entry in payload if _is_domain_entry(entry)
        ]
    except (OSError, TypeError, ValueError) as err:
        log.warning("Invalid domains file %s (%s)", domains_file, type(err).__name__)
        return []
    if len(result) != len(payload):
        log.warning("Domains file %s has entries with an invalid id, name or weight", domains_file)
        return []
    return sorted(result)
