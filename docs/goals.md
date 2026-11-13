# Goals

<!-- Written by the owner. AI tools may format or translate this file, never invent its content. Source: the v0.2.0 phase document and the owner's answers on 2026-11-13. Confirm or correct. -->

## Vision

A local-first Windows desktop agent that makes spaced study happen: it asks short quizzes at random moments of real study time, and never controls the computer covertly.

## Users

The owner, a single user on a personal Windows 10 or 11 account, studying Google Cloud Data Engineer material and similar topics. The project is also a portfolio piece.

## Objectives

- A resident agent in the Windows user session with a tray icon, a hideable panel and one instance.
- Opt-in study sessions and schedules that survive a restart, with a surprise quiz of five questions after 10 to 25 minutes of eligible activity.
- Instant local questions first (Fieldnotes bank), local Ollama only when chosen, so the panel never waits for a model.
- Later: deterministic validation of practical work (PPTX, PDF, Markdown) and, with FocoLocal, temporary leisure restrictions.

## Non-goals

- No covert control, no resistance to uninstalling, no blocking of whole browsers, work tools, system settings or emergencies.
- No telemetry, no paid services, no keylogging, no screen, audio or camera monitoring.
- No UI in a Windows service (Session 0). No promise of protection against an administrator.
- No leisure credit from unverified questions or unreviewed work. Those are practice only.

## Success criteria

- The acceptance list of delivery A in `docs/specs/` passes on a real Windows machine, including 125 and 150 percent scaling and two monitors.
- The unit tests pass in CI on `windows-latest` and locally.
- With Ollama stopped, the panel still opens and a quiz loads from the local bank.
- The emergency exit and Exit are always visible and work.

## Priorities

- Trust and reversibility over features.
- Local and offline over convenient.
- Verified evidence over claims: nothing is called done without a run.

## Constraints

- Windows 10 or 11 x64, Python 3.11, tkinter, standard library only.
- Free and local tools only. Reading the question bank is read-only (349 original questions, never modified).
- Personal code: free local models may be used for small tasks.
