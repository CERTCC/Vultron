---
title: No spec says a derived actor endpoint collection carries no clock stamp, and ARCH-12-006's `str | None` no longer describes the core field
type: learning
timestamp: 2026-09-29T21:30:00Z
source: ISSUE-3732
signal: spec-gap
---

`as_Actor` derives an actor's `inbox`/`outbox` `OrderedCollection` from a bare
URI or from the actor's own id. Until PR #3904 those collections were stamped
with `published`/`updated` from `now_utc()` by `as_Object`'s defaults, and the
datalayer — which keeps an actor as `CoreActor` with URI-only endpoints
(ARCH-12-006) — dropped the stamps on write and minted new ones on read. A
stored actor read back equal to itself only when the two calls shared a
wall-clock second (#3732, #3726). The fix builds a derived endpoint as an
*address*: no clock stamp, while a stamp that arrives on a collection is kept
as received.

No requirement states either half of that rule:

- Nothing says a derived endpoint collection carries no `published`/`updated`.
  ARCH-23-003 pins the endpoint wire form to "address, type and items", and
  its ratchet test had been popping both keys before it could make that claim.
  ADR-0103 says an object this process *authors* is stamped and an inbound
  omission stays `None`; a *derived address* is neither, and no clause places
  it. The rule lives in `notes/datalayer-design.md` and an AGENTS.md cell, and
  in tests, but not in a spec.
- ARCH-12-006 says the core actor's `inbox`/`outbox` "MUST be typed
  `str | None`". Since #3616 they are `str`, never `None`: an absent, `None`
  or blank endpoint is derived from `id_`, because ActivityPub requires both.
  The statement's substance (URI-only, no collection wrapping) still holds; its
  type clause does not.

Candidate home: an ARCH-23 or ARCH-12 statement that a derived endpoint
collection is unstamped and an arrived stamp is carried, plus a wording fix to
ARCH-12-006 (`str`, derived when absent). `test_derived_endpoint_carries_no_clock_stamp`
and `test_actor_round_trips_through_uri_endpoints_across_a_clock_tick` in
`test/wire/as2/vocab/base/test_actor_endpoints.py` are ready to carry a
`@pytest.mark.spec` marker once the id exists.
