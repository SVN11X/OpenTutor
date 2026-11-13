# ADR-0001: Resident agent mechanism (v0.2.0, delivery A)

Status: accepted for v0.2.0. Date: 2026-11-13.

## Context
Guardian v0.1.x is a tkinter window the user must keep open. v0.2.0 needs a
user-session resident process: tray icon, hideable panel, single instance and
explicit, persistent study sessions. It must start without Ollama and must not
add paid services, telemetry or hidden control.

## Decision
- Keep tkinter (already in `desktop.py`, no new dependency, MIT-compatible stdlib).
- Tray icon with `ctypes` over `Shell_NotifyIconW` in its own thread (`tray.py`).
  Rejected: `pystray` (LGPLv3, not installed, needs Pillow glue); a Windows
  service (Session 0 cannot draw UI in the user session).
- Single instance with a named mutex `Local\OpenTutorGuardian` (`single_instance.py`).
- Sessions persist in `%LOCALAPPDATA%\OpenTutorGuardian\session.json`
  (`session_state.py`). Only: active, until, paused_until, topic, source.
  Expired or corrupt state is discarded. Nothing starts without a prior explicit start.
- No autostart in v0.2.0. `--hidden` exists for a future user-chosen shortcut.
- Close button hides the panel only when the tray icon was created, otherwise it
  exits, so there is never an invisible agent. Emergency and Exit are in both the
  tray menu and the panel.
- Leisure blocking and FocoLocal leases are NOT implemented (see CONTRACTS.md).

## Consequences
- Tray menu clicks arrive on the tray thread and cross to Tk through a queue.
- Windows children of a hidden panel are not `transient`, or they would be invisible.
- Unverified question sources keep giving practice only, never unlock credit.

## Deviations from the v0.2.0 spec (2026-11-13)
- Session, schedule and pending quiz live in `session.json`, not SQLite. The spec asks for
  SQLite with migrations. JSON is atomic and versioned (`schema_version`) and enough for one
  small record, but the spec item stays open until the state machine needs history.
- Autostart is an HKCU Run value (`autostart.py`), off by default, toggled by a checkbox.
- FocoLocal health is always `unavailable`: no IPC exists yet.
- The surprise popup uses WS_EX_NOACTIVATE so it does not take keyboard focus.
  Not yet verified while typing in another app.
