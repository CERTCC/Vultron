---
source: NOTES-embargo-default-semantics--no-pre-case-embargo-phase
timestamp: '2026-10-02T16:31:00.863818+00:00'
title: No Pre-Case Embargo Phase
type: note
---

**Archived:** 2026-10-02
**Reason:** redundant — ADR-0096 records the decision, the evidence table and the docs correction to rm_em.md
**Superseded by:** ADR-0096; EP-04-009

---

## No Pre-Case Embargo Phase

CONCERN-2215 asked whether Vultron gets a protocol phase before a case exists, on
the strength of `model_interactions/rm_em.md` stating that the EM process MAY begin
before the report is sent. **ADR-0096 answered no**, and the reason is stronger
than "not implemented":

| Fact | Where |
|---|---|
| EM is defined as a global **per-case** state machine | `docs/reference/glossary.md` |
| EM state exists only as `CaseStatus.em` (an `EmDimension`) | `vultron/core/models/dimensions.py` |
| `EmbargoEvent.context` is required, and every core construction site set it to `case_id` | `case/nodes/embargo.py`, `triggers/embargo/{propose,revise}.py` |
| `propose_embargo(case_id=…)` raises `VultronNotFoundError` when the case does not resolve | `vultron/core/services/embargo_lifecycle/proposals.py` |

So the documented $q^{em} \in N \xrightarrow{p} P$ before any case exists named a
machine instance that could not exist. `rm_em.md` has been corrected: its
*motivation* survives (a sender may want terms fixed before disclosing), its
*mechanism claim* is withdrawn.

What replaces the phase is two rules, both above: the protocol default means a
reporter never faces "no embargo at all", and the embedded proposal means they can
always state the terms they want. Shortest-wins settles any disagreement at case
creation.

Note that EP-04-009's context widening does give pre-case embargo terms a
legitimate home. What ADR-0096 declines is the *phase*, not the *representation* —
so if a genuine pre-submission negotiation is ever wanted, the object it would
negotiate over already exists.
