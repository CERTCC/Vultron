---
title: "REFACTOR-1 \u2014 CM-03-006 Status History Renames"
type: implementation
timestamp: '2026-03-09T00:00:00+00:00'
source: REFACTOR-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 221
legacy_heading: "Phase REFACTOR-1 \u2014 CM-03-006 Status History Renames\
  \ (COMPLETE 2026-02-27)"
date_source: git-blame
legacy_heading_dates:
- '2026-02-27'
---

## REFACTOR-1 — CM-03-006 Status History Renames

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:221`
**Canonical date**: 2026-03-09 (git blame)
**Legacy heading**

```text
Phase REFACTOR-1 — CM-03-006 Status History Renames (COMPLETE 2026-02-27)
```

**Legacy heading dates**: 2026-02-27

- `VulnerabilityCase.case_status` (list) → `case_statuses`; `case_status` added
  as read-only property (REFACTOR-1.1)
- `CaseParticipant.participant_status` (list) → `participant_statuses`;
  `participant_status` added as read-only property (REFACTOR-1.2)
- All references in handlers, behaviors, and tests updated (REFACTOR-1.3)
