"""Presence flags, Windows message mapping and the daily activity log."""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from guardian.activity_log import ActivityLog
from guardian.presence import FULLSCREEN, PRESENTATION, Presence, busy_from_state
from guardian.tray import WM_POWERBROADCAST, WM_WTSSESSION_CHANGE, system_event


class BusyStateTests(unittest.TestCase):
    def test_full_screen_states_make_the_quiz_wait(self):
        for state in (2, 3, 7):
            self.assertEqual(busy_from_state(state), FULLSCREEN)

    def test_presentation_mode_makes_the_quiz_wait(self):
        self.assertEqual(busy_from_state(4), PRESENTATION)

    def test_other_states_let_the_quiz_open(self):
        for state in (0, 1, 5, 6, 99):
            self.assertIsNone(busy_from_state(state))


class PresenceTests(unittest.TestCase):
    def test_suspension_and_lock_pause_the_clock_until_they_end(self):
        presence = Presence()
        self.assertIsNone(presence.paused_reason(active=True))
        presence.on_event("suspend")
        self.assertEqual(presence.paused_reason(active=True), "equipo en suspensión")
        presence.on_event("resume")
        presence.on_event("lock")
        self.assertEqual(presence.paused_reason(active=True), "pantalla bloqueada")
        presence.on_event("unlock")
        self.assertIsNone(presence.paused_reason(active=True))

    def test_idle_user_pauses_the_clock(self):
        self.assertEqual(Presence().paused_reason(active=False), "sin actividad")

    def test_menu_commands_are_not_presence_events(self):
        presence = Presence()
        self.assertFalse(presence.on_event("open"))
        self.assertFalse(presence.suspended or presence.locked)


class SystemEventTests(unittest.TestCase):
    def test_power_messages(self):
        self.assertEqual(system_event(WM_POWERBROADCAST, 0x4), "suspend")
        self.assertEqual(system_event(WM_POWERBROADCAST, 0x7), "resume")
        self.assertEqual(system_event(WM_POWERBROADCAST, 0x12), "resume")
        self.assertIsNone(system_event(WM_POWERBROADCAST, 0xA))  # power status change

    def test_session_messages(self):
        self.assertEqual(system_event(WM_WTSSESSION_CHANGE, 0x7), "lock")
        self.assertEqual(system_event(WM_WTSSESSION_CHANGE, 0x8), "unlock")
        self.assertIsNone(system_event(WM_WTSSESSION_CHANGE, 0x1))  # console connect

    def test_other_messages_are_ignored(self):
        self.assertIsNone(system_event(0x0010, 0x4))


class ActivityLogTests(unittest.TestCase):
    def test_adds_seconds_per_day_and_survives_reopening(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "guardian.sqlite3"
            log = ActivityLog(path)
            log.add(date(2026, 11, 16), 30)
            log.add(date(2026, 11, 16), 12.5)
            log.add(date(2026, 11, 17), 5)
            self.assertEqual(ActivityLog(path).seconds_on(date(2026, 11, 16)), 42.5)
            self.assertEqual(log.seconds_on(date(2026, 11, 17)), 5)
            self.assertEqual(log.seconds_on(date(2026, 11, 18)), 0)

    def test_rejects_negative_seconds(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                ActivityLog(Path(d) / "g.sqlite3").add(date(2026, 11, 16), -1)


if __name__ == "__main__":
    unittest.main()
