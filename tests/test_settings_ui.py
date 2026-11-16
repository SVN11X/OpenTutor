"""The "Qué te pregunto" section: mode mapping, bank status, domain labels, reading the form, saving
by itself after a change, and the bank found by itself shown in its field."""

import json
import os
import tempfile
import time
import tkinter as tk
import unittest
from dataclasses import replace
from pathlib import Path
from tkinter import ttk
from unittest import mock

from guardian.fieldnotes import BANK_ENV, find_bank_path
from guardian.settings_store import DEFAULTS, SettingsStore
from guardian.settings_ui import (
    LANGUAGE_LABELS,
    QuestionSettingsPanel,
    bank_summary,
    domain_labels,
    quiz_mode,
)


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
        self.bank = write_bank(Path(self.tmp.name))
        env = mock.patch.dict(os.environ, {BANK_ENV: str(self.bank)})
        env.start()
        self.addCleanup(env.stop)
        self.panel = self.make_panel()
        self.root.update_idletasks()  # theme setup runs now, not in a later test's update

    def make_panel(self, settings=DEFAULTS):
        return QuestionSettingsPanel(
            ttk.Frame(self.root), self.store, settings, self.saved.append, self.messages.append
        )

    def wait_for_save(self):
        deadline = time.monotonic() + 5
        while not self.saved and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.02)

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

    def test_the_language_combobox_saves_english(self):
        self.panel.language_var.set(LANGUAGE_LABELS["en"])
        self.panel.save()
        self.assertEqual(self.saved[-1].language, "en")
        self.assertEqual(self.store.load().language, "en")

    def test_a_change_saves_by_itself_without_a_button(self):
        with mock.patch("guardian.settings_ui.SAVE_DELAY_MS", 10):
            self.panel.min_var.set("12")
            self.wait_for_save()
        self.assertEqual(self.store.load().interval_min, 12)
        self.assertIn("Cambios guardados", self.messages[-1])
        texts = [w.cget("text") for w in self.panel.frame.winfo_children() if isinstance(w, ttk.Button)]
        self.assertNotIn("Guardar ajustes", texts)

    def test_typing_saves_once_after_the_last_key(self):
        with mock.patch("guardian.settings_ui.SAVE_DELAY_MS", 200):
            for text in ("1", "15"):
                self.panel.max_var.set(text)
            self.wait_for_save()
        self.assertEqual([s.interval_max for s in self.saved], [15])

    def test_the_bank_found_by_itself_is_shown_in_its_field_and_saved_empty(self):
        self.assertEqual(self.panel.bank_var.get(), str(self.bank))
        self.assertNotIn(str(self.bank), self.panel.bank_text.get())
        self.panel.save()
        self.assertEqual(self.store.load().bank_path, "")

    def test_a_chosen_bank_folder_is_saved(self):
        other = Path(self.tmp.name) / "other"
        other.mkdir()
        self.panel.bank_var.set(str(other))
        self.panel.save()
        self.assertEqual(self.store.load().bank_path, str(other))
        self.assertIn("No encuentro el banco", self.panel.bank_text.get())

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
