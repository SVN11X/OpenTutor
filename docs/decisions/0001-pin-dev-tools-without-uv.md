# 0001. Pin development tools in requirements-dev.txt, not a uv lockfile

- Status: proposed
- Date: 2026-11-13
- Proposed by: Claude Code
- Accepted by: owner

## Context

The software profile asks for pinned dependencies and a committed lockfile. Guardian has no runtime
dependencies, only Ruff for development. `uv` is not installed on the owner's machine, and a new tool
must pass the radar first.

## Decision

Pin Ruff in `requirements-dev.txt` (`ruff==0.17.2`) and use `pyproject.toml` for metadata and lint config.

## Alternatives considered

Install `uv` and commit `uv.lock`. It is cleaner, but it adds a tool for one pinned development package.

## Consequences

Easy: one pinned line, works in CI with pip. Harder: no hash lock. Undo: add `uv` after a radar entry and replace the file.
