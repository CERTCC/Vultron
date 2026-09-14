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
- **How-to:** [Establishing an Embargo](../../howto/activitypub/activities/establish_embargo.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#em-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import propose_embargo, json2md

print(json2md(propose_embargo()))
```

## ER — Embargo Proposal Rejection

- **Protocol role:** The Participant has rejected an embargo proposal.
- **Triggering transition:** Proposed → None (P → N).
- **Wire activity:** `Reject(Invite(Event)[context=VulnerabilityCase])`.
- **How-to:** [Managing an Embargo](../../howto/activitypub/activities/manage_embargo.md).
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
- **How-to:** [Managing an Embargo](../../howto/activitypub/activities/manage_embargo.md).
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
- **How-to:** [Managing an Embargo](../../howto/activitypub/activities/manage_embargo.md).
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
- **How-to:** [Managing an Embargo](../../howto/activitypub/activities/manage_embargo.md).
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
- **How-to:** [Managing an Embargo](../../howto/activitypub/activities/manage_embargo.md).
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
- **How-to:** [Managing an Embargo](../../howto/activitypub/activities/manage_embargo.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#em-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import remove_embargo, json2md

print(json2md(remove_embargo()))
```

## EK — Embargo Acknowledgement

- **Protocol role:** Acknowledges receipt of an EM message.
- **Triggering transition:** any valid EM message.
- **Wire activity:** none dedicated. Acknowledgement of ledger-replicated state
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
