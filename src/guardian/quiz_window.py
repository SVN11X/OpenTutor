"""The five-question quiz window.

In insistent mode (decision 0007) it opens centered, on top and with focus, has no exit button and comes
back a few seconds after it is closed or minimized. It hides while Windows reports a full-screen app or
presentation mode and returns when that ends. Keys and clicks are ignored for two seconds each time it
appears, so typing in another app cannot answer by accident, and a line says so. Emergencia and Salir stay
in the tray menu. Siguiente and Posponer live in a footer outside the scrolled question, so a long question
never hides them.
"""

from __future__ import annotations

import re
import time
import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import messagebox, ttk

from .core import QUESTIONS_PER_QUIZ, Question
from .i18n import t
from .presence import busy_reason
from .widgets import primary_style, scrolled

INPUT_GUARD_MS = 2000
WATCH_MS = 1000
RESHOW_SECONDS = 5.0
TEXT_FONT = ("Segoe UI", 11)
QUESTION_FONT = ("Segoe UI", 11, "bold")
# Where the last sentence of a prompt starts: after a sentence end or a line break.
_SENTENCE_START = re.compile(r"[.!?:]\s+|\n\s*")


def clean_prompt(text: str) -> str:
    """Imported bank text as plain lines: no tabs after bullets, one bullet per line, no runs of blanks."""
    text = text.replace("\t", " ")
    text = re.sub(r"\s*•\s*", "\n• ", text)
    lines = [" ".join(line.split()) for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def split_prompt(text: str) -> tuple[str, str]:
    """(context, question): the final question goes apart so only it is shown in bold.

    A prompt that does not end with a question mark has no question to set apart.
    """
    text = clean_prompt(text)
    if not text.endswith("?"):
        return text, ""
    starts = [m.end() for m in _SENTENCE_START.finditer(text, 0, len(text) - 1)]
    start = starts[-1] if starts else 0
    return text[:start].rstrip(), text[start:]


class QuizWindow:
    """One quiz. on_done gets the five answers. on_leave runs when a non-insistent quiz is postponed."""

    def __init__(
        self,
        root: tk.Tk,
        *,
        questions: Sequence[Question],
        source: str,
        insistent: bool,
        on_done: Callable[[list[int]], None],
        on_leave: Callable[[], None],
        busy: Callable[[], str | None] = busy_reason,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.questions, self.insistent = list(questions), insistent
        self.on_done, self.on_leave, self.busy, self.clock = on_done, on_leave, busy, clock
        self.current = 0
        self.answers: list[int] = []
        self.accepting = True  # False during the input guard, so Enter cannot answer either
        self.hidden_until: float | None = None  # set when the owner closes or minimizes an insistent quiz
        self.waiting_for: str | None = None  # full-screen or presentation reason while hidden
        self.window = tk.Toplevel(root)
        self.window.title(t("quiz.window_title"))
        self.window.minsize(600, 460)
        if not insistent and root.state() != "withdrawn":  # a transient of a hidden panel is invisible
            self.window.transient(root)
        self.selected = tk.IntVar(value=-1)
        self._build(source)
        self._render()
        self.window.bind("<Return>", lambda _e: self._next())
        if insistent:
            self.window.protocol("WM_DELETE_WINDOW", self._hide_for_a_while)
            self.present()
            self.window.after(WATCH_MS, self._watch)
        else:
            self.window.protocol("WM_DELETE_WINDOW", self._leave)
            self.window.bind("<Escape>", lambda _e: self._leave())
            self.window.geometry("760x620")
            self.window.lift()
            self.window.focus_force()  # the owner opened it, so the keyboard goes to it once

    @property
    def alive(self) -> bool:
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def _build(self, source: str) -> None:
        # The footer is packed first, so it keeps its place and only the question scrolls.
        footer = ttk.Frame(self.window, padding=(20, 10))
        footer.pack(side="bottom", fill="x")
        ttk.Separator(self.window, orient="horizontal").pack(side="bottom", fill="x")
        if not self.insistent:
            ttk.Button(footer, text=t("quiz.postpone"), command=self._leave).pack(side="right")
        self.finish = ttk.Button(
            footer, style=primary_style(self.window), default="active", command=self._next
        )
        self.finish.pack(side="right", padx=(0, 8))
        self.guard_text = tk.StringVar(value="")
        ttk.Label(footer, textvariable=self.guard_text, wraplength=420, justify="left").pack(
            side="left", fill="x", expand=True
        )

        self.canvas, content = scrolled(self.window, padding=20)
        self.canvas.bind("<Configure>", lambda e: self._fit(e.width), add="+")
        self.number = ttk.Label(content, foreground="#555555")
        self.number.pack(anchor="w", pady=(0, 6))
        self.context = ttk.Label(content, justify="left", font=TEXT_FONT, wraplength=650)
        self.question = ttk.Label(content, justify="left", font=QUESTION_FONT, wraplength=650)
        self.question.pack(anchor="w", pady=(0, 12))
        self.choices = ttk.Frame(content)
        self.choices.pack(fill="x")
        notes = []
        if source.startswith("fieldnotes-practice"):
            notes.append(t("quiz.practice_note"))
        else:
            notes.append(t("quiz.pass_note"))
        notes.append(t("quiz.insistent_note") if self.insistent else t("quiz.postpone_note"))
        self.note = ttk.Label(
            content, text=" ".join(notes), justify="left", foreground="#555555", wraplength=650
        )
        self.note.pack(anchor="w", pady=(16, 0))
        self.wrapped = [self.context, self.question, self.note]

    def _fit(self, width: int) -> None:
        """Wrap the text to the window width, so a wide window is used and a narrow one cuts nothing."""
        wrap = max(300, width - 60)
        for label in self.wrapped:
            label.configure(wraplength=wrap)
        for child in self.choices.winfo_children():
            child.configure(wraplength=wrap - 30)

    def _render(self) -> None:
        q = self.questions[self.current]
        context, question = split_prompt(q.prompt)
        self.number.configure(
            text=t("quiz.question_number", number=self.current + 1, total=QUESTIONS_PER_QUIZ)
        )
        self.context.pack_forget()
        if context:
            self.context.configure(text=context)
            self.context.pack(anchor="w", pady=(0, 10), before=self.question)
        self.question.configure(text=question)
        self.selected.set(-1)
        wrap = int(str(self.question.cget("wraplength")) or 0) or 650
        for child in self.choices.winfo_children():
            child.destroy()
        for i, option in enumerate(q.options):
            tk.Radiobutton(
                self.choices,
                text=option,
                value=i,
                variable=self.selected,
                anchor="w",
                justify="left",
                font=TEXT_FONT,
                wraplength=max(270, wrap - 30),
                state="normal" if self.accepting else "disabled",
            ).pack(anchor="w", pady=6)
        self.canvas.yview_moveto(0)
        last = self.current == QUESTIONS_PER_QUIZ - 1
        self.finish.configure(text=t("quiz.finish") if last else t("quiz.next"))

    def _set_input(self, enabled: bool) -> None:
        self.accepting = enabled
        state = "normal" if enabled else "disabled"
        for child in self.choices.winfo_children():
            child.configure(state=state)
        self.finish.configure(state=state)
        self.guard_text.set("" if enabled else t("quiz.input_guard", seconds=INPUT_GUARD_MS // 1000))

    def present(self) -> None:
        """Show the window centered, on top and with focus, ignoring input for a moment."""
        if not self.alive:
            return
        self.hidden_until = None
        screen_w, screen_h = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        w, h = min(760, screen_w - 40), min(620, screen_h - 80)  # the footer must stay on a small screen
        x = max(0, (screen_w - w) // 2)
        y = max(0, (screen_h - h) // 2)
        self.window.geometry(f"{w}x{h}+{x}+{y}")
        self.window.deiconify()
        self.window.attributes("-topmost", True)
        self.window.lift()
        self.window.focus_force()
        self._set_input(False)
        self.window.after(INPUT_GUARD_MS, lambda: self.alive and self._set_input(True))

    def _hide_for_a_while(self) -> None:
        self.window.withdraw()
        self.hidden_until = self.clock() + RESHOW_SECONDS

    def _watch(self) -> None:
        """Keep an insistent quiz visible: back after a close or minimize, away during full screen."""
        if not self.alive:
            return
        try:
            state = self.window.state()
            self.waiting_for = self.busy()
            if self.waiting_for is not None:
                if state != "withdrawn":
                    self.window.withdraw()
            elif state == "iconic" and self.hidden_until is None:
                self.hidden_until = self.clock() + RESHOW_SECONDS
            elif state in ("iconic", "withdrawn") and (self.hidden_until or 0) <= self.clock():
                self.present()
            elif state == "normal":
                self.window.attributes("-topmost", True)  # another app may have taken the top
        except tk.TclError:
            return  # destroyed while checking
        self.window.after(WATCH_MS, self._watch)

    def _next(self) -> None:
        if not self.accepting:
            return
        if self.selected.get() not in range(4):
            messagebox.showinfo(
                t("quiz.answer_missing_title"),
                t("quiz.answer_missing_body"),
                parent=self.window,
            )
            return
        self.answers.append(self.selected.get())
        if self.current < QUESTIONS_PER_QUIZ - 1:
            self.current += 1
            self._render()
            return
        answers = list(self.answers)
        self.close()
        self.on_done(answers)

    def _leave(self) -> None:
        self.close()
        self.on_leave()

    def close(self) -> None:
        if self.alive:
            self.window.destroy()
