---
status: accepted
date: 2026-08-12
deciders: Allen D. Householder
consulted: Vultron protocol maintainers
informed: Vultron contributors
---

# Adjudicate Received `ParticipantStatus` Per Dimension, Not as a Unit

## Context and Problem Statement

A `ParticipantStatus` is not a single state value. It is a snapshot of several
independent state machines: `rm` (Report Management), `vfd` (vendor fix path),
`em` (Embargo Management), `pxa` (public state) and `consent` (Participant
Embargo Consent). When one arrives over the wire in
`Add(ParticipantStatus, CaseParticipant)`, the receiving CaseActor must decide
what to believe.

Before this decision it decided all-or-nothing. `ValidateRMTransitionNode`
refused any backwards `rm` step and any status for a participant already at
terminal `RM.CLOSED`, and its FAILURE inside the `AppendParticipantStatusBT`
Sequence discarded the entire snapshot — including dimensions the receiver had
no grounds to refuse. Worse, the FAILURE aborted the enclosing Sequence before
`StatusAdoptionGate` and `EmitAddCaseStatusToSelfNode`, so the StatusAdoptionGate → EmbargoTeardownAuthorizationGate
emit never happened and embargo teardown silently did not run (ADR-0046,
RSH-01-003, RSH-01-004). A vendor that had closed its report management
workflow could not report deploying its fix at all.

Reported as ISSUE-2235, under the liberal-accept epic ISSUE-2229 (Postel's
maxim: be conservative in what you send, liberal in what you accept).

## Decision Drivers

- The dimensions are genuinely independent state machines; a refusal in one
  carries no information about the others.
- Liberal accept (ISSUE-2229): refuse the narrowest thing that must be refused.
- Refusals must be *visible*. The pre-existing behaviour was a silent drop.
- CLP-10-006 receive-side ordering: precondition guards run before
  `GuardedCommit`; guards MUST NOT write to the DataLayer.
- The canonical `CaseLedgerEntry` is hash-chained and replicated to every
  participant. Whatever it snapshots becomes every replica's view.
- Monotonic visibility: a replica must never un-see progress it has observed.

## Considered Options

- **Keep all-or-nothing, but return SUCCESS on refusal.** Fixes the aborted
  EmbargoTeardownAuthorizationGate emit only.
- **Per-dimension adjudication with a filtered snapshot.** Refuse each
  dimension independently; carry the participant's current value forward for
  the refused ones; record the resulting filtered `ParticipantStatus`.
- **Per-dimension adjudication plus an outbound refusal message.** As above,
  plus a new wire message telling the sender what was refused.

## Decision Outcome

Chosen option: **per-dimension adjudication with a filtered snapshot**.

`FilterParticipantStatusDimensionsNode`
(`vultron/core/behaviors/status/nodes/dimension_filter.py`) adjudicates `rm`,
`vfd` and `pxa` separately, then publishes a filtered `ParticipantStatus` in
which each refused dimension carries the participant's current value forward.
That filtered object is what gets persisted, appended to the participant, and
snapshotted in the canonical ledger entry. It runs as a read-only precondition
guard of `add_participant_status_tree`, replacing
`CheckParticipantRMNotClosedNode`.

Per-dimension rules:

- `rm` — accepted when it confirms the current value, is a valid adjacent
  transition, or is a monotone forward jump. `RM.CLOSED` is terminal: once a
  participant has closed, no further `rm` value is accepted, *including*
  `CLOSED` again.
- `vfd` and `pxa` — each is a triple of independent one-way latches
  (`v→V`, `f→F`, `d→D`; `p→P`, `x→X`, `a→A`). Accepted when no component
  regresses from uppercase back to lowercase.
- `em` — not adjudicated here. Embargo state is EmbargoTeardownAuthorizationGate's (`add_case_status_tree`,
  RSH-02-001); StatusAdoptionGate adjudicating it would duplicate and could contradict
  EmbargoTeardownAuthorizationGate's decision. Tracked in ISSUE-2256.

> **Amended by ISSUE-2906 (2026-09-01).** Per-dimension rules are necessary but
> not sufficient. Adjudicating each dimension on its own cannot see a claim that
> is impossible only *in combination*. A snapshot can pass every rule above and
> still describe a state no sequence of events could produce — a fix reported
> *ready* or *deployed* by a participant whose `rm` has not reached acceptance,
> or a fix *deployed* without being *ready*.
>
> A final pass therefore evaluates the cross-machine entailments — RM↔VF and
> RM↔D (CSB-18-001) and VF↔D (CSB-17-001) — and refuses the dimension whose
> asserted value *moved*, carrying the current value forward like any other
> refusal (RSH-05-020). Which side gets refused is load-bearing: VF↔D constrains
> a pair, and refusing the incumbent side carries its value straight back, which
> would leave the impossible combination recorded while reporting a refusal that
> changed nothing. A dimension the sender omitted is never reported as refused.
>
> The pass runs on the *effective* post-adjudication state so a refused or
> carried-forward `vf` cannot license the `d` the sender paired it with. For `rm`
> this is not a tightening — `rm` is refused only when the asserted value is not
> a forward move, so the carried value always ranks at or above the asserted one
> on the RM progress scale.
>
> Emit and receive share one evaluator, `cross_machine_violations()` in
> `vultron/core/states/cross_machine_invariants.py`. Before this amendment the
> receive path composed only VF↔D by hand while the emit path composed all
> three, so an assertion the actor would have refused to *emit* was accepted,
> hash-chained and replicated when it arrived from a peer instead.
>
> The guarantee is conditional: if the participant's current state satisfies the
> entailments, so does the recorded state. An already-impossible incumbent state
> cannot be repaired by refusing a dimension, because every carry-forward writes
> the offending value back; that case is logged instead. It is reachable via the replica-apply path, which detects the violation,
> emits `Create(ProcessingFault)`, and refuses the entry (RSH-05-021).
>
> This does **not** narrow the monotone-forward rule above: multi-step `vf`, `d`
> and `pxa` advances remain accepted (CSB-16-001), because a peer may have
> advanced several steps between status messages. Nor does it treat an absent
> dimension as an initial state — a non-VENDOR participant has no vendor path
> (ADR-0075), so no entailment applies through it, and a first observation of a
> dimension is accepted when nothing contradicts it.
>
> Under the ADR-0075 VFD split the `vfd` rule above now reads as two independent
> dimensions, `vf` (`v→V`, `f→F`) and `d` (`d→D`).

The refusal is made visible through the canonical ledger rather than a new wire
message: the committed entry snapshots the accepted portion, so it differs from
what the sender asserted and every participant sees the receiver's actual view.
No new message type is introduced (an outbound refusal is deferred; see
ISSUE-2255 for the separate problem that the HTTP response is `202 Accepted`
regardless of outcome).

A status update whose accepted portion is indistinguishable from the
participant's current state is refused *in full* — nothing appended, no ledger
entry committed. Such an assertion carries no acceptable information, and
recording it would grow both the status history and the hash chain with no
state change.

On the replica side, `ApplyParticipantStatusFromLedgerNode` enforces two
invariants. First, the RM ratchet (RSH-05-007): an `Announce(CaseLedgerEntry)`
that would move the local `rm` backwards has that dimension carried forward at
the local value, while every other dimension is applied as the entry describes
it. Lateral moves at the same rank (`VALID` ↔ `INVALID`, `DEFERRED` ↔
`ACCEPTED`) are the Case Actor re-adjudicating, not a regression, and are
applied unchanged. Second, the composite-state fault (RSH-05-021): if the
entry's effective state violates `composite_state_violations()`, the tree MUST
NOT apply the status and MUST emit `Create(ProcessingFault)` with failure class
`StatusAssertionRefused/ImpossibleState` to the CaseActor.

### Consequences

- Good, because a refused dimension no longer destroys accepted state, and no
  longer kills the StatusAdoptionGate → EmbargoTeardownAuthorizationGate emit or embargo teardown.
- Good, because the canonical ledger — the thing that actually replicates — now
  records what the receiver believes rather than what the sender claimed.
- Good, because the guard is read-only with respect to the DataLayer, so it
  fits CLP-10-006 ordering and can run before the commit.
- Good, because a `RM.CLOSED` participant can still report VFD/PXA progress.
- Bad, because the sender still gets no explicit signal that a dimension was
  refused; it must observe the canonical ledger. The HTTP-status half of that
  gap is ISSUE-2255.
- Bad, because the guard-to-append handoff uses the py_trees blackboard, which
  is process-global and not cleared between executions. Both keys are therefore
  written on every tick (with `None` when inapplicable) and matched by object ID
  on read. This is a real hazard, not a hypothetical one.
- Neutral, because `CheckParticipantRMNotClosedNode` was removed (along with
  `ValidateCaseStatusTransitionNode`, its CaseStatus counterpart) per the
  project's no-backwards-compat-shims policy. Both nodes are superseded by
  their respective per-dimension filter replacements.

## Validation

`test/core/behaviors/status/test_partial_accept_participant_status.py` covers
each rule: a refused `rm` with accepted `vfd`/`pxa`, survival of the EmbargoTeardownAuthorizationGate
emit, the ledger snapshot carrying the accepted `rm`, a `RM.CLOSED` participant
advancing `vfd`, whole-update refusal committing no entry, and the replica-side
RM ratchet.

For the ISSUE-2906 amendment: `vf=VF` and `d=D` each refused against a
pre-acceptance effective `rm` and accepted once `rm` reaches acceptance; a VF↔D
violation refusing the side that moved rather than an incumbent `d`; an omitted
dimension never named as refused; a refusal retiring one violation not
triggering a second on a stale one; no dimension named twice; the refusal
staying per-dimension; an end-to-end run confirming the refused value never
reaches the committed `payloadSnapshot`; and a ratchet asserting the emit path
still delegates to the shared evaluator.

## Pros and Cons of the Options

### Keep all-or-nothing, but return SUCCESS on refusal

- Good, because it is a one-line change that unblocks embargo teardown.
- Bad, because accepted dimensions are still silently discarded — the
  liberal-accept violation remains.
- Bad, because the canonical entry would still snapshot the raw assertion.

### Per-dimension adjudication with a filtered snapshot

- Good, because it matches the actual structure of the data: independent state
  machines adjudicated independently.
- Good, because it makes the refusal visible in the one artifact that is
  replicated and hash-chained.
- Neutral, because it needs a guard→append handoff channel; the blackboard is
  the available mechanism and carries the leakage hazard noted above.

### Per-dimension adjudication plus an outbound refusal message

- Good, because the sender learns immediately and precisely what was refused.
- Bad, because it introduces a new wire message type and its authorization
  semantics — a much larger surface than the bug requires.
- Bad, because a refusal message invites refusal loops between peers that
  disagree; that needs its own design.

## More Information

- ISSUE-2235 — the bug this decision resolves.
- ISSUE-2229 — liberal-accept epic (Postel's maxim).
- ISSUE-2255 — receive path returns `202 Accepted` regardless of BT outcome.
- ISSUE-2256 — EmbargoTeardownAuthorizationGate `em` adjudication.
- ADR-0046 — two-gate authorization model.
- `notes/sync-ledger-replication.md` — monotonic visibility and the
  reject-on-divergence invariants.

Generated spec requirements: `received-status-handling.yaml` RSH-05-001 through
RSH-05-008. The same per-dimension adjudication decision was subsequently
extended to `Add(CaseStatus)` (EM and PXA dimensions only): RSH-05-015 through
RSH-05-019 (ISSUE-2256, ISSUE-2671).
