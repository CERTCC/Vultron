---
source: ISSUE-699
timestamp: '2026-06-03T20:38:09.614580+00:00'
title: 'Scoping: #699 decomposed into 7 blocking sub-issues'
type: implementation
---

## Issue #699 — Migrate domain objects from wire/as2/vocab/objects/ to core/models/

Scoping session, not an implementation. `build` selected #699 but discovered
the work is much larger than the original `size:L` estimate: the 7 wire types
depend deeply on wire-only types (`as_Object`, `ActivityStreamRef[T]`,
`as_NoteRef`, `as_Activity`, `VOCABULARY` registry), and 134 files import from
`vultron/wire/as2/vocab/objects/`.

Per maintainer direction, the right framing is to build a parallel core class
hierarchy (analog of `as_Base`/`as_Object`), migrate domain logic into it
type-by-type, and make the wire layer a thin projection.

**Key architectural decision (to be recorded in the ADR landed by #724):**
refs (`FooRef` patterns) are a wire concern only — core fields hold full
objects; the DataLayer hydrates on read; wire projections handle ref-or-inline
translation at the serialization boundary.

### Decomposition

All sub-issues blocked-by chain; all parented to #539; all added to Project #24
with Schedule=Someday:

- #724 — Foundation + ADR (size:M)
- #725 — CaseStatus + ParticipantStatus (size:M, blocked by #724)
- #726 — EmbargoPolicy + EmbargoEvent (size:M, blocked by #725)
- #727 — VulnerabilityReport + VulnerabilityRecord + CaseLogEntry (size:M, blocked by #726)
- #728 — CaseParticipant + 8 role subclasses (size:L, blocked by #727)
- #729 — VulnerabilityCase + CaseEvent + CaseReference + CaseActor (size:L, blocked by #728)
- #730 — Vultron actor types (Person/Organization/Service/Application) (size:M, blocked by #729)

Issue #699 itself resized to size:S; it closes once the chain lands by typing
`VultronActivity.object_` as a Pydantic discriminated union and deleting the
`_STUB_OBJECT_MODEL_MAP`/`_STUB_OBJECT_TYPES` workaround in
`vultron/adapters/driving/fastapi/outbox_handler.py`.

## Outcome

No code changes. PR [#731](https://github.com/CERTCC/Vultron/pull/731)
records the scoping decision in `plan/BUILD_LEARNINGS.md`.
