---
source: CONCERN-2962
timestamp: '2026-09-28T14:35:09.477673+00:00'
title: outbox per-pass cap re-queue ordering
type: learning
---

## Summary

The `outbox_handler` drain loop in
`vultron/adapters/driving/fastapi/outbox_handler.py` re-queues a failed
activity before checking its per-pass cap (lines 330–335). Because the drain
loop is `while outbox_list()`, the re-queued activity lands at the tail of the
*current* pass — not the next one — and can be popped and attempted again in
the same pass. This violates OX-13-011's "skip for the current pass, defer to
the next drain" guarantee and consumes the dead-letter budget faster than the
documented `(DEFAULT_MAX_RETRIES + 1) × ~3 drain passes` formula assumes.

## Root Cause

The ordering bug only manifests when failures are out of step: a second bad
activity joins mid-pass after the first has already accumulated some errors.
A single bad activity (or several that fail in lockstep) each hit the cap in
turn and the pass ends cleanly — so the single-bad-activity test shape
proposed in the issue cannot reproduce the bug.

## Decision

Variant C: keep re-queuing right away (activity always stays in the persistent
queue), and record capped activities in an in-memory `capped_this_pass` set.
When the loop pops an ID in that set, re-queue without delivery, without
incrementing the attempt counter, and without backoff, then continue. The pass
ends when every queued item is in the set.

Deferring re-queue to end-of-loop (Option A from the issue) was rejected: a
crash mid-pass would discard the in-memory set and lose those activities.

ADR-0066 "Per-activity abort scope" section corrected to reflect this
implementation; a pitfall note added to `notes/outbox-delivery-reliability.md`.

**Resolved**: 2026-09-28 — implementation tracked in #3770.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3769>.
Notes: `notes/outbox-delivery-reliability.md`.
