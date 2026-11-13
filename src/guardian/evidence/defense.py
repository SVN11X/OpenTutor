"""Deterministic defense about the user's own file. No model, no network.

A defense shows the owner knows what is inside the file they handed in: how many slides, sections
or pages it has, the title of one of them and one term that really appears. It is weak proof, so it
only adds to the rubric and never decides alone. PDF files have no readable titles, so their
defense is the page count only.
"""

from __future__ import annotations

from random import Random, SystemRandom

from ..core import Question
from .check import KIND_INFO
from .pptx_check import Result

_TITLE_DECOYS = ("Introducción", "Resumen", "Conclusiones", "Agenda", "Gracias", "Preguntas")
_TERM_DECOYS = (
    "Kubernetes",
    "Terraform",
    "Firestore",
    "Spanner",
    "Dataproc",
    "Composer",
    "Looker",
    "Bigtable",
    "Datastream",
    "Dataplex",
    "Vertex",
    "Memorystore",
)


def _options(correct: str, wrong: list[str], rng: Random | SystemRandom) -> tuple[tuple[str, ...], int]:
    """Return four distinct options (case-insensitive) with the correct one at a random position."""
    chosen: list[str] = []
    seen = {correct.casefold()}
    for item in wrong:
        if item.casefold() not in seen:
            seen.add(item.casefold())
            chosen.append(item)
        if len(chosen) == 3:
            break
    if len(chosen) < 3:
        raise ValueError("No hay suficientes opciones distintas")
    options = [correct, *chosen]
    rng.shuffle(options)
    return tuple(options), options.index(correct)


def _count_question(count: int, kind: str, rng) -> Question:
    info = KIND_INFO[kind]
    nearby = [n for n in (count - 1, count + 1, count + 2, count + 3, count - 2) if n > 0]
    options, index = _options(str(count), [str(n) for n in nearby], rng)
    return Question(
        f"¿Cuántas {info['plural']} tiene {info['owner_thing']}?",
        options,
        index,
        f"El archivo entregado tiene {count} {info['plural']}.",
    )


def _title_question(titles: tuple[str, ...], k: int, kind: str, rng) -> Question:
    info = KIND_INFO[kind]
    others = [t for i, t in enumerate(titles) if i != k and t]
    rng.shuffle(others)
    decoys = list(_TITLE_DECOYS)
    rng.shuffle(decoys)
    options, index = _options(titles[k], [*others, *decoys], rng)
    return Question(
        f"¿Cuál es el título de la {info['singular']} {k + 1}?",
        options,
        index,
        f"La {info['singular']} {k + 1} se titula «{titles[k]}».",
    )


def _term_question(correct: str, full_text: str, rng) -> Question:
    absent = [d for d in _TERM_DECOYS if d.casefold() not in full_text]
    rng.shuffle(absent)
    options, index = _options(correct, absent, rng)
    return Question(
        "¿Cuál de estos términos aparece en tu archivo?",
        options,
        index,
        f"«{correct}» aparece en el texto de tu archivo. Los otros no.",
    )


def build_defense(
    result: Result, required_terms: tuple[str, ...] = (), rng: Random | SystemRandom | None = None
) -> list[Question]:
    """Up to three questions. Returns [] when there is nothing reliable to ask about."""
    rng = rng if rng is not None else SystemRandom()
    kind = result.kind if result.kind in KIND_INFO else "pptx"
    if kind == "pdf":
        return [_count_question(result.unit_count, "pdf", rng)] if result.unit_count else []
    titles = result.titles
    if not titles or not all(titles):
        return []
    count = result.unit_count or len(titles)
    questions = [
        _count_question(count, kind, rng),
        _title_question(titles, rng.randrange(len(titles)), kind, rng),
    ]
    present = [t for t in required_terms if t.casefold() in result.full_text]
    pool = present or [w for w in result.vocabulary if len(w) >= 6]
    if pool:
        try:
            questions.append(_term_question(rng.choice(pool), result.full_text, rng))
        except ValueError:
            pass  # the file mentions almost every decoy: two questions are enough
    return questions
