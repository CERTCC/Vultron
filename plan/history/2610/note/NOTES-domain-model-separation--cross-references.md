---
source: NOTES-domain-model-separation--cross-references
timestamp: '2026-10-12T19:32:39.555991+00:00'
title: Cross-References (domain-model-separation)
type: note
---

**Archived:** 2026-10-12
**Reason:** index of pointers for a note being retired (notes sweep #4496)
**Superseded by:** notes/wire-core-boundary.md; ADR-0099

---

## Cross-References

- `specs/case-management.yaml` CM-03-006 — `case_statuses` rename requirement
- `specs/code-style.yaml` CS-10-001 — typed Pydantic objects at port/adapter boundaries
- `specs/code-style.yaml` CS-10-002 — `FooActivity` vs `FooEvent` naming convention
- `specs/datalayer.yaml` — DataLayer port requirements (auto-rehydration, type-safe writes)
- `notes/datalayer-design.md` — DataLayer design notes (auto-rehydration decision,
  storage record evaluation, vocabulary registry entanglement)
- `notes/case-state-model.md` — CaseStatus/ParticipantStatus append-only
  history model
- `notes/activitystreams-semantics.md` — `case_activity` type limitation,
  Accept/Reject `object_` field patterns
- `notes/use-case-behavior-trees.md` — use case/BT layering and mapping from
  protocol activities to use cases
- `AGENTS.md` — pitfalls for `case_activity`, `active_embargo`,
  and `case_status` (singular) field
- `docs/adr/_adr-template.md` — template for future ADR on this separation
