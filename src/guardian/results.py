"""Read-only exam result models, independent of any desktop toolkit."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .core import CERTIFIED_QUESTION_SOURCES, Question


@dataclass(frozen=True)
class ReviewedAnswer:
    number: int
    question: str
    selected: str
    expected: str
    explanation: str
    correct: bool


@dataclass(frozen=True)
class ExamReport:
    topic: str
    score: int
    certified_pass: bool
    verified: bool
    items: tuple[ReviewedAnswer, ...]

    @property
    def status(self) -> str:
        if not self.verified:
            return "PRÁCTICA · CLAVES SIN VERIFICAR"
        return "APROBADO" if self.certified_pass else "REQUIERE REPASO"


def build_exam_report(
    *, topic: str, questions: Sequence[Question], answers: Sequence[int],
    score: int, passed: bool, source: str,
) -> ExamReport:
    """Prepare presentation from original records; do not reinterpret keys."""
    if len(questions) != 5 or len(answers) != 5:
        raise ValueError("El informe requiere cinco preguntas y cinco respuestas")
    if any(type(a) is not int or a not in range(4) for a in answers):
        raise ValueError("Respuesta fuera de rango")
    computed = sum(a == q.answer_index for q, a in zip(questions, answers))
    if score != computed:
        raise ValueError("La puntuación no coincide con las respuestas")
    verified = source in CERTIFIED_QUESTION_SOURCES
    # Only certified records are allowed to show a verified pass.
    certified = bool(passed and verified)
    items = tuple(
        ReviewedAnswer(
            number=i, question=q.prompt, selected=q.options[answer],
            expected=q.options[q.answer_index], explanation=q.explanation,
            correct=answer == q.answer_index,
        )
        for i, (q, answer) in enumerate(zip(questions, answers), 1)
    )
    return ExamReport(topic=topic, score=score,
                      certified_pass=certified, verified=verified, items=items)


def report_as_text(report: ExamReport) -> str:
    lines = [
        "OpenTutor Guardian · Resultado del examen",
        f"Tema: {report.topic}",
        f"Resultado: {report.score}/5 ({report.score * 20}%)",
        f"Estado: {report.status}",
    ]
    if not report.verified:
        lines.append("Claves originales sin verificar. No habilita desbloqueos.")
    for item in report.items:
        lines.extend([
            "", f"Pregunta {item.number} · {'Correcta' if item.correct else 'A revisar'}",
            item.question, f"Tu respuesta: {item.selected}",
            f"Respuesta según clave: {item.expected}",
            f"Explicación original: {item.explanation}",
        ])
    return "\n".join(lines)
