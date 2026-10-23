---
source: NOTES-federation-ideas--case-journal-vs-delivery-log
timestamp: '2026-09-17T17:25:20.615853+00:00'
title: Case Journal vs Delivery Log
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) delivered as hash-chained ledger
**Superseded by:** specs/case-ledger-processing.yaml; notes/case-ledger-authority.md

---

## 8. Case Journal vs. Delivery Log

The CaseActor maintains two distinct collections, exposed as AS2 named streams:

**Case Journal** (`/outbox`)

- Append-only, sequenced, hash-chained log of meaningful case events.
- Contains: `Create`, `Update`, `Offer`, `Accept`, `Add`, `Remove`, `Resolve`,
  etc.
- Sequence numbers only increment on Journal entries — Relay activities do not
  consume sequence positions.
- This is the sync target for participant mirrors and the authoritative audit
  record.
- Hash chain: each Journal entry carries a `prev` field referencing the hash of
  the prior entry, making the log tamper-evident.

**Delivery Log** (`/streams/delivery`)

- Contains *Relay* (`Announce`) activities — the record of what was sent to
  whom and when.
- Useful for debugging, retry tracking, and delivery receipt verification.
- **Not** part of the sync protocol; not included in on-demand reconciliation.
- Can be pruned or archived without affecting case integrity.
- Delivery Log will have a lot of noise compared to the Case Journal,
  because the delivery log includes every relay to every participant, for
  example, one
  `Create(Note)` to 20 participants will be 1 `Create(Note)` Journal entry
  but 1 `Create(Note)` followed by 20 `Announce(Create(Note))` Delivery Log
  entries.
