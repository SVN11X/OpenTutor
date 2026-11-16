# 0010. Guardian and FocoLocal stay independent

- Status: accepted
- Date: 2026-11-16
- Proposed by: owner
- Accepted by: owner, in chat on 2026-11-16

## Context

docs/goals.md listed temporary leisure restrictions with FocoLocal as a later objective, and docs/focolocal-ipc-plan.md proposed a local channel through which Guardian would ask FocoLocal to block leisure sites for a few minutes. Asked which sites Guardian may block, the owner answered that no web page is blocked, and that Guardian and FocoLocal are independent apps with different purposes and, for now, no relation.

## Decision

Guardian never talks to FocoLocal and never asks it, or anything else, to block a site. The panel no longer lists FocoLocal among its services. The plan and the earlier audit stay in docs/ as history, marked as archived. FocoLocal is not changed.

## Alternatives considered

- Notices without blocking: Guardian asks FocoLocal to show a reminder on leisure sites. It still links the two apps, which the owner does not want.
- Reading FocoLocal's state only: the smallest link, but still a link with no use for the owner.

## Consequences

Guardian has one fewer service to explain and no cross-app contract to keep. A validated task gives no leisure credit, because nothing grants leisure. To undo, write a new decision and reopen docs/focolocal-ipc-plan.md, which keeps the verified facts about FocoLocal as of 2026-11-16.
