# Improvement plan

Goal confirmed by the owner (2026-11-13): adopt the SVN11X standard first, then quality, then new features. Personal code only.
Order: structure, standard files, security, build and tests, docs, then product.

## Structure (yellow, needs approval)

- [x] YELLOW: git mv guardian_mvp/ to src/guardian/ and tests to tests/, fix imports, fieldnotes parents[3], autostart path and rewrite of the old Run value, move run_dev.ps1 to scripts/, update CI and README. Keep guardian_mvp.sqlite3.
- [x] YELLOW: move guardian_mvp/docs/*.md into docs/ and the ADR into docs/decisions/ without translating, delete AGENT_HANDOFF.md if obsolete, and fold guardian_mvp/README.md into README.md. Separate PR.

## Standard files (green)

- [x] Run standard.py init --existing --profile software --option kind=desktop and agents, so .standard.yml, AGENTS.md, CLAUDE.md, docs/glossary.md and docs/decisions/ exist, and make the standard check pass.
- [x] Write docs/goals.md from the confirmed answers and the v0.2.0 spec: vision, users, objectives, non-goals, success criteria, constraints.
- [x] Add CHANGELOG.md with a v0.2.0 entry and pyproject.toml created with uv init (version 0.2.0, Ruff as dev dependency, guardian entry point), and commit the lockfile.

## Security and privacy (green)

- [x] Regenerate .secrets.baseline (it lists deleted files), run gitleaks and detect-secrets on the tree and on the history, and record the result.
- [x] Replace silent except blocks that hide real errors in tray, desktop and session code with a logger writing to the app data folder, and assert the log line in the corrupt session.json test.

## Build and tests (green)

- [x] Add Ruff config, format and lint the code, and enforce both in the CI workflow next to the unit tests.
- [x] Add the standard check to CI and keep workflow permissions at contents read only.
- [x] Add tests for study-window edge cases (midnight crossing, DST change with aware datetimes) and for the tick state machine with a fake clock, so suspension never adds eligible time.

## Product (after the standard)

- [x] DECIDED (manual list, see docs/decisions/0004): where should practical tasks come from now that the OpenTutor planner was removed (manual list, a local JSON file, or FocoLocal)? Needed before the evidence tab.
- [x] DECIDED (SQLite, see docs/decisions/0003): results already live in SQLite. Keep session.json or move only the session to SQLite as the v0.2.0 spec asks? Record the decision in docs/decisions/.
- [x] SKIPPED: owner chose to keep the fork for now. Create the own repository OpenTutor-Guardian with the full history and detach from the fork. Needs the owner's explicit order.
- [x] Wire the PPTX validator to a panel tab named Evidencia with the three-question defense. Depends on the task source decision above.
