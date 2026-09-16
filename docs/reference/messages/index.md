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
  [ActivityPub how-to guides](../../howto/activitypub/activities/index.md).

The mapping between the two is **many-to-many in both directions**, and roughly
half the wire vocabulary has no formal shorthand at all. A shorthand and a wire
activity are not interchangeable names for one thing. The design rationale for
keeping the two vocabularies distinct is recorded in
[ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md).

## The pages

Each page opens with a rendered mapping table and then gives one section per
message type, stating protocol role, triggering transition, the wire activity
that conveys it, any discriminating payload field, and a rendered example.

| Page | Covers |
|---|---|
| [Report Management (RM)](rm.md) | `RS RI RV RD RA RC RK RE` |
| [Embargo Management (EM)](em.md) | `EP ER EA EV EJ EC ET EK EE` |
| [Case State (CS)](cs.md) | `CV CF CD CP CX CA CK CE` |
| [General (GI)](general.md) | `GI GK GE` |
| [Faults and Acknowledgements](faults_and_acknowledgements.md) | fault trichotomy; cumulative hash-chain ACK |
| [Case Management](case_management.md) | case lifecycle, participant roster, ownership transfer |
| [Case Proposal](case_proposal.md) | pre-case bootstrap (ADR-0023) |
| [Ledger Replication](ledger_replication.md) | SYNC substrate (ADR-0077) |

## How to read the mapping tables

Every row joins one `MessageSemantics` wire activity to its formal shorthand(s).
The **Status** column states the kind of relationship:

| Status | Meaning |
|---|---|
| `direct` | One shorthand maps to exactly one wire activity. |
| `collapse` | Several shorthands share one wire activity. Multiple shorthands appear in a single row; the **Discriminator** column names the payload field (or context) that distinguishes them. |
| `expansion` | One shorthand is realized by several wire activities. The same shorthand appears in more than one row. |
| `evolved` | The shorthand's purpose is served by a mechanism partitioned on a different axis (fault reporting or cumulative acknowledgement), not by a dedicated wire activity. |
| `—` | The wire activity has no formal shorthand counterpart. |

Reading the many-to-many relationship from a table:

- **Multiple shorthands in one row** is a collapse — for example `CP CX CA`
  ride a single `Add(CaseStatus)`, discriminated by `pxa_state`.
- **One shorthand across multiple rows** is an expansion — for example `EP`
  spans four embargo wire activities.

The `evolved` shorthands (`RE`, `EE`, `CE`, `GE`, `EK`, `CK`, `GK`) have no
dedicated wire activity. Faults are conveyed by `Create(ProcessingFault)`,
`as:Reject`, or `Create(Note)`, partitioned by failure mode. Acknowledgement of
ledger-replicated state is cumulative and implicit through hash-chain continuity;
`RK` survives as a real wire activity because report submission is not
ledger-replicated. See
[ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)
for the full treatment.
