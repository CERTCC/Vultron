---
title: "SPEC-COMPLIANCE-1 \u2014 Object Model Gaps"
type: implementation
timestamp: '2026-03-09T00:00:00+00:00'
source: SPEC-COMPLIANCE-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 266
legacy_heading: "Phase SPEC-COMPLIANCE-1 \u2014 Object Model Gaps (COMPLETE\
  \ 2026-03-06)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-06'
---

## SPEC-COMPLIANCE-1 — Object Model Gaps

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:266`
**Canonical date**: 2026-03-09 (git blame)
**Legacy heading**

```text
Phase SPEC-COMPLIANCE-1 — Object Model Gaps (COMPLETE 2026-03-06)
```

**Legacy heading dates**: 2026-03-06

- **SC-1.1**: `VulnerabilityRecord` Pydantic model added
  (`vultron/as_vocab/objects/vulnerability_record.py`); unit tests added.
- **SC-1.2**: `CaseReference` Pydantic model added
  (`vultron/as_vocab/objects/case_reference.py`); unit tests added.
  (Previously named `Publication`; renamed per commit ad46802.)
- **SC-1.3**: `create_case` BT verified to record vendor as initial
  `CaseParticipant`; `SetCaseAttributedTo` and `CreateInitialVendorParticipant`
  BT nodes added to `vultron/behaviors/case/nodes.py`.
