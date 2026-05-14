---
title: Case Creation Sequence
status: active
description: >
  Design decisions and BT implementation mapping for the canonical case
  initialization sequence at Offer(Report) receipt (CM-14, ADR-0015).
related_specs:
  - specs/case-management.yaml
related_notes:
  - notes/case-state-model.md
  - notes/embargo-default-semantics.md
  - notes/protocol-event-cascades.md
  - notes/participant-embargo-consent.md
relevant_packages:
  - vultron/core/behaviors/case
  - vultron/core/behaviors/report
  - vultron/core/use_cases/received
---

# Case Creation Sequence

## Overview

When a vendor actor receives an `Offer(Report)` activity, it immediately
creates a `VulnerabilityCase` (ADR-0015, CM-12-001) and runs a canonical
initialization sequence before any other case activity can proceed.

This note captures the ordering decisions, their rationale, and the
mapping to the behavior tree nodes that implement each step.

**Spec reference**: `specs/case-management.yaml` CM-14 (source: IDEA-26050501).

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| When is the case created? | At `Offer(Report)` receipt (RM.RECEIVED) | ADR-0015; eliminates pre-case tracking complexity |
| Who is the first participant? | Case owner (receiving actor) | Embargo must be created by an existing participant |
| Does the owner participant exist before the embargo? | Yes — owner MUST precede embargo | An embargo without a participant lacks an owning actor |
| When is the default embargo initialized? | After owner participant exists, before reporter is added | Owner initiates the embargo on behalf of the case |
| Is the owner seeded as SIGNATORY? | Yes — automatically at embargo initialization | Case owner created the embargo; separate accept step is paradoxical |
| Is the reporter seeded as SIGNATORY? | Yes — automatically when added as participant | Reporter already holds the information; requiring explicit accept before content access is a deadlock |
| When is `Create(Case)` sent to reporter? | After embargo init, before reporter is added as participant | Reporter must have case object before receiving fan-out log entries |
| Can additional parties be invited before initialization completes? | No — initialization MUST complete first (CM-14-007) | Prevents race conditions and protocol violations |

---

## Canonical Sequence (CM-14-001)

The following steps MUST execute in order:

| Step | Action | Key Constraint |
|---|---|---|
| 1 | Create `VulnerabilityCase` with receiving actor as `attributed_to` | — |
| 2 | Create case-owner `VultronParticipant` (RM.RECEIVED, `CVDRole.CASE_OWNER`) | **Must precede step 3** |
| 3 | Initialize default embargo → `EM.ACTIVE`; seed owner as `SIGNATORY` | Conditional on embargo policy being configured (CM-12-004) |
| 4 | Queue `Create(Case)` activity addressed to reporter; flush outbox | **Must precede step 5** |
| 5 | Add reporter `VultronParticipant` (RM.ACCEPTED, `CVDRole.FINDER`/`REPORTER`); seed as `SIGNATORY` | — |
| 6 | Commit case log entry → `Announce(CaseLogEntry)` fan-out to all participants | Reporter is now a participant and receives the fan-out |

Steps 3 and 6 are each conditional (embargo policy must exist for step 3;
fan-out only reaches the participants who exist at that point for step 6),
but their *position* in the sequence is fixed.

---

## BT Node Mapping

The `receive_report_case_tree.py` (`create_receive_report_case_tree`) is the
canonical implementation of this sequence. The node order matches the
required ordering above (implemented in commit `2d8ce2c4`).

**Current (spec-correct) node order:**

| Step | BT Node | Module |
|---|---|---|
| 1 | `CreateCaseNode` | `vultron/core/behaviors/report/nodes.py` |
| 2 | `CreateCaseOwnerParticipant` | `vultron/core/behaviors/case/nodes.py` |
| 3 | `InitializeDefaultEmbargoNode` + owner SIGNATORY seed | `vultron/core/behaviors/case/nodes.py` |
| 4a | `CreateCaseActivity` | `vultron/core/behaviors/report/nodes.py` |
| 4b | `UpdateActorOutbox` | `vultron/core/behaviors/case/nodes.py` |
| 5 | `CreateCaseParticipantNode` + reporter SIGNATORY seed | `vultron/core/behaviors/case/nodes.py` |
| 6 | `CommitCaseLogEntryNode` | `vultron/core/behaviors/case/nodes.py` |

---

## Implementation Notes

### Gaps 1–3: Resolved in commit `2d8ce2c4`

Gaps 1, 2, and 3 described below were present when this note was authored
(2026-05-05) but were resolved on the same day in commit `2d8ce2c4`
("feat(case-init): implement CM-14 canonical case initialization sequence"):

- **Gap 1** — wrong step ordering (`InitializeDefaultEmbargoNode` before
  `CreateCaseOwnerParticipant`): **resolved**. The tree now runs
  `CreateCaseOwnerParticipant` at step 2, then `InitializeDefaultEmbargoNode`
  at step 3, matching CM-14-002.
- **Gap 2** — owner not seeded as SIGNATORY (BUG-26042204): **resolved**.
  `InitializeDefaultEmbargoNode` seeds the owner via `_seed_owner_as_signatory`
  in `vultron/core/behaviors/case/nodes.py` (CM-14-003).
- **Gap 3** — reporter not seeded as SIGNATORY: **resolved**.
  `CreateCaseParticipantNode` seeds the reporter as SIGNATORY when an active
  embargo exists (CM-14-005), implemented in `nodes.py`.

### Gap 4: Reporter embargo proposal (forward-looking)

No wire-format mechanism exists for a reporter to include an embargo
proposal in an `Offer(Report)`. CM-14-006 captures this as a SHOULD
requirement for future implementation.

**See**: `notes/embargo-default-semantics.md` "Known Gap: No Reporter
Embargo Proposal Mechanism"; `specs/embargo-policy.yaml` EP-04-003.

---

## Boundary Rule (CM-14-007)

Additional participants MUST NOT be invited and embargo modifications
MUST NOT be initiated until all six initialization steps are complete.
The case-initialization BT is an atomic unit from the protocol's
perspective. Any trigger endpoint (e.g., `suggest-actor-to-case`,
`propose-embargo`) that arrives while initialization is in progress MUST
be deferred or rejected with a retriable error.

---

## Cross-references

- `specs/case-management.yaml` CM-14 (normative requirements)
- `docs/adr/0015-create-case-at-report-receipt.md` (timing decision)
- `notes/embargo-default-semantics.md` (embargo init semantics and gaps)
- `notes/participant-embargo-consent.md` (PEC state machine)
- `notes/protocol-event-cascades.md` (cascade automation principles)
- `vultron/core/behaviors/case/receive_report_case_tree.py` (implementation)
