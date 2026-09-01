---
status: accepted
date: 2026-09-01
deciders: sei-ahouseholder
consulted: sei-ahouseholder
informed: Vultron contributors
---

# The Formal Message Set and the AS2 Wire Vocabulary Are Deliberately Different Shapes; the Mapping Is the Reconciling Artifact

## Context and Problem Statement

Vultron has two message vocabularies. The formal protocol
([Message Types](../reference/formal_protocol/messages.md)) defines 28 shorthand
symbols partitioned by which state machine a message belongs to: RM, EM, CS, and
General. The implementation has a `SEMANTIC_REGISTRY` of AS2 wire activities,
each pairing an `ActivityPattern` with a `MessageSemantics` value, an event
class, a use case, and a rendering phrase.

These two sets do not correspond one-to-one, and until now nothing said so
plainly. The prevailing implicit assumption — that a shorthand and a wire
activity are two names for one thing — is wrong in three distinct ways, and it
has already produced a normative defect and a documented-but-never-built wire
format.

Concretely, at the time of this decision:

- Several shorthands **collapse** onto one wire activity. `CV` and `CF` both ride
  `as_ParticipantStatus.vf_state`; `CP`, `CX`, and `CA` all ride
  `as_CaseStatus.pxa_state`; `EV`, `EJ`, and `EC` are sent as `EP`, `ER`, and
  `EA`. The discriminator is a *payload field*, not the activity type.
- Several shorthands **expand** into many wire activities. `EP` is realized by
  four; `GI` covers the whole note lifecycle *and* the actor-suggestion
  handshake. The `Create(X)` + `Add(X → Y)` split is itself an expansion with no
  formal counterpart at all.
- Roughly half the registry has **no formal counterpart**: case lifecycle,
  participant roster, invitations, role delegation, ownership transfer, case
  proposal, and ledger replication.

Two consequences of the unstated assumption were already live defects.
MSM-03-001 through MSM-03-003 asserted at `MUST` that `CV`, `CF`, and `CD`
dispatch as `ADD_CASE_STATUS_TO_CASE` and that `as_CaseStatus` carries
`vendor_aware` / `fix_ready` / `fix_deployed` payload flags. No such fields exist;
the V/F/D dimensions are participant-scoped and live on `as_ParticipantStatus`
per [ADR-0075](0075-split-vfd-state-machine.md). And
`howto/activitypub/activities/error.md` documents a four-way wire fault taxonomy
(`RmError`, `EmError`, `CsError`, `GmError`, discriminated by `as:inReplyTo`)
that exists in no ontology file and no code, while
`ActivityPattern.in_reply_to_` is used by no registered pattern.

The question this ADR settles: is the divergence a defect to be driven to zero,
or a deliberate property to be documented?

## Decision Drivers

- The formal message set is normative and versioned with the protocol
  specification; it must remain stable for interoperability and conformance
  claims.
- The AS2 wire vocabulary must remain idiomatic ActivityStreams, reusing existing
  verbs rather than minting Vultron-specific ones.
- Implementers need one place that answers "what is this message, when is it
  sent, what does it look like on the wire, and where do I handle it."
- Silent divergence between the two sets has already produced a wrong `MUST`
  requirement and a phantom wire format. Whatever is chosen must make divergence
  visible rather than merely absent.
- Hand-maintained correspondence tables in this project have a demonstrated
  failure record.

## Considered Options

- Treat the divergence as deliberate and make the mapping a first-class,
  rendered artifact
- Force the wire vocabulary to mirror the formal message set one-to-one
- Retire the formal message set and treat the wire vocabulary as the only
  message definition
- Leave both sets as they are and document neither the mapping nor the divergence

## Decision Outcome

Chosen option: **treat the divergence as deliberate and make the mapping a
first-class, rendered artifact**, because the two sets are answering different
questions and flattening either one onto the other destroys information that the
protocol needs.

The formal set partitions by **which state machine** a message concerns, which is
the right axis for reasoning about protocol conformance and for the transition
tables. The wire vocabulary partitions by **what ActivityStreams verb and object
faithfully express the act**, which is the right axis for interoperability with
ActivityPub tooling. Neither axis is derivable from the other, so the mapping is
irreducible and belongs in the specification rather than in a reader's head.

Three commitments follow.

**1. The mapping is normative and bidirectional.**
`specs/message-semantics-mapping.yaml` (MSM) is the authoritative bridge. It
records collapses and expansions explicitly, and every row carries a status
saying which kind of relationship it is. MSM-04 adds the General shorthands that
were previously absent from the corpus.

**2. Fault and acknowledgement mechanisms are partitioned on their own axes, and
that is recorded rather than treated as a gap.** MSM-05 specifies both:

- Faults are partitioned by **failure mode**, not by state machine:
  `Create(ProcessingFault)` for received-but-not-understood, `as:Reject` for
  understood-but-declined, and `Create(Note)` / `Add(Note → Case)` for a
  condition needing narrative explanation. Failure mode is actionable to a
  receiver in a way that originating state machine is not, which is why the
  formal `RE`/`EE`/`CE`/`GE` partition was not reproduced.
- Acknowledgement of ledger-replicated state is **cumulative and implicit** via
  hash-chain continuity: a matching `prev_log_hash` is the acknowledgement, and a
  mismatch triggers `Reject(CaseLedgerEntry)` and gap-fill replay. Per-message
  `EK`/`CK`/`GK` would be redundant. `RK` survives as a real wire activity
  because report submission is not ledger-replicated.

Both were previously recorded in MSM only as absences ("no AS2 wire
representation"), which invited the reading that the behaviour was
unimplemented. It is implemented; it is shaped differently.

**3. Reference material is rendered from the registries, never hand-written.**
The consolidated per-message-type pages under `docs/reference/messages/` render
their mapping tables at build time from the MSM spec registry joined against
`SEMANTIC_REGISTRY`, following the existing `docs/reference/specs/*.md` pattern.
A ratchet asserts every registry entry appears on exactly one page.

### Consequences

- Good, because the collapses become documented facts rather than traps. An
  implementer reading the `CS` page learns that six shorthands share two wire
  activities and which payload field discriminates them.
- Good, because the wire vocabulary can evolve toward better ActivityStreams
  idiom without being pinned to the formal set's partitioning, and the formal set
  can stay stable for conformance without being dragged by prototype churn.
- Good, because divergence is now detectable. A new registry entry with no MSM
  row, or an MSM row with no registry entry, fails a check instead of quietly
  becoming a stale table.
- Good, because it caught the MSM-03 defect: the mapping could not be rendered
  correctly from an incorrect spec, which forced the error into the open.
- Bad, because there are now two vocabularies a contributor must learn, and the
  mapping is a third artifact to keep correct.
- Bad, because the mapping is genuinely many-to-many, so no simple lookup table
  suffices and the reference pages must carry per-row status annotations to be
  honest.
- Neutral, because the divergences MSM-05 records are now visible enough to
  reopen deliberately. Whether `messages.md` should grow new message types for
  the currently-unmapped wire activities, or restate its error and
  acknowledgement partitioning, is a normative-specification question this ADR
  makes askable without answering.

## Validation

- `spec-lint` validates MSM structure and cross-references, including that every
  cited ADR and spec ID resolves.
- `test/test_message_semantics_mapping.py` asserts the MSM-04 and MSM-05 claims
  against the live registry: that `GI` expands across the note lifecycle and the
  actor-suggestion exchange, that no dispatch value is named for `GK`/`GE`/`EK`/
  `CK`, that the three fault mechanisms are all registered, that the ledger NAK
  path exists, and that `as:Reject` is overloaded across error and ordinary
  refusal.
- The MSM-06 ratchet asserts every `SEMANTIC_REGISTRY` entry appears on exactly
  one reference page, with `unknown` and `unknown_unresolvable_object` as the
  declared exemptions.
- Because the mapping tables are rendered from the registries rather than
  authored, table-versus-code drift is structurally impossible rather than
  merely tested for.

## Pros and Cons of the Options

### Treat the divergence as deliberate and make the mapping a first-class artifact

- Good, because each vocabulary stays optimal for its own purpose.
- Good, because it is the only option that can express a many-to-many
  relationship without losing information.
- Good, because it makes the unmapped regions visible and therefore schedulable.
- Bad, because it institutionalizes a translation layer that must be maintained.

### Force the wire vocabulary to mirror the formal message set one-to-one

- Good, because a single vocabulary is simpler to learn.
- Bad, because it is not achievable without damage in either direction. Splitting
  `Add(CaseStatus)` into `CP`/`CX`/`CA` variants would mint three Vultron-specific
  activities where ActivityStreams already has one adequate verb, violating the
  design goal in `howto/activitypub/activities/index.md` of not creating
  activity types when an existing type suffices.
- Bad, because the reverse direction would require the formal set to absorb
  roughly 28 case and roster mechanics it deliberately does not model as
  messages, plus the `Create`/`Add` object-lifecycle split, which is a wire
  concern with no protocol meaning.
- Bad, because it cannot represent the V/F/D scope asymmetry at all: a
  case-scoped `CV` message cannot say which vendor became aware.

### Retire the formal message set and treat the wire vocabulary as the only message definition

- Good, because it removes the mapping entirely.
- Bad, because the formal set is the basis of the transition tables, the
  behavioral conformance specs, and any conformance claim; the wire vocabulary is
  a prototype artifact that changes far more often.
- Bad, because it would make protocol conformance depend on the current shape of
  one implementation's dispatch registry.

### Leave both sets as they are and document neither

- Bad, because this is the status quo that produced the MSM-03 defect and the
  phantom `RmError` taxonomy. The divergence exists whether or not it is written
  down; leaving it unwritten only removes the opportunity to notice when it is
  wrong.

## More Information

Design rationale, the full collapse and expansion inventory, the page
architecture, and the MSM-03 post-mortem are in `notes/message-type-reference.md`
(repository-only; not published to the docs site).

Related decisions: [ADR-0075](0075-split-vfd-state-machine.md) (the V/F/D split
that MSM-03 predated), [ADR-0036](0036-status-dimension-objects.md) (dimension
objects), [ADR-0039](0039-offer-case-participant-role-wire-type.md)
(role-delegation wire format), [ADR-0023](0023-case-proposal-protocol.md)
(case proposal), and
[ADR-0077](0077-ledger-replication-companion-spec.md) (ledger replication).

Source: IDEA-605.

Generated spec requirements: `message-semantics-mapping.yaml` MSM-04 through
MSM-06, and the corrections to MSM-01-007, MSM-02-008, MSM-02-009, MSM-03-001
through MSM-03-003, MSM-03-007, and MSM-03-008.
