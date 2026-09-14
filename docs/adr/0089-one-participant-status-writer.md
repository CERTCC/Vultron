---
status: accepted
date: 2026-09-14
deciders: [adh, Claude Opus 5]
consulted: []
informed: []
---

# ADR-0089: One `ParticipantStatus` Writer, and Pre-Case RM State Belongs to `ReportCaseLink`

## Context and Problem Statement

ADR-0086 composed every rule governing a `ParticipantStatus` write into one
evaluator, `participant_transition_violations()`, and required every validating
node to call it (BTND-10-002). CONCERN-3111 recorded that two writers stayed
outside it and asked whether to consolidate them.

Scoping the concern found seven writers, not two — and three of them are
invisible to the ratchet that was built to discover the population:

| Writer | Validates | Discovered by the ratchet? |
|---|---|---|
| `CreateParticipantStatusNode` | the whole rule set | yes |
| `CaseParticipant.append_rm_state()` | RM adjacency only | yes, declared |
| `as_CaseParticipant.append_rm_state()` | RM adjacency only | yes, declared |
| `_ReportPhaseRMTransition._write_latch()` | RM adjacency only | yes, declared |
| `common.py::_get_or_create_accepted_status()` | **nothing** | **no** |
| `owner.py::_build_owner_initial_status()` | **nothing** | **no** |
| `case_proposal_received_tree.py::_build_bootstrap_statuses()` | **nothing** | **no** |

`test_no_undeclared_participant_status_validator` flags a module only when it
*both* names a member predicate *and* constructs a dimension object. A writer
that validates nothing names no predicate, so it is never flagged. The detector
therefore catches partially-validating writers and misses wholly-unvalidated
ones — the worse of the two.

Two further findings shaped the decision.

**The type has two jobs.** Most `ParticipantStatus` records are rungs on a
participant's ladder, held in `CaseParticipant.participant_statuses`. But
`_ReportPhaseRMTransition` writes a standalone record under a deterministic id
derived from `(actor, report, rm_state)`, and code asks "does that id exist?" to
answer "has this step happened?". It exists because RM state starts when a
report arrives, and the case may not exist yet — or ever: a receiver may declare
a bare report `INVALID` or `CLOSED` and never propose a case.

**The two jobs are already entangled.** `_build_owner_initial_status()` reuses
the marker's *id* when building the participant's first ladder rung, so marker
and rung become one record. `_get_or_create_accepted_status()` goes further: it
assigns directly to a stored `ParticipantStatus` (`existing.cvd_role = …`,
`existing.consent = …`, `existing.context = …`) and saves it — the
post-construction mutation door `notes/domain-validation.md` documents — and
creates the record outright when it is absent. So the marker is not a
side-channel; it is the pre-case home of participant RM state, later adopted
into the ladder by id reuse.

Two questions follow. Where does pre-case RM state belong? And how is the single
writer reached, given that its callers reach it three different ways today?

## Decision Drivers

- One type, one job. A class serving two jobs cannot have one writer, and the
  next reader cannot tell which job a given record is doing.
- One way to do a thing. Where two mechanisms exist for one purpose, both must
  be maintained and tested, and they drift. This is the DRY driver ADR-0087
  states for itself and CS-22-001 states project-wide.
- The ratchet must be able to see every writer. A structural detector that a
  writer can escape by validating *less* inverts the incentive.
- ADR-0041 already owns the pre-case window. It created
  `VultronReportCaseLink(status=PENDING_PROPOSAL)` for exactly the interval
  between report receipt and case creation.
- The cost of the rule must be measured, not assumed. CONCERN-3111 named an
  "unmeasured blast radius" as a reason not to act.

## Considered Options

Where pre-case RM state belongs:

- **Move it onto `ReportCaseLink` and delete the marker.**
- **Add a fourth ADR-0087 disposition** so the writer can run with no case, and
  keep the marker as a `ParticipantStatus`.
- **Revive the proto-case (ADR-0015)** — create a real case at report receipt
  with the receiver as sole participant, then hand the `CASE_MANAGER` role to a
  CaseActor when the case is formalised.
- **Give the marker its own type**, leaving it outside the writer but no longer
  able to be confused with participant state.

How the single writer is reached:

- **Always a real tree child.**
- **Always nested** — built and ticked inside a wrapper node's `update()`.
- **Two writers sharing one evaluator**, as the receive and replica-apply paths
  already do.

## Decision Outcome

Chosen: **move pre-case RM state onto `ReportCaseLink` and delete the marker**,
and **reach the writer only as a real tree child**.

### `ParticipantStatus` becomes ladder-only

`VultronReportCaseLink` gains the report-scoped RM state. The marker record and
its three supporting helpers — `_report_phase_status_id()`,
`report_phase_context()` and `_current_report_phase_rm_state()` — are deleted.

This is subtractive. `_current_report_phase_rm_state()` reads up to six
deterministic ids to find the highest-progress state; a field is one read. The
idempotency check in `CheckRMStateValid` becomes `link.rm_state == RM.VALID`
instead of "does this id exist". The id-reuse promotion in
`_build_owner_initial_status()` disappears: once the case exists, the CaseActor
creates the participant (ADR-0041) and local RM state arrives with the replica.

Crucially, it makes the fourth ADR-0087 disposition unnecessary. The writer
always has a case, because state written when there is no case is no longer a
`ParticipantStatus` at all.

### One writer, always a tree child

`CreateParticipantStatusNode` is the only writer. It is always a real child of a
tree, never constructed and ticked inside another node's `update()`.

Five sites do the nested thing today (`deploy_fix.py`, `develop_fix.py`,
`close_case_effect.py`, and twice in `leave.py`). A nested `update()` call skips
`setup()` and the tick cycle, and `deploy_fix.py` wraps it in `try/except` —
the failure-swallowing shape `notes/bt-integration.md` warns about. Six further
nodes bypass the writer entirely and call `update_participant_rm_state()`
instead; five of those six do nothing else and are deleted rather than
converted.

### One way to supply each input

- **`case_id` is always the blackboard port.** `CreateParticipantStatusNode`
  loses its `case_id` constructor argument and mixes in
  `CaseIdInputPortMixin`. A port is the only mechanism that works everywhere:
  in received trees the case is discovered at tick time by dereferencing the
  report. Trees that know the case at build time seed `/case_id` through
  `BTBridge.execute_with_setup(**context_data)`.
- **The subject actor is always explicit.** The blackboard `actor_id` is the
  *executing* actor; the subject of the write is frequently someone else — the
  deferring actor, the sender, the leaver. Conflating them was bug #2300.
  `_ReportPhaseRMTransition._acting_actor_id()`'s
  `self.sender_actor_id or self.actor_id` fallback is removed: it is the
  two-path shape this decision exists to eliminate.

One mechanism per input, so there is no second path to test.

### The ratchet fires on construction, not on validation

The detector's gate changes from "names a member predicate **and** builds a
dimension" to "**builds a participant dimension**". Validating less no longer
buys invisibility. The widened detector lands first, with every
then-remaining writer declared, so the exclusion list can only shrink as the
work proceeds. It ends holding two entries, both deliberate: the receive path
(`_adjudication.py`, ADR-0061) and the replica-apply path
(`participant_status_effect.py`, RSH-05-021).

### Blast radius: measured, and zero on legal data

CONCERN-3111 feared that applying the whole rule set to an RM-only write would
newly enforce the cross-machine entailments, with unknown cost. Enumerating
`composite_state_violations()` over every `(RM, vf, d)` triple settles it.

The entailments fire only when the F bit or the D bit is set *and* RM is not in
`{ACCEPTED, DEFERRED, CLOSED}`. Three of the converted sites write `ACCEPTED`,
`DEFERRED` or `CLOSED`, so they cannot fire. The other two write `VALID` and
`INVALID`; `VALID` is reachable only from `RECEIVED` or `INVALID`, `INVALID`
only from `RECEIVED`, and `RECEIVED` only from `START`. Reaching a fix-ready
`vf` requires having passed `ACCEPTED`, and RM never walks back to `RECEIVED`.
So no legal state can present a fix-ready or deployed value at those targets.

The only combinations that remain refusable are `(vf, D)` and `(Vf, D)` —
deployed before ready. Those states are already corrupt; refusing them is a fix,
and repairing them is the receive path's job (RSH-05-020).

### Consequences

- Good, because `ParticipantStatus` gets one job and one writer, so the
  divergence CONCERN-3111 describes becomes unrepresentable rather than merely
  repaired.
- Good, because the change is net subtractive: three helpers, one marker record
  shape, six nodes, two model mutators, and one dead module are removed.
- Good, because the ratchet can no longer be escaped by validating less.
- Good, because ADR-0087 does not grow a fourth regime.
- Good, because the id-reuse promotion between marker and ladder — a mechanism
  no requirement described — disappears.
- Bad / accepted cost: about 35 test call sites use
  `CaseParticipant.append_rm_state()` as an arrange step and must move to a
  test-side builder.
- Bad / accepted cost: eleven call sites change tree shape, and the five
  formerly-nested sites gain a sibling node where they had an inline call.
- Bad / accepted cost: records already stored under the old marker ids are not
  migrated. This is consistent with ADR-0041, which removed the back-fill nodes
  rather than migrating.

## Validation

- `test/architecture/test_participant_status_validation.py` — the widened
  detector fires on any module constructing a participant dimension; the
  exclusion list ends at two entries.
- A new ratchet assertion pins that `CreateParticipantStatusNode` is never
  constructed inside another node's `update()`.
- A new ratchet assertion pins the two input rules: no `case_id` constructor
  argument, and no fallback from an explicit subject actor to the blackboard
  `actor_id`.
- The entailment enumeration above is committed as a test, so the
  zero-blast-radius claim cannot silently stop being true.

## Pros and Cons of the Options

### Move pre-case RM state onto `ReportCaseLink` (chosen)

- Good, because `ReportCaseLink` already exists for this window under ADR-0041.
- Good, because it is subtractive — no new type, no new ADR-0087 regime.
- Good, because a field read replaces a six-id scan.
- Neutral, because it moves report-scoped state onto the report-scoped record,
  which is a relocation rather than a new concept.
- Bad, because stored marker records become unreadable.

### Fourth ADR-0087 disposition

- Good, because the marker keeps working unchanged.
- Bad, because it adds a regime to a policy whose value is that it enumerates a
  closed set, and requires the writer to run with neither a case nor a
  participant.
- Bad, because `ParticipantStatus` keeps two jobs, so "one writer" stays a
  statement about one of them.

### Revive the proto-case (ADR-0015)

- Good, because it removes the pre-case window entirely: there is always a case.
- Bad, because ADR-0041 supersedes ADR-0015 for precisely this. Its stated
  reason is the architecture gap created when the vendor creates the case object
  before the authoritative CaseActor exists.
- Bad, because the later `CASE_MANAGER` handoff it depends on is the step
  ADR-0041's "what is removed" list deletes from initialisation.

### Give the marker its own type

- Good, because the two jobs could never be confused again.
- Bad, because it adds a model type and a storage shape to hold state that
  `ReportCaseLink` is already positioned to hold.

### Always nested, or two writers sharing one evaluator

- Good, because both leave existing tree shapes alone.
- Bad, because nesting skips `setup()` and the tick cycle and invites the
  `try/except` that swallows a child's failure.
- Bad, because both preserve more than one write path, which is the property
  this decision removes.

## More Information

Source: CONCERN-3111, scoped under epic #2684. Supersedes CONCERN-3111 §2's
conclusion that the report phase is "a deliberate separate lifecycle": the
id-reuse promotion in `_build_owner_initial_status()` and the in-place backfill
in `_get_or_create_accepted_status()` show one lifecycle at two stages. This
decision resolves that by making the earlier stage stop using the later stage's
type.

Related decisions: ADR-0086 (one evaluator, report every violation),
ADR-0061 (receive-path per-dimension adjudication), ADR-0087 (case-resolution
dispositions), ADR-0041 (CaseActor-authoritative initialization, superseding
ADR-0015), ADR-0075 (role-owned dimensions), ADR-0033 (lifecycle-staged types).

Generated spec requirements: `specs/behavior-tree-node-design.yaml` BTND-10-002
(amended) and BTND-10-004 through BTND-10-006; `specs/report-management.yaml`
RM-pre-case entry for `ReportCaseLink`. Design notes:
`notes/domain-validation.md`.
