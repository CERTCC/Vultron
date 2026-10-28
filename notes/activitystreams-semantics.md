---
title: ActivityStreams Semantics in Vultron
status: active
kind: guidance
tags: [as2, activitystreams, wire, semantics, extractor, rehydration, accept-reject]
description: >
  Activities as state-change statements, not commands; inbound/outbound
  semantics, Accept/Reject object rules, and rehydration.
related_specs:
  - specs/semantic-extraction.yaml
  - specs/response-format.yaml
  - specs/case-management.yaml
  - specs/embargo-policy.yaml
related_notes:
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

## Responses Reference the Request Twice

A response to an Offer or Invite sets `object` to the full inline Offer/Invite
**and** `inReplyTo` to its ID (RF-02-004, RF-03-003, RF-04-003, RF-08-001). The
object may travel inline or by reference on the wire (RF-02-004, RF-02-005), but
this codebase requires the inline typed activity, not a bare ID string
(RF-02-006, RF-02-007, a prototype shortcut): the internal Accept/Reject classes
reject a string at construction. When the request came from
the DataLayer, `rehydrate(obj, dl=dl)` (`vultron/wire/as2/rehydration.py`)
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

## Accepting an Embargo Accepts the Invite

Embargo negotiation works like a calendar invitation: the proposer sends
`Invite(Actor, EmbargoEvent)`, invitees answer `Accept(Invite)` or
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

## `Reject(Invite(actor, stub))` Carries the Stub in `inner_target`

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
