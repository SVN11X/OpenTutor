# 0003. Keep the study session in SQLite

- Status: accepted
- Date: 2026-11-13
- Proposed by: Claude Code
- Accepted by: owner

## Context

The v0.2.0 spec asks for sessions and the pending quiz in SQLite. They were first written to a JSON file because it was
the simplest atomic option for one small record. The owner chose SQLite.

## Decision

Store the session, schedule and pending quiz in one row (`guardian_session`) of the same SQLite file as the results.
Import an old `session.json` once, never over a saved row, and rename it to `.migrated` (or `.corrupt`).

## Alternatives considered

Keep the JSON file: simpler, but it splits the state in two places and does not follow the spec.

## Consequences

One file holds all state, and a corrupt database is logged and ignored. A session history would now be a small change.
To undo it, read the row and write the JSON again. The `.migrated` file keeps the last imported copy.
