---
status: accepted
date: 2026-08-20
deciders: sei-ahouseholder
---

# Refuse Misaddressed Activities at the Inbox with a Synchronous 4xx

## Context and Problem Statement

Each Vultron actor has its own isolated DataLayer (ADR-0066, ADR-0012). The
DataLayer's owner is the authoritative answer to "whose replica is this?" —
but only if every Activity stored in that DataLayer was actually addressed to
its owner. Currently, `POST /actors/{actor_id}/inbox/` returns 202 and
processes any Activity delivered to it, even when the Activity's addressing
fields (`to`, `cc`, `bto`, `bcc`) name a completely different actor. This
undermines the per-actor isolation guarantee and violates the Actor Knowledge
Model (AKM): an actor should only hold state derived from Activities that
were directed at it.

## Decision Drivers

- Per-actor DataLayer isolation is only trustworthy if the store's owner was
  the intended recipient of every Activity it contains (ADR-0066).
- Liberal Accept (Postel's Law): refuse the narrowest thing that must be
  refused; accept anything uncertain.
- The refusal must be synchronous so the sender receives a 4xx rather than a
  silent discard. A 4xx is itself the signal.
- Outbound Activities already carry a non-empty `to` field (OX-08), so
  legitimately-delivered Activities always have addressing to check against.

## Considered Options

1. **Synchronous 4xx before the 202** — check addressing before accepting the
   request; return HTTP 400 when the Activity provably excludes the receiving
   actor; accept (fall through) when addressing is absent or unresolvable.
2. **Return 202 and dead-letter it in the pipeline** — reuse
   `vultron/core/behaviors/inbox/nodes/dead_letter.py`; give an admin-visible
   record; process asynchronously.
3. **Both, split by cause** — synchronous 4xx for "not for me"; dead-letter
   for "I cannot tell".

## Decision Outcome

Chosen option: **"Synchronous 4xx before the 202"**, because:

- It prevents writing a misaddressed Activity to the wrong actor's store at
  all — option 2 would persist it first, which is a mild instance of
  exactly the cross-actor contamination ADR-0066 removes.
- Liberal Accept resolves the "I cannot tell" case in favour of accepting, so
  the two-mechanism split of option 3 is unnecessary: absent addressing
  falls through unchanged, and only provable exclusion triggers the refusal.
- The parsed Activity is already available at the route boundary via the
  `parse_activity` FastAPI dependency, so no extra parse step is needed.

### Consequences

- Good: the Actor Knowledge Model invariant is structurally enforced at the
  HTTP boundary, not inferred from downstream logic.
- Good: senders receive an unambiguous error signal (4xx) rather than silent
  discard.
- Good: the check requires no new infrastructure — it is a thin guard on data
  already present at the route level.
- Neutral: the implementation lives in the FastAPI adapter layer rather than
  in the core inbox orchestration module (IO-03-003b). This is a justified
  exception: the refusal must be synchronous and precede the 202, which
  requires acting before the background task is scheduled. The tradeoff is
  documented here so future maintainers do not move it into core without
  reconsidering the synchrony requirement.

## Validation

- IE-11-001 through IE-11-003 in `specs/inbox-endpoint.yaml` record the
  normative requirements; unit tests in
  `test/adapters/driving/fastapi/routers/actors/test_inbox.py` verify the
  helper logic, and route-level tests in
  `test/adapters/driving/fastapi/routers/test_actors.py` verify the HTTP
  response.

Generated spec requirements: `inbox-endpoint.yaml` IE-11-001, IE-11-002,
IE-11-003.
