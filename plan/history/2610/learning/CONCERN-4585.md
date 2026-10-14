---
source: CONCERN-4585
timestamp: '2026-10-14T20:02:24.403103+00:00'
title: CLP-10-005 forbids the pre-step expiry tree that CLP-07-013 and CM-21-017 need
type: learning
---

## Problem

Two received-side rules pull against each other when the CASE_MANAGER must
record a decision it takes from its own clock before it judges an activity.

- CLP-10-005: a received `execute()` calls `BTBridge.execute_with_setup()`
  exactly once, with "no second `execute_with_setup()` call".
- CLP-10-010 / CLP-10-006: inside a received tree nothing is committed before
  the guards.
- CLP-07-013 and CM-21-017 / CM-28-009: a clock decision (an expiry) is
  committed as its own entry *before* the activity that prompted it is acted
  on — including when that activity is then refused.

Both expiries in the code today resolve this the same way: a standalone
CASE_MANAGER-gated expiry tree, run from a helper before the received tree
(`AcceptInviteToEmbargoOnCaseReceivedUseCase._run_expiry_tree` and, since the
issue #4491 Part B PR, `_expire_overdue_offer` in
`vultron/core/use_cases/received/actor/ownership.py`). The architecture test
for CLP-10-005 only counts calls written directly in `execute()`, so the helper
passes it, but the requirement's text does not allow the second run. The
ratchets already list these expiry trees as sanctioned
(`KNOWN_FACTORIES_BYPASSING_INTAKE`, `GATE_CALLERS_OUTSIDE_RECEIVED_TREES`), so
the code, the ratchets and the spec text disagree.

## Why it matters

A reviewer reading CLP-10-005 sees a violation each time; a third clock-driven
step would copy the loophole without a recorded rule for when it is allowed.

## Options

1. Amend CLP-10-005 with a named carve-out: a CASE_MANAGER-gated clock-decision
   tree that commits only its own entry may run before the received tree.
   Smallest change; matches what the code does.
2. Add a stage to `create_receive_activity_tree` for CASE_MANAGER clock
   decisions, and amend CLP-10-010 to allow one commit of that kind before the
   guards. One tree per delivery, but changes the four-stage model (ADR-0111).

Recommendation: option 1, since both existing uses fit it and it changes no
code.

Where: specs/case-ledger-processing.yaml (CLP-10-005, CLP-10-010)

**Resolved**: 2026-10-14 — the concern was wider than the two expiry trees: about 15 received handlers chained trees through helpers. Decision: compose, never chain (ADR-0135); one tree per delivery counted through helpers; a CASE_MANAGER clock-decision stage between the door guards and the precondition guards (CLP-10-023); drained gap-buffer entries handed back to the actor's own inbox (SYNC-14-009). The issue's option 1 (a named carve-out) was rejected because it re-legalizes the Python-chosen cascade ADR-0022 rejected. Implementation tracked in #4641, #4642, #4643, #4644, #4645 under Epic #4638.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4636>.
Spec: `specs/case-ledger-processing.yaml`, `specs/sync-ledger-replication.yaml`.
Notes: `notes/bt-integration.md`.
