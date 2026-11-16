"""Read-only exam result models, independent of any desktop toolkit."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .core import CERTIFIED_QUESTION_SOURCES, Question
from .i18n import t


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
            return t("result.status_practice")
        return t("result.status_pass") if self.certified_pass else t("result.status_review")


def build_exam_report(
    *,
    topic: str,
    questions: Sequence[Question],
    answers: Sequence[int],
    score: int,
    passed: bool,
    source: str,
) -> ExamReport:
    """Prepare presentation from original records; do not reinterpret keys."""
    if len(questions) != 5 or len(answers) != 5:
        raise ValueError(t("result.error_count"))
    if any(type(a) is not int or a not in range(4) for a in answers):
        raise ValueError(t("result.error_range"))
    computed = sum(a == q.answer_index for q, a in zip(questions, answers, strict=True))
    if score != computed:
        raise ValueError(t("result.error_score"))
    verified = source in CERTIFIED_QUESTION_SOURCES
    # Only certified records are allowed to show a verified pass.
    certified = bool(passed and verified)
    items = tuple(
        ReviewedAnswer(
            number=i,
            question=q.prompt,
            selected=q.options[answer],
            expected=q.options[q.answer_index],
            explanation=q.explanation,
            correct=answer == q.answer_index,
        )
        for i, (q, answer) in enumerate(zip(questions, answers, strict=True), 1)
    )
    return ExamReport(topic=topic, score=score, certified_pass=certified, verified=verified, items=items)


def report_as_text(report: ExamReport) -> str:
    lines = [
        t("result.text_title"),
        t("result.text_topic", topic=report.topic),
        t("result.text_score", score=report.score, percent=report.score * 20),
        t("result.text_status", status=report.status),
    ]
    if not report.verified:
        lines.append(t("result.text_unverified"))
    for item in report.items:
        lines.extend(
            [
                "",
                t(
                    "result.text_item_header",
                    number=item.number,
                    status=t("result.correct") if item.correct else t("result.to_review"),
                ),
                item.question,
                t("result.text_your_answer", answer=item.selected),
                t("result.text_expected", answer=item.expected),
                t("result.text_explanation", explanation=item.explanation),
            ]
        )
    return "\n".join(lines)
