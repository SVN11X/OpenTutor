"""Wording and buttons of the Hoy tab: every state has an icon and words, said once, with the reason a
pending quiz waits, and only the buttons that do something now."""

import unittest
from datetime import datetime, timedelta, timezone

from guardian.today_view import AgentState, actions, active_today, counter_line, headline, setup_steps

TZ = timezone(timedelta(hours=-3))
NOW = datetime(2026, 11, 16, 9, 0, tzinfo=TZ)


def state(**changes):
    base = dict(enabled=True, all_day=True, until=None, paused_until=None, pending=False, in_quiz=False)
    base.update(changes)
    return AgentState(**base)


class HeadlineTests(unittest.TestCase):
    def test_each_state_has_its_own_line(self):
        self.assertEqual(headline(state(), NOW), "● Estudiando (Todo el día)")
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

    def test_a_waiting_quiz_says_why(self):
        self.assertEqual(
            headline(state(pending=True, wait="hay una app en pantalla completa"), NOW),
            "● Examen pendiente, en espera: hay una app en pantalla completa",
        )
        self.assertIn("se abre en unos segundos", headline(state(pending=True), NOW))
        self.assertIn("Hacer examen ahora", headline(state(pending=True, insistent=False), NOW))

    def test_a_pause_keeps_saying_a_quiz_is_pending(self):
        paused = state(pending=True, paused_until=NOW + timedelta(minutes=15))
        self.assertEqual(headline(paused, NOW), "⏸ En pausa hasta las 09:15 · tienes un examen pendiente")

    def test_an_expired_pause_is_not_shown(self):
        self.assertEqual(
            headline(state(paused_until=NOW - timedelta(minutes=1)), NOW), "● Estudiando (Todo el día)"
        )


class CounterTests(unittest.TestCase):
    def test_counter_says_why_it_is_stopped(self):
        self.assertEqual(
            counter_line(True, "pantalla bloqueada", 0, 600), "Contador en pausa: pantalla bloqueada"
        )

    def test_counter_shows_minutes_left_and_never_zero(self):
        self.assertIn("unos 7 min", counter_line(True, None, 180, 600))
        self.assertIn("unos 1 min", counter_line(True, None, 599, 600))

    def test_the_counter_does_not_repeat_the_headline(self):
        self.assertEqual(counter_line(False, None, 0, 600), "")
        self.assertEqual(counter_line(True, None, 600, 600, pending=True), "")

    def test_active_today(self):
        self.assertEqual(active_today(5 * 3600 + 7 * 60 + 59), "Tiempo activo hoy: 5 h 7 min")


class ActionsTests(unittest.TestCase):
    def names(self, current):
        return [name for name, _main in actions(current, NOW)]

    def main(self, current):
        return [name for name, main in actions(current, NOW) if main]

    def test_each_state_shows_its_buttons_with_one_main_action(self):
        cases = {
            "no session": (state(enabled=False), ["start", "quiz"]),
            "no session, pending": (state(enabled=False, pending=True), ["quiz", "start"]),
            "studying": (state(), ["pause", "quiz", "stop"]),
            "paused": (state(paused_until=NOW + timedelta(minutes=5)), ["resume", "quiz", "stop"]),
            "pending": (state(pending=True), ["quiz", "pause", "stop"]),
            "in quiz": (state(in_quiz=True), ["quiz", "stop"]),
        }
        for name, (current, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(self.names(current), expected)
                self.assertEqual(self.main(current), expected[:1])

    def test_no_state_offers_both_start_and_stop(self):
        for current in (state(), state(enabled=False), state(pending=True), state(in_quiz=True)):
            self.assertFalse({"start", "stop"} <= set(self.names(current)))


class SetupStepsTests(unittest.TestCase):
    def test_missing_steps_say_what_to_do(self):
        steps = setup_steps(bank_found=False, all_day=False, autostart=True)
        self.assertEqual([done for done, _ in steps], [False, False, True])
        self.assertIn("Elige la carpeta", steps[0][1])


if __name__ == "__main__":
    unittest.main()
