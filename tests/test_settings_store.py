"""Settings survive a restart, reject bad input and never stop the agent from starting."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path

from guardian.settings_store import DEFAULTS, Settings, SettingsStore, validate


class SettingsStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "guardian.sqlite3"

    def test_defaults_match_the_owner_choices(self):
        self.assertEqual(SettingsStore(self.path).load(), DEFAULTS)
        self.assertEqual(DEFAULTS.source, "practice")
        self.assertTrue(DEFAULTS.insistent)
        self.assertEqual((DEFAULTS.interval_min, DEFAULTS.interval_max), (10, 25))

    def test_round_trip_survives_reopening(self):
        wanted = Settings(
            source="reviewed",
            domains=(4, 2, 2),
            interval_min=30,
            interval_max=60,
            bank_path=r"C:\bank",
            all_day=True,
            insistent=False,
        )
        saved = SettingsStore(self.path).save(wanted)
        self.assertEqual(saved.domains, (2, 4))
        self.assertEqual(SettingsStore(self.path).load(), saved)

    def test_invalid_values_are_rejected_before_writing(self):
        store = SettingsStore(self.path)
        for bad in (
            replace(DEFAULTS, interval_min=30, interval_max=20),
            replace(DEFAULTS, interval_min=1),
            replace(DEFAULTS, domains=(9,)),
            replace(DEFAULTS, source="web"),
            replace(DEFAULTS, question_set="other"),
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                store.save(bad)
        self.assertEqual(store.load(), DEFAULTS)

    def test_a_damaged_value_keeps_its_default_and_the_rest(self):
        store = SettingsStore(self.path)
        store.save(replace(DEFAULTS, all_day=True))
        with closing(sqlite3.connect(self.path)) as con, con:
            con.execute("UPDATE guardian_settings SET value_json = 'not json' WHERE key = 'source'")
            con.execute("UPDATE guardian_settings SET value_json = '7' WHERE key = 'domains'")
        with self.assertLogs("guardian.settings_store", level="WARNING"):
            loaded = store.load()
        self.assertEqual(loaded.source, DEFAULTS.source)
        self.assertEqual(loaded.domains, ())
        self.assertTrue(loaded.all_day)

    def test_unreadable_file_gives_defaults(self):
        self.path.write_bytes(b"this is not a database")
        with self.assertLogs("guardian.settings_store", level="WARNING"):
            self.assertEqual(SettingsStore(self.path).load(), DEFAULTS)

    def test_validate_rejects_non_integer_minutes(self):
        with self.assertRaises(ValueError):
            validate(replace(DEFAULTS, interval_min="10"))


if __name__ == "__main__":
    unittest.main()
