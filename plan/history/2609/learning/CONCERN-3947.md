---
source: CONCERN-3947
timestamp: '2026-09-30T19:17:51.034417+00:00'
title: Received ledger snapshot renders the extractor's rebuilt VultronActivity, not
  the AS2 that arrived
type: learning
---

## Problem

A received activity's ledger `payloadSnapshot` is not the AS2 activity that arrived.
The extractor (`_build_activity_snapshot` in `vultron/wire/as2/extractor/_builders.py`) rebuilds the inbound activity as a core-branch `VultronActivity` that keeps a chosen subset of fields.
`build_activity_payload_snapshot` then renders that rebuilt object through `WireRenderPort`.
Any field the extractor does not carry is absent from the canonical entry, so the snapshot is a normalization of what the extractor kept, not the bytes the participant sent.

## Why it matters

CLP-07-011 allows the snapshot to be "the verbatim AS2 activity that was asserted, or a deterministic canonical normalization of it", and #3930's AC-3 asked that a snapshot be "carried as received, not re-rendered".
Today only the normalization branch is reachable, and nothing specifies which fields that normalization must preserve.
A receiver replaying the ledger cannot tell a dropped field from one the sender never set.

Found while doing #3930 (routing the core by_alias sites through WireRenderPort).
That PR changed nothing here: the port's rendering is identical to the inline `by_alias` dump it replaced.

## Options

1. Carry the received AS2 dict to core at the parse edge (for example on the event) and snapshot that, which makes CLP-07-011's verbatim branch real.
2. Keep the rendering and specify which fields the extractor's `VultronActivity` must preserve for a snapshot to count as a deterministic normalization.
3. Accept the status quo and say explicitly in CLP-07-011 that the snapshot is the extractor's normalization.

Governing specs: CLP-07-011, CLP-07-009, ARCH-20-001

**Resolved**: 2026-09-30 — already decided by ADR-0107 (postmark on the received envelope); implementation tracked in #3742 (Epic #3738 step 5), amended with AC-6 (carry the sealed evidence onto the dispatched event), AC-7 (retire the normalization branch of CLP-07-011 and CLP-02-003) and AC-8 (notes and ADR staging updated). No interim spec or code change. Docs PR: <https://github.com/CERTCC/Vultron/pull/3967>.
