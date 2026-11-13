# OpenTutor Guardian

A local-first Windows desktop agent for spaced study. It lives in the system tray, and during a study
session you started yourself it interrupts you every 10 to 25 minutes of real activity with a
5-question quiz.

Derived from [OpenTutor](https://github.com/zijinz456/OpenTutor) (MIT). This repository keeps only the
desktop agent. The web app and API were removed on purpose: everything here runs on your machine.

## What works today

- Tray icon with Open panel, Start session, Pause, End, Emergency, Exit. One instance per user.
- Closing the window hides it to the tray. If the tray icon cannot be created, closing exits.
- Opt-in sessions, study schedule and pending quiz survive a restart. Nothing starts by itself.
- Optional autostart, off by default, reversible, current user only.
- 5-question quiz from a local question bank first, Ollama (local, optional) only when you pick it.
- Unverified questions are always practice and never count as certified.
- Panel tabs: Hoy, Tareas, Repasos, Progreso, Ajustes. Status uses icon and text, not only color.
- Practical tasks you write by hand (Tareas tab). Hand in a PowerPoint, Markdown or PDF file and a deterministic
  rubric checks it (Evidencia tab), followed by a short defense about your own file. Safe reading: no macros, no
  active content, no rendering.

## What does not exist yet

No app or website blocking, no FocoLocal integration and no installer. A validated task gives no leisure credit,
because that system does not exist yet. PDF text cannot be read reliably, so a PDF with required terms goes to review.
See `docs/` for the usage guide, design notes and audits.

## Run (Windows PowerShell, from the repository root)

```
.\scripts\run-dev.ps1
.\scripts\run-dev.ps1 -Hidden
.\scripts\run-dev.ps1 -TestsOnly
```

Requires Python 3.11 or newer with tkinter. No third-party packages. No network except the
optional local Ollama at `127.0.0.1:11434`. No telemetry.

## Privacy and safety

Data stays in `%LOCALAPPDATA%\OpenTutorGuardian` (one SQLite file with results, session, tasks and evidence). Guardian does
not watch keys, screen, audio or window titles. The emergency button and Exit are always visible.

## License

MIT. See `LICENSE`.
