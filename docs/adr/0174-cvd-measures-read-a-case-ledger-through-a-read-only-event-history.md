---
status: proposed
date: 2026-11-04
created: 2026-11-04
updated: 2026-11-04
revision: 1
deciders: Allen D. Householder
consulted: []
informed: []
stakeholder_type: [project-contributor]
---

# CVD Measures Read a Case Ledger Through a Read-Only Event History, Derived by State Comparison

## Context and Problem Statement

Both families of proposed CVD measures — the ordering desiderata and the in-case
timing metrics — need the same input: the case's event history, each Coordinated
Vulnerability Disclosure event labelled by participant and cause, with its time.
The case ledger already records every state change as its own entry, but nothing
turns those entries into an event history, so the existing scoring code in
`vultron/core/case_states/hypercube.py` has no source of real histories to score.

Deciding how to get from a ledger to an event history settles several things at once:
what the layer reads, where it sits relative to the protocol, how an event is
recognised, and what shape it hands to a consumer. Each had a plausible alternative,
and three of them interact with decisions the protocol has already made — in
particular ADR-0075, which split per-participant vendor-path and deployer-path
tracking apart, and ADR-0060, which kept the legacy hypercube as a reference oracle
rather than a protocol path.

## Decision Drivers

- A measure must be computable over an archived ledger, a committed demo recording,
  or another deployment's ledger — not only a live store.
- A measure over a history with a hole is **wrong**, not imprecise, so the layer has
  to be able to say "I cannot answer" rather than return a plausible number.
- Analysis code must not be able to change what it measures, nor reach the protocol
  path.
- One ledger format should have one reader; two drift apart, and the drift shows up
  only as a state one tool reads and the other reports absent.
- The derivation must survive a multi-party case, where a participant may hold the
  Vendor role, the Deployer role, both, or neither.

## Considered Options

- **Input**: read case-ledger JSONL files, or read through the DataLayer.
- **Event recognition**: compare each entry's state against the state already
  reached, or key a table on the entry's semantic type.
- **Home**: a new read-only package outside the protocol path, or a module inside
  `vultron/demo/`, or inside `vultron/core/`.
- **Ledger copy**: prefer the CASE_MANAGER's own copy, or merge every replica
  always, or score whatever copy is handed over.
- **Case-state sequences**: project one per participant that can replay one, or one
  per participant holding the Vendor or Deployer role, or one collapsed sequence per
  case.
- **Scope**: stop at the validated sequence, or also compute the desiderata score.

## Decision Outcome

Chosen options, each with the alternative it rejects:

**Read case-ledger JSONL, not the DataLayer.** A file is readable offline, so one
measure implementation serves an archived ledger, a committed recording and a foreign
deployment's ledger. A DataLayer read would need a live store and could reach none of
those.

**Recognise an event by comparing state, with the semantic type as the cause label.**
Several different protocol acts move the same state machine — accepting a stub Invite
seats a joiner, answering a full-case Invite records a verdict, a status update
reports any move, and a `Leave` walks the leaver to closed — so a table keyed on the
semantic type alone misses whichever act it omitted. Two kinds of event are the
exception and *are* derived from the semantic type and carried object, because they
are not status dimensions at all: the embargo's start and exit, and a participant's
consent answer. Joining is a third exception for a different reason — it changes no
state, so it is keyed on the acceptance entry.

**A new read-only package outside the protocol path.** Nothing in the protocol path
imports it, and it writes to no store, so an analysis change cannot reach case
behaviour and a reader cannot break a hash chain. Which package holds it is a layout
choice and is not fixed by an ADR or a spec requirement.

**Prefer the CASE_MANAGER's copy; a merge of replicas is the fallback, and it reports
its holes.** Only the CASE_MANAGER's ledger is complete: a replica stops receiving
entries while its embargo consent has lapsed and after its report closes, so an event
in a gap it missed is simply absent. The canonical copy is identified from the
entries, never from a file or directory name.

**Project a case-state sequence per participant that can replay one, keyed on the
presence of a vendor-awareness event rather than on a role.** This is the decision
that interacts with ADR-0075. That record split per-participant VFD tracking into a
nullable vendor path and a nullable deployer path precisely because the monolithic
four-state chain could not represent a Deployer-only participant. The six-event
case-state history is that monolithic form, so a participant holding the Deployer
role but not the Vendor role has no vendor-fix state of its own, cannot open a
sequence, and must not have one built for it: `vfD` has no spelling among the four
valid vendor-path states. Such a participant is reported unprojectable with a stated
reason, and its events stay in the event history. Several vendors are never collapsed
into one sequence for the case — which vendor's event stands for the case is an open
research question.

**Stop at the validated sequence; compute no score.** This is where the plan's own
first premise turned out to be wrong, and the ADR records it so the next reader does
not repeat it. The existing desiderata scorer, `CVDmodel.score_hist`, admits only a
*complete* six-event history and raises on anything shorter, while an incomplete
sequence is the normal result for a real case — every sequence derivable from the
committed recordings today is incomplete. So "hand the existing scorer a real history"
is not achievable by handing it these sequences. How an incomplete sequence earns a
score is a separate research question, and CSB-17-011 suggests the shape of an answer:
every accepted prefix has at least one valid completion among the 70 valid complete
histories, so a prefix can be scored through its completions rather than refused.

### Consequences

- Good, because a measure can be recomputed over any archived ledger without a
  running deployment, which makes a published result reproducible.
- Good, because the layer can refuse to answer. A caller gets named missing log
  indices, a named unprojectable participant, or a named excluded entry, instead of a
  number derived from a history with a hole in it.
- Good, because one tolerant reader serves both this layer and the demo ledger report
  tool, so a dimension spelling handled in one place is handled for both.
- Neutral, because the prefix check this layer runs duplicates no check the
  CASE_MANAGER performs: that actor validates a participant's dimensions and the
  case's public state separately and skips rules reading an absent dimension, so a
  fully valid ledger can still project a compound sequence that does not replay. The
  check belongs to whoever builds the compound.
- Bad, because a Deployer-only participant gets no scorable sequence at all. The
  ordering desiderata cannot speak about such a participant until the open
  multi-vendor question is settled.
- Bad, because the layer delivers no score, so the desiderata work needs a further
  decision before it can report one.

## Validation

The generated `CEH` requirements each carry a `verification:` clause naming the test
that must exist. Three structural ones are architecture tests: no module under
`vultron/core/`, `vultron/wire/` or `vultron/adapters/` imports the layer; the layer
performs no save, create or write-mode open other than a command's own output file;
and the layer exposes no score. The derivation is checked against every committed
canonical recording under `ui/src/recordings/`, with hand-built fixtures for the four
shapes no recording holds — an end-time embargo exit, a declined invitation, a
timed-out invitation, and a Deployer holding no Vendor role.

## More Information

Design reasoning that is not a decision between options — the four data-gap labels,
the two clocks, the tolerant-reader-and-strict-wrapper split, and where the code
goes — is in [notes/case-event-history.md](../../notes/case-event-history.md).

Related records: [ADR-0075](0075-split-vfd-state-machine.md) (the vendor-path and
deployer-path split this layer must respect),
[ADR-0060](0060-re-express-legacy-cs-invariants.md) (the legacy hypercube as
reference oracle, not a protocol path),
[ADR-0122](0122-per-embargo-participant-consent.md) and
[ADR-0124](0124-case-is-a-projection-of-its-ledger.md) (the ledger as the case's
source of truth), and
[ADR-0079](0079-case-ledger-causal-ordering.md) (log order is the causal order this
layer sorts by).

Generated spec requirements: `case-event-history.yaml` CEH-01 through CEH-06.
