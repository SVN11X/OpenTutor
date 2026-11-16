"""Wording of the Hoy tab: every state has an icon and words."""

import unittest
from datetime import datetime, timedelta, timezone

from guardian.today_view import AgentState, active_today, counter_line, headline, setup_steps

TZ = timezone(timedelta(hours=-3))
NOW = datetime(2026, 11, 16, 9, 0, tzinfo=TZ)


def state(**changes):
    base = dict(enabled=True, all_day=True, until=None, paused_until=None, pending=False, in_quiz=False)
    base.update(changes)
    return AgentState(**base)


class HeadlineTests(unittest.TestCase):
    def test_each_state_has_its_own_line(self):
        self.assertEqual(headline(state(), NOW), "● Estudiando todo el día")
        self.assertEqual(
            headline(state(all_day=False, until=NOW + timedelta(hours=1)), NOW),
            "● Estudiando hasta las 10:00",
        )
        self.assertEqual(
            headline(state(paused_until=NOW + timedelta(minutes=15)), NOW), "⏸ En pausa hasta las 09:15"
        )
        self.assertTrue(headline(state(pending=True), NOW).startswith("● Examen pendiente"))
        self.assertTrue(headline(state(in_quiz=True), NOW).startswith("✎ Examen abierto"))
        self.assertEqual(headline(state(enabled=False), NOW), "○ Sin sesión de estudio")

    def test_a_pending_quiz_is_mentioned_without_a_session(self):
        self.assertIn("examen pendiente", headline(state(enabled=False, pending=True), NOW))

    def test_an_expired_pause_is_not_shown(self):
        self.assertEqual(
            headline(state(paused_until=NOW - timedelta(minutes=1)), NOW), "● Estudiando todo el día"
        )


class CounterTests(unittest.TestCase):
    def test_counter_says_why_it_is_stopped(self):
        self.assertIn("inicia una sesión", counter_line(False, None, 0, 600))
        self.assertEqual(
            counter_line(True, "pantalla bloqueada", 0, 600), "Contador en pausa: pantalla bloqueada"
        )

    def test_counter_shows_minutes_left_and_never_zero(self):
        self.assertIn("unos 7 min", counter_line(True, None, 180, 600))
        self.assertIn("unos 1 min", counter_line(True, None, 599, 600))

    def test_a_pending_quiz_holds_the_counter(self):
        self.assertIn("examen pendiente", counter_line(True, None, 600, 600, pending=True))

    def test_active_today(self):
        self.assertEqual(active_today(5 * 3600 + 7 * 60 + 59), "Tiempo activo hoy: 5 h 7 min")


class SetupStepsTests(unittest.TestCase):
    def test_missing_steps_say_what_to_do(self):
        steps = setup_steps(bank_found=False, all_day=False, autostart=True)
        self.assertEqual([done for done, _ in steps], [False, False, True])
        self.assertIn("Elige la carpeta", steps[0][1])


if __name__ == "__main__":
    unittest.main()
