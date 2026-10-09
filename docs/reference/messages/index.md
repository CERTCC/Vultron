---
description: >
  How the formal message set relates to the ActivityStreams 2.0 (AS2) wire
  vocabulary the prototype sends and receives.
stakeholder_type: [platform-developer]
level: 400
contents: generated
---

# Message Types

Vultron describes its protocol messages in two vocabularies, and they do not
correspond one-to-one:

- The **formal message set** is 28 shorthand symbols, partitioned by which state
  machine a message belongs to — Report Management (RM), Embargo Management (EM),
  Case State (CS), and General (GI). It is normative and versioned with the
  protocol. See [Message Types](../formal_protocol/messages.md) and
  [Transitions](../formal_protocol/transitions.md).
- The **AS2 wire vocabulary** is the set of ActivityStreams 2.0 (AS2) activities
  the prototype sends and receives, keyed by `MessageSemantics`. See the
  [Vultron AS Activity Guides](../../howto/activitypub/activities/index.md).

The mapping between the two is **many-to-many in both directions**, and roughly
half the wire vocabulary has no formal shorthand at all. A shorthand and a wire
activity are not interchangeable names for one thing. The design rationale for
keeping the two vocabularies distinct is recorded in
[ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)
and explained in
[Activity Vocabulary Design](../../topics/activity_vocabulary_design.md), which
also covers the verb choices and the `Create`/`Add` split that produce the
collapses and expansions cataloged here.

## The pages

Each page opens with a rendered mapping table and then gives one section per
message type, stating protocol role, triggering transition, the wire activity
that conveys it, any discriminating payload field, and a rendered example.

<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml nav or a listed page's description: frontmatter, then run `uv run docs-site --write` -->

- [Report Management (RM)](rm.md) — Wire activities for the Report Management message types RS, RI, RV, RD, RA, RC, RK, and RE.
- [Embargo Management (EM)](em.md) — Wire activities for the Embargo Management message types EP, ER, EA, EV, EJ, EC, ET, EK, and EE, and the Case Owner's decision on a proposal.
- [Case State (CS)](cs.md) — Wire activities for the Case State message types CV, CF, CD, CP, CX, CA, CK, and CE.
- [General (GI)](general.md) — Wire activities for the General message types GI, GK, and GE.
- [Faults and Acknowledgments](faults_and_acknowledgements.md) — The fault trichotomy and the cumulative hash-chain acknowledgment.
- [Case Management](case_management.md) — Case lifecycle, participant roster, and ownership transfer activities.
- [Case Proposal](case_proposal.md) — The pre-case bootstrap exchange (ADR-0023).
- [Ledger Replication](ledger_replication.md) — The SYNC substrate that replicates the case ledger (ADR-0077).

<!-- END GENERATED SECTION CONTENTS -->

## How to read the mapping tables

Every row joins one `MessageSemantics` wire activity to its formal shorthand(s).
The **Status** column states the kind of relationship:

| Status | Meaning |
|---|---|
| `direct` | One shorthand maps to exactly one wire activity. |
| `collapse` | Several shorthands share one wire activity. Multiple shorthands appear in a single row; the **Discriminator** column names the payload field (or context) that distinguishes them. |
| `expansion` | One shorthand is realized by several wire activities. The same shorthand appears in more than one row. |
| `evolved` | The shorthand's purpose is served by a mechanism partitioned on a different axis (fault reporting or cumulative acknowledgment), not by a dedicated wire activity. |
| `—` | The wire activity has no formal shorthand counterpart. |

Reading the many-to-many relationship from a table:

- **Multiple shorthands in one row** is a collapse — for example `CP CX CA`
  ride a single `Add(CaseStatus)`, discriminated by `pxa_state`.
- **One shorthand across multiple rows** is an expansion — for example `EP`
  spans four embargo wire activities.

The `evolved` shorthands (`RE`, `EE`, `CE`, `GE`, `EK`, `CK`, `GK`) have no
dedicated wire activity. Faults are conveyed by `Create(ProcessingFault)`,
`as:Reject`, or `Create(Note)`, partitioned by failure mode. Acknowledgment of
ledger-replicated state is cumulative and implicit through hash-chain continuity;
`RK` survives as a real wire activity because report submission is not
ledger-replicated. See
[ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)
for the full treatment.
