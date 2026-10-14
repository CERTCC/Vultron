---
source: NOTES-participant-role-management--decision-table
timestamp: '2026-10-12T19:36:45.622207+00:00'
title: Decision Table
type: note
---

**Archived:** 2026-10-12
**Reason:** decision summary; the live rules (use roles/add_role, ratchet tests) are restated in the note body
**Superseded by:** specs/participant-role-management.yaml PRM-01; test/architecture/test_participant_case_roles.py

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Where do new tests go? | New `test/core/models/test_participant.py` | Mirrors source layout; keeps `test_base.py` focused on the base model contract |
| Should core code read `case_roles` directly? | No — use `roles` property | Decouples callers from storage field; allows future representation changes |
| What does the `roles` property return? | `list[CVDRole]` | Keeps callers working with domain types; `.value` extraction stays at call sites |
| Should the wire participant match the core participant interface? | Yes — they are one class (`as_CaseParticipant` is `CaseParticipant`, ADR-0099) | Callers should not need to know which layer they hold to manage roles |
| Should wire-layer `model_validator` role inits use `add_role()`? | Yes | Routes all role mutations through the single invariant-check point |
| Should an architecture test enforce the no-direct-mutation rule? | Yes, with ≤1 s budget | Machine-checkable enforcement; targeted scan stays fast |
| Should an architecture test enforce the no-direct-read rule (`getattr(*, "case_roles")`)? | Yes — `test_no_getattr_case_roles_read_in_core()` added in PR #1443 | Complements the mutation ratchet; enforces PRM-01-003 |

---
