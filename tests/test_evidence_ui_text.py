import unittest

from guardian.evidence_ui import CHECK_LABELS, STATUS_LABELS, check_line, status_label
from guardian.task_store import FAILED, NEEDS_REVIEW, PENDING_DEFENSE, VALIDATED


class EvidenceTextTests(unittest.TestCase):
    def test_every_status_has_icon_and_text(self):
        for status in (FAILED, NEEDS_REVIEW, PENDING_DEFENSE, VALIDATED):
            label = status_label(status)
            self.assertTrue(label[0] in "✖◐◌✔" and len(label) > 3, label)
        self.assertEqual(len(set(STATUS_LABELS.values())), 4)

    def test_check_lines_use_plain_spanish_and_show_the_detail(self):
        self.assertEqual(check_line("macros", True, ""), "✔ Sin macros")
        self.assertEqual(
            check_line("slide_count", False, "3 diapositivas, se esperaban 5"),
            "✖ Cantidad de diapositivas: 3 diapositivas, se esperaban 5",
        )
        self.assertEqual(check_line("unknown_check", True, ""), "✔ unknown_check")

    def test_labels_cover_every_check_the_rubric_can_emit(self):
        import re
        from pathlib import Path

        source = (Path(__file__).parent.parent / "src" / "guardian" / "evidence" / "pptx_check.py").read_text(
            encoding="utf-8"
        )
        emitted = set(re.findall(r'(?:Check|_fail)\(\s*"(\w+)"', source))
        self.assertTrue(emitted)
        self.assertLessEqual(emitted, set(CHECK_LABELS), emitted - set(CHECK_LABELS))


if __name__ == "__main__":
    unittest.main()
