"""Read-only, accessible and compact review screen for the Guardian MVP.

No score, source trust, question key or unlock policy is changed here.
"""
from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from typing import Sequence

from .core import Question
from .results import ExamReport, build_exam_report, report_as_text

BG = "#f4f7fb"
WHITE = "#ffffff"
INK = "#17243a"
MUTED = "#52627a"
BORDER = "#dce4ee"
BLUE = "#255ab7"
GREEN = "#16734e"
RED = "#a33542"
AMBER = "#915c0c"
PALE_BLUE = "#e7effd"
PALE_AMBER = "#fff5df"
PALE_RED = "#fff0f2"
PALE_GREEN = "#e9f7ef"


@dataclass(frozen=True)
class SidebarStatus:
    """Non-color-only status; unverified keys never claim correctness."""
    icon: str
    label: str
    accent: str


def sidebar_status(verified: bool, correct: bool) -> SidebarStatus:
    """Color, icon and text agree without treating imported keys as ground truth."""
    if verified:
        return (SidebarStatus("✓", "Correcta", GREEN) if correct else
                SidebarStatus("×", "Incorrecta", RED))
    return (SidebarStatus("≈", "Coincide con clave", BLUE) if correct else
            SidebarStatus("≠", "Difiere de clave", AMBER))


def provisional_score_label(report: ExamReport) -> str:
    """Do not present unverified answer keys as an authoritative examination grade."""
    if not report.verified:
        return f"{report.score}/5 coincidencias · provisional"
    return f"{report.score}/5 · {report.score * 20}%"


def answer_status_label(verified: bool, correct: bool) -> str:
    if not verified:
        return "Coincide con clave" if correct else "Difiere de clave"
    return "Correcta" if correct else "A revisar"


def preview_explanation(text: str, limit: int = 270) -> tuple[str, bool]:
    """Create a concise reversible preview; never rewrite the original explanation."""
    if len(text) <= limit:
        return text, False
    cut = text.rfind(" ", max(1, limit // 2), limit)
    if cut < 1:
        cut = limit
    return text[:cut].rstrip() + "…", True


def show_exam_result(
    parent: tk.Tk, *, topic: str, questions: Sequence[Question],
    answers: Sequence[int], score: int, passed: bool, source: str,
) -> tk.Toplevel:
    """One-question-at-a-time review, with predictable keyboard and scroll navigation."""
    report = build_exam_report(topic=topic, questions=questions, answers=answers,
                               score=score, passed=passed, source=source)
    win = tk.Toplevel(parent)
    win.title("OpenTutor Guardian · Revisión del examen")
    win.geometry("990x700")
    win.minsize(740, 520)
    win.configure(bg=BG)
    if parent.state() != "withdrawn":  # a transient child of a hidden panel would be invisible
        win.transient(parent)

    shell = tk.Frame(win, bg=BG, padx=20, pady=16)
    shell.pack(fill="both", expand=True)

    header = tk.Frame(shell, bg=BG)
    header.pack(fill="x")
    tk.Label(header, text="Revisa tus respuestas", bg=BG, fg=INK,
             font=("Segoe UI", 18, "bold")).pack(side="left")
    tk.Label(header, text=provisional_score_label(report), bg=BG,
             fg=AMBER if not report.verified else BLUE,
             font=("Segoe UI", 12, "bold")).pack(side="right")

    tk.Label(shell, text=f"Tema: {report.topic}   ·   {report.status}", bg=BG,
             fg=MUTED if not report.verified else (GREEN if report.certified_pass else RED),
             anchor="w", font=("Segoe UI", 10, "bold")).pack(fill="x", pady=(3, 10))

    if not report.verified:
        alert = tk.Frame(shell, bg=PALE_AMBER, padx=12, pady=8)
        alert.pack(fill="x", pady=(0, 10))
        warning = tk.Label(
            alert, bg=PALE_AMBER, fg="#79500a", justify="left", anchor="w",
            text="Claves sin verificar: las coincidencias son orientativas y NO permiten desbloqueos.",
            wraplength=880, font=("Segoe UI", 10),
        )
        warning.pack(fill="x")
        alert.bind("<Configure>", lambda ev: warning.configure(wraplength=max(260, ev.width - 30)))

    main = tk.Frame(shell, bg=BG)
    main.pack(fill="both", expand=True)
    nav = tk.Frame(main, bg=WHITE, width=236, padx=9, pady=12,
                   highlightbackground=BORDER, highlightthickness=1)
    nav.pack(side="left", fill="y", padx=(0, 12))
    nav.pack_propagate(False)
    tk.Label(nav, text="REVISAR PREGUNTAS", bg=WHITE, fg=MUTED,
             font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
    if not report.verified:
        tk.Label(nav, text="CLAVES SIN VERIFICAR", bg=WHITE, fg=AMBER,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 10))

    detail = tk.Frame(main, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
    detail.pack(side="left", fill="both", expand=True)
    canvas = tk.Canvas(detail, bg=WHITE, highlightthickness=0)
    scroll = ttk.Scrollbar(detail, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    body = tk.Frame(canvas, bg=WHITE, padx=22, pady=18)
    body_id = canvas.create_window((0, 0), window=body, anchor="nw")
    body.bind("<Configure>", lambda _ev: canvas.configure(scrollregion=canvas.bbox("all")))
    dynamic_labels: list[tk.Label] = []

    def resize_content(event: tk.Event) -> None:
        canvas.itemconfigure(body_id, width=event.width)
        wrap_width = max(200, event.width - 74)
        for label in dynamic_labels:
            label.configure(wraplength=wrap_width)

    canvas.bind("<Configure>", resize_content)

    selected_index = 0
    nav_rows: list[tuple[tk.Frame, tk.Button]] = []

    def add_label(text: str, *, heading: bool = False, color: str = INK,
                  pady: tuple[int, int] = (0, 10)) -> tk.Label:
        label = tk.Label(body, text=text, bg=WHITE, fg=color,
                         font=("Segoe UI", 10 if heading else 11,
                               "bold" if heading else "normal"),
                         anchor="nw", justify="left", wraplength=max(250, canvas.winfo_width() - 74))
        label.pack(fill="x", anchor="w", pady=pady)
        dynamic_labels.append(label)
        return label

    def show_item(index: int) -> None:
        nonlocal selected_index
        selected_index = index
        item = report.items[index]
        for child in body.winfo_children():
            child.destroy()
        dynamic_labels.clear()
        for i, (row, button) in enumerate(nav_rows):
            selected = i == index
            row.configure(highlightbackground=BLUE if selected else BORDER)
            button.configure(bg=PALE_BLUE if selected else WHITE,
                             activebackground=PALE_BLUE)

        state = sidebar_status(report.verified, item.correct)
        add_label(f"PREGUNTA {item.number} DE {len(report.items)}   ·   "
                  f"{state.icon} {state.label.upper()}",
                  heading=True, color=state.accent, pady=(0, 12))
        add_label(item.question, pady=(0, 18))

        add_label("TU RESPUESTA", heading=True, color=MUTED, pady=(0, 5))
        add_label(item.selected,
                  color=INK if not report.verified else (GREEN if item.correct else RED),
                  pady=(0, 15))
        add_label("SEGÚN LA CLAVE ORIGINAL" if not report.verified else "RESPUESTA CORRECTA",
                  heading=True, color=MUTED, pady=(0, 5))
        add_label(item.expected, color=INK, pady=(0, 18))

        add_label("EXPLICACIÓN DEL BANCO", heading=True, color=MUTED, pady=(0, 7))
        explanation_preview, shortened = preview_explanation(item.explanation)
        explanation = add_label(explanation_preview, color=INK, pady=(0, 8))
        if shortened:
            expanded = tk.BooleanVar(value=False)

            def toggle_full() -> None:
                expanded.set(not expanded.get())
                explanation.configure(text=item.explanation if expanded.get() else explanation_preview)
                expand_btn.configure(text="Mostrar menos" if expanded.get() else "Leer explicación completa")
                canvas.configure(scrollregion=canvas.bbox("all"))

            expand_btn = ttk.Button(body, text="Leer explicación completa", command=toggle_full)
            expand_btn.pack(anchor="w", pady=(0, 12))
        if not report.verified:
            add_label("Texto original, posiblemente en inglés y aún sin validar.",
                      color=MUTED, pady=(0, 8))
        prev_button.configure(state="normal" if index > 0 else "disabled")
        next_button.configure(state="normal" if index < len(report.items) - 1 else "disabled")
        position.configure(text=f"Pregunta {index + 1} de {len(report.items)}")
        canvas.yview_moveto(0)

    for i, item in enumerate(report.items):
        status = sidebar_status(report.verified, item.correct)
        row = tk.Frame(nav, bg=WHITE, highlightbackground=BORDER,
                       highlightthickness=1)
        row.pack(fill="x", pady=3)
        # Vertical accent + Unicode symbol + text: no reliance on color alone.
        stripe = tk.Frame(row, width=5, bg=status.accent)
        stripe.pack(side="left", fill="y")
        stripe.pack_propagate(False)
        button = tk.Button(
            row, text=f"{item.number}   {status.icon} {status.label}",
            command=lambda n=i: show_item(n),
            font=("Segoe UI", 10), anchor="w", justify="left",
            wraplength=180, padx=10, pady=10, bg=WHITE, fg=status.accent,
            relief="flat", bd=0, cursor="hand2", activeforeground=status.accent,
            activebackground=PALE_BLUE, highlightthickness=0,
        )
        button.pack(side="left", fill="x", expand=True)
        nav_rows.append((row, button))

    def wheel(event: tk.Event) -> None:
        # Scroll only if the mouse is inside the details pane.
        x, y = win.winfo_pointerxy()
        if not (canvas.winfo_rootx() <= x < canvas.winfo_rootx() + canvas.winfo_width()
                and canvas.winfo_rooty() <= y < canvas.winfo_rooty() + canvas.winfo_height()):
            return
        if getattr(event, "delta", 0):
            canvas.yview_scroll(-int(event.delta / 120) or (-1 if event.delta > 0 else 1), "units")

    win.bind("<MouseWheel>", wheel)

    footer = tk.Frame(shell, bg=BG)
    footer.pack(fill="x", pady=(12, 0))

    def copy_summary() -> None:
        win.clipboard_clear()
        win.clipboard_append(report_as_text(report))
        copy_button.configure(text="Resumen copiado ✓")

    copy_button = ttk.Button(footer, text="Copiar resumen", command=copy_summary)
    copy_button.pack(side="left")
    ttk.Button(footer, text="Cerrar", command=win.destroy).pack(side="right")

    navigation_footer = tk.Frame(footer, bg=BG)
    navigation_footer.pack(side="right", padx=(0, 20))
    prev_button = ttk.Button(navigation_footer, text="← Anterior",
                             command=lambda: show_item(selected_index - 1))
    prev_button.pack(side="left", padx=4)
    position = tk.Label(navigation_footer, bg=BG, fg=MUTED, font=("Segoe UI", 9))
    position.pack(side="left", padx=8)
    next_button = ttk.Button(navigation_footer, text="Siguiente →",
                             command=lambda: show_item(selected_index + 1))
    next_button.pack(side="left", padx=4)

    win.bind("<Left>", lambda _ev: show_item(selected_index - 1) if selected_index > 0 else None)
    win.bind("<Right>", lambda _ev: show_item(selected_index + 1)
             if selected_index < len(report.items) - 1 else None)
    win.bind("<Escape>", lambda _ev: win.destroy())
    show_item(next((i for i, item in enumerate(report.items) if not item.correct), 0))
    win.lift()
    win.focus_set()
    return win
