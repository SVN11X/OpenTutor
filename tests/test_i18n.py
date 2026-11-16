"""Every text key used in the code exists in locales/es.json, and no text in the file is unused."""

import ast
import string
import unittest
from pathlib import Path

from guardian.i18n import messages, t

SRC = Path(__file__).resolve().parents[1] / "src" / "guardian"


def used_keys() -> set[str]:
    """Literal keys passed to t(...) anywhere in the package."""
    keys = set()
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "t"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                keys.add(node.args[0].value)
    return keys


class LocaleTests(unittest.TestCase):
    def test_every_used_key_exists(self):
        self.assertEqual(sorted(used_keys() - set(messages())), [])

    def test_no_text_is_left_unused(self):
        self.assertEqual(sorted(set(messages()) - used_keys()), [])

    def test_texts_are_not_empty_and_placeholders_are_named(self):
        for key, text in messages().items():
            with self.subTest(key=key):
                self.assertTrue(text.strip())
                names = [name for _, name, _, _ in string.Formatter().parse(text) if name is not None]
                self.assertTrue(all(name.isidentifier() for name in names), names)

    def test_text_comes_from_the_file(self):
        self.assertEqual(t("tray.open"), "Abrir panel")

    def test_a_missing_key_fails_loudly(self):
        with self.assertRaises(KeyError):
            t("no.such.key")


if __name__ == "__main__":
    unittest.main()
