---
source: CONCERN-804
timestamp: '2026-06-05T19:48:32.899665+00:00'
title: 'ADR-0017 Option D scope gap: shared-base hierarchy for non-actor objects'
type: learning
---

## Concern #804 — ADR-0017 Option D scope gap

The #798 epic (implementing ADR-0017 Option D) and its children (#799–#802) were
scoped to actor-related infrastructure only. The broader intent of ADR-0017 Option D —
that `VultronBase`/`VultronObject` is the shared root for **all** core and wire objects —
was not tracked for non-actor types.

Investigation found:

- Six core non-actor objects (`CaseEvent`, `ActorConfig`, `ObjectStatus`,
  `VultronOutbox`, `VultronEvent`, `CaseLogEntry`, `ReplicationState`) inherit
  directly from `BaseModel` without documented rationale.
- Most are intentional BaseModel (config/DTO/transient envelope): `ActorConfig`,
  `VultronEvent`, and the local `CaseLogEntry` in `case_log.py` (a separate class
  from the wire-serialisable `CaseLogEntry(CoreObject)` in `case_log_entry.py`).
- `ReplicationState(BaseModel)` in `case_log.py` is stale — superseded by
  `VultronReplicationState(VultronObject)` in `replication_state.py`.
- `ObjectStatus`/`OfferStatus` in `status.py` appear unused (no importers found).
- `CaseEvent` deprecation is tracked in epic #788 / issue #792 — not re-tracked here.

The naming collision between `case_log.py:CaseLogEntry(BaseModel)` (local hash-chain
processor) and `case_log_entry.py:CaseLogEntry(CoreObject)` (wire-serialisable domain
model) is a recurring agent confusion hazard.

**Resolved**: 2026-06-05 — implementation tracked in #806, #807, #808, #809
(all children of #798, blocked by #804).
Docs PR: [#805](https://github.com/CERTCC/Vultron/pull/805).
Spec: `specs/architecture.yaml` ARCH-12-007.
