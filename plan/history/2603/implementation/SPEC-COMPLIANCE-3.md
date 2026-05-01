---
title: "SPEC-COMPLIANCE-3 partial \u2014 SC-3.1 + SC-PRE-1"
type: implementation
timestamp: '2026-03-09T00:00:00+00:00'
source: SPEC-COMPLIANCE-3
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 289
legacy_heading: "Phase SPEC-COMPLIANCE-3 partial \u2014 SC-3.1 + SC-PRE-1\
  \ (COMPLETE 2026-03-06)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-06'
---

## SPEC-COMPLIANCE-3 partial — SC-3.1 + SC-PRE-1

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:289`
**Canonical date**: 2026-03-09 (git blame)
**Legacy heading**

```text
Phase SPEC-COMPLIANCE-3 partial — SC-3.1 + SC-PRE-1 (COMPLETE 2026-03-06)
```

**Legacy heading dates**: 2026-03-06

- **SC-3.1**: `accepted_embargo_ids: list[str]` field added to `CaseParticipant`
  (CM-10-001, CM-10-003); serialization round-trip tests pass.
- **SC-PRE-1**: `CaseEvent` plain Pydantic model added
  (`vultron/as_vocab/objects/case_event.py`); `VulnerabilityCase.events:
  list[CaseEvent]` field and `record_event()` append-only helper added;
  19 tests in `test/as_vocab/test_case_event.py`. Key invariant: `received_at`
  is always set via `now_utc()` — callers MUST NOT pass `received_at` from
  an incoming activity payload.
