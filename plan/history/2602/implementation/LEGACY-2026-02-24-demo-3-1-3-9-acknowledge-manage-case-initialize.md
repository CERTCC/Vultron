---
title: "DEMO-3.1\u20133.9 \u2014 Acknowledge, Manage Case, Initialize Participant"
type: implementation
timestamp: '2026-02-24T00:00:00+00:00'
source: LEGACY-2026-02-24-demo-3-1-3-9-acknowledge-manage-case-initialize
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 141
legacy_heading: "Phase DEMO-3.1\u20133.9 \u2014 Acknowledge, Manage Case,\
  \ Initialize Participant (COMPLETE 2026-02-24)"
date_source: git-blame
legacy_heading_dates:
- '2026-02-24'
---

## DEMO-3.1–3.9 — Acknowledge, Manage Case, Initialize Participant

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:141`
**Canonical date**: 2026-02-24 (git blame)
**Legacy heading**

```text
Phase DEMO-3.1–3.9 — Acknowledge, Manage Case, Initialize Participant (COMPLETE 2026-02-24)
```

**Legacy heading dates**: 2026-02-24

- `acknowledge_demo.py` — submit → ack_report workflow + dockerized
- `manage_case_demo.py` — full RM lifecycle including defer/reengage via second
  `RmEngageCase` + dockerized
- `initialize_participant_demo.py` — standalone participant creation workflow +
  dockerized
- Tests: `test/scripts/test_acknowledge_demo.py`,
  `test/scripts/test_manage_case_demo.py`,
  `test/scripts/test_initialize_participant_demo.py`
