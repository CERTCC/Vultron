---
title: PRM-06-004 permits an on-behalf d→D for a deployer "under the same pattern" as PRM-06-003's never-joined vendor, but the CS entailment refuses D for any participant whose RM is START — so the on-behalf d→D exists only for a deployer who already joined
type: learning
timestamp: 2026-09-30T23:30:00Z
source: ISSUE-3832
signal: spec-ambiguity
---

Routing `SvcAddOnBehalfStatusUseCase` over HTTP (#3832, AC-5) meant driving
d→D on behalf of a Deployer end to end for the first time; the unit tests had
only exercised the v→V path and the request-layer f→F refusal.  The first
HTTP attempt — a Case Manager asserting `d_state="D"` for a deployer that had
never joined the case — was refused by `CreateParticipantStatusNode` with the
cross-machine entailment from `rm_em_cs.md` § Fix Deployment:

> D='D' (D bit set) requires RM ∈ {ACCEPTED, DEFERRED, CLOSED}, but RM='START'.

`EnsureOnBehalfParticipantExistsNode` mints a minimal participant for an
absent target (ADR-0084), and a minimal participant sits at `RM.START`, so the
on-behalf d→D for a never-joined deployer is refused by construction.  It
succeeds only for a deployer who is already a participant at `RM.ACCEPTED` (or
`DEFERRED`/`CLOSED`) and has not self-reported deployment — which the HTTP
test now pins in both directions.

The spec reads as if the two on-behalf assertions have the same reach.
PRM-06-003 scopes v→V to "a vendor notified or invited but not yet — or never —
a participant"; PRM-06-004 says d→D is permitted "under the same
externally-evidenced pattern".  Read literally, "the same pattern" includes the
never-a-participant case, and for d→D that case cannot be written.  Nothing in
PRM-06 names the entailment, and nothing in CSB names the on-behalf carve-out,
so a reader of either alone concludes the other allows more than it does.

What would resolve it: either PRM-06-004 states that an on-behalf d→D is
scoped to a deployer who has already accepted the case (the entailment is the
reason, and "expected to be rare" then has a mechanism behind it), or ADR-0084
decides that an externally evidenced deployment by a never-joined deployer
should also carry the RM the evidence implies — a design choice this task did
not make.  The registry work took the first reading and tested it; the spec
still says the second.

Tracked as Concern #4006 (filed from the same session), which holds the two
resolution options; this file records the evidence behind it.

**Promoted**: 2026-10-02 — Already closed — PRM-06-004 scoped to a deployer already in the case (Concern #4006 closed).
Docs PR: <https://github.com/CERTCC/Vultron/pull/4174>.
