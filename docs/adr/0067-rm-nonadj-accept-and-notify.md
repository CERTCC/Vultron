---
status: accepted
date: 2026-08-20
created: 2026-08-20
updated: 2026-08-20
revision: 1
deciders: Allen D. Householder
consulted: Vultron protocol maintainers
informed: Vultron contributors
stakeholder_type: [project-contributor]
---

# Accept Non-Adjacent Forward RM Jumps and Notify; Refuse Backward Regressions Non-Silently

## Context and Problem Statement

When a CaseActor receives `Add(ParticipantStatus, CaseParticipant)` and
compares the reported `rm` state against its local replica, three cases arise:

1. **Adjacent valid transition** — no anomaly; accept silently.
2. **Non-adjacent forward jump** — the sender skipped intermediate states
   (e.g. `RECEIVED → ACCEPTED` without passing through `VALID`). The existing
   `FilterParticipantStatusDimensionsNode._rm_is_acceptable()` already accepts
   these and documents the rationale (*"sender is authoritative about own RM
   progress"*), but acceptance is silent.
3. **Backward regression** — the sender reports a state earlier on the RM
   progress scale than what the receiver has already observed (e.g.
   `ACCEPTED → VALID`). `ValidateRMTransitionNode` refuses these, which is
   correct, but the refusal is also silent.

Two independent bugs arise from the silent treatment:

- Forward jumps are accepted without any log entry at WARNING level or any
  protocol-level notification. An anomaly that should trigger a clarification
  request passes through as if nothing unusual happened (ISSUE-2258).
- Backward regressions are refused without emitting a protocol-level note.
  A remote actor's replica is now permanently diverged from the receiver's, with
  no signal to either party.

The broader principle: CVD is inherently asynchronous. Events happen at time t₀
but are only recognised as anomalous at time t₁ > t₀. When a protocol-level
anomaly is detected on receipt, the receiver must both act correctly *and* act
non-silently. Silence on anomalies breaks the protocol's observability and makes
diagnosis impossible.

## Decision Drivers

- **Liberal accept / Postel's law** (ISSUE-2229): accept everything acceptable;
  refuse only what must be refused.
- **Sender is authoritative about its own RM progress**: refusing a
  non-adjacent forward jump would leave the receiver's replica permanently wrong,
  because the sender will not resend the intermediate transitions it never
  reported.
- **RM is monotonic**: backward regressions indicate either a protocol error or
  a divergent replica state. Neither is acceptable; both warrant correction.
- **Non-silence principle**: anomalies detected asynchronously must produce an
  observable effect — at minimum a WARNING log, and on the production path an
  `Add(Note, VulnerabilityCase)` addressed to the sender.
- **ADR-0049**: core does not model inbound protocol error message types
  (`RE` from the original BT protocol design). The pragmatic substitute is
  `Add(Note, VulnerabilityCase)` via the existing note-emission infrastructure.
- **Consistency across call paths**: `FilterParticipantStatusDimensionsNode`
  (production path, `add_participant_status_tree`) and
  `ValidateRMTransitionNode` (standalone path, `append_participant_status_tree`)
  must implement the same acceptance policy. The standalone path is test-only;
  it has no case context and therefore cannot emit a note, but it must still log
  at WARNING level.

## Considered Options

- **Refuse non-adjacent forward jumps** — reject the `rm` dimension and carry
  the receiver's current value forward (as RSH-05 does for other refusals).
- **Accept silently** — current behaviour; no log, no notification.
- **Accept and notify** — accept the forward jump (honouring sender authority),
  log at WARNING level, and on the production path emit
  `Add(Note, VulnerabilityCase)` describing the anomaly and requesting
  clarification.

## Decision Outcome

Chosen option: **accept and notify**.

### Forward jumps (non-adjacent, monotonically forward)

The receiver MUST accept the reported RM state. Refusing would leave the
replica permanently wrong. The receiver MUST:

1. Log a WARNING naming the sender, the observed gap (`before → after`), and
   the fact that the jump is non-adjacent.
2. On the production `add_participant_status_tree` path, emit
   `Add(Note, VulnerabilityCase)` requesting the sender to clarify the
   intermediate path it took.

### Backward regressions

The receiver MUST refuse the `rm` update (current behaviour, preserved). In
addition it MUST:

1. Log a WARNING (already done; confirmed correct).
2. On the production `add_participant_status_tree` path, emit
   `Add(Note, VulnerabilityCase)` describing the refused regression.

### Implementation shape

This decision constrains any implementation by the invariants below; the concrete nodes and trees that satisfy them are tracked by the governing requirements RSH-06-001 through RSH-06-005, whose `verification:` fields name the current tests — this ADR does not name them, so an implementation refactor does not invalidate it.

- The anomaly — a non-adjacent forward jump, or a backward regression — is detected and recorded at the moment of receipt, on whichever received path carried the declaration.
- The clarification `Add(Note, VulnerabilityCase)` to the sender is emitted only by the CASE_MANAGER, because only the CASE_MANAGER adjudicates a declaration into case state.
- A wholly refused backward regression still owes the sender that note, even though the refusal is a precondition-guard failure that stops the tree before its ordinary effects; the note is therefore emitted on the refusal path, once per received activity, so a redelivery does not repeat it.
- The test-only standalone path has no case context: it logs the anomaly at WARNING and emits no note.

### Consequences

- Good, because replica correctness is preserved (forward jumps accepted).
- Good, because anomalies become observable at the protocol level.
- Good, because both call paths now agree: forward jumps are always accepted.
- Good, because the asynchronous non-silence principle is encoded as a spec
  requirement, not just a one-off fix.
- Neutral, because `Add(Note, VulnerabilityCase)` is a pragmatic substitute
  for the `RE` (Report Management Error) message type from the original BT
  protocol. A future ADR may formalise `RE` in `MessageSemantics` and replace
  the note; that change would be backward-compatible with this decision.
- Bad, because note emission adds a new effect to the `add_participant_status_tree`
  path; tests must cover the case where no anomaly is present so that the
  node is a no-op in the happy path.

## Validation

- `ValidateRMTransitionNode`: unit tests assert WARNING log + anomaly flag on
  forward gap; WARNING log + FAILURE on backward regression.
- `FilterParticipantStatusDimensionsNode`: unit tests assert anomaly flag is
  set when a non-adjacent forward jump is accepted.
- `add_participant_status_tree` integration tests: note emitted on forward gap;
  note emitted on backward rejection; no note on adjacent transition.
- `append_participant_status_tree` unit tests: WARNING log on forward gap; no
  note (standalone path has no case context).

## More Information

- Original protocol `RE` message type: `vultron.bt.messaging.states`; not yet
  in core `MessageSemantics`. ADR-0049 explains why core does not model
  inbound error types.
- RSH-05 (ADR-0061): per-dimension partial accept — the complement of this
  decision. This ADR governs the `rm` dimension's anomaly notification policy
  while RSH-05 governs the per-dimension filter and snapshot shape.
- ISSUE-2258: the concrete bug; `ValidateRMTransitionNode` accepted forward
  gaps at INFO level with no notification.
- ISSUE-2229: liberal-accept epic (Postel's law).

Generated spec requirements: `specs/received-status-handling.yaml` RSH-06-001
through RSH-06-005.

## Amendment — 2026-10-09

The "Implementation shape" section is rewritten to record decision-level invariants only; the decision itself is unchanged.
As first written, the section named concrete node classes and a factory parameter — `rm_transition_anomaly`, `FilterParticipantStatusDimensionsNode`, `ValidateRMTransitionNode`, `EmitRMGapNoteNode`, and the `effect_nodes` of `add_participant_status_tree`.
A later refactor (the received-tree factory work landed with #4310) renamed those nodes and moved the note from a single effect stage to both the accepted-path effects and the refusal-path effects, which left the ADR describing an implementation that no longer existed.
The replacement text states only what any implementation MUST satisfy — where the anomaly is detected, that the note is emitted only by the CASE_MANAGER, that a wholly refused backward regression still owes the sender a note on the refusal path once per received activity, and that the test-only standalone path logs but emits no note — and defers the live node and tree mapping to RSH-06-001 through RSH-06-005, whose `verification:` fields track the current tests.
This also records the missing fact the original section lacked: that a wholly refused regression is a precondition-guard failure whose note runs as a refusal effect, not an ordinary effect (#4348, found while implementing #4310).
