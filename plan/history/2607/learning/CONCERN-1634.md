---
signal: spec-gap
source: CONCERN-1634
timestamp: '2026-07-23T16:50:42.557099+00:00'
title: No spec or code contract requires receiver_actor_id in fix-lifecycle milestone
  checks to be a VENDOR-role actor
type: learning
---

`verify_fix_ready` and `verify_fix_deployed` in `vultron/demo/helpers/milestones.py`
accepted a `receiver_actor_id` with no enforcement that the actor holds `CVDRole.VENDOR`.
An actor without a VENDOR role has no VFD lifecycle state, so passing a non-Vendor actor
ID caused the check to silently read the wrong participant's state rather than failing loudly.

Root cause of M4/M5 CI failures in PR #1623 (issue #1593): `fcv_demo.py` passed
`coordinator.id_` instead of `vendor.id_`. DEMOMA-12-005 stated "Only Vendor's fix path
(VFD) is tracked" as a postcondition but imposed no precondition on callers.

**Resolved**: 2026-07-23 — implementation tracked in #1643.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1642>.
Spec: `specs/multi-actor-demo.yaml` DEMOMA-14-001.
