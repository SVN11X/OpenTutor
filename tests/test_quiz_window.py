"""The insistent quiz window comes back after a close or minimize, waits during full screen, ignores
input for a moment, and has no exit button. The normal window can be postponed."""

import tkinter as tk
import unittest
from tkinter import ttk

from guardian.questions import FALLBACK_GCP
from guardian.quiz_window import RESHOW_SECONDS, QuizWindow


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class QuizWindowTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as err:
            self.skipTest(f"No display for Tk: {err}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.clock = FakeClock()
        self.busy = None
        self.done, self.left = [], []

    def make(self, insistent=True):
        return QuizWindow(
            self.root,
            questions=FALLBACK_GCP[:5],
            source="fallback-reviewed",
            insistent=insistent,
            on_done=self.done.append,
            on_leave=lambda: self.left.append(True),
            busy=lambda: self.busy,
            clock=self.clock,
        )

    def buttons(self, quiz):
        found, stack = [], [quiz.window]
        while stack:
            widget = stack.pop()
            stack.extend(widget.winfo_children())
            if isinstance(widget, ttk.Button):
                found.append(widget.cget("text"))
        return found

    def test_insistent_has_no_exit_button_and_ignores_input_at_first(self):
        quiz = self.make()
        self.root.update()
        self.assertNotIn("Posponer / salir", self.buttons(quiz))
        self.assertEqual(str(quiz.finish.cget("state")), "disabled")
        self.assertTrue(all(str(r.cget("state")) == "disabled" for r in quiz.choices.winfo_children()))
        self.assertEqual(quiz.window.attributes("-topmost"), 1)

    def test_closing_comes_back_after_a_few_seconds(self):
        quiz = self.make()
        quiz.window.tk.call(quiz.window.protocol("WM_DELETE_WINDOW"))  # what the X button does
        self.assertEqual(quiz.window.state(), "withdrawn")
        quiz._watch()
        self.assertEqual(quiz.window.state(), "withdrawn")
        self.clock.now += RESHOW_SECONDS
        quiz._watch()
        self.assertEqual(quiz.window.state(), "normal")

    def test_minimizing_comes_back_after_a_few_seconds(self):
        quiz = self.make()
        self.root.update()
        quiz.window.iconify()
        self.root.update()
        quiz._watch()
        self.assertEqual(quiz.window.state(), "iconic")
        self.clock.now += RESHOW_SECONDS
        quiz._watch()
        self.assertEqual(quiz.window.state(), "normal")

    def test_waits_during_full_screen_and_returns_after(self):
        quiz = self.make()
        self.busy = "fullscreen"
        quiz._watch()
        self.assertEqual(quiz.window.state(), "withdrawn")
        self.assertEqual(quiz.waiting_for, "fullscreen")
        self.busy = None
        quiz._watch()
        self.assertEqual(quiz.window.state(), "normal")

    def test_five_answers_close_the_window_and_report(self):
        quiz = self.make()
        quiz._set_input(True)
        for q in FALLBACK_GCP[:5]:
            quiz.selected.set(q.answer_index)
            quiz._next()
        self.assertEqual(self.done, [[q.answer_index for q in FALLBACK_GCP[:5]]])
        self.assertFalse(quiz.alive)

    def test_normal_quiz_can_be_postponed(self):
        quiz = self.make(insistent=False)
        self.assertIn("Posponer / salir", self.buttons(quiz))
        quiz.window.tk.call(quiz.window.protocol("WM_DELETE_WINDOW"))
        self.assertEqual(self.left, [True])
        self.assertFalse(quiz.alive)


if __name__ == "__main__":
    unittest.main()
