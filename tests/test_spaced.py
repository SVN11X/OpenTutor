"""Tests for the spaced repetition scheduler (Leitner boxes and pool picking)."""

import random
import unittest
from datetime import UTC, datetime, timedelta

from guardian.core import Question
from guardian.spaced import BOX_INTERVALS, Card, key, next_card, pick, question_key

NOW = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)


def question(prompt: str, uid: str = "") -> Question:
    return Question(prompt, ("A", "B", "C", "D"), 0, "Porque la fuente lo indica.", uid=uid)


class NextCardTests(unittest.TestCase):
    def test_wrong_answer_restarts_at_box_zero(self):
        card = next_card(None, False, NOW)
        self.assertEqual(card.box, 0)
        self.assertEqual(card.due_at, NOW + timedelta(minutes=10))

    def test_first_correct_answer_enters_box_one(self):
        card = next_card(None, True, NOW)
        self.assertEqual(card.box, 1)
        self.assertEqual(card.due_at, NOW + timedelta(hours=1))

    def test_correct_answer_advances_one_box(self):
        card = next_card(Card(box=1, due_at=NOW), True, NOW)
        self.assertEqual(card.box, 2)
        self.assertEqual(card.due_at, NOW + timedelta(hours=4))

    def test_box_caps_at_the_last_interval(self):
        last = len(BOX_INTERVALS) - 1
        card = next_card(Card(box=last, due_at=NOW), True, NOW)
        self.assertEqual(card.box, last)
        self.assertEqual(card.due_at, NOW + BOX_INTERVALS[last])


class QuestionKeyTests(unittest.TestCase):
    def test_uid_wins_over_the_prompt_key(self):
        self.assertEqual(question_key(question("P0", uid="imp-12")), "imp-12")
        self.assertEqual(question_key(question("P0")), key("P0"))

    def test_the_same_uid_in_two_languages_shares_one_slot_in_pick(self):
        spanish = question("¿P0?", uid="imp-1")
        english = question("P0", uid="imp-1")
        self.assertEqual(pick([spanish, english], {}, NOW, k=5), [spanish])
        self.assertEqual(pick([english, spanish], {}, NOW, k=5), [english])


class PickTests(unittest.TestCase):
    def test_due_lowest_box_first_then_new_then_later(self):
        pool = [question(f"P{i}") for i in range(6)]
        cards = {
            key("P0"): Card(0, NOW - timedelta(minutes=1)),
            key("P1"): Card(2, NOW - timedelta(hours=1)),
            key("P2"): Card(1, NOW - timedelta(hours=2)),
            key("P4"): Card(0, NOW + timedelta(days=1)),
        }
        picked = pick(pool, cards, NOW, k=5, rng=random.Random(0))
        self.assertEqual([q.prompt for q in picked[:3]], ["P0", "P2", "P1"])
        self.assertEqual({q.prompt for q in picked[3:]}, {"P3", "P5"})

    def test_duplicates_keep_the_first_occurrence(self):
        first = question("P0")
        duplicate = question("P0")
        picked = pick([first, duplicate], {}, NOW, k=5)
        self.assertEqual(picked, [first])

    def test_small_pool_returns_the_whole_pool_without_raising(self):
        pool = [question(f"P{i}") for i in range(3)]
        picked = pick(pool, {}, NOW, k=5)
        self.assertEqual(len(picked), 3)

    def test_rng_makes_the_new_part_deterministic(self):
        pool = [question(f"P{i}") for i in range(5)]
        first = [q.prompt for q in pick(pool, {}, NOW, k=5, rng=random.Random(7))]
        second = [q.prompt for q in pick(pool, {}, NOW, k=5, rng=random.Random(7))]
        self.assertEqual(first, second)
        expected = [q.prompt for q in pool]
        random.Random(7).shuffle(expected)
        self.assertEqual(first, expected)


if __name__ == "__main__":
    unittest.main()
