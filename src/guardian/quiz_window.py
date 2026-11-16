"""The five-question quiz window.

In insistent mode (decision 0007) it opens centered, on top and with focus, has no exit button and comes
back a few seconds after it is closed or minimized. It hides while Windows reports a full-screen app or
presentation mode and returns when that ends. Keys and clicks are ignored for two seconds each time it
appears, so typing in another app cannot answer by accident. Emergencia and Salir stay in the tray menu.
"""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import messagebox, ttk

from .core import QUESTIONS_PER_QUIZ, Question
from .i18n import t
from .presence import busy_reason

INPUT_GUARD_MS = 2000
WATCH_MS = 1000
RESHOW_SECONDS = 5.0


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
        if insistent:
            self.window.protocol("WM_DELETE_WINDOW", self._hide_for_a_while)
            self.present()
            self.window.after(WATCH_MS, self._watch)
        else:
            self.window.protocol("WM_DELETE_WINDOW", self._leave)
            self.window.geometry("760x620")
            self.window.lift()

    @property
    def alive(self) -> bool:
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def _build(self, source: str) -> None:
        # Long imported questions and answer options must remain reachable.
        canvas = tk.Canvas(self.window, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.window, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        content = ttk.Frame(canvas, padding=20)
        body_id = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(body_id, width=e.width))
        self.window.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-int(e.delta / 120), "units"))
        self.canvas = canvas
        self.title = ttk.Label(content, wraplength=650, justify="left", font=("Segoe UI", 13, "bold"))
        self.title.pack(anchor="w", pady=(0, 15))
        self.choices = ttk.Frame(content)
        self.choices.pack(fill="x")
        practice = source.startswith("fieldnotes-practice")
        note = t("quiz.practice_note") if practice else ""
        note += t("quiz.insistent_note") if self.insistent else t("quiz.note")
        ttk.Label(content, text=note, wraplength=650, justify="left").pack(anchor="w", pady=20)
        self.finish = ttk.Button(content, command=self._next)
        self.finish.pack(anchor="e", pady=8)
        if not self.insistent:
            ttk.Button(content, text=t("quiz.postpone"), command=self._leave).pack(anchor="e")

    def _render(self) -> None:
        q = self.questions[self.current]
        self.title.configure(
            text=t("quiz.question_header", number=self.current + 1, total=QUESTIONS_PER_QUIZ, prompt=q.prompt)
        )
        self.selected.set(-1)
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
                wraplength=640,
            ).pack(anchor="w", pady=8)
        self.canvas.yview_moveto(0)
        last = self.current == QUESTIONS_PER_QUIZ - 1
        self.finish.configure(text=t("quiz.finish") if last else t("quiz.next"))

    def _set_input(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for child in self.choices.winfo_children():
            child.configure(state=state)
        self.finish.configure(state=state)

    def present(self) -> None:
        """Show the window centered, on top and with focus, ignoring input for a moment."""
        if not self.alive:
            return
        self.hidden_until = None
        w, h = 760, 620
        x = max(0, (self.window.winfo_screenwidth() - w) // 2)
        y = max(0, (self.window.winfo_screenheight() - h) // 2)
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
