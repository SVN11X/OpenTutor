import sys
import unittest

from guardian.tray import MENU_ITEMS, TrayIcon


class TrayMenuTests(unittest.TestCase):
    def test_required_commands_present_and_unique(self):
        commands = [c for c, _ in MENU_ITEMS]
        self.assertEqual(len(commands), len(set(commands)))
        self.assertEqual(set(commands), {"open", "start", "pause", "stop", "emergency", "exit"})

    def test_labels_are_visible_text(self):
        self.assertTrue(all(label.strip() for _, label in MENU_ITEMS))

    @unittest.skipIf(sys.platform == "win32", "non-Windows fallback only")
    def test_start_reports_no_tray_off_windows(self):
        self.assertFalse(TrayIcon(lambda _c: None).start())


if __name__ == "__main__":
    unittest.main()
