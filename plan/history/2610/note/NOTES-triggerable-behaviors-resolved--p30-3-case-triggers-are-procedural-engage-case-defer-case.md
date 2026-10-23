---
source: NOTES-triggerable-behaviors-resolved--p30-3-case-triggers-are-procedural-engage-case-defer-case
timestamp: '2026-10-02T16:28:29.103939+00:00'
title: 'P30-3: Case Triggers are Procedural (engage-case, defer-case)'
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered/confusion-resolved — engage-case and defer-case are BT-backed (engage_defer_trigger_tree);_update_participant_rm_state no longer exists
**Superseded by:** vultron/core/use_cases/triggers/case/engage.py

---

## P30-3: Case Triggers are Procedural (engage-case, defer-case)

`engage-case` and `defer-case` are also implemented procedurally. Key pattern
differences from report triggers:

- **`_resolve_case()` helper**: Reads the case from the DataLayer and returns
  HTTP 404 if absent or HTTP 422 if the resolved object is not a
  `VulnerabilityCase`. Shared across case-scoped trigger endpoints.
- **`_update_participant_rm_state()` helper**: Locates the actor's own
  `CaseParticipant` record in the DataLayer (participants are stored as ID
  strings in `case.case_participants`, so each must be fetched individually)
  and updates `participant_statuses`. If no participant record exists for the
  actor, a WARNING is logged and the endpoint still returns 202 (non-blocking).
- **State update target**: The participant document is updated directly, not
  the case document, consistent with existing BT node patterns.
- **Relationship to receive-side BTs**: `EngageCaseBT`/`DeferCaseBT` handle
  the *inbound* case — recording another actor's already-made decision.
  The trigger endpoints handle the *outbound* case — the local actor deciding
  to engage or defer. The `EvaluateCasePriority` BT node is
  **outgoing-only** and does NOT appear in the receive-side trees.
