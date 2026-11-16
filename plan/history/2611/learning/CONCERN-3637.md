---
source: CONCERN-3637
timestamp: '2026-11-16T18:48:22.357522+00:00'
title: Remote actors recorded by URI alone get a guessed inbox instead of their declared
  one
type: learning
---

Theme: theme:wire-delivery — stops remote actors recorded by URI alone from getting a guessed inbox.

## Concern

When actor discovery can't fetch a remote peer, `vultron/core/use_cases/triggers/actor.py:257` records `CoreActor(id_=actor_id)` with "only URI known". Since #3614 (#3616), `CoreActor` fills in the missing inbox/outbox as `{id}/inbox` and `{id}/outbox`. That is correct for actors Vultron hosts. For a remote actor it is a **guess**, stored alongside real data with nothing marking it as a guess.

ActivityPub's answer is to dereference the actor and read its `inbox` and `outbox` from its profile. Until discovery does that, a stored remote record cannot be trusted as the peer's address. Once delivery reads the stored inbox (see the companion delivery Concern), a wrong guess becomes a misdelivery.

## Evidence needed / direction

- When discovery succeeds, the recorded actor should carry the inbox/outbox from the fetched profile. Check whether it does today.
- When discovery fails, choose between marking the record as unconfirmed (so delivery re-fetches or refuses) and restricting the id-based fill-in to actors Vultron hosts, which would need a way for a remote stub to exist without a derived inbox.
- Decide whether the fill-in in `CoreActor._derive_endpoints_from_id` should apply only to locally hosted actors.

Surfaced while fixing #3616 (PR #3614).

**Resolved**: 2026-11-16 — answered by AKM-02-006 (an actor does not record or send an inbox or outbox derived from another actor's id) and OX-12-010; `CoreActor._derive_endpoints_from_id` is gone and `CoreActor.inbox` defaults to `None`. Found by the learn run's Concern staleness check.
Docs PR: https://github.com/CERTCC/Vultron/pull/6528.
