from pathlib import Path
import tempfile
import unittest

from guardian.core import Question, ResultStore, attempt_label


def _questions():
    return [Question(f"Q{i}", ("a", "b", "c", "d"), 0, "because") for i in range(5)]


class PanelDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ResultStore(Path(self.tmp.name) / "r.sqlite3")
        self.addCleanup(self.store.close)

    def test_labels_have_icon_and_text_and_unverified_is_practice(self):
        self.assertTrue(attempt_label(5, True, "fieldnotes-reviewed").startswith("✔ Aprobado"))
        self.assertTrue(attempt_label(2, False, "fieldnotes-reviewed").startswith("✖ Repasar"))
        practice = attempt_label(5, True, "fieldnotes-practice")
        self.assertTrue(practice.startswith("◐ Práctica"))
        self.assertIn("sin verificar", practice)

    def test_recent_and_average(self):
        self.assertIsNone(self.store.average_score())
        self.assertEqual(self.store.recent_attempts(), [])
        self.store.record(topic="A", questions=_questions(), answers=[0, 0, 0, 0, 1], source="fieldnotes-reviewed")
        self.store.record(topic="B", questions=_questions(), answers=[0, 0, 0, 0, 0], source="fieldnotes-practice")
        recent = self.store.recent_attempts()
        self.assertEqual([r[1] for r in recent], ["B", "A"])  # newest first
        self.assertEqual([r[2] for r in recent], [5, 4])
        self.assertFalse(recent[0][3])  # unverified source never counts as a certified pass
        self.assertTrue(recent[1][3])
        self.assertEqual(self.store.average_score(), 4.5)


if __name__ == "__main__":
    unittest.main()
