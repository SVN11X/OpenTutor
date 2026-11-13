import sqlite3
import tempfile
import unittest
import zlib
from pathlib import Path
from random import Random

from guardian.evidence.check import check_file
from guardian.evidence.defense import build_defense
from guardian.evidence.md_check import check_markdown
from guardian.evidence.pdf_check import MAX_STREAM_OUT, check_pdf
from guardian.task_store import TaskStore

GOOD_MD = """# Overview

BigQuery is a serverless warehouse. This section has enough words to count as real content here.

## Partitioning

Partitioning splits a table by date or integer range so queries read less data and cost less money.

## Clustering

Clustering sorts rows by chosen columns inside each partition to prune blocks during scans of data.
"""


def pdf_bytes(pages: int = 2, extra: bytes = b"", text: str = "BigQuery partitioning") -> bytes:
    """A tiny hand-built PDF with a flate content stream that shows some text."""
    content = zlib.compress(f"BT /F1 12 Tf ({text}) Tj ET".encode())
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [] /Count 0 >>"]
    objs += [b"<< /Type /Page /Parent 2 0 R /Contents 9 0 R >>" for _ in range(pages)]
    body = b"%PDF-1.4\n"
    for i, obj in enumerate(objs, 1):
        body += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    body += b"9 0 obj\n<< /Filter /FlateDecode >>\nstream\n" + content + b"\nendstream\nendobj\n" + extra
    return body + b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"


class FileCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, name: str, data: bytes | str) -> Path:
        path = self.dir / name
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return path


class MarkdownTests(FileCase):
    def test_good_document_passes_with_titles(self):
        r = check_markdown(self.write("a.md", GOOD_MD), expected_sections=3, required_terms=("BigQuery",))
        self.assertEqual(r.status, "passed")
        self.assertEqual(r.titles, ("Overview", "Partitioning", "Clustering"))
        self.assertFalse(r.credit_eligible)
        self.assertEqual((r.kind, r.unit_count), ("md", 3))

    def test_too_few_sections_empty_section_and_placeholders_fail(self):
        self.assertEqual(check_markdown(self.write("a.md", GOOD_MD), expected_sections=5).status, "failed")
        empty = GOOD_MD + "\n## Empty heading\n"
        self.assertEqual(check_markdown(self.write("b.md", empty), expected_sections=3).status, "failed")
        todo = GOOD_MD.replace("serverless", "TO" + "DO serverless")
        self.assertEqual(check_markdown(self.write("c.md", todo), expected_sections=3).status, "failed")
        lorem = GOOD_MD.replace("serverless", "Lorem" + " Ipsum")
        self.assertEqual(check_markdown(self.write("d.md", lorem), expected_sections=3).status, "failed")

    def test_the_spanish_word_todo_is_not_a_placeholder(self):
        text = GOOD_MD.replace("serverless", "todo el almacén")
        self.assertEqual(check_markdown(self.write("e.md", text), expected_sections=3).status, "passed")

    def test_headings_inside_code_fences_do_not_count(self):
        fenced = GOOD_MD + "\n```\n# not a heading\n```\n"
        self.assertEqual(check_markdown(self.write("f.md", fenced), expected_sections=3).unit_count, 3)

    def test_duplicate_headings_fail_and_missing_terms_need_review(self):
        dup = GOOD_MD.replace("## Clustering", "## Partitioning")
        self.assertEqual(check_markdown(self.write("g.md", dup), expected_sections=3).status, "failed")
        r = check_markdown(self.write("h.md", GOOD_MD), expected_sections=3, required_terms=("Dataflow",))
        self.assertEqual(r.status, "needs_review")

    def test_bad_files(self):
        self.assertEqual(check_markdown(self.write("x.txt", "# a")).checks[0].name, "extension")
        self.assertEqual(check_markdown(self.write("bin.md", b"\x00\x01")).status, "failed")
        self.assertEqual(check_markdown(self.write("latin.md", "# é".encode("latin-1"))).status, "failed")
        big = self.write("big.md", "# t\n" + "word " * 500_000)
        self.assertEqual(check_markdown(big).status, "failed")
        self.assertEqual(check_markdown(self.dir / "missing.md").status, "failed")


class PdfTests(FileCase):
    def test_good_pdf_passes(self):
        r = check_pdf(self.write("a.pdf", pdf_bytes(2)), expected_pages=2, required_terms=("BigQuery",))
        self.assertEqual((r.status, r.unit_count, r.kind), ("passed", 2, "pdf"))

    def test_wrong_page_count_fails(self):
        self.assertEqual(check_pdf(self.write("a.pdf", pdf_bytes(2)), expected_pages=5).status, "failed")

    def test_unreadable_terms_need_review_never_failure(self):
        r = check_pdf(self.write("a.pdf", pdf_bytes(2)), expected_pages=2, required_terms=("Dataflow",))
        self.assertEqual(r.status, "needs_review")

    def test_javascript_is_rejected_in_plain_and_in_compressed_streams(self):
        plain = pdf_bytes(1, extra=b"<< /S /JavaScript /JS (app.alert(1)) >>\n")
        self.assertEqual(check_pdf(self.write("p.pdf", plain)).checks[2].name, "active_content")
        self.assertEqual(check_pdf(self.write("p.pdf", plain)).status, "failed")
        hidden = zlib.compress(b"<< /S /Launch /F (cmd.exe) >>")
        packed = pdf_bytes(
            1, extra=b"10 0 obj\n<< /Type /ObjStm >>\nstream\n" + hidden + b"\nendstream\nendobj\n"
        )
        r = check_pdf(self.write("c.pdf", packed))
        self.assertEqual(r.status, "failed")
        self.assertIn("Launch", r.checks[2].detail)

    def test_decompression_bomb_is_rejected(self):
        bomb = zlib.compress(b"\0" * (MAX_STREAM_OUT + 1024))
        data = pdf_bytes(1, extra=b"11 0 obj\n<<>>\nstream\n" + bomb + b"\nendstream\nendobj\n")
        r = check_pdf(self.write("bomb.pdf", data), expected_pages=1)
        self.assertEqual((r.status, r.checks[0].name), ("failed", "safe_streams"))

    def test_not_a_pdf_truncated_and_wrong_extension(self):
        self.assertEqual(check_pdf(self.write("n.pdf", b"hello")).checks[0].name, "readable")
        self.assertEqual(check_pdf(self.write("t.pdf", pdf_bytes(1)[:-40])).status, "failed")
        self.assertEqual(check_pdf(self.write("n.txt", b"%PDF-1.4")).checks[0].name, "extension")

    def test_ordinary_names_with_js_prefix_are_not_active_content(self):
        data = pdf_bytes(1, extra=b"<< /JSON-like /JSX 1 /Jsx 2 >>\n")
        self.assertEqual(check_pdf(self.write("ok.pdf", data), expected_pages=1).status, "passed")


class DispatchAndDefenseTests(FileCase):
    def test_check_file_dispatches_by_kind(self):
        self.assertEqual(check_file("md", self.write("a.md", GOOD_MD), 3, ()).kind, "md")
        self.assertEqual(check_file("pdf", self.write("a.pdf", pdf_bytes(1)), 1, ()).kind, "pdf")
        with self.assertRaises(ValueError):
            check_file("docx", self.dir / "a.docx", 1, ())

    def test_markdown_defense_asks_about_sections(self):
        result = check_markdown(
            self.write("a.md", GOOD_MD), expected_sections=3, required_terms=("BigQuery",)
        )
        questions = build_defense(result, ("BigQuery",), Random(2))
        self.assertEqual(len(questions), 3)
        self.assertIn("secciones", questions[0].prompt)
        self.assertEqual(questions[0].options[questions[0].answer_index], "3")

    def test_pdf_defense_is_the_page_count_only(self):
        result = check_pdf(self.write("a.pdf", pdf_bytes(3)), expected_pages=3)
        questions = build_defense(result, (), Random(2))
        self.assertEqual(len(questions), 1)
        self.assertIn("páginas", questions[0].prompt)
        self.assertEqual(questions[0].options[questions[0].answer_index], "3")

    def test_failed_pdf_has_no_defense(self):
        self.assertEqual(build_defense(check_pdf(self.dir / "none.pdf")), [])


class TaskKindTests(FileCase):
    def test_kinds_are_stored_and_unknown_kinds_rejected(self):
        store = TaskStore(self.dir / "g.sqlite3")
        store.add_task("Notes", 3, "", kind="md")
        store.add_task("Slides", 5)
        self.assertEqual([t.kind for t in store.list_tasks()], ["md", "pptx"])
        with self.assertRaises(ValueError):
            store.add_task("x", 1, "", kind="exe")

    def test_database_made_before_kinds_is_migrated_and_keeps_its_tasks(self):
        db = self.dir / "old.sqlite3"
        con = sqlite3.connect(str(db))
        con.execute(
            "CREATE TABLE guardian_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
            "expected_slides INTEGER NOT NULL, required_terms_json TEXT NOT NULL, created_at TEXT NOT NULL, "
            "archived INTEGER NOT NULL DEFAULT 0)"
        )
        con.execute(
            "INSERT INTO guardian_tasks (title, expected_slides, required_terms_json, created_at) "
            "VALUES ('Old deck', 4, '[]', '2026-11-01')"
        )
        con.commit()
        con.close()
        tasks = TaskStore(db).list_tasks()
        self.assertEqual([(t.title, t.kind, t.expected_slides) for t in tasks], [("Old deck", "pptx", 4)])


if __name__ == "__main__":
    unittest.main()
