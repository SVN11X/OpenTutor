"""Texts of the Hoy tab, computed from the agent state. Pure functions, so the wording is tested.

Every state carries an icon and words, never color alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .i18n import t


@dataclass(frozen=True)
class AgentState:
    enabled: bool
    all_day: bool
    until: datetime | None
    paused_until: datetime | None
    pending: bool
    in_quiz: bool


def headline(state: AgentState, now: datetime) -> str:
    """One line that says what Guardian is doing right now."""
    if state.in_quiz:
        return t("today.headline_in_quiz")
    if not state.enabled:
        suffix = t("today.headline_pending_suffix") if state.pending else ""
        return t("today.headline_no_session") + suffix
    if state.paused_until is not None and now < state.paused_until:
        return t("today.headline_paused", time=state.paused_until)
    if state.pending:
        return t("today.headline_pending")
    if state.all_day:
        return t("today.headline_all_day")
    return t("today.headline_until", time=state.until) if state.until else t("today.headline_studying")


def counter_line(enabled: bool, paused_reason: str | None, eligible: float, target: float) -> str:
    """How far the next question is, or why the clock is stopped."""
    if not enabled:
        return t("today.counter_stopped")
    if paused_reason:
        return t("today.counter_paused", reason=paused_reason)
    left = max(0, int(target - eligible))
    return t("today.counter_next", minutes=max(1, left // 60))


def active_today(seconds: float) -> str:
    total = int(seconds)
    return t("today.active_time", hours=total // 3600, minutes=total % 3600 // 60)


def setup_steps(*, bank_found: bool, all_day: bool, autostart: bool) -> list[tuple[bool, str]]:
    """First steps for an all-day setup: (done, text). The panel shows them until the owner hides them."""
    return [
        (bank_found, t("today.step_bank_done") if bank_found else t("today.step_bank_todo")),
        (all_day, t("today.step_all_day_done") if all_day else t("today.step_all_day_todo")),
        (autostart, t("today.step_autostart_done") if autostart else t("today.step_autostart_todo")),
    ]
