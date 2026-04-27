---
status: accepted
date: 2026-04-28
deciders: Vultron maintainers
---

# Create VulnerabilityCase at Report Receipt (RM.RECEIVED)

## Context and Problem Statement

When a vendor actor receives a `Offer(Report)` activity (i.e., a reporter
submits a vulnerability report), the current implementation defers
`VulnerabilityCase` creation until the report passes validation — that
is, until the `ValidateReport` behavior tree transitions the receiver's
RM state to `RM.VALID`.

This was originally a natural mapping from the CVD process model: a "case"
traditionally implies the vendor has committed to working the issue.
However, in the Vultron prototype this deferral creates several problems:

1. **Awkward pre-case tracking**: Before a case exists, the system needs
   separate mechanisms to track the receiver's RM state and the reporter's
   participation. These "proto-case" structures mimic a case without being
   one, adding complexity with no benefit.
2. **Late finder notification**: The reporter does not learn that a case
   has been opened until after validation. Under MPCVD, this creates
   unnecessary gaps in coordination.
3. **Overcrowded `ValidateReport` BT**: The validate-report behavior tree
   currently performs both report validation and case/participant setup.
   These are distinct concerns. Mixing them makes the tree harder to
   reason about and test.
4. **Blocking FINDER-PART-1**: The need to track participants before a
   case exists drove the FINDER-PART-1 task, which required a complex
   retroactive re-linking mechanism. This complexity dissolves if the
   case is created earlier.

The question is: **when should the `VulnerabilityCase` object be
created?**

## Decision Drivers

- Simplicity: minimize distinct tracking mechanisms
- Protocol fidelity: the CVD process begins at receipt, not at validation
- Separation of concerns: case setup vs. report validation are distinct
  workflows
- Finder visibility: reporters should know a case was opened as soon as
  possible

## Considered Options

1. **Keep case creation at RM.VALID** (status quo) — create the case only
   after the report is validated
2. **Create case at RM.VALID, but emit earlier notification** — keep
   creation deferred but send provisional notification sooner
3. **Create case at AckReport (RM.RECEIVED, post-ack)** — wait for the
   receiver to acknowledge before creating the case
4. **Create case at `Offer(Report)` receipt (RM.RECEIVED)** — create the
   case immediately in `SubmitReportReceivedUseCase`

## Decision Outcome

Chosen option: **Option 4 — Create case at `Offer(Report)` receipt
(RM.RECEIVED)**.

When `SubmitReportReceivedUseCase` processes an inbound `Offer(Report)`,
it MUST invoke a new behavior tree (`receive_report_case_tree`) that
creates a `VulnerabilityCase`, two initial `VultronParticipant` records
(reporter at RM.ACCEPTED, receiver at RM.RECEIVED), a default embargo,
and queues a `Create(Case)` notification to the reporter.

The `ValidateReport` BT is slimmed to validation-only logic.

### Consequences

- **Good**: No separate "pre-case" object or participant tracking mechanism
  is needed. The case object exists from the moment the report is received.
- **Good**: `ValidateReport` BT focuses on what it is named for: evaluating
  report credibility and validity. Case/participant creation moves to its
  own BT.
- **Good**: Reporter receives immediate `Create(Case)` notification,
  improving MPCVD coordination latency.
- **Good**: `InvalidateReportReceivedUseCase`, `CloseReportReceivedUseCase`,
  and `ValidateReportReceivedUseCase` can all dereference `report_id →
  case_id` and delegate to corresponding case-level use cases. This
  makes report-centric flows consistent.
- **Good**: FINDER-PART-1 (the complex retroactive re-linking task) is
  superseded and can be removed from the backlog.
- **Neutral**: The term "proto-case" is preserved but **redefined**. A
  proto-case is now a case object in the RM.RECEIVED or RM.INVALID stage
  (i.e., the case exists but has not yet been validated). The
  caterpillar/butterfly analogy still holds: caterpillar = case in
  RM.RECEIVED/INVALID stages; butterfly = case in RM.VALID/ACCEPTED/
  DEFERRED stages.
- **Neutral**: Cases for reports that are later invalidated or closed
  without validation do exist as persisted objects in a terminal
  proto-case state (RM.INVALID or RM.CLOSED). This is acceptable and
  consistent with the protocol model.
- **Bad**: `SubmitReportReceivedUseCase` becomes more complex (requires
  BT invocation). This is offset by `ValidateReport` BT becoming simpler.
- **Bad**: The `InitializeDefaultEmbargoNode` and participant-creation
  nodes move from the validate-report BT to the new case-from-report BT.
  The BT tests for these nodes must be updated accordingly.

## Validation

This decision is validated by:

- `test/core/use_cases/received/test_submit_report.py`: verifies that
  `SubmitReportReceivedUseCase` creates a case, two participants, and
  queues `Create(Case)` to the outbox
- `test/core/behaviors/case/test_receive_report_case_tree.py`: verifies
  the new BT creates case and participants with correct initial RM states
- `test/core/behaviors/report/test_validate_tree.py`: verifies the
  slimmed validate-report BT does NOT create case or participants
- All existing tests for `ValidateReportReceivedUseCase` continue to
  pass (the report→case dereference is transparent to callers)

## Pros and Cons of the Options

### Option 1 — Keep case creation at RM.VALID (status quo)

- Good, because it preserves the traditional CVD meaning of "case" (an
  accepted commitment to work the issue)
- Bad, because it requires separate pre-case tracking for RM state and
  participants
- Bad, because `ValidateReport` BT mixes two concerns
- Bad, because finder notification is delayed until after validation

### Option 2 — Emit earlier notification, keep deferred creation

- Good, because "case" retains its committed-work meaning
- Bad, because adds another activity type to the protocol with no
  corresponding state change
- Bad, because the pre-case tracking problem remains

### Option 3 — Create case at AckReport

- Good, because case creation is still tied to an explicit vendor action
- Bad, because the `AckReport` step is optional and may not occur in all
  demo or protocol paths
- Bad, because complicates the path for implementations that skip
  explicit acknowledgment

### Option 4 — Create case at `Offer(Report)` receipt (chosen)

- Good, because aligns case object lifecycle with the start of CVD work
- Good, because eliminates pre-case tracking complexity
- Good, because separates validation from case setup
- Good, because sends immediate notification to reporter
- Neutral, because "proto-case" term requires redefinition (not removal)
- Bad, because cases for subsequently-invalidated reports persist in
  storage (acceptable; they are in a terminal state)

## More Information

- **Supersedes**: FINDER-PART-1 task in `plan/IMPLEMENTATION_PLAN.md`
- **Refines**: `notes/case-state-model.md` (proto-case / caterpillar–butterfly
  metaphor)
- **Updates**: `specs/case-management.yaml` (new CM-12 requirements)
- **Updates**: `specs/duration.yaml` (DUR-07-002 timing, new DUR-07-004)
- **Updates**: `notes/protocol-event-cascades.md` (cascade list)
- **Source idea**: IDEA-260408-01 in `plan/IDEAS.md`
