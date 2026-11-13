"""Read-only adapter for the local GCP Data Engineer Fieldnotes question bank.

Never copy/modify source questions, images or answer keys. Only questions
explicitly reviewed and gradable in the source are candidates for scoring.
"""
from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path
from random import SystemRandom

from .core import Question


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
        locations.extend([
            Path(__file__).resolve().parents[3] / BANK_DIR,
            Path.cwd().parent / BANK_DIR,
        ])
    for location in locations:
        candidate = location if location.suffix.lower() == ".json" else location / BANK_FILE
        if candidate.is_file():
            return candidate.resolve()
    return None


@lru_cache(maxsize=4)
def _load_questions(path: str, mtime_ns: int, size: int, reviewed_only: bool) -> tuple[Question, ...]:
    """Cache by file metadata; skip incomplete/unreviewed/image questions."""
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("questions"), list):
        raise ValueError("Formato del banco Fieldnotes inválido")

    result = []
    for item in payload["questions"]:
        if not isinstance(item, dict):
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
            explanation = (
                "Clave original sin verificar; no garantiza validez. "
                + explanation
            )
        try:
            result.append(Question(prompt, tuple(options), letters.index(answer[0]), explanation))
        except ValueError:
            continue
    return tuple(result)


def reviewed_questions(recent: set[str], *, bank_path: Path | str | None = None,
                       limit: int = 5, reviewed_only: bool = True) -> list[Question]:
    """Fast local selection. Does not invoke the network or write to Fieldnotes."""
    path = find_bank_path(bank_path)
    if path is None:
        return []
    info = path.stat()
    questions = _load_questions(str(path), info.st_mtime_ns, info.st_size, reviewed_only)
    used = {s.strip().casefold() for s in recent}
    candidates = [q for q in questions if q.prompt.strip().casefold() not in used]
    return SystemRandom().sample(candidates, min(limit, len(candidates)))
