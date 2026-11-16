# 0009. No insistent quiz without a tray icon

- Status: accepted
- Date: 2026-11-16
- Proposed by: Claude Code
- Accepted by: owner, through the authorization given in chat on 2026-11-16

## Context

Decision 0007 made the insistent quiz window without an exit button. Its only exits, Emergencia and Salir, live in the tray menu. If the tray icon cannot start, an insistent quiz could never be left. docs/goals.md forbids covert control and requires reversibility.

## Decision

Insistent mode applies only when the tray icon started. Without a tray, every quiz behaves as a normal quiz: a Posponer button and the small notice with "Más tarde". The saved setting `insistent` never changes, so the behavior returns by itself when the tray works again. The panel status line says so.

## Alternatives considered

- An exit button in the quiz only without a tray. It needs a second window layout and a path that is rarely exercised.
- Refusing to start without a tray. It leaves the owner with no Guardian at all for a cosmetic failure.

## Consequences

An insistent quiz can always be left. Without a tray, the owner gets weaker nagging, which is the safe side. To undo, remove the `_insistent()` check in `GuardianUI`.
