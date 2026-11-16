"""Without a tray icon an insistent quiz would have no exit, so every quiz must behave as a normal one."""

import dataclasses
import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from guardian import desktop
from guardian.fieldnotes import BANK_ENV


def fake_tray(starts):
    class FakeTray:
        def __init__(self, _put):
            pass

        def start(self):
            return starts

        def stop(self):
            pass

    return FakeTray


class NoTrayTests(unittest.TestCase):
    def build(self, tray_starts):
        try:
            root = tk.Tk()
        except tk.TclError as err:
            self.skipTest(f"No display for Tk: {err}")
        root.withdraw()
        self.addCleanup(root.destroy)
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        for patch in (
            mock.patch.dict(os.environ, {"LOCALAPPDATA": tmp.name, BANK_ENV: str(Path(tmp.name) / "none")}),
            mock.patch.object(desktop, "TrayIcon", fake_tray(tray_starts)),
            mock.patch.object(desktop.autostart, "refresh_if_stale", lambda *_a: False),
            mock.patch.object(desktop.autostart, "is_enabled", lambda *_a: False),
            mock.patch.object(desktop.GuardianUI, "_refresh_health", lambda self, repeat=True: None),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        ui = desktop.GuardianUI(root)
        self.addCleanup(ui.store.close)  # Windows cannot delete an open database

        def cancel_timers():
            for job in root.tk.splitlist(root.tk.call("after", "info")):
                root.after_cancel(job)

        self.addCleanup(cancel_timers)
        return ui

    def test_without_a_tray_the_saved_setting_stays_but_is_not_applied(self):
        ui = self.build(False)
        ui.settings = dataclasses.replace(ui.settings, insistent=True)
        self.assertFalse(ui._insistent())
        self.assertTrue(ui.settings.insistent)

    def test_with_a_tray_insistent_applies(self):
        ui = self.build(True)
        ui.settings = dataclasses.replace(ui.settings, insistent=True)
        self.assertTrue(ui._insistent())

    def test_without_a_tray_a_pending_quiz_is_the_normal_one(self):
        ui = self.build(False)
        ui.settings = dataclasses.replace(ui.settings, insistent=True)
        ui._start()
        ui.pending = True
        ui._refresh_views()
        self.assertIn("Hacer examen ahora", ui.headline_text.get())


if __name__ == "__main__":
    unittest.main()
