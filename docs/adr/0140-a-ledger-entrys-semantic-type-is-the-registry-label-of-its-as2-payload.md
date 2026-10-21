---
status: proposed
date: 2026-10-15
created: 2026-10-15
updated: 2026-10-21
revision: 2
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0083, ADR-0104, ADR-0128, ADR-0137; specs/semantic-extraction.yaml SE;
  specs/case-ledger-processing.yaml CLP-02, CLP-07; issues #3743, #4723, #4724, #4725
informed: []
stakeholder_type: [project-contributor]
---

# A Ledger Entry's Semantic Type Is the Registry Label of Its AS2 Payload

## Context and Problem Statement

Every case ledger entry carries two descriptions of one act.
Its `payloadSnapshot` holds an ActivityStreams 2.0 (AS2) activity, such as `Invite(VulnerabilityCase)` or `Add(ParticipantStatus)`.
Its `eventType` holds a semantic type, a name for what that activity means, such as `invite_actor_to_case`.

The semantic registry (`vultron/semantic_registry/`) already maps a wire activity's shape to its semantic type for received messages, and the message vocabulary docs are generated from it ([ADR-0128](0128-message-vocabulary-docs-are-projections-of-the-semantic-registry.md)).
The ledger does not use it.
Each write path stamps `eventType` from its own string constant.
About ten of those strings name semantic types the registry does not know, for acts the CASE_MANAGER records on its own, such as creating a participant record, fully closing a case, or the lapse of an embargo invitation.
One payload uses an activity type that is not AS2 at all.

A reader of a ledger then has no single source for what an entry means.
The demo UI ([ADR-0104](0104-interactive-demo-ui-live-ledger-watcher.md)) shows the consequence: it keeps its own closed list of event names, and that list had already drifted from what the code writes when it was audited.

The question this record settles is what an entry's meaning is, and where it comes from.

## Decision Drivers

- Vultron's vocabulary should be one known set: every AS2 activity Vultron can send, receive, or write to a ledger, each with one semantic type.
- Even the CASE_MANAGER's own acts are expressible as AS2 activities, so they need no separate naming scheme.
- Replicas route ledger replay on `eventType` alone, and that should stay cheap.
- Readers outside Python, such as the demo UI and the report tool, need the vocabulary as data they can check against.

## Considered Options

- The payload is the only source; `eventType` is dropped and every reader classifies the payload
- `eventType` stays an independent label from a closed list, and the payload is unconstrained
- The payload is valid AS2, and `eventType` is stored but must equal the registry's label for it

## Decision Outcome

Chosen option: "The payload is valid AS2, and `eventType` is stored but must equal the registry's label for it", because it gives the ledger one source of meaning without making every replica run the pattern matcher on replay.

1. **The registry is Vultron's complete vocabulary.**
   It labels every AS2 activity shape that Vultron can send, receive, or write to a case ledger, including the CASE_MANAGER's own acts.
   A semantic type means the same thing wherever the activity appears.
2. **Every ledger payload is a valid AS2 activity.**
   No payload uses an activity type that AS2 does not define.
3. **An entry's `eventType` is the semantic type the registry assigns to its `payloadSnapshot`.**
   It is written at commit time and kept so that replay can route on it, but it is never chosen independently of the payload.
   Where two meanings share one shape, the distinguishing fact goes into the payload, so a pattern can see it, or the two meanings are one semantic type.
4. **A CASE_MANAGER decision is an occasion, and its record is a real activity.**
   When the clock or the CASE_MANAGER's policy decides something (an invitation's deadline passes, a late answer is honoured, an offer's deadline passes), that decision is the occasion for an act the CASE_MANAGER performs.
   The act is an activity the CASE_MANAGER builds with a factory, commits from its sealed blob and delivers like any of its acts; it is never a ledger entry shaped to look like an activity, and never an activity attributed to a participant that sent nothing.
   - An expired embargo invitation is the CASE_MANAGER's `Update(EmbargoConsent)` carrying the invitee's `TIMED_OUT` row.
   - An honoured late `Accept` of an embargo invitation is the CASE_MANAGER's `Update(EmbargoConsent)` carrying the accepter's `AGREED` row; the late `Accept` itself is not committed.
   - An expired ownership-transfer `Offer` is the CASE_MANAGER's `Undo(Offer)`, carrying the `Offer` inline with the `endTime` it passed. The CASE_MANAGER made that `Offer` ([ADR-0148](0148-an-owner-proposes-an-ownership-transfer-offer-and-the-case-manager-makes-it.md)), so it is the one that withdraws it; the Case Owner's own withdrawal is an `Undo` of its proposal, a different shape. The entry keeps its own semantic type, `offer_case_ownership_transfer_expired`.
   No separate act entry precedes the `Update(EmbargoConsent)`: the row's state already tells an expiry from a refusal, and a second entry would record an act nobody sent.
   The synthetic `Expire` type is retired.
5. **Recognizing a semantic type does not imply a handler for it.**
   A receiver maps a received activity to a use case by its semantic type; when none is registered, the activity is not processed ("no use case found").
   That outcome says the receiver does not handle the message, not that the message is invalid.
   Permission to send a message is a separate question, owned by the use cases that handle it ([ADR-0115](0115-received-handlers-check-sender-entitlement.md)), never by the inbox.

### Consequences

- Good, because a ledger entry's meaning has one source, and a label that disagrees with its payload fails a test instead of reaching a replica.
- Good, because the registry can be exported as data, so the demo UI and the report tool share one vocabulary and its phrasing.
- Good, because a semantic type the registry recognizes but no receiver handles is visible as a gap, which tells implementers which handlers are still missing.
- Neutral, because `eventType` stays on the entry as a stored copy, so the stored ledger format does not change.
- Bad, because every ledger-only act needs a registry entry and a pattern, and a shape that today carries two meanings needs a payload change or a merge.
- Bad, because a received activity whose shape is only ever ledgered, such as a `Create` of a case record ([ADR-0137](0137-case-records-are-attached-by-one-message-never-created-first.md)), is now recognized and then left unhandled, where before it was unrecognized.

## Validation

- A test runs every registered demo scenario and asserts that, for every ledger entry written, the registry's matcher returns the entry's `eventType` (#4724).
- A test asserts that no ledger payload uses a non-AS2 activity type.
- The exported registry table that the demo UI reads is drift-tested against the registry (#4725).

## Pros and Cons of the Options

### The payload is the only source

- Good, because no stored label can ever disagree with the payload.
- Bad, because every replica would run the pattern matcher on every entry it replays, where today it compares one string.
- Bad, because it changes the stored ledger format and the replication wire shape.

### An independent label from a closed list

- Good, because it is the smallest change: declare the existing strings as one enumeration and export it.
- Bad, because the label and the payload remain two descriptions with nothing tying them together.
- Bad, because ledger-only acts keep a naming scheme of their own, outside the vocabulary the registry documents.

### Valid AS2 payload, with `eventType` equal to the registry's label

- Good, because the ledger and the registry describe one vocabulary, and the stored label is checked rather than trusted.
- Good, because replay keeps routing on one string.
- Bad, because the equality is a test-time guarantee over the scenarios the tests run, not a construction-time one.

## More Information

- Decided in the 2026-10-15 demo UI planning session, which audited the merged demo UI (PR #3754).
- The replacement for the non-AS2 payload type and the rulings for the honoured late `Accept` and the two expiries (item 4) were decided on #4723 and built in #3743. The shapes for the other ledger-only acts, and the rulings for the other shared shapes, are still decided in #4723.
- Whether to rename `eventType` to match the glossary term is open in #4734.
- Glossary: **Semantic type** in `CONTEXT.md` and [the glossary](../reference/glossary.md).
