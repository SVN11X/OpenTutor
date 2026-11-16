"""Read-only adapter for the local GCP Data Engineer Fieldnotes question bank.

Never copy/modify source questions, images or answer keys. Only questions
explicitly reviewed and gradable in the source are candidates for scoring.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from .core import Question

log = logging.getLogger(__name__)

BANK_ENV = "GUARDIAN_GCP_BANK"
BANK_DIR = "GCP_Data_Engineer_Fieldnotes"
BANK_FILE = Path("content") / "imported.json"


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


@lru_cache(maxsize=4)
def _load_questions(
    path: str, mtime_ns: int, size: int, reviewed_only: bool, domains: tuple[int, ...] = ()
) -> tuple[Question, ...]:
    """Cache by file metadata; skip incomplete/unreviewed/image questions and other domains."""
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("questions"), list):
        raise ValueError("Formato del banco Fieldnotes inválido")

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
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8000:
            continue
        if any(not isinstance(opt, str) or not opt.strip() or len(opt) > 4000 for opt in options):
            continue
        if not isinstance(explanation, str) or not explanation.strip():
            # Do not manufacture a source-supported explanation.
            explanation = "Pregunta revisada en Fieldnotes; consulta allí la fundamentación."
        if not reviewed_only:
            explanation = "Clave original sin verificar; no garantiza validez. " + explanation
        try:
            result.append(Question(prompt, tuple(options), letters.index(answer[0]), explanation))
        except ValueError:
            continue
    return tuple(result)


def load_pool(
    bank_path: Path | str | None = None, *, reviewed_only: bool = True, domains: Sequence[int] = ()
) -> list[Question]:
    """Every usable question of the bank. Read-only, never writes to Fieldnotes."""
    path = find_bank_path(bank_path)
    if path is None:
        return []
    info = path.stat()
    questions = _load_questions(str(path), info.st_mtime_ns, info.st_size, reviewed_only, tuple(domains))
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
