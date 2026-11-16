"""All-day sessions end at the next local midnight, normal ones after 60 minutes."""

import unittest
from datetime import datetime, timedelta, timezone

from guardian.desktop import session_end

LIMA = timezone(timedelta(hours=-5))


class SessionEndTests(unittest.TestCase):
    def test_all_day_ends_at_the_next_local_midnight(self):
        start = datetime(2026, 11, 16, 8, 30, tzinfo=LIMA)
        self.assertEqual(session_end(start, all_day=True), datetime(2026, 11, 17, 0, 0, tzinfo=LIMA))

    def test_all_day_started_just_before_midnight_lasts_until_it(self):
        start = datetime(2026, 11, 16, 23, 59, 30, tzinfo=LIMA)
        self.assertEqual(session_end(start, all_day=True) - start, timedelta(seconds=30))

    def test_normal_session_lasts_sixty_minutes(self):
        start = datetime(2026, 11, 16, 8, 30, tzinfo=LIMA)
        self.assertEqual(session_end(start, all_day=False), start + timedelta(minutes=60))

    def test_end_keeps_the_time_zone(self):
        start = datetime(2026, 11, 16, 8, 30, tzinfo=LIMA)
        self.assertEqual(session_end(start, all_day=True).utcoffset(), timedelta(hours=-5))


if __name__ == "__main__":
    unittest.main()
