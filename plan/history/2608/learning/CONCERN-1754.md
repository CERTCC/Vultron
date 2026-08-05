---
source: CONCERN-1754
timestamp: '2026-08-05T21:00:53.282093+00:00'
title: Ledger idempotency guards must be silent — no rejected entries on duplicate
  detection
type: learning
---

## Context

Concern #1754: when `CheckInviteeNotAlreadyParticipantNode` fires (actor already a participant),
a downstream `disposition="rejected"` ledger entry was written, appearing in demo reports as
"Invited an actor to the case [rejected]" with no actor name and no state transition.

## Root Cause

Two distinct uses of `disposition="rejected"` were conflated:

1. **Emit-side correlation markers** (valid, documented bt-pitfalls ISSUE-1325): written by
   the emitter to detect duplicate outbound activities. These entries are local-only, bypass
   `_validate_canonical_entry`, and anchor dedup.

2. **Idempotency guard no-ops** (invalid per ADR-0019): when a guard detects "already processed,"
   it should return `Status.FAILURE` with only `logger.info`/`logger.debug` — no ledger write
   of any kind.

ADR-0019 states the ledger should "either record the event or stay silent." Guard no-ops are
process-log content, not protocol events.

## Resolution

- Added CLP-13 spec group (`specs/case-ledger-processing.yaml`): CLP-13-001 (idempotency guards
  MUST_NOT write ledger entries) and CLP-13-002 (behaviour must be in a reusable
  `SilentIdempotencyGuardMixin`).
- Added bt-pitfalls section "Idempotency Guards Must Be Silent" with three-row distinction table.

## Outcome

- Docs PR: <https://github.com/CERTCC/Vultron/pull/2009>
- Implementation issue: #2010 (child of epic #1753 "FVCV-Handoff demo credibility", Schedule=Focus)
