"""The insistent quiz window comes back after a close or minimize, waits during full screen, ignores
input for a moment and says so, and has no exit button. The normal window can be postponed. Siguiente and
Posponer stay in view, and only the final question of a prompt is bold."""

import tkinter as tk
import unittest
from tkinter import ttk

from guardian.core import Question
from guardian.questions import FALLBACK_GCP
from guardian.quiz_window import RESHOW_SECONDS, QuizWindow, clean_prompt, split_prompt

LONG_PROMPT = (
    "Your organization currently uses:\n"
    "•\tApache Hadoop clusters for processing multiple large data sets, "
    * 4
    + "\n•\tApache Airflow to orchestrate hundreds of pipelines.\n\n"
    + "You need a new architecture with minimal changes. What should you do?"
)


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

    def make(self, insistent=True, questions=None):
        return QuizWindow(
            self.root,
            questions=questions or FALLBACK_GCP[:5],
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
        self.assertNotIn("Posponer", self.buttons(quiz))
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
        self.assertIn("Posponer", self.buttons(quiz))
        quiz.window.tk.call(quiz.window.protocol("WM_DELETE_WINDOW"))
        self.assertEqual(self.left, [True])
        self.assertFalse(quiz.alive)

    def test_the_input_guard_is_announced_and_then_cleared(self):
        quiz = self.make()
        self.assertIn("2 segundos", quiz.guard_text.get())
        quiz._set_input(True)
        self.assertEqual(quiz.guard_text.get(), "")

    def test_enter_does_nothing_during_the_guard_and_answers_after(self):
        quiz = self.make()
        quiz.selected.set(FALLBACK_GCP[0].answer_index)
        quiz._next()
        self.assertEqual(quiz.answers, [])
        quiz._set_input(True)
        quiz.selected.set(FALLBACK_GCP[0].answer_index)
        quiz.window.event_generate("<Return>")
        self.assertEqual(quiz.answers, [FALLBACK_GCP[0].answer_index])

    def test_escape_postpones_a_normal_quiz(self):
        quiz = self.make(insistent=False)
        quiz.window.event_generate("<Escape>")
        self.assertEqual(self.left, [True])

    def test_next_and_postpone_stay_in_view_with_a_long_question(self):
        options = tuple(
            f"Option {letter}: " + "a long answer about Dataproc and Composer " * 3 for letter in "ABCD"
        )
        questions = [Question(LONG_PROMPT, options, 1, "x", uid=f"q{i}") for i in range(5)]
        quiz = self.make(insistent=False, questions=questions)
        quiz.window.geometry("800x600")
        self.root.update()
        bottom = quiz.window.winfo_rooty() + quiz.window.winfo_height()
        for button in (
            quiz.finish,
            *[b for b in quiz.finish.master.winfo_children() if b is not quiz.finish],
        ):
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(), bottom)
        self.assertGreater(quiz.canvas.bbox("all")[3], quiz.canvas.winfo_height())  # the question scrolls

    def test_only_the_final_question_is_bold(self):
        questions = [Question(LONG_PROMPT, ("a", "b", "c", "d"), 0, "x", uid=f"q{i}") for i in range(5)]
        quiz = self.make(questions=questions)
        self.assertEqual(quiz.question.cget("text"), "What should you do?")
        self.assertNotIn("\t", quiz.context.cget("text"))
        self.assertIn("bold", str(quiz.question.cget("font")))
        self.assertNotIn("bold", str(quiz.context.cget("font")))


class PromptTests(unittest.TestCase):
    def test_bullets_lose_their_tabs_and_keep_their_lines(self):
        text = clean_prompt("It uses:\n•\tHadoop  clusters.\n•\tAirflow.\n\n\n\nWhat now?")
        self.assertEqual(text, "It uses:\n• Hadoop clusters.\n• Airflow.\n\nWhat now?")

    def test_bullets_glued_in_one_line_get_their_own_lines(self):
        self.assertEqual(clean_prompt("Usa: • Hadoop. • Airflow."), "Usa:\n• Hadoop.\n• Airflow.")

    def test_the_last_sentence_is_the_question(self):
        self.assertEqual(
            split_prompt("You run Hadoop. You need less work. What should you do?"),
            ("You run Hadoop. You need less work.", "What should you do?"),
        )
        self.assertEqual(
            split_prompt("Usa Hadoop y Airflow. ¿Qué debería hacer?"),
            ("Usa Hadoop y Airflow.", "¿Qué debería hacer?"),
        )

    def test_a_prompt_without_a_question_mark_has_no_bold_part(self):
        self.assertEqual(split_prompt("Choose the best service:"), ("Choose the best service:", ""))

    def test_a_single_question_is_all_question(self):
        self.assertEqual(split_prompt("Which service stores blobs?"), ("", "Which service stores blobs?"))


if __name__ == "__main__":
    unittest.main()
