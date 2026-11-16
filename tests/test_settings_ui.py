"""The "Qué te pregunto" section: mode mapping, bank status, domain labels and reading the form."""

import json
import tempfile
import tkinter as tk
import unittest
from dataclasses import replace
from pathlib import Path
from tkinter import ttk

from guardian.fieldnotes import find_bank_path
from guardian.settings_store import DEFAULTS, SettingsStore
from guardian.settings_ui import QuestionSettingsPanel, bank_summary, domain_labels, quiz_mode


def write_bank(root: Path, *, domains: bool = True) -> Path:
    content = root / "GCP_Data_Engineer_Fieldnotes" / "content"
    content.mkdir(parents=True)
    questions = [
        {
            "text": f"Pregunta {i}?",
            "choices": [{"letter": x, "text": f"Opción {x}{i}"} for x in "ABCD"],
            "answer": ["A"],
            "status": "reviewed" if i < 3 else "unreviewed",
            "gradable": i < 3,
            "required": 1,
            "domain": 1 + i % 5,
            "explanation": "Fuente.",
        }
        for i in range(8)
    ]
    (content / "imported.json").write_text(json.dumps({"questions": questions}), encoding="utf-8")
    if domains:
        (content / "domains.json").write_text(
            json.dumps([{"id": 1, "name": "Designing", "weight": 22}]), encoding="utf-8"
        )
    return content.parent


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_quiz_mode_matches_the_saved_source(self):
        self.assertEqual(quiz_mode("practice"), "bank-practice")
        self.assertEqual(quiz_mode("reviewed"), "bank-only")
        self.assertEqual(quiz_mode("ollama"), "ollama")

    def test_bank_summary_counts_usable_and_reviewed_questions(self):
        bank = write_bank(Path(self.tmp.name))
        found, text = bank_summary(str(bank))
        self.assertTrue(found)
        self.assertIn("8 preguntas usables, 3 revisadas", text)

    def test_bank_summary_explains_a_missing_bank(self):
        found, text = bank_summary(str(Path(self.tmp.name) / "nothing"))
        self.assertFalse(found)
        self.assertIn("Elige la carpeta", text)

    def test_the_content_folder_is_accepted_too(self):
        bank = write_bank(Path(self.tmp.name))
        self.assertEqual(find_bank_path(bank / "content"), (bank / "content" / "imported.json").resolve())

    def test_domain_labels_use_bank_names_and_fill_the_rest(self):
        bank = write_bank(Path(self.tmp.name))
        labels = domain_labels(str(bank))
        self.assertEqual(labels[1], "1. Designing (22 %)")
        self.assertEqual(labels[5], "Dominio 5")


class FormTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as err:
            self.skipTest(f"No display for Tk: {err}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SettingsStore(Path(self.tmp.name) / "g.sqlite3")
        self.saved, self.messages = [], []
        self.panel = QuestionSettingsPanel(
            ttk.Frame(self.root), self.store, DEFAULTS, self.saved.append, self.messages.append
        )

    def test_all_domains_checked_are_saved_as_all(self):
        self.panel.save()
        self.assertEqual(self.saved[-1].domains, ())
        self.assertEqual(self.store.load(), self.saved[-1])

    def test_some_domains_and_minutes_are_saved(self):
        self.panel.domain_vars[1].set(False)
        self.panel.min_var.set("15")
        self.panel.max_var.set("40")
        self.panel.save()
        self.assertEqual(self.saved[-1].domains, (2, 3, 4, 5))
        self.assertEqual((self.saved[-1].interval_min, self.saved[-1].interval_max), (15, 40))

    def test_saving_the_section_keeps_settings_saved_elsewhere(self):
        self.store.save(replace(DEFAULTS, all_day=True))
        self.panel.save()
        self.assertTrue(self.store.load().all_day)

    def test_bad_input_is_reported_and_not_saved(self):
        for domain in self.panel.domain_vars.values():
            domain.set(False)
        self.panel.save()
        self.panel.domain_vars[1].set(True)
        self.panel.min_var.set("diez")
        self.panel.save()
        self.assertEqual(self.saved, [])
        self.assertIn("al menos un dominio", self.messages[0])
        self.assertIn("números enteros", self.messages[1])


if __name__ == "__main__":
    unittest.main()
