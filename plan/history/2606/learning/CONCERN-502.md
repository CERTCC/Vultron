---
source: CONCERN-502
timestamp: '2026-06-01T18:47:07.493365+00:00'
title: Actor-scoped vs shared DataLayer scope boundaries
type: learning
---

## Concern #502 — Actor-scoped vs shared DataLayer scope boundaries are fragile and under-tested

**Category**: Top risk
**Severity**: High

### Root Cause

`SqliteDataLayer` serves two distinct roles — shared object storage and
actor-scoped queue operations — conflated in a single `DataLayer` Protocol.
Queue methods use `self._actor_id or ""` as the key, so calling them on a
shared (unscoped) DL silently operates on a phantom `""` queue. The codebase
has no type-level enforcement that prevents callers from passing a shared DL
where an actor-scoped one is required.

A second, related bug (BUG-2026040901): `record_outbox_item(actor_id, …)`
writes a queue row keyed by the exact string passed as `actor_id`. If a
short-UUID path param is used to write but the canonical URI is used to read
(or vice versa), the queue appears empty and outbound activities are silently
dropped. `get_canonical_actor_dl()` is the existing fix, but it has no
dedicated unit tests.

### Resolution

- Added ARCH-13 spec group (ARCH-13-001 through ARCH-13-005) to
  `specs/architecture.yaml` formalizing the shared-vs-actor-scoped contract
  and the canonical URI identity rule.
- Added §DataLayer Scope Boundaries to
  `notes/architecture-ports-and-adapters.md` documenting the split, the
  identity contract, and the planned `ActorScopedDataLayer` Protocol.
- Added two pitfall entries to `vultron/adapters/AGENTS.md`.

**Resolved**: 2025-07-16 — specs, notes, and AGENTS.md updated.
Docs PR: [#657](https://github.com/CERTCC/Vultron/pull/657).
Implementation tracked in [#655](https://github.com/CERTCC/Vultron/issues/655)
(Protocol split, size:M) and [#656](https://github.com/CERTCC/Vultron/issues/656)
(regression tests, size:S, blocked by #655).
