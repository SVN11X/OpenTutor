"""The panel as the owner meets it: Hoy shows the state once and only the buttons that act now, with the
main one marked; Emergencia stands apart from the exits and says what it does; Ajustes has no Guardar
button and saves the study hours by itself."""

import os
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest import mock

from guardian import desktop
from guardian.fieldnotes import BANK_ENV
from guardian.widgets import PRIMARY


class FakeTray:
    def __init__(self, _put):
        pass

    def start(self):
        return True

    def stop(self):
        pass


def widgets(top, kind):
    found, stack = [], [top]
    while stack:
        widget = stack.pop()
        stack.extend(widget.winfo_children())
        if isinstance(widget, kind):
            found.append(widget)
    return found


class PanelTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as err:
            self.skipTest(f"No display for Tk: {err}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        for patch in (
            mock.patch.dict(os.environ, {"LOCALAPPDATA": tmp.name, BANK_ENV: str(Path(tmp.name) / "none")}),
            mock.patch.object(desktop, "TrayIcon", FakeTray),
            mock.patch.object(desktop.autostart, "refresh_if_stale", lambda *_a: False),
            mock.patch.object(desktop.autostart, "is_enabled", lambda *_a: False),
            mock.patch.object(desktop.GuardianUI, "_refresh_health", lambda self, repeat=True: None),
            mock.patch("guardian.desktop.SAVE_DELAY_MS", 10),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.ui = desktop.GuardianUI(self.root)
        self.addCleanup(self.ui.store.close)  # Windows cannot delete an open database
        self.addCleanup(self.cancel_timers)  # the tick and the tray poll must not outlive this test
        self.root.update_idletasks()

    def cancel_timers(self):
        for job in self.root.tk.splitlist(self.root.tk.call("after", "info")):
            self.root.after_cancel(job)

    def buttons(self):
        self.ui._refresh_views()
        return [(b.cget("text"), str(b.cget("style")) == PRIMARY) for b in self.ui.controls.winfo_children()]

    def test_hoy_shows_the_buttons_of_each_state(self):
        self.assertEqual(self.buttons(), [("Iniciar estudio (60 min)", True), ("Hacer examen ahora", False)])
        self.ui._start()
        self.assertEqual(
            self.buttons(), [("Pausar 15 min", True), ("Hacer examen ahora", False), ("Terminar", False)]
        )
        self.ui._pause()
        self.assertEqual(self.buttons()[0], ("Reanudar", True))
        self.ui._resume()
        self.assertEqual(self.buttons()[0], ("Pausar 15 min", True))
        self.ui._stop()
        self.assertEqual(self.buttons()[0], ("Iniciar estudio (60 min)", True))

    def test_the_state_is_said_once(self):
        self.ui._start()
        self.ui.pending = True
        self.ui.wait_reason = "hay una app en pantalla completa"
        self.ui._refresh_views()
        self.assertEqual(
            self.ui.headline_text.get(), "● Examen pendiente, en espera: hay una app en pantalla completa"
        )
        self.assertEqual(self.ui.counter_text.get(), "")
        self.assertEqual(self.ui.status.get(), "")

    def test_emergencia_is_apart_from_the_exits_and_explained(self):
        buttons = {b.cget("text"): b for b in widgets(self.root, ttk.Button)}
        emergency, leave = buttons["Emergencia"], buttons["Salir"]
        self.assertIsNot(emergency.master, leave.master)
        self.assertEqual(str(leave.pack_info()["side"]), "right")
        texts = [str(label.cget("text")) for label in widgets(emergency.master, ttk.Label)]
        self.assertTrue(any("descarta el examen pendiente" in text for text in texts))

    def test_ajustes_has_no_save_button_and_saves_the_hours(self):
        texts = [b.cget("text") for b in widgets(self.root, ttk.Button)]
        self.assertNotIn("Guardar ajustes", texts)
        self.ui.schedule.set("08:00-12:00")
        deadline = time.monotonic() + 5
        while self.ui.windows != (("08:00", "12:00"),) and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.02)
        self.assertEqual(self.ui.windows, (("08:00", "12:00"),))
        self.assertIn("Cambios guardados", self.ui.settings_status.get())

    def test_a_bad_schedule_is_reported_in_ajustes(self):
        self.ui.schedule.set("ocho")
        deadline = time.monotonic() + 5
        while "No se guardó" not in self.ui.settings_status.get() and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.02)
        self.assertIn("No se guardó", self.ui.settings_status.get())
        self.assertEqual(self.ui.windows, ())


if __name__ == "__main__":
    unittest.main()
