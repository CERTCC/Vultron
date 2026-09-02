---
title: A SIGNATORY rejecting an embargo revision has no legal PEC path on the received side
type: learning
timestamp: "2026-09-02T00:00:00Z"
source: ISSUE-2762
signal: spec-gap
---

Surfaced while reviewing the `reject_invite_to_embargo_tree` half of #2762.
Re-targeting the DECLINE from the receiving actor to the actual rejecter is
correct, but it changes *which* participant's PEC state the transition is
checked against — and makes an illegal transition more reachable.

`DECLINE` is legal only from `NO_EMBARGO | INVITED | LAPSED`
(`vultron/core/states/participant_embargo_consent.py`). The actor most likely to
reject an embargo **revision** is one who already consented and is therefore
`SIGNATORY`. The legal route to `DECLINED` from there is two hops —
`SIGNATORY --REVISE--> LAPSED --DECLINE--> DECLINED` — and the received-side
reject tree runs no EM lifecycle node, so the `ACTIVE → REVISE` PEC cascade in
`services/embargo_lifecycle.py` never happens in the *receiver's* store to
supply the first hop.

What happens instead: `apply_pec_transition()` raises
`VultronInvalidStateTransitionError`, `BTBridge.execute_tree` catches it and
returns FAILURE (logging at ERROR with a traceback, so it is not invisible), and
the use case adds a DEBUG line. The ledger receipt for the Reject is committed —
it is ordered before the protocol effects per CLP-10-010 — while the consent
change is dropped. Fail-closed, so no wrong write, but the participant is left
`SIGNATORY` after having explicitly rejected. A redelivered Reject
(`DECLINED --DECLINE-->`) takes the same path.

Pinned as `test_reject_from_signatory_is_refused_not_applied` in
`test/core/use_cases/received/test_embargo_invite_lapse.py`, which documents the
current behavior rather than endorsing it.

The open question is which of these is right:

1. The received reject tree should run the REVISE cascade first, so a rejecting
   SIGNATORY passes through `LAPSED` — makes the receiver's replica mirror the
   trigger side, but puts EM lifecycle work on the received path.
2. `DECLINE` should be legal from `SIGNATORY` — simpler, but erases the
   distinction between "declined an open invitation" and "withdrew consent",
   which `LAPSED` exists to carry.
3. It is genuinely unreachable in practice and the guard is doing its job — in
   which case the test should say so explicitly and a spec note should record
   why.

Deliberately not decided inside a bugfix PR: option 1 is an EM lifecycle change
on the received path, and the choice turns on whether withdrawal of consent is a
distinct protocol event from rejection. Related: the `cc:`-on-invite removal
filed as Concern #2996 came out of the same investigation, as did
[[20260901-2762-optional-lookup-participant-fallback]].
