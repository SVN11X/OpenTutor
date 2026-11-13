"""Deterministic Guardian domain logic. Only Python stdlib required."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as clock_time
from pathlib import Path
from random import Random, SystemRandom
import json
import sqlite3
from typing import Sequence


MIN_INTERVAL_SECONDS = 10 * 60
MAX_INTERVAL_SECONDS = 25 * 60
QUESTIONS_PER_QUIZ = 5
PASS_COUNT = 4
# Only keys reviewed or manually curated can grant a certified pass.
# AI-generated or imported unreviewed keys are for practice only.
CERTIFIED_QUESTION_SOURCES = frozenset({
    "fieldnotes-reviewed", "fieldnotes+fallback-reviewed", "fallback-reviewed",
})


@dataclass(frozen=True)
class Question:
    prompt: str
    options: tuple[str, str, str, str]
    answer_index: int
    explanation: str

    def __post_init__(self) -> None:
        if not isinstance(self.prompt, str) or not self.prompt.strip() or len(self.options) != 4:
            raise ValueError("Una pregunta requiere enunciado y cuatro opciones")
        if type(self.answer_index) is not int or not 0 <= self.answer_index < 4:
            raise ValueError("Índice de respuesta inválido")
        if any(not isinstance(x, str) or not x.strip() for x in self.options):
            raise ValueError("Las opciones deben estar completas")
        if len({x.strip().casefold() for x in self.options}) != 4:
            raise ValueError("Las opciones deben ser diferentes")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise ValueError("Falta una explicación")

    def to_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "options": list(self.options),
            "answer_index": self.answer_index,
            "explanation": self.explanation,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Question":
        if not isinstance(data, dict):
            raise ValueError("La pregunta debe ser un objeto JSON")
        options = data["options"]
        if not isinstance(options, list) or len(options) != 4:
            raise ValueError("Las opciones deben ser una lista de cuatro textos")
        return cls(
            prompt=data["prompt"],
            options=tuple(options),
            answer_index=data["answer_index"],
            explanation=data["explanation"],
        )


def validate_questions(raw: Sequence[dict], count: int = QUESTIONS_PER_QUIZ) -> list[Question]:
    if not isinstance(raw, list) or len(raw) != count:
        raise ValueError(f"Se requieren exactamente {count} preguntas")
    questions = [Question.from_dict(item) for item in raw]
    if len({q.prompt.strip().casefold() for q in questions}) != count:
        raise ValueError("Hay preguntas duplicadas")
    return questions


def grade(questions: Sequence[Question], answers: Sequence[int]) -> tuple[int, bool]:
    if len(questions) != QUESTIONS_PER_QUIZ or len(answers) != QUESTIONS_PER_QUIZ:
        raise ValueError("El examen requiere cinco preguntas y cinco respuestas")
    if any(type(a) is not int or a not in range(4) for a in answers):
        raise ValueError("Respuesta fuera de rango")
    correct = sum(a == q.answer_index for q, a in zip(questions, answers))
    return correct, correct >= PASS_COUNT


def within_study_window(now: datetime, windows: Sequence[tuple[str, str]]) -> bool:
    """No study by default. Windows are local 24h HH:MM, no midnight crossing."""
    if not windows:
        return False
    minute = now.hour * 60 + now.minute
    for start, end in windows:
        a, b = _parse_minute(start), _parse_minute(end)
        if a == b:
            continue
        if a < b and a <= minute < b:
            return True
        if a > b and (minute >= a or minute < b):
            return True
    return False


def _parse_minute(s: str) -> int:
    try:
        t = clock_time.fromisoformat(s)
        if len(s) != 5 or t.second or t.microsecond:
            raise ValueError
        return t.hour * 60 + t.minute
    except (TypeError, ValueError):
        raise ValueError("Horario inválido, use HH:MM") from None


class SurpriseClock:
    """Accumulates eligible *active* seconds, never elapsed sleep/offline time."""

    def __init__(
        self,
        rng: Random | SystemRandom | None = None,
        interval: tuple[int, int] = (MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS),
    ) -> None:
        low, high = interval
        if low < 1 or high < low:
            raise ValueError("Intervalo inválido")
        self.rng = rng if rng is not None else SystemRandom()
        self.interval = interval
        self.target = self.rng.randint(low, high)
        self.eligible = 0.0
        self.surprise_due = False

    def tick(self, elapsed_seconds: float, *, active: bool, allowed: bool, protected: bool = False) -> bool:
        if elapsed_seconds < 0:
            raise ValueError("Tiempo negativo")
        if self.surprise_due:
            return True
        if active and allowed and not protected:
            # Caller uses bounded monotonic steps; do not count a machine suspended for hours.
            self.eligible += min(elapsed_seconds, 5.0)
        if self.eligible >= self.target:
            self.surprise_due = True
        return self.surprise_due

    def reset_after_quiz(self) -> None:
        self.eligible = 0.0
        self.surprise_due = False
        self.target = self.rng.randint(*self.interval)


class ResultStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(db_path))
        self.con.execute("PRAGMA busy_timeout=3000")
        self.con.execute("""CREATE TABLE IF NOT EXISTS guardian_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            topic TEXT NOT NULL,
            question_prompts_json TEXT NOT NULL,
            answers_json TEXT NOT NULL,
            score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 5),
            passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
            source TEXT NOT NULL
        )""")
        self.con.commit()

    def record(self, *, topic: str, questions: Sequence[Question], answers: Sequence[int], source: str) -> tuple[int, bool]:
        score, passed = grade(questions, answers)
        # Never award an unlock-eligible pass from source keys awaiting review.
        certified_pass = passed and source in CERTIFIED_QUESTION_SOURCES
        with self.con:
            self.con.execute(
                """INSERT INTO guardian_attempts
                (created_at, topic, question_prompts_json, answers_json, score, passed, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (datetime.now().astimezone().isoformat(timespec="seconds"), topic,
                 json.dumps([q.prompt for q in questions], ensure_ascii=False),
                 json.dumps(list(answers)), score, int(certified_pass), source),
            )
        return score, certified_pass

    def recent_prompts(self, limit: int = 20) -> set[str]:
        rows = self.con.execute(
            "SELECT question_prompts_json FROM guardian_attempts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return {p.strip().casefold() for (payload,) in rows for p in json.loads(payload)}

    def stats(self) -> tuple[int, int]:
        total, passed = self.con.execute(
            "SELECT COUNT(*), COALESCE(SUM(passed), 0) FROM guardian_attempts"
        ).fetchone()
        return int(total), int(passed)

    def recent_attempts(self, limit: int = 8) -> list[tuple[str, str, int, bool, str]]:
        """Newest first: (created_at, topic, score, certified_pass, source)."""
        rows = self.con.execute(
            "SELECT created_at, topic, score, passed, source FROM guardian_attempts ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [(c, t, int(s), bool(p), src) for c, t, s, p, src in rows]

    def average_score(self) -> float | None:
        (avg,) = self.con.execute("SELECT AVG(score) FROM guardian_attempts").fetchone()
        return None if avg is None else float(avg)

    def close(self) -> None:
        self.con.close()


def attempt_label(score: int, certified_pass: bool, source: str) -> str:
    """Icon + text, never color alone. Unverified sources are practice, whatever the score."""
    if source not in CERTIFIED_QUESTION_SOURCES:
        return f"◐ Práctica ({score}/5, sin verificar)"
    return f"✔ Aprobado ({score}/5)" if certified_pass else f"✖ Repasar ({score}/5)"
