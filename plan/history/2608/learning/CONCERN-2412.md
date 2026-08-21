---
source: CONCERN-2412
timestamp: '2026-08-21T18:27:38.870536+00:00'
title: Transition guards live in callers, not at the persistence/model boundary
type: learning
---

Audit of all five state-machine write boundaries (RM, VFD, PXA, PEC, EM) found:

- **RM**: Validated at model layer via `CaseParticipant.append_rm_state()`; minor bypass in `_upgrade_participant_to_accepted()`.
- **VFD**: `CreateParticipantStatusNode` never calls `is_valid_vfd_transition()`. CSB-16-001 spec exists but is unimplemented. Guards live in upstream BT nodes (ValidateTriggerTransitionsNode, CheckVendorRoleNode, CheckDeployerRoleNode).
- **PXA/CS**: `is_valid_cs_transition()` and `is_ephemeral_cs_state()` from `cs_invariants.py` are dead code in production write paths. SM-09-001 and CSB-16-002 specs exist but are unimplemented. Per-dimension validators do not catch compound-state ephemeral invariants.
- **PEC**: Fixed. `apply_pec_transition()` is fail-closed via `PecDimension.transition()`. The fail-open `apply_pec_trigger()` is latent dead code (not wired into any production path).
- **EM**: Three BT nodes (`EmActivateEmbargo`, `ClearEmbargo`, `SetDefaultActiveEmbargoNode`) bypass `EmbargoLifecycle` with direct `case.current_status.em = EmDimension(...)` + `dl.save(case)`. Two use warning-only validation; one has no validation at all. No spec existed for this pattern.

**Resolved**: 2026-08-21 — implementation tracked in #2478, #2479, #2480, #2481.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2477>.
Spec: `specs/em-behavior.yaml` (EMB-18-001, EMB-18-002), `specs/state-machine.yaml` (SM-09-001 rationale corrected).
