"""Local Ollama assessment generation with conservative validation.

MVP relies on generated answer keys; this is NOT a guarantee of factual truth.
Educators should review a generated bank before using results for high-stakes unlocks.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .core import Question, validate_questions
from .fieldnotes import load_pool
from .i18n import t
from .spaced import Card, key, pick

log = logging.getLogger(__name__)

# Validated, manually authored fallback for one known topic only. No fake
# auto-grading of arbitrary subjects when Ollama is unavailable.
_FALLBACK_PATH = Path(__file__).resolve().parent / "content" / "fallback_gcp.json"


def _load_fallback_gcp(path: Path) -> list[Question]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        questions = [Question.from_dict(item) for item in raw]
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise RuntimeError(f"Fallback question file is missing or invalid: {path} ({err})") from err
    if not questions:
        raise RuntimeError(f"Fallback question file has no questions: {path}")
    return questions


FALLBACK_GCP = _load_fallback_gcp(_FALLBACK_PATH)


SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "minItems": 5,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
                    "answer_index": {"type": "integer", "minimum": 0, "maximum": 3},
                    "explanation": {"type": "string"},
                },
                "required": ["prompt", "options", "answer_index", "explanation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}


def get_questions(
    topic: str,
    recent: set[str],
    model: str = "qwen3.5:4b",
    endpoint: str = "http://127.0.0.1:11434",
    *,
    mode: str = "bank-first",
    bank_path=None,
    cards: Mapping[str, Card] | None = None,
    domains: Sequence[int] = (),
    language: str = "es",
    now: datetime | None = None,
) -> tuple[list[Question], str]:
    """Prefer reviewed local questions; use Ollama only when explicitly requested.

    Modes: 'bank-first', 'bank-only', 'bank-practice' use local Fieldnotes; 'ollama'
    requests generation. The local bank is read-only and not automatically
    downloaded. Remote Ollama endpoints are forbidden by this MVP. Without cards,
    recent prompts are deprioritized; with cards, the scheduler decides spacing.
    """
    if endpoint not in ("http://127.0.0.1:11434", "http://localhost:11434"):
        raise ValueError(t("questions.local_only"))
    if mode not in {"bank-first", "bank-only", "bank-practice", "ollama"}:
        raise ValueError(t("questions.invalid_mode"))
    if cards is None:
        # A far-future due date pushes recent prompts to the very end of the pool,
        # so they are avoided while anything else exists but never exhaust the bank.
        cards = {key(p): Card(box=0, due_at=datetime.max.replace(tzinfo=UTC)) for p in recent}
    moment = now if now is not None else datetime.now().astimezone()

    gcp = topic.strip().casefold() in {
        "google cloud",
        "gcp",
        "google cloud pde",
        "google cloud data engineer",
    }
    if gcp and mode != "ollama":
        practice = mode == "bank-practice"
        pool = load_pool(bank_path, reviewed_only=not practice, domains=domains, language=language)
        selected = pick(pool, cards, moment, 5)
        reviewed_count = len(selected)
        if reviewed_count < 5:
            used = {key(q.prompt) for q in selected}
            remaining = [q for q in FALLBACK_GCP if key(q.prompt) not in used]
            selected.extend(pick(remaining, cards, moment, 5 - reviewed_count))
        if len(selected) == 5:
            if practice and reviewed_count:
                return selected, "fieldnotes-practice-unverified"
            if reviewed_count == 5:
                return selected, "fieldnotes-reviewed"
            return selected, "fieldnotes+fallback-reviewed" if reviewed_count else "fallback-reviewed"
        raise RuntimeError(t("questions.bank_exhausted"))
    if mode in {"bank-only", "bank-practice"}:
        raise RuntimeError(t("questions.no_bank_for_topic"))

    query = {
        "model": model,
        "stream": False,
        "format": SCHEMA,
        "options": {"temperature": 0.2},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres tutor. Devuelve solo JSON que siga el esquema. "
                    "Genera 5 preguntas en español, cada una con 4 opciones diferentes, "
                    "una sola opción correcta y explicación clara. "
                    "No uses respuestas obvias ni hechos dudosos. No inventes fuentes."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Tema: {topic[:160]}. Evita repetir: " + "; ".join(list(sorted(recent))[:8])[:1000]
                ),
            },
        ],
    }
    request = Request(
        endpoint + "/api/chat",
        data=json.dumps(query).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
        generated = json.loads(payload["message"]["content"])
        questions = validate_questions(generated["questions"])
        if any(q.prompt.strip().casefold() in recent for q in questions):
            raise ValueError(t("questions.repeated_questions"))
        return questions, "ollama-unreviewed"
    except (URLError, HTTPError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as err:
        log.warning(
            "Ollama gave no usable questions (%s); falling back to the reviewed bank", type(err).__name__
        )
        if not gcp:
            raise RuntimeError(t("questions.ollama_invalid")) from None
        available = pick(FALLBACK_GCP, cards, moment, 5)
        if len(available) < 5:
            raise RuntimeError(t("questions.reviewed_bank_exhausted")) from None
        return available, "fallback-reviewed"
