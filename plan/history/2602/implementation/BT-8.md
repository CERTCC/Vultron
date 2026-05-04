---
title: "BT-8 \u2014 Missing MessageSemantics"
type: implementation
timestamp: '2026-02-24T00:00:00+00:00'
source: BT-8
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 124
legacy_heading: "Phase BT-8 \u2014 Missing MessageSemantics (COMPLETE 2026-02-24)"
date_source: git-blame
legacy_heading_dates:
- '2026-02-24'
---

## BT-8 — Missing MessageSemantics

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:124`
**Canonical date**: 2026-02-24 (git blame)
**Legacy heading**

```text
Phase BT-8 — Missing MessageSemantics (COMPLETE 2026-02-24)
```

**Legacy heading dates**: 2026-02-24

- `UPDATE_CASE` (`as:Update(VulnerabilityCase)`) fully wired: `MessageSemantics` enum
  value, `UpdateCasePattern`, `update_case` handler, and tests (BT-8.6–BT-8.9)
- `REENGAGE_CASE` (`as:Undo(object=RmDeferCase)`) — **decided not to implement as a
  separate semantic type**. Re-engagement is achieved by emitting a second
  `RmEngageCase` (`as:Join`) activity from the `DEFERRED` state. The `reengage_case()`
  factory in `vocab_examples.py` is retained as a legacy documentation artifact only.
  See `notes/activitystreams-semantics.md` for the rationale.
- `CHOOSE_PREFERRED_EMBARGO` (`as:Question`) — **deferred**. The core
  propose/accept/reject flow covers the vast majority of embargo workflows. The
  placeholder class in `vultron/as_vocab/activities/embargo.py` is retained; no
  handler or pattern wired. Revisit if multiple simultaneous embargo proposals
  prove necessary in practice.
