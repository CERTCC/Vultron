---
stakeholder_type: [platform-developer]
level: 400
description: >
  Wire activities for the Embargo Management message types EP, ER, EA, EV, EJ, EC, ET, EK, and EE.
---

# Embargo Management (EM) Messages

The EM process is global to the case. A Participant emits an EM message when the
case's EM state changes. The AS2 wire vocabulary **collapses** the
revision-negotiation shorthands onto their initial-negotiation counterparts:
`EV` is sent as `EP`, `EJ` as `ER`, and `EC` as `EA`, discriminated by EM state
context rather than by a payload field (MSM-02).

## Message mapping

```python exec="true" idprefix=""
from vultron.metadata.msm.render import render_page

# heading=False omits render_page's "## <model> Messages" heading so it does
# not duplicate this page's H1. The table is the #2998-rendered artifact.
print(render_page("em", heading=False))
```

## EP — Embargo Proposal

- **Protocol role:** Proposes embargo terms (e.g. an expiration date/time).
- **Triggering transition:** None or Proposed → Proposed ({N,P} → P).
- **Wire activity:** `Invite(Event)[context=VulnerabilityCase]`. `EP`
  **expands** across four wire activities in the prototype —
  `Create(Event)`, `Add(Event)[target=VulnerabilityCase]`,
  `Invite(Event)`, and `Announce(Event)` — as shown in the mapping
  table above.
- **How-to:** [How to Establish an Embargo](../../howto/activitypub/activities/establish_embargo.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#em-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import propose_embargo, json2md

print(json2md(propose_embargo()))
```

### Add Embargo to Case

`Add(Event)[target=VulnerabilityCase]` attaches an embargo to a case without a
preceding proposal. The Case Owner uses it when the terms need no negotiation.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_embargo_to_case, json2md

print(json2md(add_embargo_to_case()))
```

### Activate Embargo

The activation form of the same `Add(Event)`, sent in reply to a proposal that has
carried. The distinction from the form above is the presence of the proposal it
answers, not the wire shape.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import activate_embargo, json2md

print(json2md(activate_embargo()))
```

### Announce Embargo

`Announce(Event)` tells participants the terms of the active embargo. It also
carries notice of a change significant enough to warrant attention beyond the
corresponding `CaseStatus` message, such as an embargo being removed from a case.

When the CASE_MANAGER activates a revision that ends no later than the embargo it replaces, it sends `Announce(Event)` with the new terms directly to each bound signatory that no longer receives ledger entries (removed, or at RM `CLOSED`).
That participant applies the new terms only when the CASE_MANAGER sent them.
A revision that ends later sends no such notice, because those participants never agreed to it.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import announce_embargo, json2md

print(json2md(announce_embargo()))
```

## ER — Embargo Proposal Rejection

- **Protocol role:** The Participant has rejected an embargo proposal.
- **Triggering transition:** Proposed → None (P → N).
- **Wire activity:** `Reject(Invite(Event)[context=VulnerabilityCase])`.
- **Refusal on a public case:** A receiver answers an `EP` with `ER` when the case is public, an exploit is public, or attacks are observed.
  The `ER` names the Invite by id, so it is sent even when the Invite named its terms only by URI.
  A receiver sends one `ER` per Invite: a re-delivered Invite is skipped.
- **Malformed Invite:** An `EP` that names no `to` recipient or several is not answered with `ER`.
  It is received but not understood, so the receiver sends `Create(ProcessingFault)` to the sender.
- **How-to:** [How to Revise or Terminate an Embargo](../../howto/activitypub/activities/manage_embargo.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#em-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import reject_embargo, json2md

print(json2md(reject_embargo()))
```

## EA — Embargo Proposal Acceptance

- **Protocol role:** The Participant has accepted an embargo proposal.
- **Triggering transition:** Proposed → Active (P → A).
- **Wire activity:** `Accept(Invite(Event)[context=VulnerabilityCase])`.
- **How-to:** [How to Revise or Terminate an Embargo](../../howto/activitypub/activities/manage_embargo.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#em-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import accept_embargo, json2md

print(json2md(accept_embargo()))
```

## EV — Embargo Revision Proposal

- **Protocol role:** Proposes a revision to embargo terms.
- **Triggering transition:** Active → Revise (A → R).
- **Wire activity:** `Invite(Event)[context=VulnerabilityCase]` —
  **collapsed onto `EP`**, discriminated by EM state context (a proposal
  received in the Active state is a revision).
- **How-to:** [How to Revise or Terminate an Embargo](../../howto/activitypub/activities/manage_embargo.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#em-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import propose_embargo, json2md

print(json2md(propose_embargo()))
```

## EJ — Embargo Revision Rejection

- **Protocol role:** The Participant has rejected a proposed embargo revision.
- **Triggering transition:** Revise → Active (R → A).
- **Wire activity:** `Reject(Invite(Event)[context=VulnerabilityCase])` —
  **collapsed onto `ER`**, discriminated by EM state context.
- **How-to:** [How to Revise or Terminate an Embargo](../../howto/activitypub/activities/manage_embargo.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#em-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import reject_embargo, json2md

print(json2md(reject_embargo()))
```

## EC — Embargo Revision Acceptance

- **Protocol role:** The Participant has accepted a proposed embargo revision.
- **Triggering transition:** Revise → Active (R → A).
- **Wire activity:** `Accept(Invite(Event)[context=VulnerabilityCase])` —
  **collapsed onto `EA`**, discriminated by EM state context.
- **How-to:** [How to Revise or Terminate an Embargo](../../howto/activitypub/activities/manage_embargo.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#em-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import accept_embargo, json2md

print(json2md(accept_embargo()))
```

## ET — Embargo Termination

- **Protocol role:** The Participant has terminated an embargo, with immediate
  effect.
- **Triggering transition:** Active or Revise → eXited ({A,R} → X).
- **Wire activity:** `Remove(Event)`.
- **Bound participants that are no longer active:** A signatory that was removed from the case, or that left it and is at RM `CLOSED`, stays bound by the embargo but no longer receives ledger entries.
  The CASE_MANAGER sends each such participant `ET` directly, one activity per participant, outside the ledger stream.
  The notice carries the embargo and nothing else, and it is not a ledger entry.
  The participant applies it only when the CASE_MANAGER sent it.
  A termination on or after the embargo's agreed end date is expiry, and sends no notice.
- **How-to:** [How to Revise or Terminate an Embargo](../../howto/activitypub/activities/manage_embargo.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#em-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import remove_embargo, json2md

print(json2md(remove_embargo()))
```

## EK — Embargo Acknowledgment

- **Protocol role:** Acknowledges receipt of an EM message.
- **Triggering transition:** any valid EM message.
- **Wire activity:** none dedicated. Acknowledgment of ledger-replicated state
  is cumulative and implicit through hash-chain continuity; a per-message `EK`
  would be redundant
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#em-message-types).

## EE — Embargo Error

- **Protocol role:** Indicates a Participant received an unexpected EM message.
- **Triggering transition:** any unexpected EM message.
- **Wire activity:** none dedicated. Faults are conveyed by
  `Create(ProcessingFault)`, `as:Reject`, or `Create(Note)`, partitioned by
  failure mode
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#em-message-types).
