---
title: "A retired exemption survives in the copies that never cited the ADR — and the surviving copy reads as deliberate, because its docstring asserts the exemption"
type: learning
timestamp: "2026-09-18T18:00:00Z"
source: ISSUE-2505
signal: theme-candidate
---

ADR-0051 gave the CASE_MANAGER a full RM lifecycle, which retired the rule that
it is exempt from RM-closure checks. That retirement *was* applied — in one
place. `AllParticipantsRMClosedConditionNode` says so in its own docstring:

> The Case Actor now has a full RM lifecycle (ADR-0051, CM-23-005), so the
> former `CVDRole.CASE_MANAGER` skip is no longer needed.

Two other copies of the same skip survived: `all_participants_rm_closed`
(`vultron/core/predicates/participants.py`) and `verify_case_closed`
(`vultron/demo/helpers/milestones.py`), plus a third site that inherited the
behaviour and described it in prose. Those were the copies the **demo** consulted,
so every scenario's "all participants RM.CLOSED" milestone passed while the
CASE_MANAGER sat at `RM.ACCEPTED` on every replica — masking a real defect
(#2505) for months.

**What made the survivors invisible is not that they were silent.** They were
documented, and their documentation asserted the exemption as intended design:

| Site | What it said | Status |
|---|---|---|
| `AllParticipantsRMClosedConditionNode` | "the former skip is no longer needed (ADR-0051)" | applied |
| `all_participants_rm_closed` | "Return `True` when every **non-CASE_MANAGER** participant is `RM.CLOSED`" | stale, reads as deliberate |
| `verify_case_closed` | "Case Manager is a coordinator; skip RM closure check." | stale, reads as deliberate |

A reviewer comparing them finds two confident statements of a rule and one
confident statement of its retirement, with nothing marking which is current.
The stale ones are *more* persuasive, because they give a reason ("is a
coordinator") while the current one only gives a citation.

**Why the ADR number is the wrong thing to grep.** The surviving copies never
mentioned ADR-0051 — that is the definition of the problem. Sweeping for the
decision finds only the sites that already know about it. Sweep for the
**shape of the exemption** instead: `CVDRole.CASE_MANAGER in`, `continue`,
`skip`. One grep for the predicate found all three in seconds.

**The downstream cost is a misdiagnosed bug report.** With the checks exempting
the CASE_MANAGER, the defect surfaced in exactly one place: a single `xfail`ed
assertion. #2505 was therefore written from the weakest evidence available and
named the wrong cause — "the fixture never sends a message that would cause the
CaseActor to close the case." The fixture does send it; CM-23-002 runs; the Case
Actor closes itself locally. The real defect was that the transition was never
recorded as a `CaseLedgerEntry`, so no replica could see it. Both fixes the issue
proposed were wrong, and one of them — exempt the CaseActor from the check —
would have written the retired exemption back in as the *fix*.

**How to apply.** When an ADR removes or narrows an exemption, guard, or
special case:

- Grep the **predicate**, not the decision. The copies that cite the ADR are
  already done; the ones that don't are the whole risk.
- Treat a helper whose *docstring states the exemption* as a prime suspect, not
  as settled design. A retired rule does not decay into a `TODO`; it persists as
  a confident sentence with a plausible rationale attached.
- When a bug report's stated cause sits downstream of a check that could be
  exempting the real subject, verify the check before accepting the diagnosis.

Corroboration: this is a **second witness** for the claim already queued in
[[20260917-3342-caseactor-rename-keeps-infrastructure-concrete]] — "when two
entries describe the same fact, make the laggard match the one that already
applied the decision" — and it generalises it from `specs/` prose to executable
code, where the laggard does not merely mislead a reader but silently answers a
different question. That entry found it via a `refines:` link that disagreed with
its parent's rationale; this one found it via a docstring that disagreed with an
ADR. Same shape, different medium, so the claim is about *any* restatement of a
decided rule, not about spec cross-references specifically.

Related: [[20260916-3192-tightening-a-resolver-wakes-dormant-checks]] is the
mirror case — there a guard was inert because its input was always empty; here a
guard was inert because it deliberately excluded its subject. Both read as
green and neither announced itself, which is the shared hazard: **a check that
passes is not evidence it examined what you think it examined.**
