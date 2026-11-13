# FocoLocal audit and adapter design (read-only, 2026-11-13)

Repo: `C:\my_drive\Portafolio\foco_Local_desktop`, branch `main`, clean tree, MIT, Go 1.23,
23 Go files. Nothing in that repo was changed.

## Verified facts
- No IPC: no named pipe, no listener, no HTTP server (`grep` found none). Config is
  `FocoLocalDesktop\config.json`, read and saved by `limit.Store` inside the app process.
- `limit.Store` holds `Config{Rules, Usage, Paused, BlockMode, SafeAutomation, ExcludedPIDs...}`.
  `Rule{Domain, Minutes, Enabled, Period, From, To, ...}`. `Period` includes `blocked`.
- Enforcement is observation-based: browser address read through UI Automation (read-only),
  `Observe(host...)` decides, then stops playback or shows an overlay. It does not kill
  processes, edit DNS, or use extensions (stated in source comments).
- Entry args: only `--minimized`. Tray and single window exist already.

## What this means for Guardian
- Guardian must NOT edit `config.json`: the running app owns it and would overwrite changes.
- A lease can only be a temporary `Rule` (`Period: "blocked"`) owned by Guardian, held in
  memory with an expiry and never mixed into the user's saved rules.
- Scope is domain or path rules that `Matches(site, domain)` supports. Whole-browser or
  app blocking is not a capability and must not be announced.

## Proposed PR to FocoLocal (separate, not part of Guardian v0.2.0)
1. `internal/limit`: add `Lease{ID, Owner, Domain, Reason, ExpiresAt}` kept in memory only,
   expired on every `Observe`, excluded from `Save()`. Tests: expiry, idempotency,
   no leak into config.json, user rules take priority over leases for essential domains.
2. `internal/ipc` (Windows): named pipe `\\.\pipe\focolocal-<user SID>` with a DACL for the
   current user only. JSON line protocol, `protocol_version: 1`.
3. Commands: `capabilities`, `apply_lease`, `release_lease`, `list_active_leases`, `health`,
   `emergency_release`. `capabilities` reports real scopes (`domain`, `path` if supported).
4. Max lease 60 minutes, owner required, `idempotency_key` required.
5. Guardian side: `focolocal_client.py` behind the existing `integrations` health state,
   `unavailable` until `capabilities` answers with a compatible version.

## Gates before any enforcement
- Contract tests in both repos, crash test (Guardian killed: leases expire by TTL),
  Windows run with a real browser, visible emergency release in tray and panel.
- A lease may only be requested from a certified source (`CERTIFIED_QUESTION_SOURCES`
  or a validated task). Practice or unreviewed material never creates or lifts a lease.
