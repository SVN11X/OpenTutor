import json
import sqlite3
import tempfile
import unittest
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from guardian.session_state import INACTIVE, SessionState, SessionStore
from guardian.single_instance import SingleInstance

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=UTC)


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "sub" / "guardian.sqlite3"
        self.legacy = self.dir / "sub" / "session.json"
        self.store = SessionStore(self.db, legacy_json=self.legacy)

    def _sql(self, sql, *args):
        con = sqlite3.connect(str(self.db))
        try:
            with con:
                con.execute(sql, args)
        finally:
            con.close()

    def test_round_trip(self):
        state = SessionState(True, NOW + timedelta(hours=1), NOW + timedelta(minutes=5), "SQL", "bank-only")
        self.store.save(state)
        self.assertEqual(self.store.load(NOW), state)

    def test_missing_store_is_inactive(self):
        self.assertEqual(self.store.load(NOW), INACTIVE)

    def test_corrupt_database_is_logged_and_ignored(self):
        self.db.parent.mkdir(parents=True)
        self.db.write_bytes(b"this is not a sqlite database at all" * 20)
        with self.assertLogs("guardian.session_state", level="WARNING") as captured:
            self.assertEqual(self.store.load(NOW), INACTIVE)
        self.assertIn("unreadable session store", captured.output[0])

    def test_expired_session_is_dropped_when_nothing_else_is_kept(self):
        self.store.save(SessionState(True, NOW - timedelta(seconds=1)))
        self.assertEqual(self.store.load(NOW), INACTIVE)
        self.assertFalse(self.store.has_saved_state())

    def test_active_without_until_is_inactive(self):
        self.store.save(SessionState(True, None))
        self.assertEqual(self.store.load(NOW), INACTIVE)

    def test_wrong_schema_is_inactive(self):
        self.store.save(SessionState(True, NOW + timedelta(hours=1)))
        self._sql("UPDATE guardian_session SET schema_version = 99")
        self.assertEqual(self.store.load(NOW), INACTIVE)

    def test_invalid_row_is_logged_and_ignored(self):
        self.store.save(SessionState(True, NOW + timedelta(hours=1)))
        self._sql("UPDATE guardian_session SET until = 'not a date'")
        with self.assertLogs("guardian.session_state", level="WARNING"):
            self.assertEqual(self.store.load(NOW), INACTIVE)

    def test_past_pause_dropped(self):
        self.store.save(SessionState(True, NOW + timedelta(hours=1), NOW - timedelta(minutes=1)))
        self.assertIsNone(self.store.load(NOW).paused_until)

    def test_naive_rejected(self):
        with self.assertRaises(ValueError):
            self.store.save(SessionState(True, datetime(2026, 1, 1)))

    def test_clear_when_missing(self):
        self.store.clear()

    def test_pending_survives_inactive_and_expired_session(self):
        self.store.save(SessionState(False, pending=True))
        self.assertTrue(self.store.load(NOW).pending)
        self.store.save(
            SessionState(True, NOW - timedelta(minutes=1), pending=True, windows=(("09:00", "12:00"),))
        )
        kept = self.store.load(NOW)
        self.assertFalse(kept.active)
        self.assertTrue(kept.pending)
        self.assertEqual(kept.windows, (("09:00", "12:00"),))

    def test_nothing_to_keep_removes_the_row(self):
        self.store.save(SessionState(True, NOW + timedelta(hours=1)))
        self.store.save(SessionState(False))
        self.assertFalse(self.store.has_saved_state())
        self.assertEqual(self.store.load(NOW), INACTIVE)

    def test_bad_windows_are_rejected_on_load(self):
        self.store.save(SessionState(False, pending=True))
        self._sql("UPDATE guardian_session SET windows_json = ?", '[["25:00", "26:00"]]')
        with self.assertLogs("guardian.session_state", level="WARNING"):
            self.assertEqual(self.store.load(NOW), INACTIVE)


class LegacyJsonImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.store = SessionStore(self.dir / "g.sqlite3", legacy_json=self.dir / "session.json")

    def write_legacy(self, **overrides):
        data = {
            "schema_version": 1,
            "active": True,
            "until": (NOW + timedelta(hours=1)).isoformat(),
            "paused_until": None,
            "topic": "BigQuery",
            "source": "bank-only",
            "pending": True,
            "windows": [["09:00", "12:00"]],
        }
        data.update(overrides)
        (self.dir / "session.json").write_text(json.dumps(data), encoding="utf-8")

    def test_old_session_json_is_imported_once_and_renamed(self):
        self.write_legacy()
        state = self.store.load(NOW)
        self.assertEqual((state.topic, state.pending, state.active), ("BigQuery", True, True))
        self.assertFalse((self.dir / "session.json").exists())
        self.assertTrue((self.dir / "session.json.migrated").exists())
        self.assertEqual(self.store.load(NOW), state)

    def test_import_never_overwrites_a_saved_row(self):
        self.store.save(SessionState(True, NOW + timedelta(hours=2), topic="Newer"))
        self.write_legacy()
        self.assertEqual(self.store.load(NOW).topic, "Newer")
        self.assertTrue((self.dir / "session.json.migrated").exists())

    def test_corrupt_legacy_file_is_set_aside_and_logged(self):
        (self.dir / "session.json").write_text("{not json", encoding="utf-8")
        with self.assertLogs("guardian.session_state", level="WARNING"):
            self.assertEqual(self.store.load(NOW), INACTIVE)
        self.assertTrue((self.dir / "session.json.corrupt").exists())


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
