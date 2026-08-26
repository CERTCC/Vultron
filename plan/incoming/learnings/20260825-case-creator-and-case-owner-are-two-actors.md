---
title: '"case creator/owner" names two different actors under ADR-0041'
type: learning
timestamp: 2026-08-25
source: ISSUE-2548
signal: spec-contradiction
---

`CBT-01-003` required the bootstrap snapshot to "identify the case creator/owner
as a participant with `CASE_OWNER` role and … the CaseActor as a participant with
`COORDINATOR` role". `PCR-01-002` uses the same compound noun: "exactly one
CaseActor per case, operated by the case creator/owner."

Under ADR-0041 the CaseActor **is** the creator. So the slash in
"creator/owner" joins two different actors, and the requirement reads as though
the CaseActor should hold `CASE_OWNER` — which the maintainer was explicit it must
never hold. The implementation had it right all along
(`case_proposal_received_tree.py:401` registers the CaseActor as
`COORDINATOR + CASE_MANAGER`; `:487` registers the report receiver as
`CASE_OWNER` at `RM.RECEIVED`), so this was a spec that disagreed with working
code, not a bug.

The distinction is load-bearing, not cosmetic:

- `CASE_OWNER` is the standing of the party whose disclosure decision the case
  exists to serve — the actor whose `CaseProposal` caused the case. **Never
  delegated.** EM-behaviour treats its stated position as gospel
  (`em-behavior.yaml` CASE_OWNER hard-bypass arm).
- `CASE_MANAGER` is the privilege of writing the canonical case ledger, held by
  the CaseActor because it created the case in its own store. `CLP-09` gates
  ledger commits on it.

Collapsing them makes "the CaseActor owns write privileges on the ledger" —
true — indistinguishable from "the CaseActor owns the case" — false. `CBT-01-003`
is amended in place to say which actor is which, and now also names `CASE_MANAGER`
(which the code assigns and the old wording omitted).

**How to apply.**

- Do not write "creator/owner", "owner/manager", or `case_owner_id` where the
  ADR-0041 split applies. Name the role: `CVDRole.CASE_OWNER` for the proposer,
  `CVDRole.CASE_MANAGER` for the CaseActor.
- `PCR-01-002` still carries the compound phrasing. It was left alone this pass
  because its claim (one CaseActor per case) survives either reading, but it is
  the next place a reader will be misled.
- Resolve authority by role held in the case, never by comparing an actor id to a
  computed `case_actor_id` — ADR-0073 already made that normative (CM-24-004);
  the wording gap here is what let the two ideas drift.
- Related: [[a-spec-can-assert-the-premise-that-causes-the-bug]] — same failure
  mode, where the spec text is the thing that needs fixing.
