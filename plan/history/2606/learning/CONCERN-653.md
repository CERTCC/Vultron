---
source: CONCERN-653
timestamp: '2026-06-10T16:38:20.734013+00:00'
title: High-churn outbox delivery module requires test-coverage gating
type: learning
---

## Original Concern

`vultron/adapters/driving/fastapi/outbox_handler.py` has accumulated 31 commits
in the last 90 days, reflecting the ongoing evolution of the actor delivery
model. Changes here affect how activities are dispatched from the outbox to
recipient inboxes.

**Severity**: Low (category: Fragile / high-churn area)

**Impact if ignored**: Delivery path regressions may go undetected if outbox
handler changes are not covered by end-to-end integration tests, causing silent
message drops or incorrect recipient targeting.

## Root Cause Analysis

The churn is driven by:

1. **Protocol feature additions** — outbox spec implementations (OX-08, OX-09),
   inline object enforcement, delivery bridges
2. **DataLayer architectural changes** — per-actor isolation (ADR-0012),
   hydration/dehydration refactors
3. **Bug fixes** — participant storage, activity serialization, recipient
   routing
4. **Refactoring** — code quality, naming conventions (NAMING-1, CC.2 reductions)

The module is **critical for CVD message delivery** — silent failures cause
participants to miss vulnerability updates.

## Resolution

**Resolved**: 2026-06-10 — implementation tracked in #873, #874
**Docs PR**: <https://github.com/CERTCC/Vultron/pull/872>
**Spec**: specs/outbox.yaml
**Notes**: notes/outbox.md (extended with test-coverage requirements)

### Approach: Test-Driven Delivery Validation

Decision: **Focus on quick-running unit tests** (not slow integration tests) for
local development velocity. CI handles integration scenarios via demo
verification.

### Commitment: Test-Coverage Gates for High-Churn Modules

Extended `notes/outbox.md` with **required test coverage** for all future
delivery-path changes:

1. **Recipient extraction and deduplication** — extract from `to` field,
   deduplicate, handle missing fields
2. **Object dehydration** — collapse references to URIs, preserve inline
   objects (OX-09-001), preserve selective-disclosure stubs (MV-10-001)
3. **Activity validation** — enforce `to:` field (OX-08-001), warn on
   `cc`/`bto`/`bcc` (OX-08-004)

### Implementation Issues Created

- **#873 (size:M)**: Add unit tests for outbox delivery-path scenarios
  - 3 focused test clusters: recipient/dehydration/validation
  - Blocked by: #653
  - Parent: #612 (Architecture Hardening epic)

- **#874 (size:L)**: Refactor outbox_handler.py to reduce complexity
  - Extract helpers within same file (no submodule fragmentation)
  - Reduce CC below 10 for main functions
  - Preserve all functionality; refactoring only
  - Blocked by: #653
  - Parent: #612 (Architecture Hardening epic)

### Philosophy

**High-churn modules need explicit test gates.** When a module experiences
significant change frequency (10+ commits/30 days), every change MUST be gated
on passing targeted unit tests for the affected code paths. This prevents
silent regressions in protocol-critical paths.
