---
source: NOTES-demo-ci-scenario-coverage--ac-2-corrections-applied
timestamp: '2026-09-17T17:21:03.742172+00:00'
title: AC-2 Corrections Applied
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) historical changelog of ISSUE-1996 fixes; state carried by Coverage Matrix
**Superseded by:** notes/demo-ci-scenario-coverage.md § Coverage Matrix

---

## AC-2 Corrections Applied

| File | Added event type |
|---|---|
| `test/ci/invariants/test_fvv_invariants.py` | `accept_invite_actor_to_case` |
| `test/ci/invariants/test_fcv_invariants.py` | `accept_invite_actor_to_case` |
| `test/ci/invariants/test_fvcv_extension_invariants.py` | `accept_invite_actor_to_case` |
| `test/ci/invariants/test_fcvcv_invariants.py` | `accept_actor_recommendation` |
| `test/ci/invariants/test_fvcv_extension_invariants.py` | `accept_actor_recommendation` |
| `test/ci/invariants/test_fccv_extension_invariants.py` | `accept_actor_recommendation` |

Corresponding DEMOMA-16 spec entries updated: 16-003, 16-004, 16-007.
New spec entry DEMOMA-16-010 added for `fccv-extension`.
