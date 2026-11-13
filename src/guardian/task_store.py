"""Practical tasks written by the owner and the evidence submitted for them. Local SQLite, stdlib only.

Privacy: a submission stores the file name only (never the path or the content) and the rubric checks.
Archiving hides a task, it never deletes submissions.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MAX_TITLE = 120
MAX_TERMS = 10
MAX_TERM_LENGTH = 40
KINDS = ("pptx", "md", "pdf")

# Final status of a submission. "validated" is evidence only: there is no leisure credit system yet.
FAILED, NEEDS_REVIEW, PENDING_DEFENSE, VALIDATED = "failed", "needs_review", "pending_defense", "validated"

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS guardian_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        expected_slides INTEGER NOT NULL CHECK (expected_slides BETWEEN 1 AND 100),
        required_terms_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1))
    )""",
    """CREATE TABLE IF NOT EXISTS guardian_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL REFERENCES guardian_tasks(id),
        created_at TEXT NOT NULL,
        file_name TEXT NOT NULL,
        rubric_status TEXT NOT NULL,
        checks_json TEXT NOT NULL,
        defense_score INTEGER,
        defense_total INTEGER,
        final_status TEXT NOT NULL
    )""",
)


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    expected_slides: int
    required_terms: tuple[str, ...]
    kind: str = "pptx"


@dataclass(frozen=True)
class Submission:
    id: int
    task_title: str
    created_at: str
    file_name: str
    rubric_status: str
    checks: tuple[tuple[str, bool, str], ...]
    defense_score: int | None
    defense_total: int | None
    final_status: str


def defense_passed(score: int, total: int) -> bool:
    """With three questions one miss is allowed. With fewer, every answer must be right."""
    return score >= total - 1 if total >= 3 else score == total


def final_status(
    rubric_status: str, defense_score: int | None = None, defense_total: int | None = None
) -> str:
    if rubric_status == "failed":
        return FAILED
    if rubric_status != "passed":
        return NEEDS_REVIEW
    if defense_score is None or defense_total is None:
        return PENDING_DEFENSE
    return VALIDATED if defense_passed(defense_score, defense_total) else NEEDS_REVIEW


def clean_terms(raw: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    items = raw.split(",") if isinstance(raw, str) else list(raw)
    terms: list[str] = []
    for item in items:
        term = item.strip()
        if not term:
            continue
        if len(term) > MAX_TERM_LENGTH:
            raise ValueError(f"Cada término admite hasta {MAX_TERM_LENGTH} caracteres")
        if term.casefold() not in {t.casefold() for t in terms}:
            terms.append(term)
    if len(terms) > MAX_TERMS:
        raise ValueError(f"Hasta {MAX_TERMS} términos por tarea")
    return tuple(terms)


class TaskStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self.db_path), timeout=3)
        try:
            for statement in _SCHEMA:
                con.execute(statement)
            columns = {row[1] for row in con.execute("PRAGMA table_info(guardian_tasks)")}
            if "kind" not in columns:  # database created before task kinds existed
                con.execute("ALTER TABLE guardian_tasks ADD COLUMN kind TEXT NOT NULL DEFAULT 'pptx'")
                con.commit()
        except sqlite3.Error:
            con.close()
            raise
        return con

    def add_task(
        self,
        title: str,
        expected_slides: int,
        terms: str | list[str] | tuple[str, ...] = (),
        kind: str = "pptx",
    ) -> int:
        """expected_slides is the number of slides, sections or pages, depending on kind."""
        if kind not in KINDS:
            raise ValueError("Tipo de tarea desconocido")
        title = title.strip()
        if not title or len(title) > MAX_TITLE:
            raise ValueError(f"El título es obligatorio y admite hasta {MAX_TITLE} caracteres")
        if type(expected_slides) is not int or not 1 <= expected_slides <= 100:
            raise ValueError("Las diapositivas deben ser un número entre 1 y 100")
        cleaned = clean_terms(terms)
        with closing(self._connect()) as con, con:
            cur = con.execute(
                "INSERT INTO guardian_tasks (title, expected_slides, required_terms_json, created_at, kind)"
                " VALUES (?, ?, ?, ?, ?)",
                (title, expected_slides, json.dumps(list(cleaned), ensure_ascii=False), _now(), kind),
            )
            return int(cur.lastrowid)

    def list_tasks(self) -> list[Task]:
        with closing(self._connect()) as con:
            rows = con.execute(
                "SELECT id, title, expected_slides, required_terms_json, kind FROM guardian_tasks"
                " WHERE archived = 0 ORDER BY id"
            ).fetchall()
        return [Task(i, t, n, tuple(json.loads(terms)), kind) for i, t, n, terms, kind in rows]

    def archive_task(self, task_id: int) -> None:
        with closing(self._connect()) as con, con:
            con.execute("UPDATE guardian_tasks SET archived = 1 WHERE id = ?", (task_id,))

    def add_submission(self, task_id: int, file_name: str, rubric_status: str, checks) -> int:
        """Record a rubric run. checks is an iterable of objects with name, ok and detail."""
        payload = [[c.name, bool(c.ok), c.detail] for c in checks]
        with closing(self._connect()) as con, con:
            cur = con.execute(
                "INSERT INTO guardian_submissions"
                " (task_id, created_at, file_name, rubric_status, checks_json, final_status)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    task_id,
                    _now(),
                    Path(file_name).name,
                    rubric_status,
                    json.dumps(payload, ensure_ascii=False),
                    final_status(rubric_status),
                ),
            )
            return int(cur.lastrowid)

    def record_defense(self, submission_id: int, score: int, total: int) -> str:
        with closing(self._connect()) as con, con:
            row = con.execute(
                "SELECT rubric_status FROM guardian_submissions WHERE id = ?", (submission_id,)
            ).fetchone()
            if row is None:
                raise ValueError("Entrega desconocida")
            status = final_status(row[0], score, total)
            con.execute(
                "UPDATE guardian_submissions SET defense_score = ?, defense_total = ?, final_status = ?"
                " WHERE id = ?",
                (score, total, status, submission_id),
            )
        return status

    def recent_submissions(self, limit: int = 8) -> list[Submission]:
        with closing(self._connect()) as con:
            rows = con.execute(
                "SELECT s.id, t.title, s.created_at, s.file_name, s.rubric_status, s.checks_json,"
                " s.defense_score, s.defense_total, s.final_status"
                " FROM guardian_submissions s JOIN guardian_tasks t ON t.id = s.task_id"
                " ORDER BY s.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            Submission(
                i, title, when, name, rubric, tuple(tuple(c) for c in json.loads(checks)), ds, dt, final
            )
            for i, title, when, name, rubric, checks, ds, dt, final in rows
        ]


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
