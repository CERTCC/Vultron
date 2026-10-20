---
description: >
  How the formal message set relates to the ActivityStreams 2.0 (AS2) wire
  vocabulary the prototype sends and receives.
stakeholder_type: [platform-developer]
level: 400
contents: generated
---

# Message Types

Each row of the table below is an [occasion](../glossary.md#messaging-and-protocol): a situation in a Coordinated Vulnerability Disclosure (CVD) case that a sender conveys with a wire activity.
The row names the activity to send, whom to send it to, who may send it, and the section that documents it.
"Send to" is the addressee: the Case Manager, a participant, or, before a case exists, an actor outside any case.
"Sent by" is the standing a receiver requires of the sender of an activity sent to that addressee.
One activity sent to two addressees can therefore have two rows with different senders.
Where several rows share one activity, a field value, the receiver's Embargo Management (EM) state, the register status of the embargo the activity names, the sender's standing, or the addressee tells them apart.
The groups follow the case lifecycle, then the protocol mechanics that carry it.

{% include-markdown "./_occasions/lookup.md" %}

## Two vocabularies

Vultron describes its protocol messages in two vocabularies, and they do not correspond one-to-one:

- The **formal message set** is 28 shorthand symbols, partitioned by which state machine a message belongs to — Report Management (RM), Embargo Management (EM), Case State (CS), and General (GI).
  It is normative and versioned with the protocol.
  See [Message Types](../formal_protocol/messages.md) and [Transitions](../formal_protocol/transitions.md).
- The **AS2 wire vocabulary** is the set of ActivityStreams 2.0 (AS2) activities the prototype sends and receives, keyed by `MessageSemantics`.
  See the [Vultron AS Activity Guides](../../howto/activitypub/activities/index.md).

The mapping between the two is **many-to-many in both directions**, and roughly half the wire vocabulary has no formal shorthand at all.
A shorthand and a wire activity are not interchangeable names for one thing.
The design rationale for keeping the two vocabularies distinct is recorded in [ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md).
[Activity Vocabulary Design](../../topics/activity_vocabulary_design.md) explains it, along with the verb choices and the `Create`/`Add` split that produce the collapses and expansions cataloged here.

## The pages

Each page includes its slice of the occasion table under an Occasions heading.
One section per occasion follows, stating when it applies, the wire activity to send, whom to send it to, who may send it, the field or state that distinguishes it, its mapping status, the pages that embed it, and a rendered example.
The four formal-model pages end with a section for each shorthand that has no dedicated wire activity.

<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml nav or a listed page's description: frontmatter, then run `uv run docs-site --write` -->

- [Report Management (RM)](rm.md) — Wire activities for the Report Management message types RS, RI, RV, RD, RA, RC, RK, and RE.
- [Embargo Management (EM)](em.md) — Wire activities for the Embargo Management message types EP, ER, EA, EV, EJ, EC, ET, EK, and EE, the Case Owner's decision on a proposal, and a participant's withdrawal from the embargo in force.
- [Case State (CS)](cs.md) — Wire activities for the Case State message types CV, CF, CD, CP, CX, CA, CK, and CE.
- [General (GI)](general.md) — Wire activities for the General message types GI, GK, and GE.
- [Faults and Acknowledgments](faults_and_acknowledgements.md) — The fault trichotomy and the cumulative hash-chain acknowledgment.
- [Case Management](case_management.md) — Case lifecycle, participant roster, and ownership transfer activities.
- [Case Proposal](case_proposal.md) — The pre-case bootstrap exchange (ADR-0023).
- [Ledger Replication](ledger_replication.md) — The SYNC substrate that replicates the case ledger (ADR-0077).

<!-- END GENERATED SECTION CONTENTS -->

## Mapping status

Each occasion section states its entry's **mapping status**, the relationship between the wire activity and the formal shorthands:

| Status | Meaning |
|---|---|
| `direct` | One shorthand maps to exactly one wire activity. |
| `collapse` | Several shorthands share one wire activity. A field value or the receiver's state distinguishes them, as the section's **Distinguished by** line states. |
| `expansion` | One shorthand is realized by several wire activities, so the same shorthand appears in more than one section. |
| `evolved` | The shorthand's purpose is served by a mechanism partitioned on a different axis (fault reporting or cumulative acknowledgment), not by a dedicated wire activity. |
| `none` | The wire activity has no formal shorthand counterpart. |

Two examples show the many-to-many relationship:

- `CP`, `CX` and `CA` are a collapse: all three ride `Add(CaseStatus)`, distinguished by `pxaState`.
- `GI` is an expansion: it spans the note lifecycle and the actor-suggestion exchange.

The shorthands `RE`, `EE`, `CE`, `GE`, `EK`, `CK` and `GK` have no dedicated wire activity.
Faults are conveyed by `Create(ProcessingFault)`, `as:Reject`, or `Add(Note)`, partitioned by failure mode.
Acknowledgment of ledger-replicated state is cumulative and implicit through hash-chain continuity.
`RK` survives as a real wire activity because report submission is not ledger-replicated.
[Faults and Acknowledgments](faults_and_acknowledgements.md) describes both mechanisms, and [ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md) records the decision.
