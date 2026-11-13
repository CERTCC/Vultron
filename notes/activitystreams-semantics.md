---
title: ActivityStreams Semantics in Vultron
status: active
kind: guidance
tags: [as2, activitystreams, wire, semantics, extractor, rehydration, accept-reject]
description: >
  Activities as state-change statements, not commands; inbound/outbound
  semantics, Accept/Reject object rules, rehydration, and how a bare
  reference matches a pattern (`object_` strict, `target_` lenient); and the
  rules for choosing an AS2 verb or property before inventing a Vultron one.
related_specs:
  - specs/semantic-extraction.yaml
  - specs/response-format.yaml
  - specs/case-management.yaml
  - specs/embargo-policy.yaml
related_notes:
  - notes/as2-vocabulary-alignment.md
  - notes/activitystreams-state-update.md
  - notes/activity-factories.md
  - notes/bt-integration.md
  - notes/demo-scenario-authoring.md
  - notes/message-type-reference.md
  - notes/embargo-lifecycle.md
  - notes/protocol-asks.md
  - notes/case-joining.md
  - notes/case-bootstrap-trust.md
  - notes/case-ledger-authority.md
  - notes/case-proposal.md
  - notes/case-state-model.md
  - notes/datalayer-design.md
  - notes/protocol-event-cascades.md
  - notes/vocabulary-registry.md
relevant_packages:
  - pydantic
  - vultron/wire/as2
  - vultron/core/models/events
---

# ActivityStreams Semantics in Vultron

See also [activitystreams-state-update.md](activitystreams-state-update.md).

## Activities Are State-Change Notifications, Not Commands

An Activity states that the sender **already** made a protocol-relevant
transition (RM, EM, or CS); it is not a remote procedure call. The receiver
treats it as an assertion about the sender's state, updates its own model of the
case (reports, participants, embargo, CS events), and then its own behavior logic
decides what to do next. Work outside the protocol (reproduction, fix
development, human negotiation) causes the Activity; the Activity never causes
the work.

## `context` Is the Case; `inReplyTo` Is the Cause

- `context` on every case-scoped activity MUST be the case URI. Inbox deferral
  (`_activity_context_id()`) reads it to find the activity's case; a non-case URI
  there queues the activity forever, a bootstrap deadlock for
  `Create(VulnerabilityCase)`.
- Causal antecedents (the Accept that authorized an action, the Offer being
  answered) go in `inReplyTo`, never `context` (CP-05-003, ADR-0045).

## Choosing AS2 Terms

The changes these rules imply for today's code are tracked in
[as2-vocabulary-alignment.md](as2-vocabulary-alignment.md).

- **Use AS2's own term before inventing one, but never manufacture a use.** The aim
  is the most natural AS2 form of each CVD sentence, so check the Vocabulary for a
  verb or property with that meaning before adding a Vultron property or type.
- **An extension type carries the core type it overlaps** (AS2 Core's example is
  `"type": ["Resign", "Leave"]`), and every Vultron property gets a JSON-LD term. A
  generic AS2 reader then still understands the message, and a JSON-LD processor
  keeps the property (AS2 Core § Extensibility). Where each declaration lives:
  [vocabulary-registry](vocabulary-registry.md) § 4a.
- **A verb describes what was done.** If the sentence would be false, such as `Move`
  for a case that stays where it is, pick another verb.
- **`origin` is where something comes from or leaves; `target` is where it goes.**
  `Remove(x, origin=…)`, `Move(x, origin=…, target=…)`, and `Add(x, target=…)` with an
  optional `origin` for a copy. One meaning per slot means a receiver never needs to
  know the verb to read it (VOC Remove, Add, Move).
- **A `Create` takes no `target`; the case it belongs to goes in `context`.** AS2 Core
  App. B maps the AS1 "post" verb to `Create` without a target and to `Add` with one,
  so a `Create` carrying a `target` reads as "added to". Creating a record and seating
  it in a case are two acts, each with its own verb (#6260).
- **`result` names what an act caused, set by the actor that caused it** (Primer:
  "changes of state or indirect outcomes"). It is not the created object, which is a
  `Create`'s `object`.
- **`attachment` includes; `tag` refers** (VOC `tag`, errata). A tag never changes
  recipients or entitlement: a `Mention` in `tag` notifies no one by itself.
- **Identity decides `Update` versus a new object.** If a thing keeps its identity
  and its author may revise it, the change is `Update(x)`. If each version is a fact
  others answer or rely on, it is a new object. Status records are append-only and
  never updated: a new status is an `Add` to the history.
- **A request for an approval of a concrete act is `Offer(<the act>)`**, answered by
  `Accept` or `Reject`; `Question` is for choices and open inquiries (VOC Offer,
  Question).
- **A request for another actor to act is `Offer(<the act>)` too, never the act
  itself.** The actor that holds the record answers `Accept` (its decision) or a
  refusal notice, then makes the act with `inReplyTo` = the Offer; the Accept and the
  act commit together (ADR-0197). Sending the bare act would state that the asker
  did it.

## Responses Reference the Request Twice

A response to an Offer or Invite sets `object` to the full inline Offer/Invite
**and** `inReplyTo` to its ID (RF-02-004, RF-03-003, RF-04-003, RF-08-001). The
object may travel inline or by reference on the wire (RF-02-004, RF-02-005), but
this codebase requires the inline typed activity, not a bare ID string
(RF-02-006, RF-02-007, a prototype shortcut): the internal Accept/Reject classes
reject a string at construction (RF-02-008, RF-02-009). When the request came from
the DataLayer, `rehydrate(obj, dl=dl)` (`vultron/wire/as2/rehydration/`)
restores the nested typed objects the store dehydrated.

## Vocabulary Examples Are the Canonical Reference

`vultron/wire/as2/vocab/examples/` holds a canonical example of every Vultron
activity type, split by topic. Consult it before the patterns in
`vultron/wire/as2/extractor/`, and add an example whenever you add a vocabulary
type or message semantic.

## Invite/Accept/Reject Land in Different Inboxes

`Invite` goes to the invitee; `Accept(Invite)` and `Reject(Invite)` go back to
the CASE_MANAGER. So the invitee's `CaseParticipant` is created on the sending
side when the CASE_MANAGER issues the stub Invite (inert, at `RM.RECEIVED`), and
the CASE_MANAGER's reply handlers update it; the invitee's handler never creates
it (ADR-0114, CM-11-006). Embargo invitations follow the same shape. The
full-case Invite that follows a stub Accept is described in
[case-joining.md](case-joining.md).

## Rehydrate Before Pattern Matching

Activity fields may be inline objects or URI strings, so rehydrate before
semantic matching (SE-01-002). The inbox pipeline does this before dispatch;
anywhere else, call `rehydrate()` before `find_matching_semantics()`.

## Bare References: `object_` Strict, `target_` Lenient

- **`object_` is strict by default.** A bare id still unresolved after
  rehydration names an object the receiver lacks, so it matches no object type
  and the activity is `UNKNOWN_UNRESOLVABLE_OBJECT`, which the inbox fetches for
  (SE-01-006, AKM-05-007). Otherwise the first pattern of the verb wins: a bare
  `Announce` of an embargo read as `Announce(VulnerabilityCase)` (#5243).
- **`accepts_bare_object=True` is the one opt-in**, for a pattern a field other
  than the object's type tells apart: only `LedgerPositionReadPattern`
  (`ledgerPosition`). `test_only_read_case_ledger_entry_accepts_a_bare_object`
  pins the set.
- **`target_`, `context_` and `to_` are lenient**: a case there travels as its URI
  (SE-01-007). `strict=True` tightens `target_` alone, on a pattern whose
  `target_` is its sole discriminator (SE-08-004); a pattern with no `target_`
  refuses it.
- **A nested bare object is unresolvable too**: `Accept(Invite(<id>))` matches
  nothing, so `find_matching_semantics()` follows the `object` chain to its end
  and returns `UNKNOWN_UNRESOLVABLE_OBJECT` (VAM-01-009). One helper,
  `bare_object_id()`, finds that end for both the classifier and the event's
  `unresolved_object_id`, which the fetch names: read one level down instead,
  `Undo(Accept(Invite(<id>)))` names the held middle `Accept`.

## Accepting an Embargo Accepts the Invite

Embargo negotiation works like a calendar invitation: the proposer sends
`Invite(EmbargoEvent)[context=VulnerabilityCase]`, invitees answer `Accept(Invite)` or
`Reject(Invite)`, and a counter-proposal is a new `Invite` with `inReplyTo` the
original. The `object` of the Accept is the proposal `Invite`, not the
`EmbargoEvent`. Background: `docs/topics/process_models/em/`.

## There Is No Multi-Candidate Embargo Poll

`ChoosePreferredEmbargo` is retired, not deferred (ADR-0100). Several open
proposals resolve sequentially, earliest expiration first (EP-08). A related
trap the retired class exposed: **a subclass field whose alias collides with an
inherited one is write-only**, because serialization and validation resolve the
collision in opposite directions.

## Re-Engagement Reuses `RmEngageCase`

Re-engaging a deferred case emits another `RmEngageCase` (`as:Join`), not a
separate activity or `Undo(Ignore)`. `Undo` means retracting a prior action's
effects, whereas `DEFERRED → ACCEPTED` is a forward RM transition. See
`docs/howto/activitypub/activities/manage_case.md`.

## `Reject(Invite(Actor)[target=VulnerabilityCaseStub])` Carries the Stub in `inner_target`

`extract_event` does not populate `request.target` for the Reject (or Accept) of
an Invite: the stub is the nested Invite's `target`, exposed as
`request.inner_target_id`. Resolve `case_id` from the case the stub names
(a typed `case_id` property on the event class), never by parsing the stub's ID
(CM-11-003).

## `SemanticEntry` Phrases Use Only `{actor}`, `{object}`, `{target}`

The render pipeline (`CaseTimelineEvent.summary`, `event_phrase()`) fills no
other slot, so `{context}` or `{inner_object}` renders a dangling `"—"` in
production. The SE-07-005 allowlist test in `test/test_semantic_registry.py`
enforces this.

## Event Phrases Come From `lookup_entry()`, Never a Local Dict

Display code maps a `MessageSemantics` value to a phrase with
`lookup_entry(semantics).phrase` (`vultron/semantic_registry/`). A local
parallel dict drifts silently as the enum grows, whereas a missing
`SemanticEntry.phrase` fails at registry construction (SE-07-003). Fall back to
`semantic_type.replace("_", " ")` only for semantic types absent from the registry.
