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
from .core import ResultStore, SurpriseClock, attempt_label, within_study_window
from .evidence_ui import EvidencePanel
from .i18n import t
from .logging_setup import setup_logging
from .presence import Presence, busy_reason, is_user_active
from .questions import get_questions
from .quiz_window import QuizWindow
from .results_ui import show_exam_result
from .session_state import SessionState, SessionStore, parse_schedule
from .settings_store import Settings, SettingsStore
from .settings_ui import SAVE_DELAY_MS, SET_TOPICS, QuestionSettingsPanel, bank_summary, quiz_mode
from .single_instance import SingleInstance
from .task_store import TaskStore
from .today_view import AgentState, actions, active_today, counter_line, headline, setup_steps
from .tray import ICON_PATH, TrayIcon
from .widgets import primary_style, scrolled


class GuardianUI:
    def __init__(self, root: tk.Tk, *, demo: bool = False) -> None:
        self.root = root
        self.root.title("OpenTutor Guardian")
        try:
            self.root.iconbitmap(default=str(ICON_PATH))  # every window of the app, not only the panel
        except tk.TclError as err:
            log.warning("Window icon not set: %s", err)
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
        self.retry_reason = t("panel.wait_startup")
        self.wait_reason: str | None = None  # why the pending insistent quiz waits, for the headline
        self.insistent_var = tk.BooleanVar(value=self.settings.insistent)
        self.presence = Presence()
        self.paused_reason: str | None = None
        self.activity = ActivityLog(app_data / "guardian_mvp.sqlite3")
        self.unsaved_seconds = 0.0
        self.activity_day = date.today()
        self.saved_today = self.activity.seconds_on(self.activity_day)
        # The user explicitly activates a bounded study session; no surprise outside it.
        self.until: datetime | None = None
        self.status = tk.StringVar(value="")  # what an action just did, never the state
        self.settings_status = tk.StringVar(value=t("settings.autosave_note"))
        self.shown_actions: tuple | None = None
        self.schedule_job: str | None = None
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
        self.health = tk.StringVar(value=t("panel.checking_services"))
        autostart.refresh_if_stale(_REPO_ROOT)  # migrate a pre-rename Run value, never creates one
        self.autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        self.task_store = TaskStore(app_data / "guardian_mvp.sqlite3")
        self.evidence_panel = EvidencePanel(root, self.task_store, self.status.set)
        self._render()
        self._refresh_stats()
        self._restore_session()
        self.schedule.trace_add("write", self._schedule_changed)
        if self.settings.all_day and not self.enabled:
            self._start()  # all-day mode: the owner chose to study from sign-in, decision 0007
        if not self.bank_found and self.settings.source != "ollama":
            self.status.set(t("panel.bank_missing_hint"))
        self.commands: queue.Queue[str] = queue.Queue()
        self.tray = TrayIcon(self.commands.put)
        self.tray_ok = self.tray.start()
        if not self.tray_ok:
            self.status.set(self.status.get() + t("panel.no_tray_suffix"))
        root.after(1000, self._tick)
        root.after(200, self._poll_commands)
        self._refresh_health()
        # With a tray icon the close button hides the panel; without one it must exit.
        root.protocol("WM_DELETE_WINDOW", self._hide if self.tray_ok else self._exit)

    def _render(self) -> None:
        frame = ttk.Frame(self.root, padding=(14, 12))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="OpenTutor Guardian", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=t("panel.tagline")).pack(anchor="w", pady=(0, 6))
        self.tabs = ttk.Notebook(frame)
        self.tabs.pack(fill="both", expand=True)
        today, tasks, evidence, reviews, progress, settings = (
            ttk.Frame(self.tabs, padding=12) for _ in range(6)
        )
        for page, name in (
            (today, t("panel.tab_today")),
            (tasks, t("panel.tab_tasks")),
            (evidence, t("panel.tab_evidence")),
            (reviews, t("panel.tab_reviews")),
            (progress, t("panel.tab_progress")),
            (settings, t("panel.tab_settings")),
        ):
            self.tabs.add(page, text=name)
        self.tabs.enable_traversal()  # Ctrl+Tab and Ctrl+PgUp/PgDn

        # Hoy: the state once, the buttons for it, first steps, then Emergencia apart from the exits
        now_box = ttk.LabelFrame(today, text=t("panel.now"), padding=10)
        now_box.pack(fill="x", pady=(0, 10))
        headline_label = ttk.Label(
            now_box,
            textvariable=self.headline_text,
            foreground="#1a4f8a",
            font=("Segoe UI", 12, "bold"),
            wraplength=520,
            justify="left",
        )
        headline_label.pack(anchor="w")
        counter = ttk.Label(now_box, textvariable=self.counter_text)
        facts = ttk.Frame(now_box)
        facts.pack(anchor="w", pady=(6, 8))
        ttk.Label(facts, textvariable=self.today_text).pack(side="left")
        ttk.Label(facts, text="  ·  ").pack(side="left")
        ttk.Label(facts, textvariable=self.last_result).pack(side="left")
        self.controls = ttk.Frame(now_box)
        self.controls.pack(anchor="w")
        feedback = ttk.Label(
            now_box, textvariable=self.status, foreground="#555555", wraplength=520, justify="left"
        )
        _pack_when_text(counter, self.counter_text, anchor="w", pady=(6, 0), after=headline_label)
        _pack_when_text(feedback, self.status, anchor="w", pady=(8, 0), after=self.controls)
        self.guide_box = ttk.LabelFrame(today, text=t("panel.first_steps"), padding=10)
        # The guide's buttons stand beside its steps, so the tab fits a 600 px high window.
        guide_actions = ttk.Frame(self.guide_box)
        guide_actions.pack(side="right", anchor="n", padx=(8, 0))
        ttk.Button(guide_actions, text=t("panel.go_settings"), command=lambda: self.tabs.select(5)).pack(
            fill="x"
        )
        ttk.Button(guide_actions, text=t("panel.hide_guide"), command=self._hide_guide).pack(
            fill="x", pady=(8, 0)
        )
        self.guide_rows = ttk.Frame(self.guide_box)
        self.guide_rows.pack(side="left", fill="x", expand=True)
        bottom = ttk.Frame(today)
        bottom.pack(side="bottom", fill="x")
        ttk.Label(
            bottom, textvariable=self.health, foreground="#555555", wraplength=520, justify="left"
        ).pack(anchor="w", pady=(0, 6))
        ttk.Separator(bottom, orient="horizontal").pack(fill="x", pady=(0, 8))
        rescue = ttk.Frame(bottom)
        rescue.pack(fill="x")
        emergency = ttk.Button(rescue, text=t("panel.emergency"), command=self._emergency)
        emergency.pack(side="left", anchor="n")
        help_text = ttk.Label(rescue, text=t("panel.emergency_help"), foreground="#555555", justify="left")
        help_text.pack(side="left", padx=(8, 0))
        rescue.bind(
            "<Configure>",
            lambda e: help_text.configure(wraplength=max(200, e.width - emergency.winfo_width() - 16)),
        )
        exits = ttk.Frame(bottom)
        exits.pack(fill="x", pady=(8, 0))
        ttk.Button(exits, text=t("panel.exit"), command=self._exit).pack(side="right")
        ttk.Button(exits, text=t("panel.hide_to_tray"), command=self._hide).pack(side="right", padx=(0, 8))

        # Tareas and Evidencia: written by the owner, checked by a deterministic rubric
        self.evidence_panel.build_tasks_tab(tasks)
        self.evidence_panel.build_evidence_tab(evidence)

        # Repasos: pending exam and recent results
        ttk.Label(reviews, textvariable=self.pending_text, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(reviews, text=t("panel.recent_results"), font=("Segoe UI", 10, "bold")).pack(
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
            text=t("panel.practice_note"),
        ).pack(anchor="w", pady=6)

        # Ajustes: what is asked, then when. Every change saves itself, the line below says when it did.
        ttk.Label(
            settings, textvariable=self.settings_status, foreground="#555555", wraplength=520, justify="left"
        ).pack(side="bottom", anchor="w", pady=(8, 0))
        _canvas, settings_body = scrolled(settings, padding=(0, 0, 8, 0))
        self.question_panel = QuestionSettingsPanel(
            settings_body,
            self.settings_store,
            self.settings,
            self._on_settings_saved,
            self.settings_status.set,
        )
        when = ttk.LabelFrame(settings_body, text=t("panel.when"), padding=10)
        when.pack(fill="x")
        ttk.Label(when, text=t("panel.schedule_label")).pack(anchor="w")
        ttk.Entry(when, textvariable=self.schedule).pack(fill="x", pady=(2, 8))
        ttk.Checkbutton(
            when,
            text=t("panel.autostart_check"),
            variable=self.autostart_var,
            command=self._toggle_autostart,
        ).pack(anchor="w", pady=(8, 0))
        ttk.Checkbutton(
            when,
            text=t("panel.all_day_check"),
            variable=self.all_day_var,
            command=self._toggle_all_day,
        ).pack(anchor="w", pady=(8, 0))
        ttk.Checkbutton(
            when,
            text=t("panel.insistent_check"),
            variable=self.insistent_var,
            command=self._toggle_insistent,
        ).pack(anchor="w", pady=(8, 0))

    def _refresh_stats(self) -> None:
        """Read results from SQLite. Only at start and after a quiz, never every second."""
        total, passed = self.store.stats()
        self.stats.set(t("panel.stats", total=total, passed=passed))
        avg = self.store.average_score()
        self.average_text.set(t("panel.average_none") if avg is None else t("panel.average", avg=avg))
        recent = self.store.recent_attempts()
        self.recent_text.set(
            "\n".join(
                f"{when[:16].replace('T', ' ')}  {topic}  {attempt_label(score, ok, src)}"
                for when, topic, score, ok, src in recent
            )
            or t("panel.no_exams")
        )
        self.last_result.set(
            t("panel.last_result", label=attempt_label(recent[0][2], recent[0][3], recent[0][4]))
            if recent
            else t("panel.last_result_none")
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
            insistent=self.settings.insistent,
            wait=self.wait_reason,
        )
        self.headline_text.set(headline(state, now))
        self.counter_text.set(
            counter_line(
                state.enabled, self.paused_reason, self.clock.eligible, self.clock.target, self.pending
            )
        )
        self.today_text.set(active_today(self.saved_today + self.unsaved_seconds))
        self.pending_text.set(t("panel.pending_exam") if self.pending else t("panel.pending_exam_none"))
        self._render_actions(state, now)
        self._refresh_guide()

    def _render_actions(self, state: AgentState, now: datetime) -> None:
        """Show only the buttons that do something now, the main one marked. Rebuilt on a change only."""
        wanted = (tuple(actions(state, now)), state.in_quiz, self.start_label.get())
        if wanted == self.shown_actions:
            return
        self.shown_actions = wanted
        try:
            focused = str(self.root.focus_get() or "").startswith(f"{self.controls}.")
        except (KeyError, tk.TclError):  # focus in a popup Tk does not name
            focused = False
        commands = {
            "start": self._start,
            "quiz": self._open_quiz,
            "pause": self._pause,
            "resume": self._resume,
            "stop": self._stop,
        }
        labels = {
            "start": self.start_label.get(),
            "quiz": t("panel.back_to_quiz") if state.in_quiz else t("panel.start_quiz"),
            "pause": t("panel.pause_15"),
            "resume": t("panel.resume"),
            "stop": t("panel.stop"),
        }
        for child in self.controls.winfo_children():
            child.destroy()
        for name, main in wanted[0]:
            button = ttk.Button(self.controls, text=labels[name], command=commands[name])
            if main:
                button.configure(style=primary_style(self.root), default="active")
                if focused:  # the button pressed is gone, keep the keyboard in the same place
                    button.focus_set()
            button.pack(side="left", padx=(0, 8))

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
            self.status.set(t("panel.save_error", error=err))

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
            self.status.set(t("panel.session_restored"))
        if self.pending:
            if self.enabled and not self.settings.insistent:
                self.root.after(2000, self._surprise_notice)

    def _start_text(self) -> str:
        return t("panel.start_all_day") if self.settings.all_day else t("panel.start_session")

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
        self.status.set("")

    def _pause(self) -> None:
        if not self.enabled:
            self.status.set(t("panel.nothing_to_pause"))
            return
        self.pause_until = _now() + timedelta(minutes=15)
        self._persist()
        self.status.set("")

    def _resume(self) -> None:
        """End a pause early. The session and its end time stay as they were."""
        self.pause_until = _EPOCH
        self._persist()
        self.status.set("")

    def _stop(self, by_user: bool = True) -> None:
        """End the session. A pending quiz stays pending: only Emergencia drops it (decision 0007)."""
        self.enabled = False
        self.until = None
        self.user_stopped = by_user
        self.clock.reset_after_quiz()
        self._close_quiz()
        self._persist()
        self.status.set("")

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
        self.status.set(t("panel.emergency_done"))

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
            self.settings_status.set(t("panel.save_error", error=err))
            return
        self.settings_status.set(t("panel.insistent_on") if on else t("panel.insistent_off"))

    def _toggle_all_day(self) -> None:
        """Save the all-day choice. Turning it on also turns on autostart, or it cannot start at sign-in."""
        on = self.all_day_var.get()
        try:
            self.settings = self.settings_store.save(replace(self.settings_store.load(), all_day=on))
        except (ValueError, OSError) as err:
            self.all_day_var.set(self.settings.all_day)
            self.settings_status.set(t("panel.save_error", error=err))
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
        self.settings_status.set(t("panel.all_day_on") if on else t("panel.all_day_off"))

    def _toggle_autostart(self) -> None:
        try:
            if self.autostart_var.get():
                autostart.enable(_REPO_ROOT)
                self.settings_status.set(t("panel.autostart_on"))
            else:
                autostart.disable()
                self.settings_status.set(t("panel.autostart_off"))
        except OSError as err:
            self.autostart_var.set(autostart.is_enabled())
            self.settings_status.set(t("panel.autostart_error", error=err))

    def _schedule_changed(self, *_args: object) -> None:
        """Save the study hours a moment after the last keystroke, like every other setting."""
        if self.schedule_job is not None:
            self.root.after_cancel(self.schedule_job)
        self.schedule_job = self.root.after(SAVE_DELAY_MS, self._save_schedule)

    def _save_schedule(self) -> None:
        self.schedule_job = None
        try:
            windows = parse_schedule(self.schedule.get())
        except ValueError as err:
            self.settings_status.set(t("settings.save_error", error=err))
            return
        if windows == self.windows:
            return  # Emergencia or a restore already applied it
        self.windows = windows
        self._persist()
        self.settings_status.set(t("settings.saved", time=_now()))

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
                if not self.settings.insistent:
                    self._surprise_notice()  # works with the panel hidden: it is a topmost Toplevel
            self.wait_reason = None
            if self.pending and self.settings.insistent and not self.in_quiz:
                wait = self._insistent_wait(now, now_mono)
                if wait is None:
                    self._open_quiz(insistent=True)
                else:
                    self.wait_reason = wait or None
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
        """Why an insistent quiz cannot open yet ('' if the headline says it already), or None if it can."""
        if not self.enabled or now < self.pause_until:
            return ""
        if now_mono < self.retry_at:
            return self.retry_reason
        if self.windows and not within_study_window(now, self.windows):
            return t("panel.wait_off_schedule")
        if self.presence.suspended:
            return ""
        if self.presence.locked:
            return t("panel.wait_locked")
        busy = busy_reason()
        if busy is not None:
            return t("panel.wait_fullscreen") if busy == "fullscreen" else t("panel.wait_presentation")
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
        notice.title(t("panel.surprise_title"))
        notice.resizable(False, False)
        notice.attributes("-topmost", True)
        w, h = 350, 132
        x = max(0, notice.winfo_screenwidth() - w - 36)
        y = max(0, notice.winfo_screenheight() - h - 95)
        notice.geometry(f"{w}x{h}+{x}+{y}")
        _no_activate(notice)  # appear without taking keyboard focus from the user's work
        body = ttk.Frame(notice, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=t("panel.surprise_body"), wraplength=315).pack(anchor="w")
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

        ttk.Button(actions, text=t("panel.respond"), command=start).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text=t("panel.later"), command=dismiss).pack(side="left")
        notice.protocol("WM_DELETE_WINDOW", dismiss)
        notice.after(30000, dismiss)

    def _open_quiz(self, insistent: bool | None = None) -> None:
        """Load five questions off the UI thread. A pending quiz in insistent mode cannot be postponed."""
        if self.in_quiz:
            if self.quiz is not None and self.quiz.alive:
                if self.quiz.insistent:
                    self.quiz.present()
                else:
                    self.quiz.window.lift()
                    self.quiz.window.focus_force()
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
        self.status.set(t("panel.loading_bank") if mode != "ollama" else t("panel.loading_ollama"))
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
                    language=settings.language,
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
            self.retry_reason = t("panel.wait_retry")
            self.status.set(t("panel.prepare_failed", error=error))
            log.warning("Insistent quiz could not load questions: %s", error)
            return
        self.status.set(t("panel.quiz_not_generated"))
        messagebox.showwarning(t("panel.prepare_failed_title"), error)

    def _present_quiz(self, topic: str, questions: list, source: str, *, insistent: bool = False) -> None:
        def done(answers: list[int]) -> None:
            self._finish_quiz(topic, questions, answers, source)

        def postponed() -> None:
            self.quiz, self.in_quiz = None, False

        self.quiz = QuizWindow(
            self.root,
            questions=questions,
            source=source,
            insistent=insistent,
            on_done=done,
            on_leave=postponed,
        )
        self.status.set("")

    def _finish_quiz(self, topic: str, questions: list, answers: list[int], source: str) -> None:
        score, passed = self.store.record(topic=topic, questions=questions, answers=answers, source=source)
        self.clock.reset_after_quiz()
        self.quiz, self.pending, self.in_quiz = None, False, False
        self._persist()
        self._refresh_stats()  # the Último resultado line shows it, the result window explains it
        self.status.set("")
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
            if not messagebox.askyesno(t("panel.exit"), t("panel.exit_confirm")):
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


def _pack_when_text(label: ttk.Label, text: tk.StringVar, **pack: object) -> None:
    """Show label only while text has words, so an empty line leaves no gap."""

    def update(*_args: object) -> None:
        if text.get() and not label.winfo_manager():
            label.pack(**pack)
        elif not text.get() and label.winfo_manager():
            label.pack_forget()

    text.trace_add("write", update)
    update()


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
    parser = argparse.ArgumentParser(description=t("panel.cli_description"))
    parser.add_argument("--demo", action="store_true", help=t("panel.arg_demo"))
    parser.add_argument("--hidden", action="store_true", help=t("panel.arg_hidden"))
    args = parser.parse_args()
    setup_logging(_app_data())
    lock = SingleInstance("OpenTutorGuardian")
    if not lock.acquire():
        print(t("panel.already_running"))
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
