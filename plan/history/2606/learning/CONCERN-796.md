---
source: CONCERN-796
timestamp: '2026-06-05T18:47:38.964394+00:00'
title: 'Core/wire class hierarchy: shared-base two-branch model'
type: learning
---

## Architecture clarification for core & wire class hierarchy

Two architectural gaps surfaced after PR #794 (migrate Vultron actor types
to core/models/):

### Item 1: ARCH-12 blocked for actor types

ARCH-12-002/003 require every wire-layer type to implement `from_core()`
and `to_core()` classmethods. Those cannot be implemented for Vultron actor
types using the normal wire-subclass pattern due to 17 field-type conflicts
between `CoreObject` and `as_Object` hierarchies. Most irreconcilable:

- `inbox`/`outbox`: `CoreActorCollection | None` vs `as_OrderedCollection`
- All `NonEmptyString | None` fields in core vs `str | None` in wire

**Root cause**: Core and wire were modeled as parallel *independent*
hierarchies. ARCH-12's `from_core()`/`to_core()` protocol was designed to
bridge the gap but cannot be implemented when field types are structurally
incompatible.

**Resolution**: Amend ADR-0017 from Option B (parallel hierarchies) to
Option D (shared-base, two-branch hierarchy). `VultronBase`/`VultronObject`
(already in `core/models/base.py`) serve as the shared root. Core branch
adds domain validators; wire branch adds AS2 concerns. ARCH-12 is replaced
with shared-base specs. Translation uses `model_validate()` round-trip — no
explicit `from_core()`/`to_core()` protocol required.

Key insight: `inbox`/`outbox` should be `str | None` in the domain (just
the endpoint URI); the AS2 `OrderedCollection` shape is a wire-only concern.
`CoreActorCollection` was over-engineering.

### Item 2: `CoreActor | as_Actor` unions in adapters

Several adapter functions use `CoreActor | as_Actor` unions because
`VOCABULARY["Actor"] = as_Actor` still exists. This collapses once proper
wire-branch actor types are in place and `VOCABULARY["Actor"]` is updated.

**Resolution**: Tracked in implementation epic #798, child issues #799–#802.

**Processed**: 2026-06-05 — implementation tracked in epic #798
(children: #799, #800, #801, #802).
Docs PR: <https://github.com/CERTCC/Vultron/pull/797>.
Spec: `specs/architecture.yaml` (ARCH-12 replaced).
ADR: `docs/adr/0017-domain-wire-object-separation.md` (amended to Option D).
