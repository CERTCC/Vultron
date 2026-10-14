---
source: CONCERN-4565
timestamp: '2026-10-14T19:25:59.501899+00:00'
title: Ownership-transfer forward resolves to its Offer by time, not by a link
type: learning
---

## Summary

`_forwarded_entry()` in `vultron/core/participants/ownership_offer.py` maps the CASE_MANAGER's forward of an ownership-transfer Offer back to the recorded Offer it stands for by time: the latest `offer_case_ownership_transfer` entry for the same transferee whose `received_at` is no later than the forward's `published`. Both times are second-precision (`now_utc`).

So when Offer A is answered and a new Offer B to the same transferee is recorded in the same second the forward of A (F_A) was published, an answer that names F_A resolves to B. The docstring argues this is safe because B names the same transferee. That held while only the Accept was acted on. Since #4475 the Reject commits too, so a late or duplicate answer to F_A, Accept or Reject, could close B, which the transferee has not yet seen.

The race needs A answered and B offered within about a second of F_A, so it is unlikely outside automation. It is still a heuristic standing in for a link.

## Why it matters

An Offer is closed only through the ledger (CM-21-014, CLP-11-001), and an answer must close the Offer it answers. A forward that names nothing it stands for leaves the CASE_MANAGER guessing.

## Options

1. **Give the forward a link to the Offer it stands for.** For example, the CASE_MANAGER sets the forward's `context` or `inReplyTo` to the recorded Offer's id, and `_forwarded_entry()` reads that link instead of comparing times. This is the fix, but it changes what the forward carries on the wire, so it needs a spec decision (CM-21-005).
2. **Mint the forward's id from the recorded Offer's id.** The mapping becomes a lookup, but the id scheme is then part of the contract.
3. **Keep the time heuristic.** Document the residual window in CM-21 or the notes and accept it.

Recommendation: option 1, decided together with the withdrawal work in #4491, which also has to name a specific Offer.

Found while reviewing PR #4559 (code from #4070).

Where: vultron/core/participants/ownership_offer.py

**Resolved**: 2026-10-14 — implementation tracked in #4631.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4633>.
Spec: `specs/case-management.yaml` (CM-21-018).
Notes: `notes/ownership-transfer.md`.

Decision: option 1, using `inReplyTo` (`context` already carries the case id). A forward with no link is refused as a protocol error, with no time fallback (prototype stores are fresh every run). The "decide with #4491" coupling is moot: withdrawal has landed, and the owner names the recorded Offer directly.
