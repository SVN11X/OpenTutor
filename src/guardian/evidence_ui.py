"""Tkinter tabs for practical tasks (Tareas) and submitted evidence (Evidencia).

The owner writes the tasks by hand. A submission runs the deterministic PPTX rubric in a worker thread, and a
passed rubric opens a three-question defense about the owner's own file. Nothing here grants leisure credit:
that system does not exist yet, and the screen says so.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk

from .core import Question
from .evidence.check import KIND_INFO, KINDS, check_file
from .evidence.defense import build_defense
from .evidence.pptx_check import Result
from .i18n import t
from .task_store import FAILED, NEEDS_REVIEW, PENDING_DEFENSE, VALIDATED, Task, TaskStore

log = logging.getLogger(__name__)

# Icon + text for every state, never color alone.
STATUS_LABELS = {
    FAILED: t("evidence.status_rejected"),
    NEEDS_REVIEW: t("evidence.status_review"),
    PENDING_DEFENSE: t("evidence.status_no_defense"),
    VALIDATED: t("evidence.status_validated"),
}


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


CHECK_LABELS = {
    "extension": t("evidence.check_extension"),
    "archive": t("evidence.check_archive"),
    "macros": t("evidence.check_macros"),
    "slides": t("evidence.check_slides"),
    "readable": t("evidence.check_readable"),
    "safe_streams": t("evidence.check_safe_streams"),
    "active_content": t("evidence.check_active_content"),
    "page_count": t("evidence.check_page_count"),
    "section_count": t("evidence.check_section_count"),
    "no_empty_sections": t("evidence.check_no_empty_sections"),
    "no_duplicate_headings": t("evidence.check_no_duplicate_headings"),
    "min_words": t("evidence.check_min_words"),
    "xml": t("evidence.check_xml"),
    "slide_count": t("evidence.check_slide_count"),
    "no_empty_slides": t("evidence.check_no_empty_slides"),
    "no_placeholder_text": t("evidence.check_no_placeholder_text"),
    "titles": t("evidence.check_titles"),
    "no_duplicate_slides": t("evidence.check_no_duplicate_slides"),
    "required_terms": t("evidence.check_required_terms"),
}


def check_line(name: str, ok: bool, detail: str) -> str:
    label = CHECK_LABELS.get(name, name)
    icon = "✔" if ok else "✖"
    if detail:
        return t("evidence.check_line_detail", icon=icon, label=label, detail=detail)
    return t("evidence.check_line", icon=icon, label=label)


class EvidencePanel:
    def __init__(self, root: tk.Tk, store: TaskStore, set_status: Callable[[str], None]) -> None:
        self.root = root
        self.store = store
        self.set_status = set_status
        self.tasks: list[Task] = []
        self.title = tk.StringVar()
        self.slides = tk.IntVar(value=5)
        self.kind_name = tk.StringVar(value=KIND_INFO["pptx"]["name"])
        self.count_label = tk.StringVar(
            value=t("evidence.count_label", kind=KIND_INFO["pptx"]["plural"].capitalize())
        )
        self.terms = tk.StringVar()
        self.message = tk.StringVar(value="")
        self.latest = tk.StringVar(value=t("evidence.latest_none"))
        self.history = tk.StringVar(value="")
        self.listbox: tk.Listbox | None = None
        self.submit_button: ttk.Button | None = None

    # ---- tabs ----
    def build_tasks_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text=t("evidence.tasks_heading"), font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.listbox = tk.Listbox(parent, height=5, exportselection=False)
        self.listbox.pack(fill="x", pady=(4, 4))
        row = ttk.Frame(parent)
        row.pack(anchor="w", pady=(0, 8))
        self.submit_button = ttk.Button(row, text=t("evidence.hand_in"), command=self._submit)
        self.submit_button.pack(side="left", padx=(0, 7))
        ttk.Button(row, text=t("evidence.archive"), command=self._archive).pack(side="left")
        ttk.Label(parent, text=t("evidence.new_task"), font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(parent, text=t("evidence.title_label")).pack(anchor="w")
        ttk.Entry(parent, textvariable=self.title).pack(fill="x", pady=(0, 4))
        line = ttk.Frame(parent)
        line.pack(anchor="w", fill="x")
        kinds = ttk.Combobox(
            line,
            textvariable=self.kind_name,
            state="readonly",
            width=18,
            values=[KIND_INFO[k]["name"] for k in KINDS],
        )
        kinds.pack(side="left", padx=(0, 10))
        kinds.bind(
            "<<ComboboxSelected>>",
            lambda _e: self.count_label.set(
                t("evidence.count_label", kind=KIND_INFO[self._kind()]["plural"].capitalize())
            ),
        )
        ttk.Label(line, textvariable=self.count_label).pack(side="left")
        ttk.Spinbox(line, from_=1, to=100, width=5, textvariable=self.slides).pack(side="left", padx=(4, 10))
        ttk.Label(parent, text=t("evidence.terms_label")).pack(anchor="w", pady=(6, 0))
        ttk.Entry(parent, textvariable=self.terms).pack(fill="x", pady=(4, 4))
        ttk.Button(parent, text=t("evidence.add_task"), command=self._add).pack(anchor="w")
        ttk.Label(parent, textvariable=self.message, foreground="#1a4f8a", wraplength=500).pack(
            anchor="w", pady=6
        )
        self.refresh()

    def build_evidence_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text=t("evidence.latest_heading"), font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(parent, textvariable=self.latest, justify="left", wraplength=500).pack(
            anchor="w", pady=(2, 8)
        )
        ttk.Label(parent, text=t("evidence.history_heading"), font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(parent, textvariable=self.history, justify="left", wraplength=500).pack(anchor="w")
        ttk.Label(
            parent,
            wraplength=500,
            justify="left",
            text=t("evidence.accepted_note"),
        ).pack(anchor="w", pady=(10, 0))
        self.refresh()

    # ---- data ----
    def refresh(self) -> None:
        self.tasks = self.store.list_tasks()
        if self.listbox is not None:
            self.listbox.delete(0, "end")
            for task in self.tasks:
                terms = f" · {', '.join(task.required_terms)}" if task.required_terms else ""
                self.listbox.insert(
                    "end", f"{task.title} · {task.expected_slides} {KIND_INFO[task.kind]['plural']}{terms}"
                )
        recent = self.store.recent_submissions()
        if recent:
            first = recent[0]
            lines = [f"{first.task_title}: {status_label(first.final_status)}  ({first.file_name})"]
            lines += [check_line(*c) for c in first.checks]
            if first.defense_total:
                lines.append(
                    t("evidence.defense_score", score=first.defense_score, total=first.defense_total)
                )
            self.latest.set("\n".join(lines))
            self.history.set(
                "\n".join(
                    f"{s.created_at[:16].replace('T', ' ')}  {s.task_title}  {status_label(s.final_status)}"
                    for s in recent
                )
            )

    def _kind(self) -> str:
        """The kind chosen in the form, from its display name."""
        for kind in KINDS:
            if KIND_INFO[kind]["name"] == self.kind_name.get():
                return kind
        return "pptx"

    def _selected_task(self) -> Task | None:
        if self.listbox is None or not self.listbox.curselection():
            return None
        index = self.listbox.curselection()[0]
        return self.tasks[index] if index < len(self.tasks) else None

    # ---- actions ----
    def _add(self) -> None:
        try:
            self.store.add_task(self.title.get(), int(self.slides.get()), self.terms.get(), self._kind())
        except (ValueError, tk.TclError) as err:
            self.message.set(t("evidence.add_error", error=err))
            return
        self.title.set("")
        self.terms.set("")
        self.message.set(t("evidence.added"))
        self.refresh()

    def _archive(self) -> None:
        task = self._selected_task()
        if task is None:
            self.message.set(t("evidence.choose_task"))
            return
        self.store.archive_task(task.id)  # hides it, the evidence already handed in stays
        self.message.set(t("evidence.archived", title=task.title))
        self.refresh()

    def _submit(self) -> None:
        task = self._selected_task()
        if task is None:
            self.message.set(t("evidence.choose_first"))
            return
        info = KIND_INFO[task.kind]
        path = filedialog.askopenfilename(
            title=t("evidence.choose_file", thing=info["owner_thing"]),
            filetypes=[(info["name"], info["pattern"])],
        )
        if not path:
            return
        if self.submit_button is not None:
            self.submit_button.state(["disabled"])
        self.message.set(t("evidence.reviewing"))
        threading.Thread(target=self._check_worker, args=(task, path), daemon=True).start()

    def _check_worker(self, task: Task, path: str) -> None:
        try:
            result = check_file(task.kind, path, task.expected_slides, task.required_terms)
        except Exception:  # the rubric must never take the app down
            log.exception("File check crashed (%s)", task.kind)
            self._later(lambda: self._finish_failed(t("evidence.check_crashed")))
            return
        self._later(lambda: self._after_check(task, path, result))

    def _later(self, fn: Callable[[], None]) -> None:
        try:
            self.root.after(0, fn)
        except (tk.TclError, RuntimeError):
            log.debug("Window closed before the result arrived")

    def _finish_failed(self, text: str) -> None:
        if self.submit_button is not None:
            self.submit_button.state(["!disabled"])
        self.message.set(text)

    def _after_check(self, task: Task, path: str, result: Result) -> None:
        if self.submit_button is not None:
            self.submit_button.state(["!disabled"])
        sub_id = self.store.add_submission(task.id, path, result.status, result.checks)
        self.refresh()
        self.message.set(t("evidence.review_done", status=result.status))
        if result.status != "passed":
            self.set_status(t("evidence.handed_in", title=task.title, status=result.status))
            return
        questions = build_defense(result, task.required_terms)
        if not questions:
            self.message.set(t("evidence.defense_prepare_failed"))
            return
        self.open_defense(sub_id, task.title, questions)

    def open_defense(self, sub_id: int, title: str, questions: list[Question]) -> None:
        window = tk.Toplevel(self.root)
        window.title(t("evidence.defense_window_title"))
        window.geometry("560x360")
        if self.root.state() != "withdrawn":
            window.transient(self.root)
        answers: list[int] = []
        current = 0
        selected = tk.IntVar(value=-1)
        body = ttk.Frame(window, padding=16)
        body.pack(fill="both", expand=True)
        heading = ttk.Label(body, wraplength=500, justify="left", font=("Segoe UI", 12, "bold"))
        heading.pack(anchor="w", pady=(0, 10))
        choices = ttk.Frame(body)
        choices.pack(fill="x")
        ttk.Label(
            body,
            wraplength=500,
            text=t("evidence.defense_note"),
        ).pack(anchor="w", pady=10)
        button = ttk.Button(body)
        button.pack(anchor="e")

        def render() -> None:
            q = questions[current]
            heading.configure(
                text=t("evidence.question_header", number=current + 1, total=len(questions), prompt=q.prompt)
            )
            selected.set(-1)
            for child in choices.winfo_children():
                child.destroy()
            for i, option in enumerate(q.options):
                tk.Radiobutton(
                    choices, text=option, value=i, variable=selected, anchor="w", wraplength=480
                ).pack(anchor="w", pady=4)
            button.configure(
                text=t("evidence.finish") if current == len(questions) - 1 else t("evidence.next")
            )

        def advance() -> None:
            nonlocal current
            if selected.get() not in range(4):
                messagebox.showinfo(
                    t("evidence.answer_pending_title"), t("evidence.answer_missing"), parent=window
                )
                return
            answers.append(selected.get())
            if current < len(questions) - 1:
                current += 1
                render()
                return
            score = sum(a == q.answer_index for a, q in zip(answers, questions, strict=True))
            status = self.store.record_defense(sub_id, score, len(questions))
            window.destroy()
            self.refresh()
            self.message.set(
                t(
                    "evidence.defense_result",
                    score=score,
                    total=len(questions),
                    status=status_label(status),
                )
            )
            self.set_status(
                t(
                    "evidence.defense_status_line",
                    title=title,
                    score=score,
                    total=len(questions),
                    status=status_label(status),
                )
            )

        button.configure(command=advance)
        render()
