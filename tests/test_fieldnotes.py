"""Tests for the fast, read-only Fieldnotes integration (no Ollama required)."""

import hashlib
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from guardian.core import ResultStore
from guardian.fieldnotes import domain_names, find_bank_path, load_pool
from guardian.questions import get_questions
from guardian.spaced import Card, key, pick, question_key

NOW = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)


def fingerprint(text: str) -> str:
    """The first 12 hex chars of the bank's own fingerprint for a field."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def entry(text: str, original: str) -> dict:
    return {"es": text, "src": fingerprint(original)}


def sample(index, *, status="reviewed", gradable=True, images=False, required=1, domain=None):
    item = {
        "id": f"imp-{index}",
        "number": index,
        "text": f"Pregunta original {index}?",
        # html differs from text, as in the real bank, so a fingerprint of the wrong field fails the tests.
        "html": f"<p>Pregunta original {index}?</p>",
        "choices": [
            {
                "letter": letter,
                "text": f"Opción {letter} de pregunta {index}",
                "html": f"<b>{letter}</b>{index}",
            }
            for letter in "ABCD"
        ],
        "answer": ["B"],
        "sourceAnswer": ["B"],
        "status": status,
        "gradable": gradable,
        "hasImages": images,
        "missingDiagram": False,
        "required": required,
        "explanation": f"Justificación editorial {index}",
    }
    if domain is not None:
        item["domain"] = domain
    return item


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
        pool = load_pool(bank_path=self.path)
        self.assertEqual([q.prompt for q in pool], ["Pregunta original 1?"])

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

    def test_recent_prompts_are_deprioritized_not_excluded(self):
        self.write([sample(i) for i in range(1, 8)])
        pool = load_pool(bank_path=self.path)
        recent = {"pregunta original 1?", "pregunta original 2?"}
        # Cards now come keyed by question_key, like ResultStore.record and store.cards() store them.
        cards = {
            question_key(q): Card(box=0, due_at=datetime.max.replace(tzinfo=UTC))
            for q in pool
            if key(q.prompt) in recent
        }
        questions = pick(pool, cards, NOW, 5)
        self.assertEqual(len(questions), 5)
        self.assertNotIn("Pregunta original 1?", [q.prompt for q in questions])
        self.assertNotIn("Pregunta original 2?", [q.prompt for q in questions])

    def test_domains_filter_keeps_matching_questions_only(self):
        items = [sample(i, domain=1 if i % 2 == 0 else 2) for i in range(1, 8)]
        self.write(items)
        pool = load_pool(bank_path=self.path, domains=(2,))
        self.assertEqual([q.prompt for q in pool], [f"Pregunta original {i}?" for i in (1, 3, 5, 7)])

    def test_missing_domain_is_skipped_only_when_a_filter_is_set(self):
        self.write([sample(i) for i in range(1, 4)])
        self.assertEqual(len(load_pool(bank_path=self.path)), 3)
        self.assertEqual(load_pool(bank_path=self.path, domains=(1,)), [])

    def test_all_cards_not_due_still_returns_five_questions(self):
        self.write([sample(i) for i in range(1, 8)])
        pool = load_pool(bank_path=self.path)
        cards = {question_key(q): Card(box=0, due_at=NOW + timedelta(days=1)) for q in pool}
        questions, source = get_questions(
            "Google Cloud", set(), mode="bank-only", bank_path=self.repo, cards=cards, now=NOW
        )
        self.assertEqual(source, "fieldnotes-reviewed")
        self.assertEqual(len(questions), 5)

    def test_environment_override(self):
        self.write([sample(1)])
        with patch.dict("os.environ", {"GUARDIAN_GCP_BANK": str(self.repo)}):
            self.assertEqual(find_bank_path(), self.path.resolve())

    def test_bad_format_rejected_not_fabricated(self):
        self.path.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Formato del banco"):
            load_pool(bank_path=self.path)

    def test_domain_names_reads_the_sorted_catalog(self):
        self.write([sample(1)])
        (self.repo / "content" / "domains.json").write_text(
            json.dumps([{"id": 2, "name": "BigQuery", "weight": 3}, {"id": 1, "name": "Datos", "weight": 1}]),
            encoding="utf-8",
        )
        self.assertEqual(domain_names(self.repo), [(1, "Datos", 1), (2, "BigQuery", 3)])

    def test_domain_names_without_a_catalog_or_bank(self):
        self.write([sample(1)])
        self.assertEqual(domain_names(self.repo), [])
        self.assertEqual(domain_names(Path("Z:/no-such-bank")), [])

    def test_domain_names_warns_on_an_invalid_catalog(self):
        self.write([sample(1)])
        (self.repo / "content" / "domains.json").write_text("{oops", encoding="utf-8")
        with self.assertLogs("guardian.fieldnotes", level="WARNING"):
            self.assertEqual(domain_names(self.repo), [])


class SpanishTranslationTests(unittest.TestCase):
    """Spanish display is all or nothing per question: a stale or partial translation keeps it English."""

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

    def write_es(self, files):
        folder = self.repo / "content" / "es"
        folder.mkdir(exist_ok=True)
        for name, payload in files.items():
            (folder / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def translations_for(self, item, *, prompt=None, options=None, explanation=None):
        """Entries for one item; None in options leaves that choice untranslated."""
        entries = {}
        if prompt is not None:
            entries["html"] = entry(prompt, item["html"])
        for i in range(4):
            if options and options[i] is not None:
                entries[f"choices.{i}.html"] = entry(options[i], item["choices"][i]["html"])
        if explanation is not None:
            entries["explanation"] = entry(explanation, item["explanation"])
        return {item["id"]: entries}

    def test_a_current_translation_shows_prompt_options_and_explanation(self):
        item = sample(1)
        self.write([item])
        self.write_es(
            {
                "imported-d1.json": self.translations_for(
                    item,
                    prompt="Pregunta traducida 1",
                    options=[f"Opción {letter}" for letter in "ABCD"],
                    explanation="Justificación traducida",
                )
            }
        )
        (question,) = load_pool(bank_path=self.path)
        self.assertEqual(question.prompt, "Pregunta traducida 1")
        self.assertEqual(question.options, ("Opción A", "Opción B", "Opción C", "Opción D"))
        self.assertEqual(question.explanation, "Justificación traducida")

    def test_a_stale_prompt_keeps_the_whole_question_in_english(self):
        item = sample(1)
        self.write([item])
        self.write_es(
            {
                "imported-d1.json": {
                    "imp-1": {
                        "html": {"es": "Pregunta traducida 1", "src": "0" * 12},
                        "explanation": entry("Justificación traducida", item["explanation"]),
                    }
                }
            }
        )
        (question,) = load_pool(bank_path=self.path)
        self.assertEqual(question.prompt, "Pregunta original 1?")
        self.assertEqual(question.options, tuple(f"Opción {letter} de pregunta 1" for letter in "ABCD"))
        self.assertEqual(question.explanation, "Justificación editorial 1")

    def test_one_missing_option_keeps_the_whole_question_in_english(self):
        item = sample(1)
        self.write([item])
        self.write_es(
            {
                "imported-d1.json": self.translations_for(
                    item, prompt="Pregunta traducida 1", options=["Opción A", None, None, None]
                )
            }
        )
        (question,) = load_pool(bank_path=self.path)
        self.assertEqual(question.prompt, "Pregunta original 1?")
        self.assertEqual(question.explanation, "Justificación editorial 1")

    def test_html_in_a_translation_becomes_plain_text(self):
        item = sample(1)
        self.write([item])
        self.write_es(
            {
                "imported-d1.json": self.translations_for(
                    item,
                    prompt="<p>¿Qué servicio <b>no</b> es de datos &amp; por qué?</p>",
                    options=[f"<em>Opción {letter}</em>" for letter in "ABCD"],
                )
            }
        )
        (question,) = load_pool(bank_path=self.path)
        self.assertEqual(question.prompt, "¿Qué servicio no es de datos & por qué?")
        self.assertEqual(question.options, ("Opción A", "Opción B", "Opción C", "Opción D"))

    def test_english_language_ignores_the_translations(self):
        item = sample(1)
        self.write([item])
        self.write_es(
            {
                "imported-d1.json": self.translations_for(
                    item,
                    prompt="Pregunta traducida 1",
                    options=[f"Opción {letter}" for letter in "ABCD"],
                    explanation="Justificación traducida",
                )
            }
        )
        (question,) = load_pool(bank_path=self.path, language="en")
        self.assertEqual(question.prompt, "Pregunta original 1?")
        self.assertEqual(question.explanation, "Justificación editorial 1")

    def test_an_invalid_translation_file_warns_and_stays_english(self):
        self.write([sample(1)])
        folder = self.repo / "content" / "es"
        folder.mkdir()
        (folder / "imported-d1.json").write_text("{oops", encoding="utf-8")
        with self.assertLogs("guardian.fieldnotes", level="WARNING"):
            (question,) = load_pool(bank_path=self.path)
        self.assertEqual(question.prompt, "Pregunta original 1?")

    def test_uid_is_the_item_id_when_it_is_a_non_empty_string(self):
        without_id = sample(2)
        del without_id["id"]
        self.write([sample(1), without_id])
        first, second = load_pool(bank_path=self.path)
        self.assertEqual(first.uid, "imp-1")
        self.assertEqual(second.uid, "")


if __name__ == "__main__":
    unittest.main()
