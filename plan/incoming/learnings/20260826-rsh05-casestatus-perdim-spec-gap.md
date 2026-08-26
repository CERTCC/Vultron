---
title: RSH-05 per-dimension adjudication not extended to CaseStatus EM/PXA
type: learning
timestamp: 2026-08-26T17:30:00Z
source: ISSUE-2256
signal: spec-gap
---

RSH-05 (*Per-Dimension Partial Accept*) was written for
`Add(ParticipantStatus, CaseParticipant)` only. Its description explicitly
names that activity type and was derived from ISSUE-2235.

ISSUE-2256 implemented the same per-dimension adjudication for
`Add(CaseStatus, VulnerabilityCase)` (EM + PXA dimensions), but there are no
RSH-05-xxx spec entries covering it. The implementation references RSH-05 and
ADR-0061 by analogy, but neither document names CaseStatus as in-scope.

A spec extension (new RSH-06 section or RSH-05 amendment) should:

- state that `Add(CaseStatus)` receives the same liberal-accept treatment
- enumerate the two dimensions (EM, PXA) and their carry-forward semantics
- reference `FilterCsEmDimensionNode`, `FilterCsPxaDimensionNode`,
  `FinalizeCsFilterNode` in `cs_dimension_filter.py` as the implementation

PR: <https://github.com/CERTCC/Vultron/pull/2669>
