"""The gallery: PNG writer, border crop, sample bank and README, which need no window."""

import importlib.util
import struct
import tempfile
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


class SampleBankTests(unittest.TestCase):
    def test_sample_bank_loads_as_a_fieldnotes_bank_with_five_domains(self):
        from guardian.fieldnotes import domain_names, load_pool

        with tempfile.TemporaryDirectory() as d:
            bank = gallery.write_sample_bank(Path(d))
            self.assertEqual(len(load_pool(bank)), 10)
            self.assertEqual([i for i, _name, _w in domain_names(bank)], [1, 2, 3, 4, 5])
            self.assertEqual(sum(w for _i, _name, w in domain_names(bank)), 100)

    def test_readme_lists_every_image_with_its_title(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            gallery.write_readme(out, [("01-a.png", "Hoy", "Nota uno.")], sample=True)
            text = (out / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Hoy", text)
        self.assertIn("![Hoy](01-a.png)", text)
        self.assertIn("sample bank", text)


if __name__ == "__main__":
    unittest.main()
