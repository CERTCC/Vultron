---
source: TWO-ACTOR-DEMO
timestamp: '2026-05-13T20:27:27.918482+00:00'
title: 'Co-located actor delivery: HTTP-routable IDs and ASGIEmitter required'
type: learning
---

## 2026-05-08 TWO-ACTOR-DEMO — Case Actor URN-based ID delivery limitation

**Issue**: The Case Actor uses a URN-based ID
(`urn:uuid:{uuid}/actors/case-actor`), so HTTP delivery via
`DeliveryQueueAdapter` always fails: the adapter logs WARNING on each retry
and ERROR when retries are exhausted, but does not raise — so inbox handlers
on the Case Actor never execute for status updates sent by participants.

**Fix applied in branch `task/463-two-actor-demo-replacement`**:

- `CreateCaseActorNode` now generates an HTTP-routable Case Actor ID
  (`{base_url}/actors/case-actor-{slug}`) instead of a URN-based path.
- `ASGIEmitter` (`vultron/adapters/driven/asgi_emitter.py`) delivers messages
  to co-located actors in-process via the ASGI interface, bypassing HTTP
  entirely for same-server recipients.
- `configure_default_emitter()` wires the `ASGIEmitter` at app startup so all
  outbox processing uses local delivery for co-located actors.

**Broader lesson**: Co-located actors must have HTTP-routable IDs, or an
in-process emitter must be configured so their inbox handlers actually fire.
The workaround of directly updating `SvcAddParticipantStatusUseCase` was
removed once proper delivery was in place.

**Promoted**: 2026-05-13 — architectural pitfall captured in AGENTS.md Common
Pitfalls; ActivityEmitter/ASGIEmitter documentation updated in
notes/architecture-ports-and-adapters.md; codebase docs refreshed in
docs/reference/codebase/ARCHITECTURE.md, INTEGRATIONS.md, STACK.md.
