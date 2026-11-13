"""Edge cases of the study schedule and the surprise clock. No GUI, no real time."""

import unittest
from datetime import UTC, datetime, timedelta, timezone
from random import Random

from guardian.core import SurpriseClock, within_study_window

DAY = datetime(2026, 3, 8, tzinfo=UTC)  # a date where many zones change clocks


def at(hour: int, minute: int, tz=UTC) -> datetime:
    return datetime(2026, 3, 8, hour, minute, tzinfo=tz)


class StudyWindowEdgeTests(unittest.TestCase):
    def test_start_is_inclusive_end_is_exclusive(self):
        windows = [("09:00", "12:00")]
        self.assertTrue(within_study_window(at(9, 0), windows))
        self.assertTrue(within_study_window(at(11, 59), windows))
        self.assertFalse(within_study_window(at(12, 0), windows))
        self.assertFalse(within_study_window(at(8, 59), windows))

    def test_midnight_crossing(self):
        windows = [("22:00", "02:00")]
        self.assertTrue(within_study_window(at(23, 30), windows))
        self.assertTrue(within_study_window(at(1, 59), windows))
        self.assertFalse(within_study_window(at(2, 0), windows))
        self.assertFalse(within_study_window(at(12, 0), windows))

    def test_equal_start_and_end_means_no_time(self):
        self.assertFalse(within_study_window(at(10, 0), [("10:00", "10:00")]))

    def test_no_windows_means_no_study(self):
        self.assertFalse(within_study_window(at(10, 0), []))

    def test_several_windows(self):
        windows = [("09:00", "10:00"), ("14:00", "15:00")]
        self.assertTrue(within_study_window(at(14, 30), windows))
        self.assertFalse(within_study_window(at(12, 0), windows))

    def test_uses_local_wall_clock_across_offset_change(self):
        # The schedule is wall-clock time. 10:30 is inside 10:00-11:00 whatever the offset is,
        # for example before and after a daylight saving change.
        winter = timezone(timedelta(hours=-5))
        summer = timezone(timedelta(hours=-4))
        windows = [("10:00", "11:00")]
        self.assertTrue(within_study_window(at(10, 30, winter), windows))
        self.assertTrue(within_study_window(at(10, 30, summer), windows))
        self.assertFalse(within_study_window(at(11, 30, summer), windows))

    def test_invalid_clock_text_is_rejected(self):
        for bad in ("9:00", "25:00", "09:60", "09:00:30", "noon"):
            with self.assertRaises(ValueError):
                within_study_window(at(10, 0), [(bad, "12:00")])


class SurpriseClockStateTests(unittest.TestCase):
    def clock(self, target=600):
        clock = SurpriseClock(rng=Random(1), interval=(target, target))
        self.assertEqual(clock.target, target)
        return clock

    def test_suspension_never_adds_more_than_a_tick(self):
        clock = self.clock()
        # The machine slept for 8 hours: the next tick reports a huge elapsed time.
        self.assertFalse(clock.tick(8 * 3600, active=True, allowed=True))
        self.assertLessEqual(clock.eligible, 5.0)

    def test_idle_outside_schedule_or_protected_adds_nothing(self):
        clock = self.clock()
        clock.tick(5, active=False, allowed=True)
        clock.tick(5, active=True, allowed=False)
        clock.tick(5, active=True, allowed=True, protected=True)
        self.assertEqual(clock.eligible, 0.0)

    def test_due_after_target_and_latches_until_reset(self):
        clock = self.clock(target=10)
        for _ in range(2):
            due = clock.tick(5, active=True, allowed=True)
        self.assertTrue(due)
        # Already due: later ticks keep it due and do not count further.
        self.assertTrue(clock.tick(5, active=False, allowed=False))
        clock.reset_after_quiz()
        self.assertFalse(clock.surprise_due)
        self.assertEqual(clock.eligible, 0.0)

    def test_negative_elapsed_time_is_rejected(self):
        with self.assertRaises(ValueError):
            self.clock().tick(-1, active=True, allowed=True)

    def test_a_pending_quiz_is_one_not_many(self):
        clock = self.clock(target=5)
        results = [clock.tick(5, active=True, allowed=True) for _ in range(5)]
        self.assertTrue(all(results))  # one latched flag, not a counter of exams


if __name__ == "__main__":
    unittest.main()
