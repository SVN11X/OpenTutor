from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from guardian_mvp.session_state import INACTIVE, SessionState, SessionStore
from guardian_mvp.single_instance import SingleInstance
import uuid

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "sub" / "session.json"
        self.store = SessionStore(self.path)

    def test_round_trip(self):
        state = SessionState(True, NOW + timedelta(hours=1), NOW + timedelta(minutes=5), "SQL", "bank-only")
        self.store.save(state)
        self.assertEqual(self.store.load(NOW), state)

    def test_missing_and_corrupt(self):
        self.assertEqual(self.store.load(NOW), INACTIVE)
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(self.store.load(NOW), INACTIVE)

    def test_expired_clears_file(self):
        self.store.save(SessionState(True, NOW - timedelta(seconds=1)))
        self.assertEqual(self.store.load(NOW), INACTIVE)
        self.assertFalse(self.path.exists())

    def test_active_without_until(self):
        self.store.save(SessionState(True, None))
        self.assertEqual(self.store.load(NOW), INACTIVE)

    def test_wrong_schema(self):
        self.store.save(SessionState(True, NOW + timedelta(hours=1)))
        data = json.loads(self.path.read_text())
        data["schema_version"] = 99
        self.path.write_text(json.dumps(data))
        self.assertEqual(self.store.load(NOW), INACTIVE)

    def test_past_pause_dropped(self):
        self.store.save(SessionState(True, NOW + timedelta(hours=1), NOW - timedelta(minutes=1)))
        self.assertIsNone(self.store.load(NOW).paused_until)

    def test_naive_rejected(self):
        with self.assertRaises(ValueError):
            self.store.save(SessionState(True, datetime(2026, 1, 1)))

    def test_clear_when_missing(self):
        self.store.clear()


class SingleInstanceTests(unittest.TestCase):
    def test_second_holder_is_refused_until_release(self):
        name = "GuardianTest" + uuid.uuid4().hex
        first, second = SingleInstance(name), SingleInstance(name)
        self.assertTrue(first.acquire())
        self.assertTrue(first.acquire())
        self.assertFalse(second.acquire())
        first.release()
        self.assertTrue(second.acquire())
        second.release()

    def test_context_manager_and_idle_release(self):
        name = "GuardianTest" + uuid.uuid4().hex
        SingleInstance(name).release()
        with SingleInstance(name):
            self.assertFalse(SingleInstance(name).acquire())
        other = SingleInstance(name)
        self.assertTrue(other.acquire())
        other.release()


if __name__ == "__main__":
    unittest.main()
