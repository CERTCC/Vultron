---
source: CONCERN-4814
timestamp: '2026-10-16T21:03:38.550144+00:00'
title: An ownership-transfer forward that fails after the commit is never sent
type: learning
---

## Summary

The CASE_MANAGER's forward of an ownership-transfer Offer can be lost after the Offer is committed. In `create_offer_ownership_transfer_tree` the guarded commit records the Offer before `ForwardOfferToTransfereeNode` runs (CLP-10-006). That node catches any exception from building or queuing the forward and returns `FAILURE`, so the handler reports `REFUSED` with the entry already in the ledger. A redelivery of the same Offer is then stopped by `NoOpenOwnershipOfferNode` as `is_redelivery` and reported `SKIPPED` before the forward runs, so the transferee never receives the Offer and the case holds an open Offer nobody can answer.

Issue #4702 fixed the same shape for the role-delegation Offer (PR #4813): the guard admits a redelivery of a recorded Offer, the commit reuses the recorded entry (`_find_equivalent_recorded_entry`), the forward is rebuilt under a derived id so the outbox does not queue it twice, and a fault in the forward escapes as an internal error instead of reading as a refusal. `test_a_forward_that_fails_after_the_commit_is_sent_on_redelivery` in `test/core/use_cases/received/actor/test_role_offer_routing.py` pins it

Where: vultron/core/behaviors/case/nodes/ownership_transfer.py (`ForwardOfferToTransfereeNode`), vultron/core/behaviors/case/nodes/ownership_offer_guard.py (`NoOpenOwnershipOfferNode`)

Governing specs: CM-21-005, CM-21-014, CLP-10-006, HP-01-003, OX-06-002, ARCH-15-001

**Resolved**: 2026-10-16 — implementation tracked in #4859.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4860>.
Spec: `specs/case-management.yaml` (CM-24-007).
