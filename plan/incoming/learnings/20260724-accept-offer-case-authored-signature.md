---
title: "CASE_AUTHORED_SIGNATURES must include Accept(Offer) for CaseManagerRole delegation"
type: learning
timestamp: "2026-07-24T19:52:00Z"
source: ISSUE-1686
signal: design-question
---

When implementing the ledger commit for `Accept(CaseManagerRole)`, CLP-07-003
blocked the commit because `("Accept", "Offer")` was not in
`_CASE_AUTHORED_SIGNATURES`.  The CaseActor is the legitimate author of this
activity (it is accepting the delegation offer on the case's behalf), so the
signature must be allowed for CaseActor authorship.

Decision: added `("Accept", "Offer")` to `_CASE_AUTHORED_SIGNATURES` in
`vultron/core/behaviors/sync/nodes/chain.py`.

Rationale: the `_CASE_AUTHORED_SIGNATURES` set is intended to enumerate
activities where it is *correct* for the CaseActor service to appear as the
author.  `Accept(CaseManagerRole)` fits that definition.  The existing
`("Accept", "Offer")` entry in `_CANONICAL_PAYLOAD_SIGNATURES` covers
`validate_report` where the actor is a *participant*, not the CaseActor — so
there was no conflict, just an incomplete allowlist.
