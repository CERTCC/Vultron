---
source: CONCERN-3466
timestamp: '2026-09-21T18:45:19.269727+00:00'
title: Promote the ratchetable-column rule
type: learning
---

## Summary

`plan/incoming/learnings/20260918-3337-a-doc-rots-first-in-the-column-no-test-can-hold.md`
claimed that when a mirrored doc table goes stale, the columns that rot are the
ones no test could hold, while the source-derivable columns stay roughly right.
It closed asking for a second witness. #3450 (PR #3464) produced one, so the
claim is now corroborated and should become durable guidance rather than sitting
in the queue. The second witness also refines the prescribed remedy, which is
the part worth acting on.

## Underlying problem

The queued entry offered a binary: a column is either ratchetable (keep it, add
the ratchet) or not (delete it and point at the live answer). The witness was a
column that looked unratchetable and was not — it was two facts wearing one
heading, and separating them made one of them derivable. Deleting it, as the
entry advised, would have discarded information the registry could hold. The
third option between "add a ratchet" and "delete": disaggregate before deciding.

## Evidence

Witness: `vultron/demo/scenario/README.md` § "Available scenario demos". The
free-prose "What it demonstrates" column read "Finder + Coordinator + Vendor +
Coordinator2" for `fcvcv` — four actors for a five-actor scenario — while the
Sub-command and Script columns were correct 9/9. Exactly the predicted ordering.
This was the second rot event in that one table; ADR-0098's Context records the
first (a `vc` row describing a `vc_demo.py` that never existed).

Discovered while implementing #3450 (PR #3464).

**Resolved**: 2026-09-21 — promoted into durable guidance. No separate
implementation issue was created: the underlying code defect was already fixed
in PR #3464 and the scenario tables were made derived artifacts by ADR-0098, so
the docs PR is the entire resolution. The #3337 learning entry was retired from
`plan/incoming/learnings/` in the same PR.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3479>.
Spec: `specs/meta-specifications.yaml` (new MS-16-002, generalising MS-16-001).
Notes: `notes/documentation-sweeps.md` (mirrored-table column-triage procedure);
`notes/specs-vs-adrs.md` (generalised the Ephemeral Counts section).
