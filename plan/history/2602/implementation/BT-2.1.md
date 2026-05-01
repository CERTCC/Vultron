---
title: "BT-2.1 \u2014 `engage_case` / `defer_case` BTs"
type: implementation
timestamp: '2026-02-24T00:00:00+00:00'
source: BT-2.1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 51
legacy_heading: "Phase BT-2.1 \u2014 `engage_case` / `defer_case` BTs (COMPLETE\
  \ 2026-02-20)"
date_source: git-blame
legacy_heading_dates:
- '2026-02-20'
---

## BT-2.1 — `engage_case` / `defer_case` BTs

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:51`
**Canonical date**: 2026-02-24 (git blame)
**Legacy heading**

```text
Phase BT-2.1 — `engage_case` / `defer_case` BTs (COMPLETE 2026-02-20)
```

**Legacy heading dates**: 2026-02-20

- `ENGAGE_CASE` and `DEFER_CASE` added to `MessageSemantics`
- `EngageCase` (Join) and `DeferCase` (Ignore) patterns added
- `PrioritizationPolicy` and `AlwaysPrioritizePolicy` added to policy module
- BT nodes: `CheckParticipantExists`, `TransitionParticipantRMtoAccepted`,
  `TransitionParticipantRMtoDeferred`, `EvaluateCasePriority` (SSVC stub)
- `vultron/behaviors/report/prioritize_tree.py` with
  `create_engage_case_tree` and `create_defer_case_tree`
- `engage_case` and `defer_case` handlers registered
- `specs/prototype-shortcuts.yaml` PROTO-05-001 documented
