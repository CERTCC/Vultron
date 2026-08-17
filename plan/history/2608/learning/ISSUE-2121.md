---
title: "Invariant 15 VFd check is scenario-specific, not universal"
type: learning
timestamp: 2026-08-10T00:00:00Z
source: ISSUE-2121
signal: design-question
---

`check_cs_state_transitions_observed` in `test/ci/invariants/common.py` was
originally written as a universal check requiring both `vfd_state == 'VFd'`
(fix ready) and a P-transition.  This assumption holds for all scenarios where
a Vendor participates and advances the VFD state machine — but the fcv-reject
scenario intentionally has no participating Vendor (Vendor rejects the
invitation), so VFd is structurally unreachable there.

The fix added a keyword-only `check_fix_ready: bool = True` parameter.
Scenario-specific harnesses that cover a reject flow (no Vendor participant)
MUST pass `check_fix_ready=False`.  All other scenarios use the default.

The broader lesson: invariants in the harness are only invariant *within their
scenario's protocol path*.  When copy-pasting invariant tests across scenarios,
audit each one against the scenario's participant set and phase list — a check
that is universal for vendor-inclusive scenarios may be inapplicable for
rejection or no-vendor flows.  This is the same class of copy-paste defect
documented in DEMOCI-06-001.

**Promoted**: 2026-08-17 — captured in notes/demo-ci-invariants.md (Invariant Scoping: Per-Scenario Participant Set Audit).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>.
