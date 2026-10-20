---
source: CONCERN-4910
timestamp: '2026-10-20T14:55:42.740842+00:00'
title: The received-activity archive is the event snapshot, not the activity as received
type: learning
---

## Problem

CLP-10-017 says intake archives the received activity "exactly as received", as a `ReceivedActivityRecord`. What intake archives is actually the event's activity *snapshot*, `_build_activity_snapshot` in `vultron/wire/as2/extractor/_builders.py`. That snapshot is a summary: it carries `to` but not `cc`, `endTime` only for an ownership-transfer Offer, and only the fields the builder copies. Until #4869 it also dropped an `Offer(VulnerabilityReport)`'s `proposedEmbargo`.

Since #4869, replies are built from that archive: the embargo `Accept`/`Reject` of an Invite, ownership answers, report validate/close/ack, and the case proposal's inline Offer (CP-01-008). So the reply embeds the snapshot, not the activity the sender sent. DL-06-004 asks for verbatim reconstitution of the original envelope in a reply's `object`. For an embargo Invite, for example, the embedded copy has no `endTime` (its RSVP deadline).

Issue #4871 removes the last full copy (the ingress row under the sender's id). After that the snapshot is the only copy the receiver holds.

## Why it matters

A field the snapshot builder does not copy is lost to every later reader, silently. #4869 found one such loss (the Reporter's proposed terms) only because a CP-01-008 test asserted them. There is no test that the archive preserves what arrived.

## Suggested approach

Decide whether `ReceivedActivityRecord` should hold the sealed received body, the verbatim JSON (ADR-0107's received evidence, #3742), beside or instead of the snapshot, and read replies from it. Otherwise, narrow CLP-10-017's "exactly as received" to the snapshot and name the fields it keeps. Either way, add a test that pins what the archive keeps.

Governing specs: CLP-10-017, DL-06-004, DL-06-006, VM-08-002

Where: vultron/wire/as2/extractor/_builders.py, vultron/core/behaviors/case/nodes/intake.py, specs/case-ledger-processing.yaml (CLP-10-017)

**Resolved**: 2026-10-20 — implementation tracked in #4943.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4942>.

ADR: `docs/adr/0148-the-received-archive-is-the-bytes-that-arrived-read-through-a-read-only-view.md`.

Notes: `notes/datalayer-design.md`.
