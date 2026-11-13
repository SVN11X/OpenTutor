import tempfile
import unittest
import zipfile
from pathlib import Path
from random import Random

from guardian.evidence.defense import build_defense
from guardian.evidence.pptx_check import Result, check_pptx
from test_pptx_check import slide_xml


def deck(tmp: Path, titles_and_bodies) -> Path:
    path = tmp / "d.pptx"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for i, (title, body) in enumerate(titles_and_bodies, 1):
            z.writestr(f"ppt/slides/slide{i}.xml", slide_xml(title, body))
    return path


class DefenseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.slides = [(f"Title number {i}", f"BigQuery partitioning clustering point {i}") for i in range(5)]
        self.result = check_pptx(deck(Path(self.tmp.name), self.slides), expected_slides=5)

    def test_result_exposes_titles_and_vocabulary(self):
        self.assertEqual(self.result.status, "passed")
        self.assertEqual(self.result.titles[0], "Title number 0")
        self.assertIn("partitioning", self.result.vocabulary)

    def test_three_valid_questions_with_one_correct_answer_each(self):
        questions = build_defense(self.result, ("BigQuery",), Random(7))
        self.assertEqual(len(questions), 3)
        for q in questions:
            self.assertEqual(len(set(o.casefold() for o in q.options)), 4)
            self.assertTrue(q.explanation)

    def test_answers_are_true_about_the_file(self):
        for seed in range(30):
            q_count, q_title, q_term = build_defense(self.result, ("BigQuery",), Random(seed))
            self.assertEqual(q_count.options[q_count.answer_index], "5")
            k = int(q_title.prompt.split()[-1].rstrip("?")) - 1
            self.assertEqual(q_title.options[q_title.answer_index], self.result.titles[k])
            self.assertIn(q_term.options[q_term.answer_index].casefold(), self.result.full_text)
            wrong = [o for i, o in enumerate(q_term.options) if i != q_term.answer_index]
            self.assertTrue(all(w.casefold() not in self.result.full_text for w in wrong))

    def test_distractor_terms_never_appear_in_the_deck(self):
        slides = [
            ("Title A", "Kubernetes Terraform Firestore Spanner Dataproc Composer"),
            ("Title B", "Looker Bigtable"),
        ]
        result = check_pptx(deck(Path(self.tmp.name), slides), expected_slides=2)
        questions = build_defense(result, (), Random(1))
        for q in questions:
            if q.prompt.startswith("¿Cuál de estos términos"):
                wrong = [o for i, o in enumerate(q.options) if i != q.answer_index]
                self.assertTrue(all(w.casefold() not in result.full_text for w in wrong))

    def test_failed_or_unreadable_result_gives_no_questions(self):
        self.assertEqual(build_defense(Result("failed")), [])

    def test_single_slide_deck_still_works(self):
        result = check_pptx(
            deck(Path(self.tmp.name), [("Only title", "Dataflow streaming pipelines")]), expected_slides=1
        )
        questions = build_defense(result, ("Dataflow",), Random(3))
        self.assertGreaterEqual(len(questions), 2)


if __name__ == "__main__":
    unittest.main()
