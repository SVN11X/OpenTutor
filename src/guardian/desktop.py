"""Opt-in Windows desktop prototype: non-privileged, no browser blocking."""

from __future__ import annotations

import argparse
import ctypes
import logging
import os
import queue
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from datetime import time as day_time
from pathlib import Path
from tkinter import messagebox, ttk

from . import autostart, fieldnotes, integrations
from .activity_log import ActivityLog
from .core import (
    CERTIFIED_QUESTION_SOURCES,
    ResultStore,
    SurpriseClock,
    attempt_label,
    within_study_window,
)
from .evidence_ui import EvidencePanel
from .logging_setup import setup_logging
from .presence import Presence, busy_reason, is_user_active
from .questions import get_questions
from .quiz_window import QuizWindow
from .results_ui import show_exam_result
from .session_state import SessionState, SessionStore, parse_schedule
from .settings_store import Settings, SettingsStore
from .settings_ui import SET_TOPICS, QuestionSettingsPanel, bank_summary, quiz_mode
from .single_instance import SingleInstance
from .task_store import TaskStore
from .today_view import AgentState, active_today, counter_line, headline, setup_steps
from .tray import TrayIcon


class GuardianUI:
    def __init__(self, root: tk.Tk, *, demo: bool = False) -> None:
        self.root = root
        self.root.title("OpenTutor Guardian")
        # Fit small laptop screens at 125 or 150 %, centered so the taskbar never hides the exits.
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        height = min(700, screen_h - 120)
        self.root.geometry(
            f"600x{height}+{max(0, (screen_w - 600) // 2)}+{max(0, (screen_h - height) // 2 - 30)}"
        )
        self.root.minsize(560, min(600, height))
        app_data = _app_data()
        self.store = ResultStore(app_data / "guardian_mvp.sqlite3")
        self.demo = demo
        self.settings_store = SettingsStore(app_data / "guardian_mvp.sqlite3")
        self.settings = self.settings_store.load()
        self.clock = SurpriseClock(interval=self._interval())
        self.session_store = SessionStore(
            app_data / "guardian_mvp.sqlite3", legacy_json=app_data / "session.json"
        )
        self.enabled = False  # opt-in: a session starts only if the user started it before
        self.user_stopped = False  # Terminar or Emergencia: all-day mode waits for the next start
        self.start_label = tk.StringVar(value=self._start_text())
        self.all_day_var = tk.BooleanVar(value=self.settings.all_day)
        self.pause_until = _EPOCH
        self.in_quiz = False
        self.pending = False
        self.surprise_popup = None
        self.quiz: QuizWindow | None = None
        self.last_tick = time.monotonic()
        # Grace after start so the desktop loads before an insistent quiz, and backoff after a failure.
        self.retry_at = self.last_tick + (5 if demo else 60)
        self.insistent_var = tk.BooleanVar(value=self.settings.insistent)
        self.presence = Presence()
        self.paused_reason: str | None = None
        self.activity = ActivityLog(app_data / "guardian_mvp.sqlite3")
        self.unsaved_seconds = 0.0
        self.activity_day = date.today()
        self.saved_today = self.activity.seconds_on(self.activity_day)
        # The user explicitly activates a bounded study session; no surprise outside it.
        self.until: datetime | None = None
        self.status = tk.StringVar(value="")
        self.headline_text = tk.StringVar(value="")
        self.counter_text = tk.StringVar(value="")
        self.today_text = tk.StringVar(value="")
        self.bank_found = bank_summary(self.settings.bank_path)[0]
        self.guide_shown: tuple | None = None
        self.stats = tk.StringVar(value="")
        self.last_result = tk.StringVar(value="")
        self.pending_text = tk.StringVar(value="")
        self.recent_text = tk.StringVar(value="")
        self.average_text = tk.StringVar(value="")
        self.windows: tuple[tuple[str, str], ...] = ()
        self.schedule = tk.StringVar(value="")
        self.health = tk.StringVar(value="Comprobando servicios…")
        autostart.refresh_if_stale(_REPO_ROOT)  # migrate a pre-rename Run value, never creates one
        self.autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        self.task_store = TaskStore(app_data / "guardian_mvp.sqlite3")
        self.evidence_panel = EvidencePanel(root, self.task_store, self.status.set)
        self._render()
        self._refresh_stats()
        self._restore_session()
        if self.settings.all_day and not self.enabled:
            self._start()  # all-day mode: the owner chose to study from sign-in, decision 0007
        if not self.bank_found and self.settings.source != "ollama":
            self.status.set("No encuentro el banco de preguntas: elige su carpeta en Ajustes")
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
        today, tasks, evidence, reviews, progress, settings = (
            ttk.Frame(self.tabs, padding=12) for _ in range(6)
        )
        for page, name in (
            (today, "Hoy"),
            (tasks, "Tareas"),
            (evidence, "Evidencia"),
            (reviews, "Repasos"),
            (progress, "Progreso"),
            (settings, "Ajustes"),
        ):
            self.tabs.add(page, text=name)
        self.tabs.enable_traversal()  # Ctrl+Tab and Ctrl+PgUp/PgDn

        # Hoy: what Guardian is doing, the controls, first steps, then the always-visible exits
        now_box = ttk.LabelFrame(today, text="Ahora", padding=10)
        now_box.pack(fill="x")
        ttk.Label(
            now_box, textvariable=self.headline_text, foreground="#1a4f8a", font=("Segoe UI", 12, "bold")
        ).pack(anchor="w")
        ttk.Label(now_box, textvariable=self.counter_text).pack(anchor="w", pady=(6, 0))
        ttk.Label(now_box, textvariable=self.today_text).pack(anchor="w", pady=(2, 8))
        controls = ttk.Frame(now_box)
        controls.pack(anchor="w")
        ttk.Button(controls, textvariable=self.start_label, command=self._start).pack(
            side="left", padx=(0, 7)
        )
        ttk.Button(controls, text="Pausar 15 min", command=self._pause).pack(side="left", padx=(0, 7))
        ttk.Button(controls, text="Terminar", command=self._stop).pack(side="left", padx=(0, 7))
        ttk.Button(controls, text="Hacer examen ahora", command=self._open_quiz).pack(side="left")
        ttk.Label(today, textvariable=self.last_result).pack(anchor="w", pady=(10, 0))
        ttk.Label(today, textvariable=self.status, foreground="#555555", wraplength=520, justify="left").pack(
            anchor="w", pady=(4, 10)
        )
        self.guide_box = ttk.LabelFrame(today, text="Primeros pasos", padding=10)
        self.guide_rows = ttk.Frame(self.guide_box)
        self.guide_rows.pack(fill="x")
        guide_actions = ttk.Frame(self.guide_box)
        guide_actions.pack(anchor="e", pady=(6, 0))
        ttk.Button(guide_actions, text="Ir a Ajustes", command=lambda: self.tabs.select(5)).pack(
            side="left", padx=(0, 7)
        )
        ttk.Button(guide_actions, text="Ocultar guía", command=self._hide_guide).pack(side="left")
        bottom = ttk.Frame(today)
        bottom.pack(side="bottom", fill="x")
        ttk.Label(
            bottom, textvariable=self.health, foreground="#555555", wraplength=520, justify="left"
        ).pack(anchor="w", pady=(0, 6))
        row = ttk.Frame(bottom)
        row.pack(anchor="w")
        ttk.Button(row, text="Emergencia", command=self._emergency).pack(side="left", padx=(0, 7))
        ttk.Button(row, text="Ocultar a bandeja", command=self._hide).pack(side="left", padx=(0, 7))
        ttk.Button(row, text="Salir", command=self._exit).pack(side="left")

        # Tareas and Evidencia: written by the owner, checked by a deterministic rubric
        self.evidence_panel.build_tasks_tab(tasks)
        self.evidence_panel.build_evidence_tab(evidence)

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

        # Ajustes: what is asked, then when
        self.question_panel = QuestionSettingsPanel(
            settings, self.settings_store, self.settings, self._on_settings_saved, self.status.set
        )
        when = ttk.LabelFrame(settings, text="Cuándo", padding=10)
        when.pack(fill="x")
        ttk.Label(
            when, text="Horario de estudio (HH:MM-HH:MM, separado por comas. Vacío = todo el día):"
        ).pack(anchor="w")
        ttk.Entry(when, textvariable=self.schedule).pack(fill="x", pady=(0, 6))
        ttk.Checkbutton(
            when,
            text="Iniciar Guardian con Windows (oculto en bandeja)",
            variable=self.autostart_var,
            command=self._toggle_autostart,
        ).pack(anchor="w")
        ttk.Checkbutton(
            when,
            text="Todo el día: la sesión empieza sola al iniciar Windows y se renueva a medianoche",
            variable=self.all_day_var,
            command=self._toggle_all_day,
        ).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(
            when,
            text="Ventana insistente: el examen no se puede posponer y vuelve si lo cierras",
            variable=self.insistent_var,
            command=self._toggle_insistent,
        ).pack(anchor="w", pady=(4, 0))

    def _refresh_stats(self) -> None:
        """Read results from SQLite. Only at start and after a quiz, never every second."""
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

    def _refresh_views(self) -> None:
        """Recompute the live texts from memory. Runs every second, so it never touches SQLite."""
        now = _now()
        state = AgentState(
            enabled=self.enabled and self.until is not None,
            all_day=self.settings.all_day,
            until=self.until,
            paused_until=self.pause_until if self.pause_until > now else None,
            pending=self.pending,
            in_quiz=self.in_quiz,
        )
        self.headline_text.set(headline(state, now))
        self.counter_text.set(
            counter_line(
                state.enabled, self.paused_reason, self.clock.eligible, self.clock.target, self.pending
            )
        )
        self.today_text.set(active_today(self.saved_today + self.unsaved_seconds))
        self.pending_text.set(
            "● Examen pendiente: pulsa 'Hacer examen ahora'" if self.pending else "○ Sin examen pendiente"
        )
        self._refresh_guide()

    def _refresh_guide(self) -> None:
        steps = setup_steps(
            bank_found=self.bank_found, all_day=self.settings.all_day, autostart=self.autostart_var.get()
        )
        shown = None if self.settings.guide_done or all(done for done, _ in steps) else tuple(steps)
        if shown == self.guide_shown:
            return
        self.guide_shown = shown
        if shown is None:
            self.guide_box.pack_forget()
            return
        for child in self.guide_rows.winfo_children():
            child.destroy()
        for done, text in shown:
            ttk.Label(self.guide_rows, text=("✔ " if done else "✖ ") + text).pack(anchor="w")
        self.guide_box.pack(fill="x", pady=(0, 10))

    def _hide_guide(self) -> None:
        try:
            self.settings = self.settings_store.save(replace(self.settings_store.load(), guide_done=True))
        except (ValueError, OSError) as err:
            self.status.set(f"No se pudo guardar: {err}")

    # ---- session lifecycle (explicit, persisted so a restart keeps the user's choice) ----
    def _persist(self) -> None:
        active = self.enabled and self.until is not None
        paused = self.pause_until if self.pause_until > _now() else None
        self.session_store.save(
            SessionState(
                active=active,
                until=self.until if active else None,
                paused_until=paused if active else None,
                topic=SET_TOPICS[self.settings.question_set],
                source=self.settings.source,
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
            self.status.set("Sesión restaurada después de reiniciar")
        if self.pending:
            self.status.set("Examen pendiente de antes del reinicio · pulsa 'Hacer examen ahora'")
            if self.enabled and not self.settings.insistent:
                self.root.after(2000, self._surprise_notice)

    def _start_text(self) -> str:
        return "Iniciar día" if self.settings.all_day else "Iniciar estudio (60 min)"

    def _start(self) -> None:
        try:
            self.windows = parse_schedule(self.schedule.get())
        except ValueError as err:
            self.status.set(str(err))
            return
        now = _now()
        self.enabled = True
        self.user_stopped = False
        self.until = session_end(now, all_day=self.settings.all_day)
        self.pause_until = _EPOCH
        self._persist()
        if self.settings.all_day:
            self.status.set("Estudiando todo el día · se cuentan solo segundos de actividad")
        else:
            self.status.set("Estudiando · 60 min · se cuentan solo segundos de actividad")

    def _pause(self) -> None:
        if not self.enabled:
            self.status.set("No hay sesión activa que pausar")
            return
        self.pause_until = _now() + timedelta(minutes=15)
        self._persist()
        self.status.set("Pausado 15 min · sin preguntas")

    def _stop(self, by_user: bool = True) -> None:
        """End the session. A pending quiz stays pending: only Emergencia drops it (decision 0007)."""
        self.enabled = False
        self.until = None
        self.user_stopped = by_user
        self.clock.reset_after_quiz()
        self._close_quiz()
        self._persist()
        self.status.set("Sesión terminada" + (" · queda un examen pendiente" if self.pending else ""))

    def _emergency(self) -> None:
        """Always-available exit: ends the session, drops any pending quiz, forgets saved state.
        Future FocoLocal leases created by Guardian must also be released here."""
        self.pending = False
        self._stop()
        self.windows = ()
        self.schedule.set("")
        self._persist()  # nothing left to keep: removes the saved row
        if self.surprise_popup is not None and self.surprise_popup.winfo_exists():
            self.surprise_popup.destroy()
        self.surprise_popup = None
        self.status.set("Emergencia: sesión terminada, sin preguntas ni restricciones activas")

    def _interval(self) -> tuple[int, int]:
        if self.demo:
            return (20, 30)
        return (self.settings.interval_min * 60, self.settings.interval_max * 60)

    def _on_settings_saved(self, settings: Settings) -> None:
        """Apply saved settings now. A new interval starts a new countdown, the pending quiz stays."""
        changed = (settings.interval_min, settings.interval_max) != (
            self.settings.interval_min,
            self.settings.interval_max,
        )
        self.settings = settings
        self.bank_found = bank_summary(settings.bank_path)[0]
        if changed:
            self.clock = SurpriseClock(interval=self._interval())
        self._persist()
        self._refresh_health(repeat=False)

    def _toggle_insistent(self) -> None:
        on = self.insistent_var.get()
        try:
            self.settings = self.settings_store.save(replace(self.settings_store.load(), insistent=on))
        except (ValueError, OSError) as err:
            self.insistent_var.set(self.settings.insistent)
            self.status.set(f"No se pudo guardar: {err}")
            return
        self.status.set(
            "Ventana insistente activada: el próximo examen no se podrá posponer"
            if on
            else "Ventana insistente desactivada: verás un aviso con 'Más tarde'"
        )

    def _toggle_all_day(self) -> None:
        """Save the all-day choice. Turning it on also turns on autostart, or it cannot start at sign-in."""
        on = self.all_day_var.get()
        try:
            self.settings = self.settings_store.save(replace(self.settings_store.load(), all_day=on))
        except (ValueError, OSError) as err:
            self.all_day_var.set(self.settings.all_day)
            self.status.set(f"No se pudo guardar: {err}")
            return
        self.start_label.set(self._start_text())
        if on and not self.autostart_var.get():
            self.autostart_var.set(True)
            self._toggle_autostart()
        if on and not self.enabled:
            self._start()
        elif on and self.until is not None:
            self.until = session_end(_now(), all_day=True)
            self._persist()
        self.status.set(
            "Todo el día activado: empieza sola al iniciar Windows. Se apaga con esta misma casilla"
            if on
            else "Todo el día desactivado: la próxima sesión durará 60 min"
        )

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

    def _refresh_health(self, repeat: bool = True) -> None:
        """Probe the services off the UI thread. Only the startup call repeats, so loops never stack."""

        def work() -> None:
            try:
                bank_ok = fieldnotes.find_bank_path(self.settings.bank_path or None) is not None
                text = "  ·  ".join(h.text() for h in integrations.check_all(bank_ok=bank_ok))
                self.root.after(0, lambda: self.health.set(text))
                if repeat:
                    self.root.after(30000, self._refresh_health)
            except (tk.TclError, RuntimeError) as err:
                log.debug("Health refresh skipped: %s", err)  # window closed while probing

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
                if self.presence.on_event(cmd):
                    if cmd == "resume":
                        self.last_tick = time.monotonic()  # never count the time spent suspended
                    continue
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

    def _tick(self) -> None:
        now_mono = time.monotonic()
        elapsed = max(0, now_mono - self.last_tick)
        self.last_tick = now_mono
        now = _now()
        try:
            self._refresh_views()
            if self.enabled and self.until is not None and now >= self.until:
                self._stop(by_user=False)
                if self.settings.all_day:
                    self._start()  # a new day of the all-day session
            active = is_user_active() and not self.presence.suspended and not self.presence.locked
            self.paused_reason = self.presence.paused_reason(active)
            before = self.clock.eligible
            due = self.clock.tick(
                elapsed,
                active=active,
                allowed=self.enabled
                and now >= self.pause_until
                and self.until is not None
                and (not self.windows or within_study_window(now, self.windows)),
                protected=self.in_quiz,
            )
            self._count_activity(self.clock.eligible - before)
            if due and not self.in_quiz and not self.pending:
                self.pending = True
                self._persist()  # the pending exam must survive a restart
                self.status.set("Tienes un examen sorpresa pendiente · pulsa 'Hacer examen ahora'")
                if not self.settings.insistent:
                    self._surprise_notice()  # works with the panel hidden: it is a topmost Toplevel
            if self.pending and self.settings.insistent and not self.in_quiz:
                wait = self._insistent_wait(now, now_mono)
                if wait is None:
                    self._open_quiz(insistent=True)
                elif wait:
                    self.status.set(f"Examen pendiente en espera: {wait}")
        finally:
            self.root.after(1000, self._tick)

    def _count_activity(self, seconds: float) -> None:
        """Keep today's eligible seconds, written to SQLite about every 30 s to avoid a write per tick."""
        self.unsaved_seconds += max(0.0, seconds)
        if self.unsaved_seconds >= 30 or date.today() != self.activity_day:
            self._flush_activity()

    def _flush_activity(self) -> None:
        if self.unsaved_seconds > 0:
            self.activity.add(self.activity_day, self.unsaved_seconds)
            self.saved_today += self.unsaved_seconds
            self.unsaved_seconds = 0.0
        if date.today() != self.activity_day:  # a new day starts from its own total
            self.activity_day = date.today()
            self.saved_today = self.activity.seconds_on(self.activity_day)

    def _insistent_wait(self, now: datetime, now_mono: float) -> str | None:
        """Why an insistent quiz cannot open yet ('' for a silent wait), or None when it can."""
        if not self.enabled or now_mono < self.retry_at:
            return ""
        if now < self.pause_until:
            return "pausa"
        if self.windows and not within_study_window(now, self.windows):
            return "fuera del horario"
        if self.presence.suspended or self.presence.locked:
            return ""
        busy = busy_reason()
        if busy is not None:
            return "pantalla completa" if busy == "fullscreen" else "modo presentación"
        return None

    def _close_quiz(self) -> None:
        if self.quiz is not None:
            self.quiz.close()
        self.quiz = None
        self.in_quiz = False

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

    def _open_quiz(self, insistent: bool | None = None) -> None:
        """Load five questions off the UI thread. A pending quiz in insistent mode cannot be postponed."""
        if self.in_quiz:
            if self.quiz is not None and self.quiz.alive and self.quiz.insistent:
                self.quiz.present()
            return
        if insistent is None:
            insistent = self.pending and self.settings.insistent
        if self.surprise_popup is not None:
            popup = self.surprise_popup
            self.surprise_popup = None
            if popup.winfo_exists():
                popup.destroy()
        self.in_quiz = True
        settings = self.settings
        mode = quiz_mode(settings.source)
        self.status.set(
            "Cargando preguntas del banco local…"
            if mode != "ollama"
            else "Generando preguntas con Ollama (máximo 30 s)…"
        )
        topic = SET_TOPICS[settings.question_set]
        recent = self.store.recent_prompts()
        cards = self.store.cards()

        def work() -> None:
            try:
                result = get_questions(
                    topic,
                    recent,
                    settings.model,
                    mode=mode,
                    bank_path=settings.bank_path or None,
                    cards=cards,
                    domains=settings.domains,
                )
                self.root.after(0, lambda: self._present_quiz(topic, *result, insistent=insistent))
            except Exception as err:
                msg = str(err)
                self.root.after(0, lambda: self._generation_failed(msg, quiet=insistent))

        threading.Thread(target=work, daemon=True).start()

    def _generation_failed(self, error: str, quiet: bool = False) -> None:
        """Keep the quiz pending. An automatic attempt retries in 5 minutes instead of showing a dialog."""
        self.in_quiz = False
        if quiet:
            self.retry_at = time.monotonic() + 300
            self.status.set(f"No se pudo preparar el examen: {error}. Reintento en 5 min")
            log.warning("Insistent quiz could not load questions: %s", error)
            return
        self.status.set("No se generó el cuestionario; no se aplicó ninguna restricción")
        messagebox.showwarning("No se pudo preparar el examen", error)

    def _present_quiz(self, topic: str, questions: list, source: str, *, insistent: bool = False) -> None:
        def done(answers: list[int]) -> None:
            self._finish_quiz(topic, questions, answers, source)

        def postponed() -> None:
            self.quiz, self.in_quiz = None, False
            self.status.set("Examen pendiente: podrás reanudarlo cuando quieras")

        self.quiz = QuizWindow(
            self.root,
            questions=questions,
            source=source,
            insistent=insistent,
            on_done=done,
            on_leave=postponed,
        )
        self.status.set("Examen abierto: responde las 5 preguntas" if insistent else "Examen abierto")

    def _finish_quiz(self, topic: str, questions: list, answers: list[int], source: str) -> None:
        score, passed = self.store.record(topic=topic, questions=questions, answers=answers, source=source)
        self.clock.reset_after_quiz()
        self.quiz, self.pending, self.in_quiz = None, False, False
        self._persist()
        self._refresh_stats()
        unverified = source not in CERTIFIED_QUESTION_SOURCES
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

    def _exit(self) -> None:
        if self.in_quiz:
            self._show()
            if not messagebox.askyesno("Salir", "¿Salir del examen sin guardar las respuestas?"):
                return
        self._flush_activity()
        self.tray.stop()
        self.store.close()
        self.root.destroy()  # the saved session (if any) is kept: it is the user's explicit choice


def session_end(now: datetime, *, all_day: bool) -> datetime:
    """When a session started now ends: the next local midnight in all-day mode, else in 60 minutes."""
    if all_day:
        return datetime.combine(now.date() + timedelta(days=1), day_time.min, tzinfo=now.tzinfo)
    return now + timedelta(minutes=60)


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
    except (OSError, tk.TclError, AttributeError) as err:
        log.debug("WS_EX_NOACTIVATE not applied: %s", err)  # cosmetic hardening only


log = logging.getLogger(__name__)


def _app_data() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share")))
    return base / "OpenTutorGuardian"


_REPO_ROOT = Path(__file__).resolve().parents[2]
_EPOCH = datetime.min.replace(tzinfo=UTC)


def _now() -> datetime:
    return datetime.now().astimezone()


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenTutor Guardian (agente residente, sin bloqueos)")
    parser.add_argument("--demo", action="store_true", help="Avisos cada 20–30 s elegibles para probar la UI")
    parser.add_argument("--hidden", action="store_true", help="Arranca con el panel oculto en la bandeja")
    args = parser.parse_args()
    setup_logging(_app_data())
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
