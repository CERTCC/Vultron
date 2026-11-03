---
source: SPEC-RETIRE-CSB-04-008
timestamp: '2026-11-03T16:50:01.048747+00:00'
title: Retired requirement CSB-04-008
type: implementation
---

Retired CSB-04-008 from `specs/cs-behavior.yaml` (#5299).

Why: It only required emitting CK. No CK message exists (MSM-03-008, MSM-05-002): the CASE_MANAGER's commit of the received activity, fanned out as Announce(CaseLedgerEntry), is the acknowledgement, so the requirement has nothing left to state.

Final text: `plan/retired-specs/CSB-04-008.md`.
