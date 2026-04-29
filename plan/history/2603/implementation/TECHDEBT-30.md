---
title: "TECHDEBT-30 \u2014 Domain-specific property getters on core event\
  \ interfaces"
type: implementation
date: '2026-03-23'
source: TECHDEBT-30
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2782
legacy_heading: "TECHDEBT-30 \u2014 Domain-specific property getters on core\
  \ event interfaces (COMPLETE 2026-03-23)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-23'
---

## TECHDEBT-30 — Domain-specific property getters on core event interfaces

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2782`
**Canonical date**: 2026-03-23 (git blame)
**Legacy heading**

```text
TECHDEBT-30 — Domain-specific property getters on core event interfaces (COMPLETE 2026-03-23)
```

**Legacy heading dates**: 2026-03-23

**Goal**: Replace AS2-generic field accesses (`object_id`, `target_id`,
`context_id`, `inner_object_id`, etc.) in core use cases with domain-specific
property names (`report_id`, `case_id`, `embargo_id`, `offer_id`, etc.).

**Approach**: Created `vultron/core/models/events/_mixins.py` with 14 reusable
property-mixin classes. Each mixin exposes one domain-specific property aliasing
the appropriate generic base-class field. Per-semantic event subclasses inherit
the relevant mixin(s) alongside `VultronEvent`. Updated all 7 use-case modules
to access domain properties instead of generic names.

**Source files changed**:

- `vultron/core/models/events/_mixins.py` — new file; 14 mixin classes
- `vultron/core/models/events/report.py` — mixin inheritance on 6 event classes
- `vultron/core/models/events/actor.py` — mixin inheritance on 3 event classes
- `vultron/core/models/events/embargo.py` — mixin inheritance on 6 event classes
- `vultron/core/models/events/case_participant.py` — mixin inheritance on 3 event classes
- `vultron/core/models/events/note.py` — mixin inheritance on 3 event classes
- `vultron/core/models/events/status.py` — mixin inheritance on 4 event classes
- `vultron/core/models/events/case.py` — mixin inheritance on `AddReportToCaseReceivedEvent`
- `vultron/core/use_cases/report.py`, `actor.py`, `embargo.py`, `case_participant.py`,
  `note.py`, `status.py`, `case.py` — all generic field references replaced

### Test results

984 passed, 5581 subtests passed.
