---
source: CONCERN-2219
timestamp: '2026-08-24T20:44:38.356985+00:00'
title: Received Activity objects are artifacts — inline sub-field snapshots are intentional
type: learning
---

A received Activity is an **artifact** — the exact wire object received is
worth storing as-is. `_dehydrate_data` in
`vultron/adapters/driven/db_record.py` deliberately does NOT recursively
dehydrate the sub-fields of inline Activity objects. This is correct and
intentional for two reasons:

1. **Technical**: Activities may not have independent DataLayer records, so
   there is nothing to resolve a bare ID reference back to.
2. **Semantic (more important)**: The sub-field values form a snapshot of
   state at receipt time. For a mutable object like `VulnerabilityCase`, the
   snapshot captures "when you offered me the case, it looked like this" —
   historical accuracy is the point.

**Two copies, not one.** If an actor receives `Offer(Case)` and extracts the
case to seed a live DataLayer record, two distinct things exist:

- The **artifact** — stored Offer with frozen Case snapshot. Immutable in the
  context of that offer. Never write it back over the live record.
- The **live record** — VulnerabilityCase actively maintained. Evolves over
  time.

These diverge by design. Confusing them is a landmine.

**No ADR or spec needed**: this is an internal implementation convention, not
externally-observable behavior (confirmed via `notes/specs-vs-adrs.md`
decision tree). Documentation belongs in `notes/` and `AGENTS.md`.

**Outcome**: documented in three places:

- `notes/datalayer-design.md` — new section "Received Activity Artifacts:
  Inline Sub-Field Snapshots Are Intentional"
- `vultron/adapters/driven/db_record.py` — expanded `_KEEP_INLINE_NESTED_TYPES`
  comment and `_dehydrate_data` docstring
- `AGENTS.md` — new pitfall "Do Not Add Recursive Dehydration to Inline
  Activity Sub-Fields in `_dehydrate_data`"

**Follow-on**: #2545 — "Design: received Activity objects have no enforcement
of artifact immutability" (Concern, blocked by #2219, parent #2222,
Schedule=Someday) — no current enforcement that received Activity objects are
not mutated downstream after storage.

**Docs PR**: <https://github.com/CERTCC/Vultron/pull/2544>
