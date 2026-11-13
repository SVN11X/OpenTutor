"""Opt-in Windows desktop prototype: non-privileged, no browser blocking."""

from __future__ import annotations

import argparse
import ctypes
import os
import queue
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk

from . import autostart, fieldnotes, integrations
from .core import ResultStore, SurpriseClock, attempt_label, within_study_window
from .questions import get_questions
from .results_ui import show_exam_result
from .session_state import SessionState, SessionStore, parse_schedule
from .single_instance import SingleInstance
from .tray import TrayIcon


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def is_user_active(idle_limit_sec: int = 180) -> bool:
    if sys.platform != "win32":
        return True  # Cross-platform demo only; real eligibility needs Windows.
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return False
    now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
    idle_ms = (now - info.dwTime) & 0xFFFFFFFF
    return idle_ms < idle_limit_sec * 1000


class GuardianUI:
    def __init__(self, root: tk.Tk, *, demo: bool = False) -> None:
        self.root = root
        self.root.title("OpenTutor Guardian — v0.2")
        self.root.geometry("560x600")
        self.root.minsize(520, 560)
        app_data = (
            Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share"))) / "OpenTutorGuardian"
        )
        self.store = ResultStore(app_data / "guardian_mvp.sqlite3")
        self.clock = SurpriseClock(interval=(20, 30) if demo else (600, 1500))
        self.session_store = SessionStore(app_data / "session.json")
        self.enabled = False  # opt-in: a session starts only if the user started it before
        self.pause_until = _EPOCH
        self.in_quiz = False
        self.pending = False
        self.surprise_popup = None
        self.last_tick = time.monotonic()
        self.topic = tk.StringVar(value="Google Cloud")
        self.model = tk.StringVar(value="qwen3.5:4b")
        self.question_source = tk.StringVar(value="Banco local (rápido)")
        # The user explicitly activates a bounded study session; no surprise outside it.
        self.until: datetime | None = None
        self.status = tk.StringVar(value="Desactivado · sin bloqueos")
        self.stats = tk.StringVar(value="")
        self.next_review = tk.StringVar(value="")
        self.last_result = tk.StringVar(value="")
        self.pending_text = tk.StringVar(value="")
        self.recent_text = tk.StringVar(value="")
        self.average_text = tk.StringVar(value="")
        self.windows: tuple[tuple[str, str], ...] = ()
        self.schedule = tk.StringVar(value="")
        self.health = tk.StringVar(value="Comprobando servicios…")
        autostart.refresh_if_stale(_REPO_ROOT)  # migrate a pre-rename Run value, never creates one
        self.autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        self._render()
        self._refresh_stats()
        self._restore_session()
        self.commands: queue.Queue[str] = queue.Queue()
        self.tray = TrayIcon(self.commands.put)
        self.tray_ok = self.tray.start()
        if not self.tray_ok:
            self.status.set(self.status.get() + " · sin icono de bandeja: cerrar la ventana sale")
        root.after(1000, self._tick)
        root.after(200, self._poll_commands)
        self._refresh_health()
        # With a tray icon the close button hides the panel; without one it must exit.
        root.protocol("WM_DELETE_WINDOW", self._hide if self.tray_ok else self._exit)

    def _render(self) -> None:
        frame = ttk.Frame(self.root, padding=(14, 12))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="OpenTutor Guardian", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text="No bloquea aplicaciones ni navegadores · sin telemetría").pack(
            anchor="w", pady=(0, 6)
        )
        self.tabs = ttk.Notebook(frame)
        self.tabs.pack(fill="both", expand=True)
        today, tasks, reviews, progress, settings = (ttk.Frame(self.tabs, padding=12) for _ in range(5))
        for page, name in (
            (today, "Hoy"),
            (tasks, "Tareas"),
            (reviews, "Repasos"),
            (progress, "Progreso"),
            (settings, "Ajustes"),
        ):
            self.tabs.add(page, text=name)
        self.tabs.enable_traversal()  # Ctrl+Tab and Ctrl+PgUp/PgDn

        # Hoy: state, next review, session controls, integration health, emergency
        ttk.Label(
            today,
            textvariable=self.status,
            foreground="#1a4f8a",
            wraplength=500,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        ttk.Label(today, textvariable=self.next_review).pack(anchor="w", pady=(6, 0))
        ttk.Label(today, textvariable=self.last_result).pack(anchor="w", pady=(2, 8))
        controls = ttk.Frame(today)
        controls.pack(anchor="w", pady=(0, 8))
        ttk.Button(controls, text="Iniciar estudio (60 min)", command=self._start).pack(
            side="left", padx=(0, 7)
        )
        ttk.Button(controls, text="Pausar 15 min", command=self._pause).pack(side="left", padx=(0, 7))
        ttk.Button(controls, text="Terminar", command=self._stop).pack(side="left")
        ttk.Button(today, text="Hacer examen ahora", command=self._open_quiz).pack(anchor="w", pady=(0, 10))
        ttk.Label(today, text="Servicios", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(today, textvariable=self.health, wraplength=500, justify="left").pack(anchor="w")
        ttk.Label(today, text="Restricciones: ninguna. El bloqueo de ocio aún no existe.").pack(
            anchor="w", pady=(6, 10)
        )
        row = ttk.Frame(today)
        row.pack(anchor="w")
        ttk.Button(row, text="Emergencia", command=self._emergency).pack(side="left", padx=(0, 7))
        ttk.Button(row, text="Ocultar a bandeja", command=self._hide).pack(side="left", padx=(0, 7))
        ttk.Button(row, text="Salir", command=self._exit).pack(side="left")

        # Tareas: honest empty state, nothing simulated
        ttk.Label(tasks, text="◌ Sin tareas", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(
            tasks,
            wraplength=500,
            justify="left",
            text=(
                "Las tareas prácticas (por ejemplo una presentación de 5 diapositivas) llegan en la "
                "Entrega B. Hoy solo existe el examen de 5 preguntas."
            ),
        ).pack(anchor="w", pady=6)

        # Repasos: pending exam and recent results
        ttk.Label(reviews, textvariable=self.pending_text, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(reviews, text="Resultados recientes", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(10, 2)
        )
        ttk.Label(reviews, textvariable=self.recent_text, justify="left", wraplength=500).pack(anchor="w")

        # Progreso
        ttk.Label(progress, textvariable=self.stats, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(progress, textvariable=self.average_text).pack(anchor="w", pady=4)
        ttk.Label(
            progress,
            wraplength=500,
            justify="left",
            text=("◐ Práctica = clave sin verificar: cuenta para estudiar, nunca para desbloquear nada."),
        ).pack(anchor="w", pady=6)

        # Ajustes
        for title, var in (("Tema de estudio:", self.topic), ("Modelo Ollama:", self.model)):
            ttk.Label(settings, text=title).pack(anchor="w")
            ttk.Entry(settings, textvariable=var).pack(fill="x", pady=(0, 6))
        ttk.Label(settings, text="Origen de las preguntas:").pack(anchor="w")
        ttk.Combobox(
            settings,
            textvariable=self.question_source,
            state="readonly",
            values=("Banco local (rápido)", "Banco completo (práctica)", "Ollama (puede tardar)"),
            width=38,
        ).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            settings, text="Horario autorizado (HH:MM-HH:MM, separado por comas; vacío = sin horario):"
        ).pack(anchor="w")
        ttk.Entry(settings, textvariable=self.schedule).pack(fill="x", pady=(0, 6))
        ttk.Checkbutton(
            settings,
            text="Iniciar Guardian con Windows (oculto en bandeja)",
            variable=self.autostart_var,
            command=self._toggle_autostart,
        ).pack(anchor="w")

    def _refresh_views(self) -> None:
        """Recompute the read-only panels from SQLite and the clock. Cheap, UI thread."""
        total, passed = self.store.stats()
        self.stats.set(f"Exámenes realizados: {total}   |   Aprobados certificados: {passed}")
        avg = self.store.average_score()
        self.average_text.set("Promedio: sin datos" if avg is None else f"Promedio: {avg:.1f}/5")
        recent = self.store.recent_attempts()
        self.recent_text.set(
            "\n".join(
                f"{when[:16].replace('T', ' ')}  {topic}  {attempt_label(score, ok, src)}"
                for when, topic, score, ok, src in recent
            )
            or "Aún no hay exámenes."
        )
        self.last_result.set(
            f"Último resultado: {attempt_label(recent[0][2], recent[0][3], recent[0][4])}"
            if recent
            else "Último resultado: ninguno"
        )
        self.pending_text.set(
            "● Examen pendiente: pulsa 'Hacer examen ahora'" if self.pending else "○ Sin examen pendiente"
        )
        if self.enabled and self.until is not None:
            left = max(0, int(self.clock.target - self.clock.eligible))
            self.next_review.set(
                f"Siguiente repaso: en unos {max(1, left // 60)} min de actividad (aleatorio)"
            )
        else:
            self.next_review.set("Siguiente repaso: sin sesión activa")

    # ---- session lifecycle (explicit, persisted so a restart keeps the user's choice) ----
    def _persist(self) -> None:
        active = self.enabled and self.until is not None
        paused = self.pause_until if self.pause_until > _now() else None
        self.session_store.save(
            SessionState(
                active=active,
                until=self.until if active else None,
                paused_until=paused if active else None,
                topic=self.topic.get().strip() or "Google Cloud",
                source=self.question_source.get(),
                pending=self.pending,
                windows=self.windows,
            )
        )

    def _restore_session(self) -> None:
        saved = self.session_store.load(_now())
        self.windows = saved.windows
        self.schedule.set(", ".join(f"{a}-{b}" for a, b in saved.windows))
        self.pending = saved.pending
        if saved.active:
            self.enabled, self.until = True, saved.until
            self.pause_until = saved.paused_until or _EPOCH
            self.topic.set(saved.topic)
            self.status.set(f"Sesión restaurada · hasta {saved.until:%H:%M} · pulsa Detener para terminar")
        if self.pending:
            self.status.set("Examen pendiente de antes del reinicio · pulsa 'Hacer examen ahora'")
            if self.enabled:
                self.root.after(2000, self._surprise_notice)

    def _start(self) -> None:
        try:
            self.windows = parse_schedule(self.schedule.get())
        except ValueError as err:
            self.status.set(str(err))
            return
        self.enabled = True
        self.until = _now() + timedelta(minutes=60)
        self.pause_until = _EPOCH
        self._persist()
        self.status.set("Estudiando · 60 min · se cuentan solo segundos de actividad")

    def _pause(self) -> None:
        if not self.enabled:
            self.status.set("No hay sesión activa que pausar")
            return
        self.pause_until = _now() + timedelta(minutes=15)
        self._persist()
        self.status.set("Pausado 15 min · sin preguntas")

    def _stop(self) -> None:
        self.enabled = False
        self.until = None
        self.pending = False
        self.clock.reset_after_quiz()
        self._persist()
        self.status.set("Desactivado · sin bloqueos")

    def _emergency(self) -> None:
        """Always-available exit: ends the session, drops any pending quiz, forgets saved state.
        Future FocoLocal leases created by Guardian must also be released here."""
        self._stop()
        self.windows = ()
        self.schedule.set("")
        self._persist()  # nothing left to keep: removes session.json
        if self.surprise_popup is not None and self.surprise_popup.winfo_exists():
            self.surprise_popup.destroy()
        self.surprise_popup = None
        self.status.set("Emergencia: sesión terminada, sin preguntas ni restricciones activas")

    def _toggle_autostart(self) -> None:
        try:
            if self.autostart_var.get():
                autostart.enable(_REPO_ROOT)
                self.status.set(
                    "Autoarranque activado (solo tu usuario). Se desactiva con esta misma casilla"
                )
            else:
                autostart.disable()
                self.status.set("Autoarranque desactivado")
        except OSError as err:
            self.autostart_var.set(autostart.is_enabled())
            self.status.set(f"No se pudo cambiar el autoarranque: {err}")

    def _refresh_health(self) -> None:
        def work() -> None:
            try:
                text = "  ·  ".join(
                    h.text() for h in integrations.check_all(bank_ok=fieldnotes.find_bank_path() is not None)
                )
                self.root.after(0, lambda: self.health.set(text))
                self.root.after(30000, self._refresh_health)
            except (tk.TclError, RuntimeError):
                pass  # window closed while probing

        threading.Thread(target=work, daemon=True).start()

    # ---- window / tray ----
    def _show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _hide(self) -> None:
        self.root.withdraw()

    def _poll_commands(self) -> None:
        try:
            while True:
                cmd = self.commands.get_nowait()
                {
                    "open": self._show,
                    "start": self._start,
                    "pause": self._pause,
                    "stop": self._stop,
                    "emergency": self._emergency,
                    "exit": self._exit,
                }.get(cmd, lambda: None)()
        except queue.Empty:
            pass
        except tk.TclError:
            return  # window already destroyed
        self.root.after(200, self._poll_commands)

    def _refresh_stats(self) -> None:
        self._refresh_views()

    def _tick(self) -> None:
        now_mono = time.monotonic()
        elapsed = max(0, now_mono - self.last_tick)
        self.last_tick = now_mono
        now = _now()
        try:
            self._refresh_views()
            if self.enabled and self.until is not None and now >= self.until:
                self._stop()
            due = self.clock.tick(
                elapsed,
                active=is_user_active(),
                allowed=self.enabled
                and now >= self.pause_until
                and self.until is not None
                and (not self.windows or within_study_window(now, self.windows)),
                protected=self.in_quiz,
            )
            if due and not self.in_quiz and not self.pending:
                self.pending = True
                self._persist()  # the pending exam must survive a restart
                self.status.set("Tienes un examen sorpresa pendiente · pulsa 'Hacer examen ahora'")
                self._surprise_notice()  # works with the panel hidden: it is a topmost Toplevel
        finally:
            self.root.after(1000, self._tick)

    def _surprise_notice(self) -> None:
        """Visible non-modal reminder; never steals keyboard focus."""
        if self.surprise_popup is not None:
            return
        notice = tk.Toplevel(self.root)
        self.surprise_popup = notice
        notice.title("Guardian · pregunta sorpresa")
        notice.resizable(False, False)
        notice.attributes("-topmost", True)
        w, h = 350, 132
        x = max(0, notice.winfo_screenwidth() - w - 36)
        y = max(0, notice.winfo_screenheight() - h - 95)
        notice.geometry(f"{w}x{h}+{x}+{y}")
        _no_activate(notice)  # appear without taking keyboard focus from the user's work
        body = ttk.Frame(notice, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="¡Repaso sorpresa! Tienes 5 preguntas pendientes.", wraplength=315).pack(
            anchor="w"
        )
        actions = ttk.Frame(body)
        actions.pack(anchor="e", pady=10)

        def dismiss() -> None:
            if self.surprise_popup is notice:
                self.surprise_popup = None
            if notice.winfo_exists():
                notice.destroy()

        def start() -> None:
            dismiss()
            self._open_quiz()

        ttk.Button(actions, text="Responder", command=start).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="Más tarde", command=dismiss).pack(side="left")
        notice.protocol("WM_DELETE_WINDOW", dismiss)
        notice.after(30000, dismiss)

    def _open_quiz(self) -> None:
        if self.in_quiz:
            return
        if self.surprise_popup is not None:
            popup = self.surprise_popup
            self.surprise_popup = None
            if popup.winfo_exists():
                popup.destroy()
        self.in_quiz = True
        mode = (
            "bank-practice"
            if self.question_source.get().startswith("Banco completo")
            else "bank-only"
            if self.question_source.get().startswith("Banco")
            else "ollama"
        )
        self.status.set(
            "Cargando preguntas del banco local…"
            if mode != "ollama"
            else "Generando preguntas con Ollama (máximo 30 s)…"
        )
        topic = self.topic.get().strip() or "Google Cloud"
        model = self.model.get().strip() or "qwen3.5:4b"
        recent = self.store.recent_prompts()

        def work() -> None:
            try:
                result = get_questions(topic, recent, model, mode=mode)
                self.root.after(0, lambda: self._present_quiz(topic, *result))
            except Exception as err:
                msg = str(err)
                self.root.after(0, lambda: self._generation_failed(msg))

        threading.Thread(target=work, daemon=True).start()

    def _generation_failed(self, error: str) -> None:
        self.in_quiz = False
        self.status.set("No se generó el cuestionario; no se aplicó ninguna restricción")
        messagebox.showwarning("No se pudo preparar el examen", error)
        # Keep the pending state to retry manually without spawning new interruptions.

    def _present_quiz(self, topic: str, questions: list, source: str) -> None:
        window = tk.Toplevel(self.root)
        window.title("Examen de 5 preguntas · Guardian")
        window.geometry("760x620")
        window.minsize(600, 460)
        if self.root.state() != "withdrawn":  # a transient child of a hidden panel would be invisible
            window.transient(self.root)
        window.lift()
        current = 0
        answers: list[int] = []
        selected = tk.IntVar(value=-1)
        # Long imported questions and answer options must remain reachable.
        canvas = tk.Canvas(window, highlightthickness=0)
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        content = ttk.Frame(canvas, padding=20)
        body_id = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(body_id, width=e.width))
        window.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-int(e.delta / 120), "units"))
        title = ttk.Label(content, wraplength=650, justify="left", font=("Segoe UI", 13, "bold"))
        title.pack(anchor="w", pady=(0, 15))
        choices = ttk.Frame(content)
        choices.pack(fill="x")
        note = (
            "Práctica: claves originales sin verificar; no otorga desbloqueos."
            if source.startswith("fieldnotes-practice")
            else "Apruebas con 4 de 5. Puedes salir sin penalización."
        )
        tip = ttk.Label(content, text=note)
        tip.pack(anchor="w", pady=20)

        def exit_quiz() -> None:
            self.in_quiz = False
            window.destroy()
            self.status.set("Examen pendiente: podrás reanudarlo cuando quieras")

        def render() -> None:
            q = questions[current]
            title.configure(text=f"{current + 1}/5  {q.prompt}")
            selected.set(-1)
            for child in choices.winfo_children():
                child.destroy()
            for i, opt in enumerate(q.options):
                tk.Radiobutton(
                    choices, text=opt, value=i, variable=selected, anchor="w", justify="left", wraplength=640
                ).pack(anchor="w", pady=8)
            canvas.yview_moveto(0)
            finish.configure(text="Corregir examen" if current == 4 else "Siguiente")

        def next_question() -> None:
            nonlocal current
            if selected.get() not in range(4):
                messagebox.showinfo(
                    "Respuesta pendiente", "Selecciona una respuesta para continuar", parent=window
                )
                return
            answers.append(selected.get())
            if current < 4:
                current += 1
                render()
                return
            score, passed = self.store.record(
                topic=topic, questions=questions, answers=answers, source=source
            )
            self.clock.reset_after_quiz()
            self.pending = False
            self.in_quiz = False
            self._persist()
            self._refresh_stats()
            window.destroy()
            unverified = source not in {
                "fieldnotes-reviewed",
                "fieldnotes+fallback-reviewed",
                "fallback-reviewed",
            }
            state = "Práctica (sin verificación)" if unverified else ("Aprobado" if passed else "Repasar")
            self.status.set(f"Resultado: {score}/5 · {state} · {source}")
            show_exam_result(
                self.root,
                topic=topic,
                questions=questions,
                answers=answers,
                score=score,
                passed=passed,
                source=source,
            )

        finish = ttk.Button(content, command=next_question)
        finish.pack(anchor="e", pady=8)
        ttk.Button(content, text="Posponer / salir", command=exit_quiz).pack(anchor="e")
        window.protocol("WM_DELETE_WINDOW", exit_quiz)
        render()

    def _exit(self) -> None:
        if self.in_quiz:
            self._show()
            if not messagebox.askyesno("Salir", "¿Salir del examen sin guardar las respuestas?"):
                return
        self.tray.stop()
        self.store.close()
        self.root.destroy()  # the saved session (if any) is kept: it is the user's explicit choice


def _no_activate(window: tk.Toplevel) -> None:
    """Mark a window WS_EX_NOACTIVATE so showing it never steals focus (Windows only)."""
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        user32 = ctypes.windll.user32
        user32.GetParent.restype = wintypes.HWND
        user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        hwnd = user32.GetParent(window.winfo_id()) or window.winfo_id()
        style = user32.GetWindowLongPtrW(hwnd, -20)  # GWL_EXSTYLE
        user32.SetWindowLongPtrW(hwnd, -20, style | 0x08000000)
    except (OSError, tk.TclError, AttributeError):
        pass  # cosmetic hardening only


_REPO_ROOT = Path(__file__).resolve().parents[2]
_EPOCH = datetime.min.replace(tzinfo=UTC)


def _now() -> datetime:
    return datetime.now().astimezone()


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenTutor Guardian (agente residente, sin bloqueos)")
    parser.add_argument("--demo", action="store_true", help="Avisos cada 20–30 s elegibles para probar la UI")
    parser.add_argument("--hidden", action="store_true", help="Arranca con el panel oculto en la bandeja")
    args = parser.parse_args()
    lock = SingleInstance("OpenTutorGuardian")
    if not lock.acquire():
        print("Guardian ya está en ejecución: busca su icono en la bandeja del sistema.")
        return
    root = tk.Tk()
    ui = GuardianUI(root, demo=args.demo)
    if args.hidden and ui.tray_ok:
        root.withdraw()
    try:
        root.mainloop()
    finally:
        lock.release()


if __name__ == "__main__":
    main()
