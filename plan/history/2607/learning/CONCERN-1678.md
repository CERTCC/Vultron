---
source: CONCERN-1678
timestamp: '2026-07-27T20:16:08.399842+00:00'
title: d→D (fix-deployed) transition not gated on CaseRole.DEPLOYER
type: learning
---

## Problem

The `demo_notify_fix_deployed` endpoint and the `add_participant_status_trigger_bt`
behavior tree applied the d→D VFD state transition without checking the caller's
CVD role. Any participant — including Finders and Coordinators — could set their
own participant status to `CS_vfd.VFD`, violating the protocol invariant that only
DEPLOYER-role actors deploy fixes.

Additionally, `demo_notify_fix_ready` lacked a VENDOR/DEPLOYER guard for the f→F
transition, and `demo_notify_published` was incorrectly setting `vfd_state=VFD`
(conflating the P event with the D event — they are independent).

## Root Cause

Role preconditions for VFD state transitions were not specified in any behavioral
spec (`specs/cs-behavior.yaml`), so there was no authoritative requirement for
BT implementation to enforce. The demo verification layer had a `_assert_vendor_role`
check, but this is post-hoc assertion, not a BT-level guard.

## Resolution

- Added CSB-15 group to `specs/cs-behavior.yaml` (v0.1.0 → v0.1.1):
  - CSB-15-001: VENDOR or DEPLOYER required for f→F (notify-fix-ready)
  - CSB-15-002: DEPLOYER required for d→D (notify-fix-deployed)
  - CSB-15-003: `notify-published` MUST_NOT set `vfd_state=VFD`

## Implementation Issues

- #1735: Add CSB-15 spec entries (size:S, blocked-by #1678, child of #1676)
- #1736: Enforce CSB-15 role guards in BT trigger tree (size:M, blocked-by #1678, child of #1676)

## Key Insight

P (public aware) and D (fix deployed) are semantically independent events. P is
participant-agnostic (whole-case state); D is participant-specific (vendor-fix path).
`notify-published` advancing vfd_state to VFD masked the missing DEPLOYER guard and
caused non-deployer participants to incorrectly reach VFD state.

## PR

<https://github.com/CERTCC/Vultron/pull/1742>
