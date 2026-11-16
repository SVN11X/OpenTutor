# OpenTutor Guardian

A local-first Windows desktop agent for spaced study. It lives in the system tray and, during a study
session you chose, asks a 5-question quiz every 10 to 25 minutes of real activity. The defaults ask
Google Cloud Professional Data Engineer questions all day, in a window that has to be answered.

The panel text is in Spanish, on purpose. This README is in English.

Derived from [OpenTutor](https://github.com/zijinz456/OpenTutor) (MIT). This repository keeps only the
desktop agent. The web app and API were removed on purpose: everything here runs on your machine.

## How to use it

1. Install it (see Install below) or run it from source. A tray icon appears next to the clock.
2. In Ajustes, check that the question bank is found, or pick its folder. Then turn on "Todo el día".
   From then on the session starts by itself when you sign in to Windows and renews at midnight.
   Without "Todo el día", press "Iniciar estudio (60 min)". Nothing starts before one of the two.
3. Study as usual. After 10 to 25 minutes of real activity the quiz opens on top of your work and
   comes back until you answer all 5 questions. It waits while a full-screen app or a presentation is on.
4. Pause, End, Emergency and Exit are always in the tray menu. Emergency also drops the pending quiz.

## What works today

- Tray icon with Open panel, Start session, Pause, End, Emergency, Exit. One instance per user.
- Closing the window hides it to the tray. If the tray icon cannot be created, closing exits.
- All-day mode, schedule and pending quiz survive a restart. The clock counts only real activity and
  stops while the computer is suspended or the screen is locked.
- Ajustes, "Qué te pregunto": question set, source, exam domains, minutes between quizzes, bank folder.
- Spaced repetition: wrong answers come back after 10 minutes, right ones after 1 hour up to 7 days.
- Insistent quiz window, on by default, with a checkbox to turn it off.
- Optional autostart, reversible, current user only.
- Ollama (a program that runs language models on your own computer) is optional and used only when you
  pick it.
- Questions from an unreviewed source are always practice and never count as a certified pass.
- Panel tabs: Hoy, Tareas, Evidencia, Repasos, Progreso, Ajustes. Status uses icon and text, not only color.
- Practical tasks you write by hand (Tareas tab). Hand in a PowerPoint, Markdown or PDF file and a deterministic
  rubric checks it (Evidencia tab), followed by three short questions about your own file, called the defense. Safe reading: no macros, no
  active content, no rendering.

## What does not exist yet

No app or website blocking. The installer is not signed yet, so Windows warns about an unknown publisher. No link with FocoLocal, the author's
separate site limiter, so a validated task gives no leisure credit, meaning no permission for free time. PDF text cannot be read reliably, so a PDF with required terms goes to review.
See `docs/` for the usage guide, design notes and audits.

## Run (Windows PowerShell, from the repository root)

```
.\scripts\run-dev.ps1
.\scripts\run-dev.ps1 -Hidden
.\scripts\run-dev.ps1 -TestsOnly
```

`run-dev.ps1` runs the tests, then starts the panel. `-Hidden` starts it in the tray only and
`-TestsOnly` runs the tests.

Requires Python 3.11 or newer with tkinter. The app has no third-party packages. No network except the
optional local Ollama at `127.0.0.1:11434`. No telemetry.

## Build an installer

From the repository root, in Windows PowerShell with Python 3.11 and Inno Setup 6 installed:

```
.\scripts\build-installer.ps1
```

The installer lands in `dist\installer\`. It installs for the current user only and has a normal uninstaller.

## Install

Run `OpenTutorGuardian-Setup-0.3.0.exe`. It needs no administrator rights and installs to
`%LOCALAPPDATA%\Programs\OpenTutorGuardian`. If Windows SmartScreen stops it, choose "More info" and then
"Run anyway". Your results and settings stay in `%LOCALAPPDATA%\OpenTutorGuardian`, also after an
uninstall. Uninstall from Windows Settings, Apps, like any other program.
It is not signed yet, so Windows shows "Unknown publisher". See `docs/decisions/0006-windows-installer-and-code-signing.md`.

## Standard

This repository follows SVN11X/standards@v1. Install the development tools, then run the check from the
repository root:

```
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m unittest discover -s tests
```

Goals and non-goals are in `docs/goals.md`.

## Privacy and safety

Full policy: `docs/privacy.md`.

Data stays in `%LOCALAPPDATA%\OpenTutorGuardian` (one SQLite file with results, session, tasks and evidence). Guardian does
not watch keys, screen, audio or window titles. The emergency button and Exit are always visible.

## License

MIT. See `LICENSE`.
