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
from .evidence.defense import build_defense
from .evidence.pptx_check import Result, check_pptx
from .task_store import FAILED, NEEDS_REVIEW, PENDING_DEFENSE, VALIDATED, Task, TaskStore

log = logging.getLogger(__name__)

# Icon + text for every state, never color alone.
STATUS_LABELS = {
    FAILED: "✖ Rechazado",
    NEEDS_REVIEW: "◐ Requiere revisión",
    PENDING_DEFENSE: "◌ Falta la defensa",
    VALIDATED: "✔ Validado",
}


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


CHECK_LABELS = {
    "extension": "Extensión .pptx",
    "archive": "Archivo válido",
    "macros": "Sin macros",
    "slides": "Tiene diapositivas",
    "xml": "Contenido legible",
    "slide_count": "Cantidad de diapositivas",
    "no_empty_slides": "Sin diapositivas vacías",
    "no_placeholder_text": "Sin texto de plantilla",
    "titles": "Todas tienen título",
    "no_duplicate_slides": "Sin diapositivas repetidas",
    "required_terms": "Términos obligatorios",
}


def check_line(name: str, ok: bool, detail: str) -> str:
    return f"{'✔' if ok else '✖'} {CHECK_LABELS.get(name, name)}" + (f": {detail}" if detail else "")


class EvidencePanel:
    def __init__(self, root: tk.Tk, store: TaskStore, set_status: Callable[[str], None]) -> None:
        self.root = root
        self.store = store
        self.set_status = set_status
        self.tasks: list[Task] = []
        self.title = tk.StringVar()
        self.slides = tk.IntVar(value=5)
        self.terms = tk.StringVar()
        self.message = tk.StringVar(value="")
        self.latest = tk.StringVar(value="Aún no entregaste ningún trabajo.")
        self.history = tk.StringVar(value="")
        self.listbox: tk.Listbox | None = None
        self.submit_button: ttk.Button | None = None

    # ---- tabs ----
    def build_tasks_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Tareas prácticas (las escribes tú)", font=("Segoe UI", 11, "bold")).pack(
            anchor="w"
        )
        self.listbox = tk.Listbox(parent, height=5, exportselection=False)
        self.listbox.pack(fill="x", pady=(4, 4))
        row = ttk.Frame(parent)
        row.pack(anchor="w", pady=(0, 8))
        self.submit_button = ttk.Button(row, text="Entregar .pptx…", command=self._submit)
        self.submit_button.pack(side="left", padx=(0, 7))
        ttk.Button(row, text="Archivar tarea", command=self._archive).pack(side="left")
        ttk.Label(parent, text="Nueva tarea", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(parent, text="Título:").pack(anchor="w")
        ttk.Entry(parent, textvariable=self.title).pack(fill="x", pady=(0, 4))
        line = ttk.Frame(parent)
        line.pack(anchor="w", fill="x")
        ttk.Label(line, text="Diapositivas:").pack(side="left")
        ttk.Spinbox(line, from_=1, to=100, width=5, textvariable=self.slides).pack(side="left", padx=(4, 10))
        ttk.Label(line, text="Términos obligatorios (separados por comas):").pack(side="left")
        ttk.Entry(parent, textvariable=self.terms).pack(fill="x", pady=(4, 4))
        ttk.Button(parent, text="Añadir tarea", command=self._add).pack(anchor="w")
        ttk.Label(parent, textvariable=self.message, foreground="#1a4f8a", wraplength=500).pack(
            anchor="w", pady=6
        )
        self.refresh()

    def build_evidence_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Última entrega", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(parent, textvariable=self.latest, justify="left", wraplength=500).pack(
            anchor="w", pady=(2, 8)
        )
        ttk.Label(parent, text="Historial", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(parent, textvariable=self.history, justify="left", wraplength=500).pack(anchor="w")
        ttk.Label(
            parent,
            wraplength=500,
            justify="left",
            text=(
                "✔ Validado es evidencia aceptada. Todavía no da crédito de ocio, porque ese sistema "
                "no existe. Las revisiones son deterministas, ningún modelo decide."
            ),
        ).pack(anchor="w", pady=(10, 0))
        self.refresh()

    # ---- data ----
    def refresh(self) -> None:
        self.tasks = self.store.list_tasks()
        if self.listbox is not None:
            self.listbox.delete(0, "end")
            for task in self.tasks:
                terms = f" · {', '.join(task.required_terms)}" if task.required_terms else ""
                self.listbox.insert("end", f"{task.title} · {task.expected_slides} diapositivas{terms}")
        recent = self.store.recent_submissions()
        if recent:
            first = recent[0]
            lines = [f"{first.task_title}: {status_label(first.final_status)}  ({first.file_name})"]
            lines += [check_line(*c) for c in first.checks]
            if first.defense_total:
                lines.append(f"Defensa: {first.defense_score}/{first.defense_total}")
            self.latest.set("\n".join(lines))
            self.history.set(
                "\n".join(
                    f"{s.created_at[:16].replace('T', ' ')}  {s.task_title}  {status_label(s.final_status)}"
                    for s in recent
                )
            )

    def _selected_task(self) -> Task | None:
        if self.listbox is None or not self.listbox.curselection():
            return None
        index = self.listbox.curselection()[0]
        return self.tasks[index] if index < len(self.tasks) else None

    # ---- actions ----
    def _add(self) -> None:
        try:
            self.store.add_task(self.title.get(), int(self.slides.get()), self.terms.get())
        except (ValueError, tk.TclError) as err:
            self.message.set(f"No se añadió: {err}")
            return
        self.title.set("")
        self.terms.set("")
        self.message.set("Tarea añadida")
        self.refresh()

    def _archive(self) -> None:
        task = self._selected_task()
        if task is None:
            self.message.set("Elige una tarea de la lista")
            return
        self.store.archive_task(task.id)  # hides it, the evidence already handed in stays
        self.message.set(f"Tarea archivada: {task.title}")
        self.refresh()

    def _submit(self) -> None:
        task = self._selected_task()
        if task is None:
            self.message.set("Elige primero la tarea que vas a entregar")
            return
        path = filedialog.askopenfilename(title="Elige tu presentación", filetypes=[("PowerPoint", "*.pptx")])
        if not path:
            return
        if self.submit_button is not None:
            self.submit_button.state(["disabled"])
        self.message.set("Revisando el archivo…")
        threading.Thread(target=self._check_worker, args=(task, path), daemon=True).start()

    def _check_worker(self, task: Task, path: str) -> None:
        try:
            result = check_pptx(
                path, expected_slides=task.expected_slides, required_terms=task.required_terms
            )
        except Exception:  # the rubric must never take the app down
            log.exception("PPTX check crashed")
            self._later(lambda: self._finish_failed("No se pudo revisar el archivo. Mira guardian.log"))
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
        self.message.set(f"Revisión: {result.status}. Mira la pestaña Evidencia")
        if result.status != "passed":
            self.set_status(f"Entrega de «{task.title}»: {result.status}")
            return
        questions = build_defense(result, task.required_terms)
        if not questions:
            self.message.set("Revisión superada, pero no se pudo preparar la defensa. Vuelve a entregar")
            return
        self.open_defense(sub_id, task.title, questions)

    def open_defense(self, sub_id: int, title: str, questions: list[Question]) -> None:
        window = tk.Toplevel(self.root)
        window.title("Defensa de tu trabajo")
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
            text="Son preguntas sobre tu propio archivo. Si cierras la ventana, la entrega queda pendiente.",
        ).pack(anchor="w", pady=10)
        button = ttk.Button(body)
        button.pack(anchor="e")

        def render() -> None:
            q = questions[current]
            heading.configure(text=f"{current + 1}/{len(questions)}  {q.prompt}")
            selected.set(-1)
            for child in choices.winfo_children():
                child.destroy()
            for i, option in enumerate(q.options):
                tk.Radiobutton(
                    choices, text=option, value=i, variable=selected, anchor="w", wraplength=480
                ).pack(anchor="w", pady=4)
            button.configure(text="Terminar" if current == len(questions) - 1 else "Siguiente")

        def advance() -> None:
            nonlocal current
            if selected.get() not in range(4):
                messagebox.showinfo("Respuesta pendiente", "Selecciona una respuesta", parent=window)
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
            self.message.set(f"Defensa {score}/{len(questions)}: {status_label(status)}")
            self.set_status(f"«{title}»: defensa {score}/{len(questions)}, {status_label(status)}")

        button.configure(command=advance)
        render()
