---
source: CONCERN-2559
timestamp: '2026-08-25T16:58:49.936392+00:00'
title: '9 BT DRY violations in vultron/core/behaviors/: copied logic creates multi-site
  bug surface and AC-1 violations'
type: learning
---

Identified 9 DRY violations across `vultron/core/behaviors/` grouped into 3
implementation clusters. Each cluster shares overlapping file context and is
tracked as a separate impl issue, all blocked-by CONCERN-2559 and sub-issues
of epic #2558.

## Group 1 — Embargo AC-1 violations (impl: #2583, size:M)

V1 and V7: two sites bypass `ReadEmStateNode`/`WriteEmStateNode` and read/write
`case.current_status.em` inline. AC-1 of issue #1474 mandates all EM state
access go through the canonical nodes.

- `embargo/nodes/teardown.py` — `ApplyEmbargoTeardownNode.update()` reads
  `case.current_status.em.state` directly; fix: delegate to
  `ClearActiveEmbargoNode` + `ResetParticipantConsentNode`, preserving the
  existing blackboard `activity` port.
- `case/nodes/embargo.py` — inline `EmDimension(state=EM.ACTIVE)` write.
- `embargo/nodes/lifecycle.py` — inline `EmDimension(state=EM.ACTIVE)` write.

## Group 2 — Report-phase dedup (impl: #2581, size:L)

V2, V3, V6, B2: four near-identical `update()` blocks in the report-phase nodes.

- Extract `_TransitionRMtoReportPhaseState(target: RM)` base from
  `rm_transitions.py`; `TransitionRMtoInvalid` and `TransitionRMtoClosed`
  become thin subclasses.
- Extract `_EmitParticipantStatusActivityBase` for `EmitCFActivity` /
  `EmitCDActivity` in `develop_fix.py` / `deploy_fix.py`.
- Extract `_CheckParticipantRMStateBase` or factory for `CheckRMStateAccepted`
  / `RMinStateDeferred`.
- Unify `CheckRMStateValid` / `CheckRMStateReceivedOrInvalid` condition logic
  (`conditions.py`).

## Group 3 — Case-domain emit base (impl: #2582, size:L)

V4, V5, B1: `invite_response.py` and `ownership_transfer.py` each contain 2–3
`update()` methods with identical guard+emit+outbox patterns.

- Create `_EmitSingleActivityBase` in `helpers.py`; concrete nodes override
  only `_call_factory()` and `_on_success()`.
- Move "BT Emit Nodes" pitfall from root `AGENTS.md` to
  `vultron/core/behaviors/AGENTS.md` once the base class exists to reference.

## Docs outcome

PR #2580 adds `## EM State Reads and Writes Must Use Canonical Nodes` section
to `vultron/core/behaviors/AGENTS.md` with a concrete `ReadEmStateNode`
delegation code pattern, complementing the existing AC-1 bullet in the
"Compose Before Create: Node Discovery Gate" section.

Docs PR: <https://github.com/CERTCC/Vultron/pull/2580>
