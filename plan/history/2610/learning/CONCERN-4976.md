---
source: CONCERN-4976
timestamp: '2026-10-26T16:32:30.552745+00:00'
title: Actor factories fabricate a partial actor profile from a bare actor URI
type: learning
---

## Problem

`recommend_actor_activity` and `rm_invite_to_case_activity` (in `vultron/wire/as2/factories/actor.py` and `case.py`) both take `as_Actor | str`. When given a URI, they build `as_Actor(id_=uri)`. The sealed body then carries an `Actor` object that nobody sent and that holds data no one asserted:

- `published` and `updated` times read from the sender's clock;
- `inbox` and `outbox` collections whose URLs are guessed from the actor id (`<id>/inbox`, `<id>/outbox`).

The same pattern feeds `offer_case_participant_activity`, through its `#participant` id.

## Why it matters

- **MV-10-001** forbids partial inline objects for any type except the case stub. A sender that does not hold the full object must reference it by URI.
- **AKM-03-003** requires the activity's `object` inline, and the outbox guard enforces that, so a bare URI is not an option either today.
- ADR-0107's dereference model (#3739) is the protocol answer: a receiver fetches an actor named by URI.

The fabricated profile hides the conflict between these rules. A receiver that stores it now holds guessed inbox and outbox URLs, plus times nobody claimed.

## Where

- `vultron/wire/as2/factories/actor.py`, `recommend_actor_activity`
- `vultron/wire/as2/factories/case.py`, `rm_invite_to_case_activity`

Found while building #3740 (PR #4975). `test/architecture/test_introduced_objects_inline.py` classifies these factories as naming an actor by URI (AKM-05-001), which is the intended behavior, not the current one.

## Decision needed

Should an actor in `object` travel as a bare URI (an AKM-03-003 exception for actors, dereferenced per #3739), or as the full profile the sender holds, refusing to send when it holds none?

Governing specs: MV-10-001, AKM-03-003, AKM-05-001

**Resolved**: 2026-10-26 — implementation tracked in #5177.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5180>.
Spec: `specs/actor-knowledge-model.yaml` (AKM-02-006, AKM-05-005), `specs/message-validation.yaml` (MV-10-001), `specs/outbox.yaml` (OX-12-009). Decision record: ADR-0159.
