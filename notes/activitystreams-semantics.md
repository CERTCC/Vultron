# ActivityStreams Semantics in Vultron

## Activities Are State-Change Notifications, Not Commands

In Vultron, an ActivityStreams Activity is a **statement about a state change
that has already occurred**, not a request for another Actor to perform an
action.

When an Actor receives an Activity, it is being informed that:

- Another Actor performed a state transition in their RM, EM, or CS process.
- The shared state of the Case has changed.
- The sender's internal model of the world has been updated accordingly.

The receiver MUST treat the Activity as an assertion about the sender's state
and update its own model of the world. This includes:

- The Case
- Reports
- Participants
- Embargo status
- Case state events (V, F, D, P, X, A)
- Known prior transitions

Receiving an Activity means:

> "Someone else observed or performed a state change and is informing me."

It does **not** mean:

> "I am being instructed to perform this action."

### Emitting Activities

When an Actor emits an Activity, it is declaring:

- "My internal state has changed."
- "I have performed a protocol-relevant transition."
- "The shared case state should now reflect this."

Activities are therefore:

- Distributed state synchronization signals.
- Logs of completed transitions.
- Assertions about protocol-visible facts.

They are **not**:

- Remote Procedure Calls.
- Commands.
- Requests to execute behavior.

### Work Outside the Protocol

Participants perform substantial work outside the Vultron messaging layer,
such as:

- Reproducing a vulnerability
- Root cause analysis
- Fix development
- Patch deployment
- Human embargo negotiation
- Document preparation

When such work results in a protocol-relevant state transition (e.g., Fix
Ready, Fix Deployed, Embargo Accepted), the Actor emits the corresponding
Activity.

**The Activity does not cause the work. The work causes the Activity.**

### Processing Is Still Required

Although Activities are not commands, recipients MUST still process them:

1. Parse and validate the Activity.
2. Update local RM/EM/CS state.
3. Potentially trigger local behaviors (e.g., reprioritize, start validation,
   update embargo tracking).

The key distinction is:

- Activities describe what has happened.
- Behavior logic determines what to do next in response.

---

## Response Activity Conventions

### inReplyTo

Responses to activities that imply a reply (Offer, Invite) MUST use the
`inReplyTo` field to reference the original activity. This is required for
threading and context.

For example, when responding to an Offer of a VulnerabilityReport:

- The response activity's `object` field MUST be the Offer/Invite being
  responded to.
- The response activity MUST set `inReplyTo` to the ID of the Offer/Invite.

This allows other actors to understand the relationship between the response
and the original offer.

**References**: `specs/response-format.md` RF-02-003, RF-03-003, RF-04-003,
RF-08-001.

---

## Vocabulary Examples as Canonical Reference

The file `vultron/scripts/vocab_examples.py` contains canonical examples of
every Vultron ActivityStreams activity type. These examples serve as:

- **Documentation**: Illustrate the expected structure for each message type.
- **Pattern-matching reference**: Show which `(Activity Type, Object Type)`
  pairs correspond to each `MessageSemantics` enum value.
- **Test fixtures**: Provide well-formed activity structures for unit tests
  against `vultron/activity_patterns.py` and handlers.

When implementing or testing a new handler, consult `vocab_examples.py` first
to understand the expected activity structure before looking at the pattern
definitions in `vultron/activity_patterns.py`.

The examples MUST be kept up to date as the vocabulary evolves. When adding a
new vocabulary type or message semantic, add a corresponding example to
`vocab_examples.py`.

**Cross-references**: `vultron/activity_patterns.py`, `vultron/enums.py`,
`vultron/as_vocab/`.

---

## Asymmetric Inbox Routing for Invite/Accept/Reject

Invite, Accept, and Reject activities are **not** all received by the same
actor. Each activity hits the inbox of a **different** actor:

| Activity | Sender | Recipient inbox | Handler |
|----------|--------|-----------------|---------|
| `Invite(object=Actor, target=Case)` | Case Owner | Target Actor | `invite_actor_to_case` — stores invite for local consideration |
| `Accept(object=Invite)` | Target Actor | Case Owner | `accept_invite_actor_to_case` — creates `CaseParticipant` |
| `Reject(object=Invite)` | Target Actor | Case Owner | `reject_invite_actor_to_case` — logs rejection |

**Consequence for implementation**: The `CaseParticipant` creation logic
belongs in `accept_invite_actor_to_case` (the case owner's inbox handler),
**not** in `invite_actor_to_case` (the target actor's inbox handler). Each
actor only processes their own inbox.

This asymmetry is easy to miss. It reflects the ActivityPub convention that
responses are addressed to the original sender, and the work triggered by the
response (creating a participant record) is the responsibility of the party
who initiated the flow (the case owner).

The same pattern applies to embargo Invite/Accept/Reject flows:
`invite_to_embargo_on_case` hits the invitee's inbox, while
`accept_invite_to_embargo_on_case` hits the inviter's (case owner's) inbox.

**Reference**: `docs/howto/activitypub/activities/invite_actor.md`,
`docs/howto/activitypub/activities/establish_embargo.md`.

---

## Rehydration Before Pattern Matching

ActivityStreams allows both inline objects and URI string references in
activity fields. Before performing semantic pattern matching, activities MUST
be rehydrated to expand string URI references into full objects.

The `inbox_handler.py` performs rehydration before dispatching, so handlers
receive fully expanded objects. However, when calling `find_matching_semantics`
outside of the dispatch pipeline, call `rehydrate()` explicitly:

```python
from vultron.api.v2.data.rehydration import rehydrate

activity = rehydrate(activity)
semantic = find_matching_semantics(activity)
```

**References**: `specs/semantic-extraction.md` SE-01-002,
`vultron/api/v2/data/rehydration.py`.
