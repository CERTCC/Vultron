---
status: proposed
date: 2026-11-13
created: 2026-11-13
updated: 2026-11-13
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0083, ADR-0131, ADR-0141;
  specs/message-semantics-mapping.yaml MSM-05-001;
  specs/case-ledger-processing.yaml CLP-02-005, CLP-02-016, CLP-05-001;
  specs/vocabulary-model.yaml VM-03
informed: []
partially_supersedes: [0141-a-refused-assertion-is-answered-with-a-reject-of-the-refused-activity.md]
stakeholder_type: [project-contributor]
---

# A Refusal Notice Is a Refuse, a Subtype of Reject

## Context and Problem Statement

ADR-0141 made the CASE_MANAGER's refusal notice a `Reject` whose object is the refused activity.
`Reject` already carries many other meanings: a participant's decline of an `Invite` or an `Offer`, a negative acknowledgement of a ledger entry, and the refusal notice.
A refusal of an `Invite` or an `Offer` has the same shape as a decline of it, so ADR-0141 let the decline's use case read it.
`Reject(Leave(VulnerabilityCase))` reaches the refusal-notice use case only because no decline pattern matches it.

The ledger already tells the two apart: a participant's decline is a case event and is ledgered, and a refusal is never ledgered (CLP-02-016, CLP-02-005).
The wire does not.
A receiver cannot tell from the message whether a participant decided against a request or the CASE_MANAGER refused it on a precondition.

## Decision Drivers

- A decline and a refusal are different acts, and the receiver must be able to tell them apart from the message alone.
- One refusal shape and one receiving use case for every refused activity (ADR-0141, CS-22-001).
- Use an AS2 core term when one fits; when none does, an extension that overlaps a core type carries the core type too (AS2 Core extensibility guidance, whose example is `["Resign", "Leave"]`).
- Inside the code, a message has one type, so pattern matching and the many readers of `type` stay simple.

## Considered Options

- **A — A `Refuse` extension type, a subtype of `Reject`, written as a type list at the wire edge.**
- **B — A `Refuse` extension type, with `type_` a list of strings everywhere in the code.**
- **C — `"type": "Refuse"` alone.**
- **D — An existing AS2 verb: `Ignore`, `Block`, `Flag`, `TentativeReject` or `Dislike`.**
- **E — Keep ADR-0141's shape: the notice is a plain `Reject`.**

## Decision Outcome

Chosen option: **A**.

A refusal notice is `"type": ["Refuse", "Reject"]`.
`Refuse` is declared in the Vultron namespace as `vultron:Refuse rdfs:subClassOf as:Reject`.
Everything else ADR-0141 decided about the notice stays: the refused activity inline, `inReplyTo` naming it, the guard's reason in `summary`, one recipient, a derived id, and no ledger entry.

The wire keeps the AS2 list.
When a message is received, one shared resolver narrows a `type` list to the most specific class the vocabulary knows, so the code holds a `Refuse`.
The resolver ignores a term the vocabulary does not know, so `["Foo", "Reject"]` resolves to `Reject`, as AS2's extensibility guidance expects of a receiver.
On the way out, the serializer writes a class that declares a core supertype as the list.
The list form is general: any later Vultron extension type that overlaps a core type uses the same resolver.

A pattern for a `Reject` never matches a `Refuse`, because the two have different types once resolved.
So a refusal of an `Invite` or an `Offer` is read by the refusal-notice use case, not by the use case that reads a decline.
This replaces ADR-0141's rule that such a refusal is read as a decline.
A `Reject` from a participant is a decline, and a `Refuse` from the CASE_MANAGER is a refusal.

Option B was rejected: AS2 allows the list, but nothing in Vultron needs more than one type at a time once the most specific one is known, and a list in the code would change every type check and every class's `type_`.
Option C was rejected: it breaks the AS2 rule that an extension type overlapping a core type also carries that core type, so a plain AS2 receiver could not read the message as a `Reject`.
Option D was rejected, verb by verb:

- `Ignore` means ignoring, and Vultron uses it for the RM defer.
- `Block` targets an actor and is not delivered to it (ActivityPub).
- `Flag` reports content to a moderator.
- `TentativeReject` is not final, and Vultron uses it for RM invalid.
- `Dislike` expresses sentiment.

Option E was rejected: it keeps the two acts identical on the wire, which is the problem this record addresses.

### Consequences

- Good, because a receiver tells a refusal from a decline by type, before it reads the object.
- Good, because the refusal-notice pattern no longer needs to exclude `Invite` and `Offer`, and pattern order no longer decides which use case reads a refusal.
- Good, because a plain AS2 receiver still reads the notice as a `Reject`.
- Bad, because the wire edge must accept a `type` list, which today it refuses, and every reader of a raw body's `type` must go through the resolver.
- Bad, because a CASE_MANAGER's plain `Reject` of an activity that is not a request is no longer read as a refusal notice.
  Every sender is this implementation, so no fallback is kept.
- Neutral, because the CASE_MANAGER's answer to a Case Owner's `Leave(VulnerabilityCase)` during an active embargo becomes the standard refusal notice, and that tree needs no exemption from it.
- Neutral, because the CASE_MANAGER's optional answer to an activity for a fully closed case, such as a late `Leave(VulnerabilityCase)`, is also a refusal, so it becomes a `Refuse` (CM-23-040, CM-23-057).
  ADR-0131's default to drop such an activity unanswered does not change.

## Validation

- A parser test confirms that `["Refuse", "Reject"]`, `["Reject", "Refuse"]` and `"Refuse"` resolve to the `Refuse` class, that `["Foo", "Reject"]` resolves to the `Reject` class, and that a list of two known, unrelated types is refused as an unknown type.
- A serialization test confirms that a refusal notice is written with `"type": ["Refuse", "Reject"]`.
- A pattern test confirms that a `Refuse` of an `Invite` or an `Offer` reaches `REFUSAL_NOTICE` and that a participant's `Reject` of the same request reaches the decline.
- The JSON-LD context declares `Refuse` as a subclass of `as:Reject`.

## More Information

- ADR-0141 — the refusal notice's content and emitter; only its rule that a refusal of an `Invite` or an `Offer` is read as a decline is replaced.
- ADR-0083 — the three fault mechanisms that MSM-05-001 records.
- `notes/as2-vocabulary-alignment.md` § "Refusal Is Its Own Type".
- #6254 — the idea this record answers.
- ADR-0131 — the post-close reply setting and its drop default, which stay.
- #6433, #6434 and #6435 implement this record.
  They amend MSM-05-001, CLP-02-005, CLP-05-001, CM-23-011, CM-23-040 and CM-23-057 to name `Refuse`, and add the VM-03 list-type rules, each with its test.
