"""The gallery's PNG writer and border crop, which need no window."""

import importlib.util
import struct
import unittest
import zlib
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "gallery", Path(__file__).resolve().parents[1] / "scripts" / "gallery.py"
)
gallery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gallery)


class PngTests(unittest.TestCase):
    def test_png_has_header_size_and_pixels(self):
        rgb = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 9, 9, 9])  # 2 x 2
        data = gallery.png_bytes(2, 2, rgb)
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", data[16:24]), (2, 2))
        length = struct.unpack(">I", data[33:37])[0]
        self.assertEqual(data[37:41], b"IDAT")
        raw = zlib.decompress(data[41 : 41 + length])
        self.assertEqual(raw, b"\x00" + rgb[:6] + b"\x00" + rgb[6:])
        self.assertTrue(data.endswith(b"IEND\xaeB`\x82"))

    def test_crop_drops_side_and_bottom_borders_and_swaps_to_rgb(self):
        width, height, border = 4, 3, 1
        bgra = bytearray()
        for y in range(height):
            for x in range(width):
                bgra += bytes([x, y, 100 + x, 255])  # B, G, R, A
        new_w, new_h, rgb = gallery.crop_bgra(bytes(bgra), width, height, border)
        self.assertEqual((new_w, new_h), (2, 2))
        self.assertEqual(rgb[:3], bytes([101, 0, 1]))  # pixel x=1, y=0 as R, G, B
        self.assertEqual(len(rgb), 2 * 2 * 3)


if __name__ == "__main__":
    unittest.main()
