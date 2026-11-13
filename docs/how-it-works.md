# How it works

<!-- An AI tool may draft this file from the real code, never from a guess. It stays a draft until the owner confirms it. Update it in the same change that alters the main flow. Paths in backticks must exist: the check reads them. -->

Status: draft.

## From start to finish

1. The user starts Guardian. It creates a tray icon and the panel, or only the icon with `--hidden`.
2. The user starts a study session, optionally with a schedule. Nothing runs before this.
3. Every second the clock adds eligible seconds, only while the user is active, inside the schedule and not paused. Suspension never adds time.
4. After 10 to 25 eligible minutes a small topmost notice appears without taking keyboard focus. One quiz stays pending at a time.
5. The user answers five questions from the local bank. Four correct from a reviewed source is a certified pass.
6. The result is stored in SQLite and shown in the Repasos and Progreso tabs. Unverified sources are marked as practice.
7. Emergency ends the session and removes the saved session. Exit closes the agent.

## Parts

- `src/guardian/desktop.py`: the tkinter panel, the tick loop, the quiz windows and the tray command queue.
- `src/guardian/tray.py`: the tray icon through Win32 in its own thread.
- `src/guardian/core.py`: questions, grading, the surprise clock and the results store.
- `src/guardian/session_state.py`: the persisted session, schedule and pending quiz.
- `src/guardian/single_instance.py`: one instance per user session.
- `src/guardian/autostart.py`: opt-in, reversible autostart in the current user registry.
- `src/guardian/fieldnotes.py` and `src/guardian/questions.py`: the question sources.
- `src/guardian/integrations.py`: honest health of Ollama and FocoLocal.
- `src/guardian/evidence/pptx_check.py`: the deterministic PPTX rubric, safe ZIP reading and no macros.
- `src/guardian/evidence/defense.py`: three questions about the owner's own file, with decoys that never appear in it.
- `src/guardian/task_store.py`: hand-written tasks and the evidence handed in, in SQLite.
- `src/guardian/evidence_ui.py`: the Tareas and Evidencia tabs.

## Where to start reading

`src/guardian/desktop.py`, because it connects every other part.

## Run it and check it

Run: `.\scripts\run-dev.ps1`. Check: `.\scripts\run-dev.ps1 -TestsOnly`.

## Not covered

No blocking of apps or sites, no FocoLocal link, no installer, no practical tasks in the panel, and no real-device check of high DPI, two monitors or suspension yet.
