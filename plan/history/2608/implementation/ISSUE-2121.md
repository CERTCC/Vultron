---
source: ISSUE-2121
timestamp: '2026-08-10T19:58:55.093883+00:00'
title: 'fix(invariants): skip VFd check for fcv-reject Invariant 15'
type: implementation
---

Issue #2121: `test_invariant_15_cs_state_transitions_observed` in
`test/ci/invariants/test_fcv_reject_invariants.py` was failing because the
shared `check_cs_state_transitions_observed` helper unconditionally checked
for `vfd_state == 'VFd'` (fix ready). In the fcv-reject scenario, Vendor
rejects the case invitation and is never added as a participant, so no actor
advances the VFD state machine — `VFd` is structurally unreachable.

Root cause: copy-paste of `test_invariant_15` from vendor-inclusive scenarios
(same class as DEMOCI-06-001). The invariant was added when demo CI was dark
(#2118 startup failure), so it never had a green CI run to catch the error.

Fix: added keyword-only `check_fix_ready: bool = True` to
`check_cs_state_transitions_observed` in `common.py`; fcv-reject's Invariant
15 now passes `check_fix_ready=False`. All 8 other scenario harnesses
verified — each calls `actor_notifies_fix_ready` in its demo, so VFd is
reachable there. Two regression tests added to `test_common.py`.

PR: <https://github.com/CERTCC/Vultron/pull/2152>
