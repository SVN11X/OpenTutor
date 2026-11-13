import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from guardian.core import Question, ResultStore
from guardian.results import build_exam_report, report_as_text


def sample_questions():
    return [
        Question(f"Pregunta {i}", ("A", "B", "C", "D"), i % 4, f"Explanation original for question {i}")
        for i in range(5)
    ]


class ResultScreenTests(unittest.TestCase):
    def test_report_preserves_selected_expected_and_explanations(self):
        q = sample_questions()
        report = build_exam_report(
            topic="GCP",
            questions=q,
            answers=[0, 0, 2, 3, 0],
            score=4,
            passed=True,
            source="fieldnotes-reviewed",
        )
        self.assertEqual(report.status, "APROBADO")
        self.assertTrue(report.items[1].correct is False)
        self.assertEqual(report.items[1].selected, "A")
        self.assertEqual(report.items[1].expected, "B")
        self.assertIn("Explanation original", report_as_text(report))

    def test_practice_warns_and_never_marks_certified(self):
        q = sample_questions()
        report = build_exam_report(
            topic="GCP",
            questions=q,
            answers=[0, 1, 2, 3, 0],
            score=5,
            passed=False,
            source="fieldnotes-practice-unverified",
        )
        self.assertFalse(report.verified)
        self.assertFalse(report.certified_pass)
        self.assertIn("sin verificar", report_as_text(report))
        self.assertIn("CLAVES SIN VERIFICAR", report.status)

    def test_ollama_not_certified_even_perfect_result(self):
        with TemporaryDirectory() as temp:
            store = ResultStore(Path(temp) / "report.db")
            q = sample_questions()
            score, passed = store.record(
                topic="GCP", questions=q, answers=[0, 1, 2, 3, 0], source="ollama-unreviewed"
            )
            self.assertEqual(score, 5)
            self.assertFalse(passed)
            self.assertEqual(store.stats(), (1, 0))
            store.close()

    def test_wrong_score_rejected(self):
        with self.assertRaises(ValueError):
            build_exam_report(
                topic="GCP",
                questions=sample_questions(),
                answers=[0, 1, 2, 3, 0],
                score=1,
                passed=False,
                source="fieldnotes-reviewed",
            )


if __name__ == "__main__":
    unittest.main()
