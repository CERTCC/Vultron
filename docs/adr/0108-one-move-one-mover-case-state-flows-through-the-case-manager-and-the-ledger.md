---
status: accepted
date: 2026-09-28
deciders: Allen D. Householder
consulted: Claude Fable 5.1
informed: Vultron contributors
stakeholder_type: [project-contributor]
---

# One Move, One Mover: Case State Flows Through the Case Manager and the Ledger, Whatever Message Carried It

## Context and Problem Statement

A single protocol state transition can arrive on the wire in more than one shape.
When a vendor decides a report is invalid, its Report Management (RM) state moves RECEIVED → INVALID, and it may say so twice: once as `TentativeReject(Offer(VulnerabilityReport))`, the formal message RI, which answers the finder's offer, and once as `Add(ParticipantStatus, CaseParticipant)` whose payload carries `rmState: INVALID`, a snapshot of its status.
The same doubling exists for every RM step, and embargo state has three carriers: the consent activities (`Accept(Invite(EmbargoEvent))` and its siblings), the case-status assertion `Add(CaseStatus)`, and the ledger broadcast `Announce(CaseLedgerEntry)`.

[ADR-0083](0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md) settled that the formal message set and the AS2 wire vocabulary are different shapes.
It said nothing about two *wire* shapes carrying one transition.
Because no rule was stated, each receiving handler answered three questions on its own, and they answered differently (CONCERN-3473):

- **Whose state is being written?** The report-valid handler advances the *sender's* RM. The report-invalid and report-closed handlers advance the *receiving actor's* RM. The acknowledgement handler advances nobody's. Four sibling handlers of one state machine, three conventions.
- **Which acceptance rule applies?** `Add(ParticipantStatus)` runs the per-dimension policy of [ADR-0061](0061-per-dimension-partial-accept.md): forward moves accepted, backward moves refused, gaps flagged with a clarification note (RSH-05, RSH-06). The activity-typed handlers pass a hardcoded target state to the single writer and get only RM adjacency validation. A peer that wants its claim adjudicated uses one message; a peer that wants it applied unexamined uses the other.
- **Who may write case state at all?** Every received-side tree gates its *ledger commit* on the receiver holding `CVDRole.CASE_MANAGER`, but runs its *state-writing effects* at every inbox. `Add(EmbargoEvent)` and `Remove(EmbargoEvent)` move a replica's embargo state from any sender with no transition check; `Add(CaseStatus)` validates the transition but also accepts any sender.

The receiving-actor bug has a traceable origin.
BT-17-006 required a received-side tree to *execute in the receiving actor's store*.
The tests written for that fix asserted that the *receiving actor's participant* changes state, reading "the tree runs as B" as "the write is about B".
That is the store-versus-subject conflation [ADR-0089](0089-one-participant-status-writer.md) later named as bug #2300, and BT-17-006's own text already says a node that advances the sender's RM must carry the sender's ID separately.

The direct-receipt effects have a traceable origin too.
PCR-03-001 says a replica accepts case-state updates only from the CASE_MANAGER, and the ledger is the channel.
But the replica-apply path handles only seven ledger event types (embargo removal, participant status, note, invite acceptance, close case, report submission, ownership transfer).
The case-status entry the CASE_MANAGER commits on every embargo or public-state change has no replay node, nor do report valid/invalid/closed or engage/defer.
Replicas learn those things today only because the effect runs at every inbox.
The direct effects fill a gap in the specified pipeline, and in filling it they bypass the CASE_MANAGER's adjudication and sender checks.

The question this ADR settles: when one transition has more than one wire carrier, which one must a receiver honour, and where does adjudication sit?

## Decision Drivers

- Participant status is self-declaratory ([ADR-0084](0084-participant-assertion-authority.md)). RM is per-participant; nobody moves another participant's RM, and the on-behalf exceptions cover only vendor-awareness and fix-deployed.
- Only the CASE_MANAGER writes canonical case state, and replicas take it from the ledger (PCR-03-001, PCR-03-006, CM-06-002, RSH-04-001). This is specified; it is not fully built.
- Liberal accept ([ADR-0061](0061-per-dimension-partial-accept.md), [ADR-0086](0086-report-every-violation-reject-the-batch.md)): the receive side records what the sender declares, refuses only what cannot be true, and never refuses silently.
- The activity type carries information the status snapshot cannot: which offer, which report, which invitation the move answers. Retiring it loses the antecedent.
- The status snapshot carries information the activity cannot: vendor-fix and public-state dimensions have no activity of their own (MSM-03), and one snapshot moves several machines at once.
- The cost of no rule is already paid: #3438 and #3439 each re-litigated "which form is authoritative" from scratch.

## Considered Options

1. **Pick one authoritative wire form per transition and retire the other.** For RM, make the activity form primary and demote the snapshot's `rmState` to a confirmation that is refused when it disagrees with what the CASE_MANAGER recorded.
2. **Unify mechanically.** One acceptance function per state machine that every received write must call, regardless of which message carried it, without deciding which message is primary.
3. **One move, one mover, one pipeline.** Recognise that an act message and a status declaration are two layers of the same move, not competing encodings; state the authority as a property of the *pipeline* rather than the message; finish the pipeline; gate the shortcuts.

## Decision Outcome

Chosen option: **one move, one mover, one pipeline**.

The rule, in one sentence: *only the participant making a move announces it, only the CASE_MANAGER turns an announcement into case state, and every other participant takes case state from the ledger; the CASE_MANAGER applies the state machine's own acceptance rule to the sender's declaration regardless of which message carried it.*

Four commitments follow.

### 1. An act and its status declaration are two layers of one move, and both are expected

`TentativeReject(Offer(Report))` is the **act**: the vendor answering the finder's offer, carrying what it answers.
`Add(ParticipantStatus)` with `rmState: INVALID` is the **declaration of resulting state**: the vendor's own statement about the vendor.
One move producing both is normal.
Neither retires, and neither is "the" authoritative encoding.
The declaration is expected to agree with what the act implied; when it does not, that is a flagged gap (RSH-06), not grounds to refuse a participant's statement about itself.

Scored against the collapse inventory in `notes/message-type-reference.md`, the row that "surprises people", RM steps carried by both a report activity and `rmState`, stops being an anomaly.
It is the general case.

### 2. The subject of a write is the sender, and the store is not the subject

A received activity is an assertion about the *sender's* state (HP-00-001).
The subject of every RM write on the receive side is therefore the sender, never the receiving actor.
The receiving actor's own RM moves only when it is itself the mover: an actor posting to its own inbox (where sender and receiver coincide), or the CASE_MANAGER advancing its own participant on owner departure, which CM-23-002 specifies as the CASE_MANAGER's own consequence.

BT-17-006 chooses the *store* a tree runs in.
It says nothing about *whose* state the tree writes, and its own sender-ID clause presumes the two differ.
The report-invalid and report-closed handlers, and the tests that pin them, conflated the two and are wrong.

### 3. The acceptance rule belongs to the state machine, not to the message

The CASE_MANAGER adjudicates a declared transition with one rule per state machine, whichever message carried it:

- the sender must be a participant on the case;
- a forward move is accepted, including a non-adjacent one;
- a backward move is refused and the current value carried forward;
- a gap is logged and, where a case context exists, a clarification note is posted (RSH-06-003 through RSH-06-005).

Today only `Add(ParticipantStatus)` does this.
The report-valid/invalid/closed and engage/defer handlers adopt the same rule in place of adjacency-only validation, and gain the sender-is-participant check.
Adjacency remains the *emit-side* rule (the trigger path is conservative, [ADR-0086](0086-report-every-violation-reject-the-batch.md)); it is not the receive-side rule, and a receiver that refuses a peer's legal self-declaration because it never saw the intermediate step is second-guessing the peer.

### 4. Replicas take state from the ledger, so the ledger must carry everything and the shortcuts must close

Every event type the CASE_MANAGER commits to the case ledger gets a replica apply node, or a recorded declaration that it has no replica effect.
Once the ledger carries a transition, the received-side effect that wrote it directly at every inbox is wrapped behind the CASE_MANAGER role gate, so a replica that receives an act by `cc` or misrouting stores the activity and writes nothing.
Order matters: replay first, gate second, or replicas go blind.

Two ratchets hold this: one asserting every committed ledger event type has a replay node or a declared exemption, and one asserting no received-side tree writes participant or case state outside a CASE_MANAGER gate.

### What this decision does *not* change

- The CS dimensions stay as they are: V/F/D on `ParticipantStatus`, P/X/A on `CaseStatus`, discriminated by payload field ([ADR-0075](0075-split-vfd-state-machine.md), [ADR-0083](0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- Embargo consent (PEC) has no wire form of its own and one transition method (MSM-07, CM-18-005). It already satisfies this rule.
- The single `ParticipantStatus` writer and composed rule evaluator ([ADR-0086](0086-report-every-violation-reject-the-batch.md), [ADR-0089](0089-one-participant-status-writer.md)) are the write-side shape this decision sits above.
- Roster holes found by the same inventory (`Add`/`Remove(CaseParticipant)` accept any sender; `Accept(Offer(VulnerabilityCase))` does not check that an offer exists) are missing authorization checks, not parallel encodings. They belong to the participant-admission epic (#3409).

### Consequences

- Good, because the "which form wins" question stops recurring: there is no winner to pick, and the next #3438-shaped question is answered by asking which layer of the move the message is.
- Good, because the adjudication bypass closes: a peer can no longer choose the lenient path by choosing the message shape.
- Good, because PCR-03-001 becomes true rather than aspirational, and the any-sender embargo writes at replicas disappear with it.
- Good, because the subject rule stops being re-derived per handler.
- Bad, because completing ledger replay is the largest piece of work this project has deferred under this epic, and gating cannot land before it.
- Bad, because the report-handler tests that pin the receiving actor as subject invert, and any demo scenario that relied on a replica learning RM state from a direct act must be checked against the ledger path.
- Neutral, because the emit side is unchanged: a participant may still send the act, the declaration, or both.

## Validation

Deferred to the implementation issues listed in CONCERN-3473's resolution comment; nothing below validates anything until they land:

- Regression tests asserting the report-invalid and report-closed handlers advance the *sender's* participant and leave the receiver's untouched (inverting the current assertions in `test/core/use_cases/received/test_report_routing_guard.py`).
- Tests asserting the report and engage/defer handlers accept a non-adjacent forward RM move, refuse a backward one, and post the RSH-06 clarification note, with the same fixtures the `Add(ParticipantStatus)` tests use.
- A ratchet in `test/architecture/` asserting every committed ledger `event_type` has a replay node or a declared exemption.
- A ratchet in `test/architecture/` asserting every received-side tree's state-writing effect nodes sit under a CASE_MANAGER role gate.

Spec requirements: `specs/received-status-handling.yaml` RSH-08 (new), RSH-06-006 (new), and the corrections to RSH-01-003 and RSH-01-004.

## Pros and Cons of the Options

### Pick one authoritative wire form and retire the other

- Good, because it is the simplest rule to state.
- Bad, because the two forms carry different information (antecedent versus multi-dimension snapshot), so either choice loses something the protocol uses.
- Bad, because demoting `rmState` to a confirmation tightens liberal accept for one dimension, contradicting RSH-06-001's reason for existing: the sender is authoritative about its own progress.
- Bad, because it treats a symptom. The bypass exists because the pipeline is incomplete, not because two messages exist.

### Unify mechanically

- Good, because it closes the adjudication bypass with the least design.
- Bad, because it leaves the direct-receipt effects at replicas in place, so any sender can still move a replica's state; the sender check is the part mechanics cannot supply.
- Bad, because it never states whose state is being written, so the subject bug survives.

### One move, one mover, one pipeline (chosen)

- Good, because it is what PCR-03 and HP-00 already say, made true.
- Good, because it explains the doubled messages instead of legislating against them.
- Bad, because it is the most work, and the work has a required order.

## More Information

Source: CONCERN-3473, under epic #3472 (wire-form authority).
The inventory that grounds this decision, one row per wire form per state machine with the subject and adjudication path of each, is recorded in the concern's history entry.

Related decisions: [ADR-0083](0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md) (formal↔wire divergence is deliberate; this ADR covers wire↔wire), [ADR-0084](0084-participant-assertion-authority.md) (self-declaration; extended here to the whole receive side), [ADR-0061](0061-per-dimension-partial-accept.md) and [ADR-0086](0086-report-every-violation-reject-the-batch.md) (liberal accept; extended here to the activity-typed handlers), [ADR-0089](0089-one-participant-status-writer.md) (one writer; the store-versus-subject conflation this ADR names again), [ADR-0046](0046-received-status-authorization.md) (two-gate adoption model; RSH-01-003/004 corrected to match the direct-write shape of RSH-04-004), [ADR-0050](0050-leave-vul-case-canonical-rm-closure.md) and CM-23-001 (the one prior per-transition authority rule, which this ADR generalizes).

Design notes: `notes/received-status-authorization.md` § "One move, one mover", `notes/message-type-reference.md` § "Collapses", `notes/bt-pitfalls.md` § "The Store Is Not the Subject".
