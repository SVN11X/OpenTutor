import random
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from guardian.core import (
    ResultStore,
    SurpriseClock,
    grade,
    validate_questions,
    within_study_window,
)
from guardian.questions import FALLBACK_GCP, get_questions
from guardian.spaced import key


class GuardianTests(unittest.TestCase):
    def test_interval_bounds_and_no_instant_repeat(self):
        clock = SurpriseClock(random.Random(42))
        self.assertGreaterEqual(clock.target, 600)
        self.assertLessEqual(clock.target, 1500)
        for _ in range(2000):
            clock.tick(1, active=True, allowed=True)
        self.assertTrue(clock.surprise_due)
        clock.reset_after_quiz()
        self.assertFalse(clock.surprise_due)
        self.assertEqual(clock.eligible, 0)

    def test_only_eligible_time_counts(self):
        clock = SurpriseClock(random.Random(0), interval=(10, 10))
        clock.tick(5000, active=False, allowed=True)
        clock.tick(5000, active=True, allowed=False)
        clock.tick(5000, active=True, allowed=True, protected=True)
        self.assertEqual(clock.eligible, 0)
        clock.tick(4000, active=True, allowed=True)
        self.assertEqual(clock.eligible, 5)
        clock.tick(5, active=True, allowed=True)
        self.assertTrue(clock.surprise_due)

    def test_study_window_opt_in_and_midnight(self):
        now = datetime(2026, 11, 12, 9, 30)
        self.assertFalse(within_study_window(now, []))
        self.assertTrue(within_study_window(now, [("09:00", "10:00")]))
        self.assertFalse(within_study_window(now, [("10:00", "11:00")]))
        self.assertTrue(within_study_window(now, [("22:00", "10:00")]))

    def test_grade_boundary(self):
        q = FALLBACK_GCP[:5]
        self.assertEqual(grade(q, [x.answer_index for x in q]), (5, True))
        answers = [x.answer_index for x in q]
        answers[0] = (answers[0] + 1) % 4
        self.assertEqual(grade(q, answers), (4, True))
        answers[1] = (answers[1] + 1) % 4
        self.assertEqual(grade(q, answers), (3, False))

    def test_validation_rejects_invalid_llm_data(self):
        valid = [x.to_dict() for x in FALLBACK_GCP[:5]]
        self.assertEqual(len(validate_questions(valid)), 5)
        valid[0]["options"][1] = valid[0]["options"][0]
        with self.assertRaises(ValueError):
            validate_questions(valid)

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "guardian.sqlite"
            db = ResultStore(p)
            db.record(
                topic="gcp",
                questions=FALLBACK_GCP[:5],
                answers=[x.answer_index for x in FALLBACK_GCP[:5]],
                source="fallback-reviewed",
            )
            self.assertEqual(db.stats(), (1, 1))
            db.close()
            db = ResultStore(p)
            self.assertEqual(db.stats(), (1, 1))
            self.assertIn(FALLBACK_GCP[0].prompt.casefold(), db.recent_prompts())
            db.close()

    def test_record_with_injected_now_updates_cards(self):
        now = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
        questions = FALLBACK_GCP[:5]
        wrong = [(q.answer_index + 1) % 4 for q in questions]
        right = [q.answer_index for q in questions]
        with tempfile.TemporaryDirectory() as d:
            db = ResultStore(Path(d) / "cards.sqlite")
            db.record(topic="gcp", questions=questions, answers=wrong, source="fallback-reviewed", now=now)
            cards = db.cards()
            self.assertEqual([cards[key(q.prompt)].box for q in questions], [0] * 5)
            self.assertEqual(
                [cards[key(q.prompt)].due_at for q in questions], [now + timedelta(minutes=10)] * 5
            )
            db.record(topic="gcp", questions=questions, answers=right, source="fallback-reviewed", now=now)
            cards = db.cards()
            self.assertEqual([cards[key(q.prompt)].box for q in questions], [1] * 5)
            self.assertEqual([cards[key(q.prompt)].due_at for q in questions], [now + timedelta(hours=1)] * 5)
            db.record(topic="gcp", questions=questions, answers=right, source="fallback-reviewed", now=now)
            cards = db.cards()
            self.assertEqual([cards[key(q.prompt)].box for q in questions], [2] * 5)
            self.assertEqual([cards[key(q.prompt)].due_at for q in questions], [now + timedelta(hours=4)] * 5)
            self.assertEqual(
                db.con.execute("SELECT seen, wrong FROM guardian_cards").fetchall(), [(3, 1)] * 5
            )
            self.assertEqual(db.recent_attempts(1)[0][0], now.isoformat(timespec="seconds"))
            db.close()

    def test_cards_skip_dates_without_time_zone(self):
        with tempfile.TemporaryDirectory() as d:
            db = ResultStore(Path(d) / "cards.sqlite")
            db.con.execute("INSERT INTO guardian_cards VALUES ('a?', 0, '2026-11-16T09:00:00', 1, 1)")
            db.con.execute("INSERT INTO guardian_cards VALUES ('b?', 1, 'not a date', 1, 0)")
            with self.assertLogs("guardian.core", level="WARNING"):
                self.assertEqual(db.cards(), {})
            db.close()


if __name__ == "__main__":
    unittest.main()


class QuestionsFailureTests(unittest.TestCase):
    def test_unknown_topic_does_not_invent_fallback(self):
        from unittest.mock import patch
        from urllib.error import URLError

        with patch("guardian.questions.urlopen", side_effect=URLError("offline")):
            with self.assertRaisesRegex(RuntimeError, "no hay banco revisado"):
                get_questions("topología algebraica", set())

    def test_gcp_offline_uses_reviewed_bank(self):
        from unittest.mock import patch
        from urllib.error import URLError

        # Hermetic: point the bank override at a missing file so a real Fieldnotes
        # checkout on this machine cannot change which source is used.
        with (
            patch.dict("os.environ", {"GUARDIAN_GCP_BANK": "Z:/does-not-exist/imported.json"}),
            patch("guardian.questions.urlopen", side_effect=URLError("offline")),
        ):
            questions, source = get_questions("GCP", set())
        self.assertEqual(len(questions), 5)
        self.assertEqual(source, "fallback-reviewed")

    def test_rejects_remote_endpoint(self):
        with self.assertRaisesRegex(ValueError, "Solo se permite"):
            get_questions("GCP", set(), endpoint="https://server.example")
