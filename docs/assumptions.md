# Assumptions

Things taken as true without confirmation. Review the open ones in every pull request. Status is open, confirmed or discarded.

| Date | Assumption | Made by | Task | Status |
|------|------------|---------|------|--------|

- Open, 2026-11-13: autostart values written before the rename are rewritten at startup only if one exists. Nobody had one enabled on the owner's machine at the time of the move.
- Open, 2026-11-13: the plugin hook checks `AGENTS.md` with standard 1.10.0 while the local standards repo is 1.12.0. `AGENTS.md` was generated with 1.10.0 so commits pass.
