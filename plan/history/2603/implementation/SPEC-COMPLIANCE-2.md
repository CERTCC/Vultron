---
title: "SPEC-COMPLIANCE-2 \u2014 Embargo Policy Model"
type: implementation
date: '2026-03-09'
source: SPEC-COMPLIANCE-2
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 279
legacy_heading: "Phase SPEC-COMPLIANCE-2 \u2014 Embargo Policy Model (COMPLETE\
  \ 2026-03-06)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-06'
---

## SPEC-COMPLIANCE-2 — Embargo Policy Model

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:279`
**Canonical date**: 2026-03-09 (git blame)
**Legacy heading**

```text
Phase SPEC-COMPLIANCE-2 — Embargo Policy Model (COMPLETE 2026-03-06)
```

**Legacy heading dates**: 2026-03-06

- **EP-1.1**: `EmbargoPolicy` Pydantic model added
  (`vultron/as_vocab/objects/embargo_policy.py`).
- **EP-1.2**: `VultronActorMixin` + `VultronPerson`, `VultronOrganization`,
  `VultronService` subclasses added (`vultron/as_vocab/objects/vultron_actor.py`);
  16 new tests; actor AS types preserved.
