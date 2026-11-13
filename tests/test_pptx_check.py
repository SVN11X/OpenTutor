from pathlib import Path
import tempfile
import unittest
import zipfile

from guardian.evidence.pptx_check import check_pptx
from guardian.evidence.safe_zip import UnsafeArchive, open_safe

NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')


def slide_xml(title: str, body: str, titled: bool = True) -> str:
    ph = '<p:nvPr><p:ph type="title"/></p:nvPr>' if titled else "<p:nvPr/>"
    return (f'<p:sld {NS}><p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="1" name="t"/><p:cNvSpPr/>{ph}</p:nvSpPr>'
            f'<p:txBody><a:p><a:r><a:t>{title}</a:t></a:r></a:p><a:p><a:r><a:t>{body}</a:t></a:r></a:p></p:txBody>'
            f'</p:sp></p:spTree></p:cSld></p:sld>')


class PptxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def make(self, name="d.pptx", slides=None, extra=None):
        path = self.dir / name
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for i, xml in enumerate(slides or [], 1):
                z.writestr(f"ppt/slides/slide{i}.xml", xml)
            for n, data in (extra or {}).items():
                z.writestr(n, data)
        return path

    def good(self, n=5):
        return [slide_xml(f"Title {i}", f"BigQuery partitioning point {i}") for i in range(n)]

    def test_passed_is_not_credit(self):
        r = check_pptx(self.make(slides=self.good()), expected_slides=5, required_terms=("BigQuery",))
        self.assertEqual(r.status, "passed")
        self.assertFalse(r.credit_eligible)

    def test_wrong_slide_count_fails(self):
        self.assertEqual(check_pptx(self.make(slides=self.good(3)), expected_slides=5).status, "failed")

    def test_missing_terms_needs_review(self):
        r = check_pptx(self.make(slides=self.good()), expected_slides=5, required_terms=("Dataflow",))
        self.assertEqual(r.status, "needs_review")

    def test_placeholder_and_duplicates_fail(self):
        slides = self.good(4) + [slide_xml("Click to edit Master title style", "x")]
        self.assertEqual(check_pptx(self.make(slides=slides), expected_slides=5).status, "failed")
        dup = [slide_xml("Same", "same")] * 2
        self.assertEqual(check_pptx(self.make("dup.pptx", slides=dup), expected_slides=2).status, "failed")

    def test_macros_rejected_without_parsing(self):
        p = self.make(slides=self.good(), extra={"ppt/vbaProject.bin": b"MZ"})
        r = check_pptx(p, expected_slides=5)
        self.assertEqual((r.status, r.checks[0].name), ("failed", "macros"))

    def test_zip_slip_and_bomb_rejected(self):
        slip = self.make("slip.pptx", slides=self.good(), extra={"../evil.txt": b"x"})
        self.assertEqual(check_pptx(slip).checks[0].name, "archive")
        bomb = self.make("bomb.pptx", slides=self.good(), extra={"ppt/media/big.bin": b"\0" * (30 * 1024 * 1024)})
        with self.assertRaises(UnsafeArchive):
            open_safe(bomb)

    def test_xml_entities_rejected(self):
        evil = '<!DOCTYPE x [<!ENTITY a "aaaa">]>' + slide_xml("T", "&a;")
        self.assertEqual(check_pptx(self.make(slides=[evil]), expected_slides=1).checks[0].name, "xml")

    def test_not_a_zip_and_wrong_extension(self):
        junk = self.dir / "junk.pptx"
        junk.write_bytes(b"not a zip")
        self.assertEqual(check_pptx(junk).status, "failed")
        self.assertEqual(check_pptx(self.dir / "a.pdf").status, "failed")


if __name__ == "__main__":
    unittest.main()
