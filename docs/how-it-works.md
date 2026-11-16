# How it works

<!-- An AI tool may draft this file from the real code, never from a guess. It stays a draft until the owner confirms it. Update it in the same change that alters the main flow. Paths in backticks must exist: the check reads them. -->

Status: draft.

## From start to finish

1. The user starts Guardian. It creates a tray icon and the panel, or only the icon with `--hidden`.
2. The user starts a study session, optionally with a schedule, or turns on all-day mode, which starts the session at sign-in and renews it at midnight. Nothing runs before one of these.
3. Every second the clock adds eligible seconds, only while the user is active, inside the schedule and not paused. Suspension and a locked session stop it, through Windows messages on the hidden tray window. The panel shows today's active time.
4. After the eligible minutes set in Ajustes (10 to 25 by default) the quiz is due. In insistent mode it opens by itself in a window that stays on top and comes back until all five answers are given. With insistent mode off, a small notice with "Más tarde" appears instead. One quiz stays pending at a time.
5. The user answers five questions chosen by spaced repetition from the local bank, so wrong answers return sooner and the bank does not run out. Four correct from a reviewed source is a certified pass.
6. The result is stored in SQLite and shown in the Repasos and Progreso tabs. Unverified sources are marked as practice.
7. Emergency ends the session and removes the saved session. Exit closes the agent.

## Parts

- `src/guardian/desktop.py`: the tkinter panel, the tick loop, the quiz windows and the tray command queue.
- `src/guardian/tray.py`: the tray icon through Win32 in its own thread.
- `src/guardian/core.py`: questions, grading, the surprise clock and the results store.
- `src/guardian/session_state.py`: the persisted session, schedule and pending quiz.
- `src/guardian/single_instance.py`: one instance per user session.
- `src/guardian/presence.py`: idle time, lock, suspension and full-screen state, read as Windows flags only.
- `src/guardian/activity_log.py`: eligible seconds per day.
- `src/guardian/quiz_window.py`: the quiz window and its insistent behavior.
- `src/guardian/settings_store.py` and `src/guardian/settings_ui.py`: the saved settings and the "Qué te pregunto" section of Ajustes.
- `src/guardian/autostart.py`: opt-in, reversible autostart in the current user registry.
- `src/guardian/fieldnotes.py` and `src/guardian/questions.py`: the question sources.
- `src/guardian/integrations.py`: honest health of Ollama and FocoLocal.
- `src/guardian/evidence/pptx_check.py`: the deterministic PPTX rubric, safe ZIP reading and no macros.
- `src/guardian/evidence/md_check.py`: the Markdown rubric (sections, empty sections, placeholders, duplicates).
- `src/guardian/evidence/pdf_check.py`: the PDF rubric (structure, active content, page count, bomb limits).
- `src/guardian/evidence/check.py`: one entry point for the three file kinds.
- `src/guardian/evidence/defense.py`: three questions about the owner's own file, with decoys that never appear in it.
- `src/guardian/task_store.py`: hand-written tasks and the evidence handed in, in SQLite.
- `src/guardian/evidence_ui.py`: the Tareas and Evidencia tabs.

## Where to start reading

`src/guardian/desktop.py`, because it connects every other part.

## Run it and check it

Run: `.\scripts\run-dev.ps1`. Check: `.\scripts\run-dev.ps1 -TestsOnly`.

## Not covered

No blocking of apps or sites, no FocoLocal link, no installer, no leisure credit, and no real-device check of high DPI, two monitors or suspension yet.
