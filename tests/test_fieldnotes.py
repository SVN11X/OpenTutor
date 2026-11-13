"""Tests for the fast, read-only Fieldnotes integration (no Ollama required)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from guardian.core import ResultStore
from guardian.fieldnotes import find_bank_path, reviewed_questions
from guardian.questions import get_questions


def sample(index, *, status="reviewed", gradable=True, images=False, required=1):
    return {
        "id": f"imp-{index}",
        "number": index,
        "text": f"Pregunta original {index}?",
        "choices": [{"letter": letter, "text": f"Opción {letter} de pregunta {index}"} for letter in "ABCD"],
        "answer": ["B"],
        "sourceAnswer": ["B"],
        "status": status,
        "gradable": gradable,
        "hasImages": images,
        "missingDiagram": False,
        "required": required,
        "explanation": f"Justificación editorial {index}",
    }


class FieldnotesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "GCP_Data_Engineer_Fieldnotes"
        (self.repo / "content").mkdir(parents=True)
        self.path = self.repo / "content" / "imported.json"

    def write(self, questions):
        self.path.write_text(
            json.dumps({"questionCount": len(questions), "questions": questions}, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_uses_local_bank_before_ollama_and_preserves_bytes(self):
        self.write([sample(i) for i in range(1, 8)])
        original = self.path.read_bytes()
        with patch("guardian.questions.urlopen", side_effect=AssertionError("Ollama should not run")):
            questions, source = get_questions("Google Cloud", set(), mode="bank-only", bank_path=self.repo)
        self.assertEqual(source, "fieldnotes-reviewed")
        self.assertEqual(len(questions), 5)
        self.assertEqual({q.answer_index for q in questions}, {1})
        self.assertEqual(self.path.read_bytes(), original)

    def test_only_graded_reviewed_without_images_or_multiselect(self):
        self.write(
            [
                sample(1),
                sample(2, status="unreviewed"),
                sample(3, gradable=False),
                sample(4, images=True),
                sample(5, required=2),
            ]
        )
        reviewed = reviewed_questions(set(), bank_path=self.path)
        self.assertEqual([q.prompt for q in reviewed], ["Pregunta original 1?"])

    def test_practice_can_include_unreviewed_but_is_not_eligible_for_pass(self):
        self.write([sample(i, status="unreviewed", gradable=False) for i in range(1, 8)])
        questions, source = get_questions("GCP", set(), mode="bank-practice", bank_path=self.path)
        self.assertEqual(source, "fieldnotes-practice-unverified")
        self.assertEqual(len(questions), 5)
        self.assertIn("sin verificar", questions[0].explanation)
        db = ResultStore(Path(self.tmp.name) / "out.sqlite3")
        score, passed = db.record(topic="GCP", questions=questions, answers=[1] * 5, source=source)
        self.assertEqual((score, passed), (5, False))
        self.assertEqual(db.stats(), (1, 0))
        db.close()

    def test_not_repeat_answered_items(self):
        self.write([sample(i) for i in range(1, 8)])
        questions = reviewed_questions({"pregunta original 1?", "pregunta original 2?"}, bank_path=self.path)
        self.assertEqual(len(questions), 5)
        self.assertNotIn("Pregunta original 1?", [q.prompt for q in questions])
        self.assertNotIn("Pregunta original 2?", [q.prompt for q in questions])

    def test_environment_override(self):
        self.write([sample(1)])
        with patch.dict("os.environ", {"GUARDIAN_GCP_BANK": str(self.repo)}):
            self.assertEqual(find_bank_path(), self.path.resolve())

    def test_bad_format_rejected_not_fabricated(self):
        self.path.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Formato del banco"):
            reviewed_questions(set(), bank_path=self.path)


if __name__ == "__main__":
    unittest.main()
