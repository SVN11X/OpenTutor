# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/2.0.0/) and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Markdown and PDF validators (rubrics md-1 and pdf-1) and a kind for each task. The PDF check finds active content also inside compressed streams, with limits against decompression bombs. PDF text cannot be read reliably, so missing terms give needs review and never a rejection.
- Tareas tab: practical tasks the owner writes by hand (title, slide, section or page count, required terms).
- Evidencia tab: hand in a .pptx, run the deterministic rubric, and answer a three-question defense about the file. Result: validated, needs review or rejected. It gives no leisure credit, because that system does not exist.

### Changed

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
