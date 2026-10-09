---
source: CONCERN-4321
timestamp: '2026-10-08T20:12:37.488952+00:00'
title: Remove or ratchet the CaseStatus.em_state setter now that EM is derived from
  the embargo register
type: learning
---

## Concern

`CaseStatus.em_state` still has a setter (`vultron/core/models/case_status.py`) that writes `em` directly.
Since #4290 (PR #4320), a case's EM is derived from its embargo register (ADR-0122), and `CaseStatus.em` on a case is only a copy that the case stamps from the register at construction, at every register step and in `add_case_status`.
A caller that writes `case.current_status.em_state = X` (or assigns `case.current_status.em`) makes the copy disagree with the register until the next stamp, and nothing refuses it.
No production code does this today (grep finds none), so this is fragility, not a live bug.

## Options

- Remove the setter, so a status's EM can only be set at construction (preferred if no wire or test path needs it).
- Or keep it and add a ratchet test that no code under `vultron/core/` assigns a case's status EM.

Governing specs: SDO-03-001, SDO-03-003, EMB-18-001, RSH-05-023

**Resolved**: 2026-10-08 — implementation tracked in #4375, #4376, #4377.

Removing the setter alone would not close the hole: `status.em = …` and
`status.em.state = …` are writable too. The plan freezes `EmDimension` and
`CaseStatus.em` (SDO-03-006), so every in-place write raises while the case's
`model_copy` stamp still works. The wider flat-shim removal SDO-03-003 already
required is split into a `CaseStatus` task and a `ParticipantStatus` task.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4374>.
Spec: `specs/status-dimension-objects.yaml` (SDO-03-006).
