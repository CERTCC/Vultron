---
title: "DEMO-3.10\u20133.15 \u2014 Manage Embargo + Manage Participants Demos"
type: implementation
timestamp: '2026-02-26T00:00:00+00:00'
source: LEGACY-2026-02-26-demo-3-10-3-15-manage-embargo-manage-participant
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 154
legacy_heading: "Phase DEMO-3.10\u20133.15 \u2014 Manage Embargo + Manage\
  \ Participants Demos (COMPLETE 2026-02-26)"
date_source: git-blame
legacy_heading_dates:
- '2026-02-26'
---

## DEMO-3.10–3.15 — Manage Embargo + Manage Participants Demos

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:154`
**Canonical date**: 2026-02-26 (git blame)
**Legacy heading**

```text
Phase DEMO-3.10–3.15 — Manage Embargo + Manage Participants Demos (COMPLETE 2026-02-26)
```

**Legacy heading dates**: 2026-02-26

- `manage_embargo_demo.py` — full propose → accept → activate → terminate cycle;
  also demonstrates propose → reject → re-propose path + dockerized
- `manage_participants_demo.py` — full invite → accept → create_participant →
  add_to_case → create_status → add_status → remove_participant cycle;
  also demonstrates reject path + dockerized
- Tests: `test/scripts/test_manage_embargo_demo.py`,
  `test/scripts/test_manage_participants_demo.py`
- **All Phase DEMO-3 tasks complete**: 568 tests passing at completion
