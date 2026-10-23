---
source: CONCERN-632
timestamp: '2026-06-03T19:55:11.844215+00:00'
title: 'BT idiom audit: pervasive anti-patterns across use cases and BT nodes'
type: learning
---

## Summary

`vultron/core/use_cases/` and `vultron/core/behaviors/` contain pervasive BT
anti-patterns across 10 findings (severity: high) that undermine auditability,
composability, and spec compliance.

## Original Concern Body

### Finding 1 — Embargo received-side: NO BTs at all (HIGHEST severity)

`vultron/core/use_cases/received/embargo.py` has 4 of 6 use cases doing
protocol-significant work with zero BT involvement:
`AddEmbargoEventToCaseReceivedUseCase`, `InviteToEmbargoOnCaseReceivedUseCase`,
`AcceptInviteToEmbargoOnCaseReceivedUseCase`,
`RejectInviteToEmbargoOnCaseReceivedUseCase` — all procedural. Compare:
`RemoveEmbargoEventFromCaseReceivedUseCase` in the same file correctly uses a BT.

### Finding 2 — Post-BT log cascade anti-pattern (HIGH severity)

`_commit_embargo_log_cascade()` called after BT execution in 5 use cases instead
of as a BT child subtree — violates BT-06-006.

### Finding 3 — EM state machine manipulation in trigger use cases (HIGH severity)

`triggers/embargo.py` directly drives `EMAdapter`/`create_em_machine()` inside
`execute()` for `SvcProposeEmbargoUseCase`, `SvcAcceptEmbargoUseCase`,
`SvcRejectEmbargoUseCase`, `SvcTerminateEmbargoUseCase`. PEC cascades also called
procedurally. Cross-reference: extends #622 scope.

### Finding 4 — Domain work done in execute() before BT runs (MEDIUM-HIGH severity)

`SvcEngageCaseUseCase`/`SvcDeferCaseUseCase` (`triggers/case.py`): RM transition
before BT. `SvcAddNoteToCaseUseCase` (`triggers/note.py`): note creation + save
before BT. `SvcAddParticipantStatusUseCase`: entire execute() procedural — no BT.

### Finding 5 — BT node calling a use case (layer boundary violation, MEDIUM)

`PublicDisclosureBranchNode` in `vultron/core/behaviors/status/nodes.py` directly
instantiates and calls `SvcTerminateEmbargoUseCase` from within `update()`.

### Finding 6 — BT node importing from use case module (layer inversion, MEDIUM)

`ApplyEmbargoTeardownNode` in `vultron/core/behaviors/embargo/nodes.py` imports
`_reset_case_participant_embargo_consent` from `vultron.core.use_cases.received.embargo`.

### Finding 7 — "God nodes" doing too much (MEDIUM severity)

`CreateCaseActorNode.update()` (~100 lines), `InitializeDefaultEmbargoNode.update()`
(~60 lines), `CreateCaseOwnerParticipant.update()`, `BroadcastStatusToPeersNode.update()`
— all in `vultron/core/behaviors/case/nodes.py`.

### Finding 8 — Non-BT use cases with BT-appropriate structure (MEDIUM)

`AddCaseStatusToCaseReceivedUseCase`, four report received use cases
(`CreateReport`, `AckReport`, `CloseReport`, `InvalidateReport`),
`UpdateCaseReceivedUseCase` — all fully procedural PPA candidates.

### Finding 9 — memory=False: generally correct but needs audit (LOW)

Inline composites in `case/nodes.py` should be verified.

### Finding 10 — ValidateCaseObject node is redundant (LOW)

Checks invariants that should be enforced at Pydantic construction time per
ARCH-10-001.

## Resolution

**Resolved**: 2026-06-03 — implementation tracked in #710 (embargo received-side
BT adoption), #711 (trigger-side EM BT integration), #712 (pre-BT domain work
refactoring), #713 (layer boundary fixes), #714 (god node decomposition), #715
(remaining procedural use cases), #716 (BT cleanup).

Three new AGENTS.md pitfalls documented (BT-IDM-01 through BT-IDM-03): BT node
calling a use case, BT node importing from use case module, god BT nodes.

Issue #622 (trigger-side inline state machine, Finding 3) wired as blocked-by
\#711 (superseded in scope).

Docs PR: <https://github.com/CERTCC/Vultron/pull/709>.
