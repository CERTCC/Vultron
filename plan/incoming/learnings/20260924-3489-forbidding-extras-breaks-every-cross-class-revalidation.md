---
title: Tightening a model to extra="forbid" breaks every cross-class revalidation into it, and the suite does not see it
type: learning
timestamp: 2026-09-24T18:00:00+00:00
source: ISSUE-3489
signal: theme-candidate
---

When ADR-0099 detail 4 moved `VultronActivity` onto `CoreObject`, it inherited
`extra="forbid"`. `outbox_delivery._load_outbound_activity` validates a *wire*
activity's dump into it (`VultronActivity.model_validate(wire.model_dump(...))`).
Every wire field `VultronActivity` did not declare became a hard delivery
failure:

- first `instrument`/`result`, which the suite caught;
- then `as_Question`'s `anyOf`/`oneOf`/`closed`, which it did not. The full
  `-m ""` suite was green, and only the pre-PR review found the break.

The shape of the hazard: `Narrow.model_validate(Wide.model_dump())`, where
`Wide` is a different class. Tightening `Narrow` fails only for the `Wide`
subclasses whose extra fields happen to be populated, and only on the paths that
reach that call. A per-example test covers only the classes it builds.

What caught it here was a structural test: for every class that can reach the
call, its dumped keys must be a subset of the keys the target accepts
(`test_vultron_activity_accepts_every_wire_activity_key`). The claim this entry
is waiting to confirm: when `extra="forbid"` is added or inherited, each
cross-class `model_validate` into that model needs a structural test like this
one, because example-based tests do not cover it. One instance so far.
