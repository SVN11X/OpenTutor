# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/2.0.0/) and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `docs/gallery/`: screenshots of 16 states of the panel and the quiz windows, shown by GitHub. `scripts/gallery.py` regenerates them with throwaway data and a sample bank, capturing only Guardian's own windows. A `gallery` workflow builds it for every pull request.

## [0.4.0] - 2026-11-16

### Added

- Guardian's own icon, a blue shield with a white check, in the tray, every window, the program file and the installer. `scripts/make_icon.py` draws it with the standard library.
- Bank questions appear in Spanish when the bank ships a current translation, with a new "Idioma de las preguntas" setting in Ajustes to keep the original English.

### Changed

- All user-facing text lives in `src/guardian/locales/es.json`, read through `guardian.i18n.t`, and the 10 backup questions in `src/guardian/content/fallback_gcp.json`. A test fails when a text is missing or unused. Nothing changes for the user.
- The tray menu says "Iniciar estudio", which fits both the 60-minute and the all-day session.
- Spaced repetition history is keyed by the bank question id, so history from before this change starts again.

### Fixed

- With a quiz pending, the counter says it waits for that quiz instead of counting down to a next question.

## [0.3.0] - 2026-11-16

### Added

- Insistent quiz window, on by default: a due quiz opens by itself, centered and on top, with no exit button. It comes back 5 seconds after a close or minimize, waits while a full-screen app or presentation mode is on, and ignores input for 2 seconds each time it appears. A failed load retries in 5 minutes. A checkbox in Ajustes turns it off.
- All-day mode in Ajustes: the session starts at sign-in, lasts until midnight and renews itself the next day. Turning it on also turns on autostart.
- Ajustes, section "Qué te pregunto": question set, source, exam domains, minutes between quizzes, the bank folder with a picker and the Ollama model. Settings are saved in SQLite, so the installed app finds the bank.
- The clock stops while the computer is suspended or the session is locked, and the panel shows today's active time and why the clock is paused.
- Markdown and PDF validators (rubrics md-1 and pdf-1) and a kind for each task. The PDF check finds active content also inside compressed streams, with limits against decompression bombs. PDF text cannot be read reliably, so missing terms give needs review and never a rejection.
- Tareas tab: practical tasks the owner writes by hand (title, slide, section or page count, required terms).
- Evidencia tab: hand in a .pptx, run the deterministic rubric, and answer a three-question defense about the file. Result: validated, needs review or rejected. It gives no leisure credit, because that system does not exist.

### Changed

- The Hoy tab shows one clear state line, the counter, today's active time and a first-steps card that can be hidden. The panel fits and centers on small screens, and the live view no longer reads SQLite every second.
- Terminar keeps a pending quiz. Only Emergencia drops it.
- The default source is the whole bank as practice. The free text topic field is gone.
- Quiz questions are chosen by spaced repetition: wrong answers return sooner, right answers later, and the bank no longer runs out when the pool is small.
- The study session, schedule and pending quiz moved from session.json to the SQLite file. An old session.json is imported once and renamed to session.json.migrated.

## [0.2.0] - 2026-11-13

### Added

- Resident Windows agent: tray icon with open, start, pause, end, emergency and exit, one instance per user session, and a panel that hides to the tray.
- Opt-in study sessions, schedule and pending quiz that survive a restart.
- Optional, reversible autostart for the current user, off by default.
- Tabbed panel: Hoy, Tareas, Repasos, Progreso and Ajustes, with honest service health.
- Deterministic PPTX validator with safe ZIP reading (not wired to the panel yet).
- Project layout `src/guardian` and `tests`, `pyproject.toml`, Ruff, and the SVN11X standard.

### Changed

- The package is now named `guardian`. The results database file name is unchanged.
- The web app and API of the upstream fork were removed. Guardian is desktop only.

### Fixed

- Quiz windows are no longer invisible when the panel is hidden.
- A unit test no longer depends on a local Fieldnotes checkout.
