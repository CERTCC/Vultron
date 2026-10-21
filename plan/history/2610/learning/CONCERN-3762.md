---
source: CONCERN-3762
timestamp: '2026-10-21T13:58:20.175929+00:00'
title: Reused activity id with a different body is refused
type: learning
---

## Concern

When the inbox receives an activity whose `id` is already stored, it keeps the stored record and routes that one, even if the new body is different. `_store_inbox_activity` (`vultron/adapters/driving/fastapi/inbox_storage.py`) catches `VultronAlreadyExistsError` and logs at DEBUG. `FastAPIIngressAdapter.rehydrate` then rebuilds the routing copy from the stored record by that `id`.

So a second body that reuses an `id` is never compared with the first. Its content is dropped and the earlier delivery is dispatched again.

## Why it matters

- A retry with the same content is harmless. A resend with different content under a reused `id` is either a sender bug or an attempt to rewrite history, and today neither surfaces. The only trace is a DEBUG line.
- Once the ledger records the received evidence verbatim (#3742, ADR-0106 step 5), the question "which body is the evidence for this `id`?" has to have one answer. PR #3761 stops the second body's evidence from being attached to the first body's routing copy, and logs it at INFO, but it does not decide the policy.

## Reproduction

1. Deliver `Offer` id X with `summary="first"`.
2. Deliver `Offer` id X with `summary="second"`.
3. The routed activity has `summary == "first"`.

This is pinned in `test/adapters/driving/fastapi/test_ingress_received_evidence.py::test_resend_under_a_held_id_routes_without_this_body_evidence`.

## Possible direction

Compare the new evidence with what the store holds for that `id`. If they are equal, treat it as an idempotent retry. If they differ, refuse or quarantine it, with a WARNING. This needs the evidence to be persisted, which is #3742.

Governing specs: VM-08-002, SYNC-03-003

**Resolved**: 2026-10-21 — implementation tracked in #5019 (blocked by #5012 and #4981).
Maintainer decisions: same id + different sealed body is refused at the inbox with a
WARNING naming activity id and sender (no quarantine, nothing routed or written);
exact SHA-256 match on the sealed text; normalisation is a recorded known limitation.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5018>.
Spec: `specs/inbox-endpoint.yaml` (IE-10-002 new; IE-10-001), `specs/vocabulary-model.yaml` (VM-08-002).
Notes: `notes/inbox-orchestration.md`.
