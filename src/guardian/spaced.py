"""Leitner-box scheduling for quiz questions, so wrong answers return sooner and the bank never runs out."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from random import Random, SystemRandom
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core import Question

BOX_INTERVALS = (
    timedelta(minutes=10),
    timedelta(hours=1),
    timedelta(hours=4),
    timedelta(days=1),
    timedelta(days=3),
    timedelta(days=7),
)


@dataclass(frozen=True)
class Card:
    box: int
    due_at: datetime  # timezone-aware


def key(prompt: str) -> str:
    return prompt.strip().casefold()


def question_key(question: Question) -> str:
    """A stable id keeps the history when the language changes."""
    return question.uid or key(question.prompt)


def next_card(card: Card | None, correct: bool, now: datetime) -> Card:
    """A wrong answer restarts at box 0, a right one climbs until the last box."""
    if not correct:
        box = 0
    elif card is None:
        box = 1
    else:
        box = min(card.box + 1, len(BOX_INTERVALS) - 1)
    return Card(box=box, due_at=now + BOX_INTERVALS[box])


def pick(
    pool: Sequence[Question],
    cards: Mapping[str, Card],
    now: datetime,
    k: int = 5,
    rng: Random | None = None,
) -> list[Question]:
    """Return up to k questions: due first (lowest box), then never-seen, then later ones."""
    unique: dict[str, Question] = {}
    for question in pool:
        unique.setdefault(question_key(question), question)
    due: list[tuple[int, datetime, Question]] = []
    new: list[Question] = []
    later: list[tuple[datetime, Question]] = []
    for prompt_key, question in unique.items():
        card = cards.get(prompt_key)
        if card is None:
            new.append(question)
        elif card.due_at <= now:
            due.append((card.box, card.due_at, question))
        else:
            later.append((card.due_at, question))
    due.sort(key=lambda item: (item[0], item[1]))
    later.sort(key=lambda item: item[0])
    shuffled = rng if rng is not None else SystemRandom()
    shuffled.shuffle(new)
    ordered = [q for _, _, q in due] + new + [q for _, q in later]
    return ordered[:k]
