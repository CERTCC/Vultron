---
source: CONCERN-4911
timestamp: '2026-10-20T14:46:27.302534+00:00'
title: The ledger-replayed ownership-transfer Offer record is stored under the sender's
  Offer id
type: learning
---

## Problem

`VultronOwnershipTransferOfferRecord` (`vultron/core/models/ownership_transfer_offer_record.py`) sets its `id_` to the Offer's `offer_id`, an id the offering sender chose. `ApplyOfferOwnershipTransferFromLedgerNode` (`vultron/core/behaviors/sync/nodes/ownership_offer_effect.py`) writes it on a replica that learns of the Offer from the ledger. It first treats any existing row under that id as "already present", an idempotent no-op.

This is the shape CLP-10-017 rules out for the received archive: a record the receiver writes, addressed by an id someone else chose. A row already under that id, whatever its type, makes the node skip its write. The accept, reject and withdraw triggers (`read_held_activity`) then read that row as the Offer.

## Why it matters

DL-06-006 keeps received *activities* off sender-chosen ids, but this core record still uses one. After #4869, the archive and the actor's own sent activities are the only other things readable by an activity id. So this record is the one reader-visible row whose key a sender picks.

## Suggested approach

Key the record by a receiver-derived id (`build_id(offer_id)`, as `VultronOfferRecord` and `ReceivedActivityRecord` do). Read it there in `read_held_activity`'s callers or in the ownership trigger and adapter, and drop the "already present under the Offer id" check. That changes a persisted record's id, so it needs explicit approval per AGENTS.md.

Governing specs: DL-06-002, DL-06-006, CLP-10-017, SYNC-12-001

Where: vultron/core/models/ownership_transfer_offer_record.py, vultron/core/behaviors/sync/nodes/ownership_offer_effect.py

**Resolved**: 2026-10-20 — implementation tracked in #4939, #4940.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4938>.

Planning found the root cause upstream of the key: one ownership transfer had two
Offers (the owner's, ledgered, and the CASE_MANAGER's forward, answered), so replicas
kept a record of the owner's Offer for the answer triggers. ADR-0148 (proposed) has the
owner propose `Offer(Offer(VulnerabilityCase))` and the CASE_MANAGER make the one Offer
under its own id, so the record is deleted rather than re-keyed. Follow-up idea, not
decided: #4936 (the same shape for the case proposal).
