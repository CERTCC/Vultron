---
status: accepted
date: 2026-09-21
deciders: [adh, Claude Opus 5]
consulted: []
informed: []
---

# ADR-0100: There Is No Multi-Candidate Embargo Poll; Open Proposals Resolve in Earliest-Expiration Order

## Context and Problem Statement

The AS2 vocabulary carried a `ChoosePreferredEmbargo` activity — an
`as:Question` whose `oneOf`/`anyOf` listed several candidate `EmbargoEvent`s —
intended to ask Participants which embargo terms they preferred. CONCERN-3433
recorded that it had a wire class and a factory but no registered
`ActivityPattern` and no `MessageSemantics` member, and asked whether the
multi-candidate poll is in scope for the protocol.

Measuring it found the gap is wider than "no pattern registered". An emitted
`ChoosePreferredEmbargo` is refused at `parse_activity`, not merely extracted as
`UNKNOWN`:

| Fact | Where |
|---|---|
| `as_Question.anyOf`/`oneOf` are typed `as_Object \| as_Link \| str \| None` — a single value, where AS2 defines a collection | `vultron/wire/as2/vocab/base/objects/activities/intransitive.py` |
| `_ChoosePreferredEmbargoActivity` added `any_of`/`one_of` alongside the inherited `anyOf`/`oneOf`, so four fields shared two wire aliases | `vultron/wire/as2/vocab/activities/embargo.py` |
| Serialization resolved the alias collision last-writer-wins; validation bound the *inherited* singular field, so the class could emit and never parse — including its own output | measured on `origin/main` |
| `find_in_vocabulary("Question")` resolves to the base `as_Question`, so the Vultron subclass was unreachable from the wire regardless | `vultron/wire/as2/vocab/base/registry.py` |

Two further facts decided the question.

**There was no wire form for an answer.** `_EmAcceptEmbargoActivity.object_` is
a required, inline-typed `_EmProposeEmbargoActivity` — an `Invite`. A candidate
`EmbargoEvent` inside a `oneOf` is not an `Invite`, so a Participant had nothing
to `Accept`. Registering a pattern and a semantic would have left the poll
askable and still unanswerable.

**The protocol already specifies a different resolution mechanism, and it is
sequential.** `docs/topics/process_models/em/defaults.md` is a normative page,
and it says:

> When two or more embargo proposals are open (i.e., none have yet been
> accepted) and $q^{em} \in P$, Participants SHOULD accept the shortest one and
> propose the remainder as revisions.
>
> When two or more embargo revisions are open … Participants SHOULD *accept* or
> *reject* them individually, in earliest to latest expiration order.

`working_with_others.md` states the same heuristic — *The Shortest Embargo
Proposed Wins* — as "accept the earliest proposed end date and immediately
propose and evaluate the rest as potential revisions". A "here are four, pick
one" poll is the construct that heuristic exists to replace.

## Decision Drivers

- A multi-candidate poll must be answerable, and no answer activity exists.
- `as:Question` has no `object`, so a pattern for it can discriminate only on
  `context`. That shape is already occupied (see below), and SE-08-001 forbids
  two patterns matching one activity.
- The EM state machine carries no exclusivity: `EM.PROPOSED` is a single scalar
  and `pending_embargo_proposal_index` is an ungrouped map, so "these are
  mutually exclusive alternatives" has nowhere to live.
- Real cases carry at most two or three candidate sets of terms at once.
  Sequential propose / accept / reject covers that without new mechanism, which
  is also the constraint EMB-15-003 imposes on counter-proposals: countering
  "MUST NOT introduce a new mechanism".
- The earliest-expiration ordering rule existed only as prose in
  `docs/topics/`, so nothing enforced it and the implementation drifted.

## Considered Options

- **Retire the poll; specify earliest-expiration ordering.**
- **Build the poll out.** Fix `as_Question`, remove the field collision,
  register a pattern and a `MessageSemantics`, add a received-side handler, and
  design an answer activity.
- **Leave it emit-only and documented as such.** Keep the caveats added by
  #3003 in place indefinitely.

## Decision Outcome

Chosen option: **"Retire the poll; specify earliest-expiration ordering"**.

The poll is not an unimplemented feature. It is a second, contradictory answer
to a question the protocol already answers sequentially, and it cannot be made
to work without inventing an answer activity that the existing `EA`/`ER`
exchange already provides per proposal.

Concretely:

1. `_ChoosePreferredEmbargoActivity`, `choose_preferred_embargo_activity`, the
   `choose_preferred_embargo()` example and its generated artifacts are removed.
2. `as_Question` **stays** — `bootstrap_replay_question_activity` (CBT-03-004)
   needs it — and its `anyOf`/`oneOf` are corrected to collections, because
   leaving an AS2-wrong field that nothing exercises is a claim no test can
   fail on.
3. Resolution of several open proposals is ordered by embargo expiration,
   earliest first, replacing the current first-recorded behavior, and the
   pending-proposal record is pruned when a proposal is decided.
4. The ordering rule becomes `specs/embargo-policy.yaml` EP-08 so it is
   testable rather than prose.

### Consequences

- Good, because the protocol has one mechanism for competing embargo terms
  instead of two, and the surviving one is already built and exercised.
- Good, because a normative rule that nothing enforced becomes a spec entry
  with a ratchet.
- Good, because `Question[context=VulnerabilityCase]` stays available to the one
  activity that legitimately uses it, with no ambiguity.
- Bad, because a Participant who genuinely wants to offer several alternatives
  in one message cannot. They send several `Invite`s instead, which is more
  round trips.
- Neutral, because no code emitted the poll, so nothing observable changes on
  the wire.

## Validation

- `test/architecture/test_vocab_examples_dispatchable.py` loses its
  `choose_preferred_embargo` exemption, so the ratchet covers the corpus with
  one fewer known-wrong entry.
- A round-trip test asserts an `as_Question` carrying several options survives
  serialization and validation, which is the defect that made the poll
  unparseable.
- A test asserts open proposals resolve earliest-expiration-first, and that a
  decided proposal leaves `pending_embargo_proposal_index`.

## Pros and Cons of the Options

### Retire the poll; specify earliest-expiration ordering

- Good, because it makes the code agree with normative documentation rather
  than adding a mechanism that contradicts it.
- Good, because it is the smaller change and removes a class that cannot parse
  its own output.
- Neutral, because it narrows the AS2 surface Vultron uses without narrowing
  the AS2 vocabulary it models.
- Bad, because the multi-candidate case, if it ever becomes common, will need
  this decision revisited.

### Build the poll out

- Good, because a single message offering N alternatives is fewer round trips.
- Bad, because it requires a new answer activity: `EA`/`ER` take an `Invite` as
  their object and a `oneOf` candidate is not one.
- Bad, because the only available discriminator for a `Question` pattern is
  `context`, which `bootstrap_replay_question_activity` already occupies.
  Distinguishing them needs a field `ActivityPattern` does not have.
- Bad, because `oneOf` exclusivity has no representation in EM state.
- Bad, because it duplicates a resolution mechanism the protocol already
  specifies, against EMB-15-003's "MUST NOT introduce a new mechanism".

### Leave it emit-only and documented as such

- Good, because it costs nothing now.
- Bad, because the caveats claim a gap that will be closed, and this decision
  is that it will not be. The documentation would be durably misleading about
  the protocol's intent.
- Bad, because the wire class remains unable to parse its own output, which the
  next agent to touch `as_Question` would have to rediscover.

## More Information

CONCERN-3433 was found while reducing `docs/howto/activitypub/activities/` to
task guides (#3003), where the how-to had been instructing readers to send the
poll and collect answers.

Measuring this surfaced a second, independent defect that is **not** resolved by
this ADR: `as:Question` has no dispatch path at all, and
`bootstrap_replay_question_activity` (CBT-03-004) is emitted live from
`vultron/adapters/driving/fastapi/inbox_pending_queue.py` and cannot be routed
by any recipient. Whether `Question` is even the right vocabulary for a replay
request — as opposed to overloading AS2 into a request/response pattern, where
Vultron otherwise uses activities as state-change notifications — is an open
question tracked with it. This ADR deliberately does not decide it; it only
relies on the fact that `Question[context=VulnerabilityCase]` is occupied.

Automatically re-proposing the remaining proposals as revisions is out of scope.
`defaults.md` makes it a `SHOULD` for Participants and
`propose_embargo_revision_trigger_bt` already exists for implementers who want
it; the protocol does not require the mechanism to be automated.

EP-04-003 covers the two-party shortest-wins comparison at case creation and is
itself not yet implemented (#3392). EP-08 and #3392 share one
earliest-end-date comparator.

Generated spec requirements: `embargo-policy.yaml` EP-08.
