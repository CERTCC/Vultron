# General (GI) Messages

The General shorthands cover messages not tied to a specific state change. `GI`
**expands** across the note lifecycle and the actor-suggestion handshake; the
mapping table below lists each wire activity it covers.

## Message mapping

```python exec="true" idprefix=""
from vultron.metadata.msm.render import render_page

# heading=False omits render_page's "## <model> Messages" heading so it does
# not duplicate this page's H1. The table is the #2998-rendered artifact.
print(render_page("general", heading=False))
```

## GI — General Inquiry

- **Protocol role:** Communicates non-state-change information — asking or
  answering a question, requesting a status update or a draft review,
  suggesting a Participant for a case, or resolving a loss of state
  synchronization.
- **Triggering transition:** none (any time).
- **Wire activities:** `GI` expands across the note lifecycle
  (`Create(Note)`, `Add(Note)[target=VulnerabilityCase]`,
  `Remove(Note)[target=VulnerabilityCase]`) and the actor-suggestion handshake
  (`Offer(Actor)[target=VulnerabilityCase]`,
  `Offer(CaseParticipant)[target=VulnerabilityCase]`, and its `Accept`/`Reject`).
  Suggesting a Participant is a `GI` inquiry, not a case-management message.
- **How-to:** [Status Updates and Comments](../../howto/activitypub/activities/status_updates.md)
  (notes); [Suggesting an Actor for a Case](../../howto/activitypub/activities/suggest_actor.md)
  (actor suggestion).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#other-message-types).

A note attached to a case:

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_note_to_case, json2md

print(json2md(add_note_to_case()))
```

Suggesting an actor for a case:

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import recommend_actor, json2md

print(json2md(recommend_actor()))
```

## GK — General Acknowledgement

- **Protocol role:** Acknowledges receipt of a `GI` message.
- **Triggering transition:** any valid `GI` message.
- **Wire activity:** none dedicated. Acknowledgement of ledger-replicated state
  is cumulative and implicit through hash-chain continuity
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#other-message-types).

## GE — General Error

- **Protocol role:** Indicates a general error has occurred.
- **Triggering transition:** any unexpected `GI` message.
- **Wire activity:** none dedicated. Faults are conveyed by
  `Create(ProcessingFault)`, `as:Reject`, or `Create(Note)`, partitioned by
  failure mode
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#other-message-types).
