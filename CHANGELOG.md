# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/2.0.0/) and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
