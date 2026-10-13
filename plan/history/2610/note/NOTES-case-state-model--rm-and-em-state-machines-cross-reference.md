---
source: NOTES-case-state-model--rm-and-em-state-machines-cross-reference
timestamp: '2026-10-12T19:32:57.746918+00:00'
title: RM and EM State Machines (Cross-Reference)
type: note
---

**Archived:** 2026-10-12
**Reason:** reference cross-reference duplicating docs/
**Superseded by:** docs/topics/process_models/; docs/reference/formal_protocol/

---

## RM and EM State Machines (Cross-Reference)

Case State (CS) is one of three interacting state machines:

- **RM (Report Management)**: Per-participant; tracks `RECEIVED → VALID →
  INVALID → ACCEPTED → DEFERRED → CLOSED` lifecycle. Tracked in
  `CaseParticipant.participant_status[].rm_state`.
- **EM (Embargo Management)**: Shared across case participants; tracks
  `NONE → PROPOSED → ACTIVE → REVISE → EXITED`. Tracked in
  `CaseStatus`. Note: `Accept` is an **activity type** that triggers the
  `PROPOSED → ACTIVE` (or `REVISE → ACTIVE`) transition, or `→ REVISE` while
  another proposal stays open (EMB-18-005) — it is not itself a state. See `vultron/bt/embargo_management/states.py`.
- **CS (Case State)**: The 6-dimensional VFD/PXA hypercube described above.

See `docs/topics/process_models/rm/`, `docs/topics/process_models/em/`, and
`docs/topics/process_models/cs/` for process model documentation. See
`docs/reference/formal_protocol/` for formal state machine definitions with
transition rules.
