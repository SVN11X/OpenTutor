"""UI-specific tests: trust cues are descriptive; scoring stays in results.py."""
import unittest
from guardian_mvp.core import Question
from guardian_mvp.results import build_exam_report
from guardian_mvp.results_ui import (answer_status_label, preview_explanation,
                                     provisional_score_label)


class ResultUIHelperTests(unittest.TestCase):
    def _report(self, source):
        questions = [Question(f"Question {i}", ("A", "B", "C", "D"), 0, "Expl.")
                     for i in range(5)]
        return build_exam_report(topic="Google Cloud", questions=questions,
                                 answers=[1, 1, 1, 1, 1], score=0, passed=False,
                                 source=source)

    def test_unverified_score_is_labeled_provisional(self):
        label = provisional_score_label(self._report("fieldnotes-practice-unverified"))
        self.assertIn("provisional", label)
        self.assertNotIn("0%", label)

    def test_verified_score_can_show_percentage(self):
        label = provisional_score_label(self._report("fieldnotes-reviewed"))
        self.assertIn("0%", label)
        self.assertNotIn("provisional", label)

    def test_unverified_mismatch_is_not_called_incorrect(self):
        self.assertEqual(answer_status_label(False, False), "Difiere de clave")
        self.assertEqual(answer_status_label(False, True), "Coincide con clave")
        self.assertEqual(answer_status_label(True, False), "A revisar")

    def test_preview_preserves_original_and_does_not_truncate_short_text(self):
        original = "ABC " * 200
        preview, truncated = preview_explanation(original, limit=100)
        self.assertTrue(truncated)
        self.assertTrue(preview.endswith("…"))
        self.assertLessEqual(len(preview), 101)
        self.assertEqual(preview_explanation("Short"), ("Short", False))


if __name__ == "__main__":
    unittest.main()
