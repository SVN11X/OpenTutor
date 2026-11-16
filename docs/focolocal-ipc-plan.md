# Guardian and FocoLocal talking to each other: implementation plan

- Status: proposed
- Date: 2026-11-16
- Proposed by: Claude Code. Needs the owner's approval before any code.

## Goal

Let Guardian ask FocoLocal for a short, visible, reversible block of leisure sites that the owner already limits, over a local channel that only the current Windows user can open.

## What exists today (verified 2026-11-16)

FocoLocal, read only, `C:\my_drive\Portafolio\foco_Local_desktop`, branch `main`, commit `095529b`, clean tree.

- Held: still no IPC. A search of all Go files for pipes, `net.Listen`, `ListenAndServe` and HTTP servers finds none. `cmd/focolocal/main_windows.go` only starts the app. The one argument is `--minimized` (`internal/windows/app_windows.go`, lines 320 and 1014).
- Changed since the audit: the lease engine now exists. `internal/limit/lease.go` (merged in PR 4, `c16a130`) has `Lease`, `LeaseRequest`, `ApplyLease`, `ReleaseLease`, `ReleaseOwnerLeases` and `ActiveLeases`, with 12 tests in `internal/limit/lease_test.go`. `docs/guardian-leases.md` there says the same: engine done, channel missing.
- Held: `limit.Store` (`internal/limit/engine.go`) owns `Config` and `config.json`. `Config` has `Rules`, `Usage`, `Paused`, `BlockMode`, `SafeAutomation`, `ExcludedPIDs`. `Rule` has `Domain`, `Minutes`, `Enabled`, `Period` (day, week, month, blocked, schedule, interval) and more. `Matches(site, domain)` is exact or subdomain. `Observe(host, sampleID, now)` returns the blocked site, and checks pause, then leases, then rules. Leases sit in an unexported `leases` slice outside `Config`, so `Save()` never writes them.
- Rules the engine already enforces: memory only, owner, reason and idempotency key required, at most 60 minutes and 20 leases per owner, a lease only for a site covered by an enabled user rule (never wider), pause wins over leases, a lease does not charge the user's budget, repeating a key returns the same lease without extending it, reusing a key for another site is an error.
- Changed from the audit: FocoLocal has no list of "essential domains". The same safety comes from the rule "only sites the user already listed". Scopes are domain keys only. No path scope exists, so `capabilities` must not claim one. Whole-browser blocking is not a capability.
- Guardian (this repository): `src/guardian/integrations.py` reports FocoLocal as `unavailable` and probes nothing. `_emergency` in `src/guardian/desktop.py` has a comment that future leases must be released there. `CERTIFIED_QUESTION_SOURCES` in `src/guardian/core.py` decides what counts as certified. `docs/goals.md` lists "temporary leisure restrictions" with FocoLocal as a later objective and gives no leisure credit for unverified or unreviewed work. Decisions 0002 to 0009 say leases are not implemented. None says when one is asked for.

## Protocol

Channel: a named pipe `\\.\pipe\focolocal-<user SID>`, created by FocoLocal with a DACL that grants access to the current user only and rejects remote clients. No port, no HTTP. One request per line, one answer per line, UTF-8 JSON, 8 KB maximum per line. Guardian is the client, FocoLocal the server. Every message has `protocol_version` (integer, now 1). A different major version gets `incompatible`.

Errors have the shape `{"ok":false,"error":"invalid|target|limit|incompatible|unknown_cmd","message":"..."}`.

```
> {"protocol_version":1,"id":"1","cmd":"capabilities"}
< {"protocol_version":1,"id":"1","ok":true,"app_version":"0.3.0","scopes":["domain"],"max_lease_minutes":60,"max_leases_per_owner":20}

> {"protocol_version":1,"id":"2","cmd":"apply_lease","owner":"guardian","domain":"youtube.com","reason":"Quiz pending","idempotency_key":"q-2026-11-16-1","expires_at":"2026-11-16T11:15:00+01:00"}
< {"protocol_version":1,"id":"2","ok":true,"created":true,"lease_id":"9f3a1c5e22b07d41","expires_at":"2026-11-16T11:15:00+01:00"}

> {"protocol_version":1,"id":"3","cmd":"list_active_leases","owner":"guardian"}
< {"protocol_version":1,"id":"3","ok":true,"leases":[{"lease_id":"9f3a1c5e22b07d41","domain":"youtube.com","reason":"Quiz pending","expires_at":"2026-11-16T11:15:00+01:00"}]}

> {"protocol_version":1,"id":"4","cmd":"release_lease","owner":"guardian","lease_id":"9f3a1c5e22b07d41"}
< {"protocol_version":1,"id":"4","ok":true,"released":true}

> {"protocol_version":1,"id":"5","cmd":"emergency_release","owner":"guardian"}
< {"protocol_version":1,"id":"5","ok":true,"released":2}

> {"protocol_version":1,"id":"6","cmd":"health"}
< {"protocol_version":1,"id":"6","ok":true,"paused":false,"active_leases":1}

> {"protocol_version":1,"id":"7","cmd":"apply_lease","owner":"guardian","domain":"example.org","reason":"Quiz pending","idempotency_key":"q-2","expires_at":"2026-11-16T11:15:00+01:00"}
< {"protocol_version":1,"id":"7","ok":false,"error":"target","message":"the site is not among the user's enabled rules"}
```

Commands map one to one to the existing Go functions. Only the owner `guardian` is accepted, so a client cannot release another owner's leases. `expires_at` must be in the future and at most 60 minutes ahead.

## Safety rules

1. Leases stay in FocoLocal's memory with an expiry. Nothing is written to `config.json`. A FocoLocal restart or a Guardian crash ends them.
2. The user's own rules win. A lease only covers sites the user listed. Pausing FocoLocal or disabling the rule stops the lease at once.
3. Emergencia and exit in Guardian send `emergency_release` before anything else. If the pipe fails, Guardian says so in the panel and the lease still ends by its expiry. FocoLocal's own pause is the second way out.
4. Nothing blocks a whole browser, app, work tool, system setting or emergency. Scope is a listed site only. Guardian sends only domains the owner chose in a Guardian setting, and FocoLocal refuses the rest.
5. FocoLocal works the same without Guardian. The server is passive. Guardian without FocoLocal shows `unavailable` and keeps asking quizzes.
6. No telemetry and no covert action. Active leases and their reason are visible in both apps.
7. Leases are never extended silently. A longer block needs a new key and a new visible request.

## Work split

Each item is its own small pull request with tests. Order matters.

FocoLocal repository (separate, each item needs the owner's go-ahead there):

1. `internal/ipc` protocol, no pipe yet. A pure function that turns one JSON line into a call on `limit.Store` and back. Tests: every command, every error code, bad JSON, oversize line, wrong `protocol_version`, wrong owner. Done when they pass and `capabilities` lists only `domain`.
2. Windows named pipe server in `internal/windows`, with the current-user DACL, started by the app. Tests: a same-user client connects, a name collision is handled, a failed start is logged and the app keeps running. Done when a manual run shows another Windows user cannot open the pipe.
3. Visible leases in the FocoLocal window and a tray action "Release Guardian leases". Done when a lease appears and disappears in a real run.

Guardian repository:

4. Decision record in `docs/decisions/` once the owner answers the open questions. Done when it is accepted.
5. `src/guardian/focolocal_client.py`, standard library only. One request at a time, short timeouts, never on the Tk thread. Tests against an in-process fake server: versions, timeouts, closed pipe, bad answers. Done when `integrations.py` reports `unavailable`, `incompatible`, `disconnected` or `ok` from a real `capabilities` call, with no lease sent.
6. Settings and panel: leisure domains chosen by the owner, a lease length, a switch off by default, a list of active leases. Done when the panel shows them and the switch does nothing without FocoLocal.
7. Emergencia and exit call `emergency_release` in `_emergency`. Done when a test shows a failed release does not stop Emergencia and the message is shown.
8. Request a lease by the rule the owner approves (open question 1). Done when only a certified, passed result can start one and a practice result never does.
9. Contract tests: one shared file of example lines checked in both repositories. Done when the same file passes in both.

Gates before turning it on: a crash test (kill Guardian, leases expire by TTL), a Windows run with a real browser at 125 and 150 percent scaling, and a visible emergency release in tray and panel. Add them to `docs/acceptance.md`.

## Risks and how to undo

- A bug leaves a site blocked. Limits: 60 minutes, memory only, FocoLocal pause, `emergency_release`, restarting FocoLocal.
- Another process opens the pipe. The DACL limits it to the current user. A process of the same user is outside the promise, as `docs/goals.md` says for administrators.
- The two repositories drift apart. The contract file (item 9) and `protocol_version` catch it.
- A Windows pipe in Go may need a new dependency. That is a yellow change there (open question 4).
- Undo: turn the Guardian switch off, or remove `focolocal_client.py` and the setting. In FocoLocal remove `internal/ipc` and the pipe server. The lease engine can stay unused.

## Open questions for the owner

1. When does Guardian ask for a lease? (a) Only when the owner presses a button in the panel. (b) While a quiz is pending and unanswered. (c) After a certified, reviewed passed result, as a block of leisure sites for a study period. `docs/goals.md` and the decisions do not settle it. The most reversible is (a). In every case practice and unreviewed material never count.
2. Should the feature be opt-in and off by default? Proposed: yes.
3. Which sites may Guardian ask about? Proposed: only domains the owner adds in Guardian that are also enabled rules in FocoLocal.
4. May FocoLocal take a Go dependency for the pipe (for example `go-winio`), or use raw Windows calls?
5. Default lease length, 5 to 60 minutes. Proposed: 15.
6. FocoLocal is a separate repository. Should I prepare its pull requests (items 1 to 3), or will you?
7. Is the user-only DACL enough, or also a shared secret file in `%LOCALAPPDATA%`? Proposed: DACL only.
