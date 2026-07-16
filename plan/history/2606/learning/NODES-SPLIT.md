---
source: NODES-SPLIT
timestamp: '2026-06-22T19:32:41.737280+00:00'
title: VulnerabilityCase.case_statuses has a default initial CaseStatus
type: learning
---

`VulnerabilityCase.case_statuses` is auto-populated with one `CaseStatus`
(em_state=EM.NONE, UUID id) when the object is created. Tests that check
`len(case.case_statuses) == 1` after a single append will fail with `2`.
Use `initial_count + 1` pattern or check only SUCCESS status.

**Promoted**: 2026-06-22 — archive only (too narrow for durable guidance).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
