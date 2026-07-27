---
source: CONCERN-1703
timestamp: '2026-07-27T18:11:06.011921+00:00'
title: 'Demo Integration: intermittent VFD broadcast timing race condition across
  all scenario demos'
type: learning
---

The `fccv-handoff` demo CI job failed intermittently with:

```text
M6 reporter: vfd_state is not VFD, found vfd (vendor_unaware)
```

**Root cause 1 — timing race (all 6 demos):** `verify_fix_ready`,
`verify_fix_deployed`, and `verify_publicly_disclosed` all call
`_check_participant_vfd_state_in` / `_assert_participant_vfd_pxa` as
single-shot, non-retrying assertions on the receiver container. The
preceding `wait_for_participant_vfd_state` only polls the
finder/reporter (secondary) container. The receiver container may not
have received the VFD broadcast yet when the assertion fires.

**Root cause 2 — wrong actor in fccv_handoff_demo.py (line 821):**
`verify_publicly_disclosed(receiver_actor_id=c1.id_)` passes C1 (a
Coordinator), but `_assert_participant_vfd_pxa` checks
`vfd_state == VFD`. A Coordinator's VFD never transitions past `vfd`.
Should be `vendor.id_`.

The broadcast participant list divergence (1 vs 2 recipients) noted in
the issue body is a secondary symptom of root cause 1 — the CaseActor
broadcasts the VFD ledger entry before the finder's CaseParticipant
registration is complete, so the finder replica arrives late.

**Resolved**: 2026-07-27 — implementation tracked in #1717.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1718>.
Spec: `specs/multi-actor-demo.yaml` DEMOMA-06-006.
