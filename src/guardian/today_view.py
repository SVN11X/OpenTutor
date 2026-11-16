"""Texts of the Hoy tab, computed from the agent state. Pure functions, so the wording is tested.

Every state carries an icon and words, never color alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


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
        return "✎ Examen abierto: responde las 5 preguntas"
    if not state.enabled:
        suffix = " · tienes un examen pendiente" if state.pending else ""
        return "○ Sin sesión de estudio" + suffix
    if state.paused_until is not None and now < state.paused_until:
        return f"⏸ En pausa hasta las {state.paused_until:%H:%M}"
    if state.pending:
        return "● Examen pendiente: se abrirá en cuanto se pueda"
    if state.all_day:
        return "● Estudiando todo el día"
    return f"● Estudiando hasta las {state.until:%H:%M}" if state.until else "● Estudiando"


def counter_line(
    enabled: bool, paused_reason: str | None, eligible: float, target: float, pending: bool = False
) -> str:
    """How far the next question is, or why the clock is stopped."""
    if not enabled:
        return "Contador detenido: inicia una sesión para recibir preguntas"
    if pending:
        return "Contador en espera: vuelve a correr cuando respondas el examen pendiente"
    if paused_reason:
        return f"Contador en pausa: {paused_reason}"
    left = max(0, int(target - eligible))
    return f"Próxima pregunta en unos {max(1, left // 60)} min de actividad (al azar)"


def active_today(seconds: float) -> str:
    total = int(seconds)
    return f"Tiempo activo hoy: {total // 3600} h {total % 3600 // 60} min"


def setup_steps(*, bank_found: bool, all_day: bool, autostart: bool) -> list[tuple[bool, str]]:
    """First steps for an all-day setup: (done, text). The panel shows them until the owner hides them."""
    return [
        (
            bank_found,
            "Banco de preguntas encontrado" if bank_found else "Elige la carpeta del banco en Ajustes",
        ),
        (all_day, "Todo el día activado" if all_day else "Activa 'Todo el día' en Ajustes"),
        (autostart, "Guardian inicia con Windows" if autostart else "Activa 'Iniciar Guardian con Windows'"),
    ]
