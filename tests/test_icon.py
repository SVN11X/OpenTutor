"""Guardian's icon: a valid ICO with every size Windows asks for, identical to what the script draws."""

import importlib.util
import struct
import unittest
from pathlib import Path

from guardian.tray import ICON_PATH, MENU_ITEMS

SPEC = importlib.util.spec_from_file_location(
    "make_icon", Path(__file__).resolve().parents[1] / "scripts" / "make_icon.py"
)
make_icon = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(make_icon)


class IconTests(unittest.TestCase):
    def test_icon_file_lists_every_size(self):
        data = ICON_PATH.read_bytes()
        reserved, kind, count = struct.unpack("<HHH", data[:6])
        self.assertEqual((reserved, kind), (0, 1))
        sizes = [data[6 + 16 * i] or 256 for i in range(count)]
        self.assertEqual(sizes, list(make_icon.SIZES))

    def test_committed_icon_matches_the_script(self):
        self.assertEqual(ICON_PATH.read_bytes(), make_icon.build(), "run python scripts/make_icon.py")

    def test_corners_are_transparent_and_center_is_drawn(self):
        rgba = make_icon.render(32)
        self.assertEqual(rgba[3], 0)  # top left pixel alpha
        center = (16 * 32 + 16) * 4
        self.assertEqual(rgba[center + 3], 255)

    def test_tray_start_label_fits_both_session_modes(self):
        self.assertIn(("start", "Iniciar estudio"), MENU_ITEMS)


if __name__ == "__main__":
    unittest.main()
