---
source: SPEC-RETIRE-CSB-06-009
timestamp: '2026-11-03T16:50:38.325432+00:00'
title: Retired requirement CSB-06-009
type: implementation
---

Retired CSB-06-009 from `specs/cs-behavior.yaml` (#5299).

Why: It only required emitting CK. No CK message exists (MSM-03-008, MSM-05-002): the CASE_MANAGER's commit of the received activity, fanned out as Announce(CaseLedgerEntry), is the acknowledgement, so the requirement has nothing left to state.

Final text: `plan/retired-specs/CSB-06-009.md`.
