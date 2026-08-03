---
source: CONCERN-1910
timestamp: '2026-08-03T15:16:03.574942+00:00'
title: DEMOMA-07-001 RM closure path — Leave(VulnerabilityCase) is canonical
type: learning
---

## Concern

`DEMOMA-07-001` mandated that RM case closure flow through
`Add(ParticipantStatus, rm_state=RM.CLOSED)`. PR #1909 (issue #1858)
changed RM closure to flow through `Leave(VulnerabilityCase)`, creating
a direct contradiction. The spec said one thing; the implementation did
another. Step 5 (`AutoCloseSequence`) in `add_participant_status_tree`
became dead code as a result — `AllParticipantsRMClosedConditionNode`
always returns FAILURE because all `Add(ParticipantStatus)` messages arrive
before any `Leave`.

## Resolution

`Leave(VulnerabilityCase)` is the canonical RM closure mechanism.
`Add(ParticipantStatus, rm_state=RM.CLOSED)` MUST NOT be used as a closure
trigger. Rationale: the Case Actor is the single authority for closure
(log-centric single-writer regime, ADR-0019/ADR-0021); the `Leave`
round-trip makes closure observable to all replicas via the canonical
ledger; a lost `Add(ParticipantStatus)` message would allow ghost-departures.

Two new ADRs were authored:

- **ADR-0050**: `Leave(VulnerabilityCase)` is the canonical RM closure
  mechanism; `Add(ParticipantStatus, rm_state=RM.CLOSED)` is prohibited.
- **ADR-0051**: CaseActor has a full RM lifecycle tracked via
  `CaseParticipant` (`RECEIVED → VALID → ACCEPTED` at bootstrap, `CLOSED`
  on owner `Leave`). Each transition is a `CaseLedgerEntry`. RM state
  meanings for the coordinator: RECEIVED=CaseProposal received,
  VALID=proposal validated+case creation begun, ACCEPTED=case created,
  CLOSED=owner Left.

A new spec group **CM-23** was added to `specs/case-management.yaml`
(CM-23-001 through CM-23-007), covering:

- Leave-only closure (CM-23-001)
- Owner Leave sequence: owner→CLOSED, CaseActor→CLOSED, final
  `case_fully_closed` entry, fan-out (CM-23-002)
- Non-owner Leave: only that participant→CLOSED (CM-23-003)
- Fan-out exclusion of RM.CLOSED participants (CM-23-004)
- CaseActor RM lifecycle bootstrap (CM-23-005 through CM-23-007)

`DEMOMA-07-001` was amended to scope its clause to CS transitions only;
`DEMOMA-07-003 step 5` and `DEMOMA-07-006` were marked `[SUPERSEDED]`.

## Implementation Issues

- #1916 — Remove `AutoCloseSequence` + conform to CM-23-001 through
  CM-23-004 (blocked by #1901)
- #1917 — CaseActor `CaseParticipant` RM lifecycle bootstrap: CM-23-005
  through CM-23-007 (blocked by #1901)
- #1918 — Idea: Rejoin semantics for departed case participants (deferred)

## Key Design Notes

- Owner Leave vs non-owner Leave: owner closes the case for all; non-owner
  removes only that participant.
- `EmitCloseCaseNode` in the dead `AutoCloseSequence` uses
  `actor=self.actor_id` — this would have advanced the CaseActor's own
  participant to `RM.CLOSED` as a departing participant, which is hazardous
  under the Leave path.
- `RM.CLOSED` is currently terminal. The rejoin question (whether it should
  be non-terminal, or whether a new `RM.TERMINATED` state is needed) is
  deferred to #1918.
- `AllParticipantsRMClosedConditionNode` currently skips
  `CVDRole.CASE_MANAGER` participants. After #1917 lands, this skip can be
  removed.
- Issue #1858 (blocked by this concern) will need #1916 and #1917 wired as
  blockers appropriately.

## Docs PR

<https://github.com/CERTCC/Vultron/pull/1915>
