---
title: One actor id is one database — reusing it for two scenarios collides
type: learning
timestamp: 2026-08-19
source: ISSUE-2238
signal: testing-pitfall
---

Under ADR-0066 an in-memory store is **named** (`?mode=memory&cache=shared`) and
the engine cache is keyed by `(db_url, actor_id)`. So two `SqliteDataLayer`
instances constructed with the same `actor_id` are **the same database**, not two
independent ones.

Two consequences, in opposite directions, and both were seen on #2238:

- **Two logical actors sharing one store** hides a missing write: the reader finds
  the writer's row and the test passes for the wrong reason. This is the defect
  class the whole issue is about.
- **One actor id used for two independent scenarios** collides: the second seed
  raises `ValueError: record with id_=... already exists`. Seen in
  `test_action_rules.py`, where five tests took a pre-seeded `dl` fixture and then
  built their own store for the same `ACTOR_ID`, and in a loop that built one store
  per EM state under a single id and so collided with itself on pass two.

Both come from treating "which actor" as a *label on* a store rather than as the
store's *identity*. The first direction loses data silently; the second fails
loudly. Only the loud one was noticeable before per-actor storage, which is why the
silent one accumulated.

**How to apply**: an actor id is a store name. Two scenarios that must not see each
other's rows need two actor ids — deriving one per test (`f"{ACTOR_ID}/{slug}"`) is
enough and is self-documenting. Conversely, do not give one logical actor two ids
just to get a fresh database; that reintroduces the masking.

Related: `test/conftest.py`'s autouse `_dispose_actor_stores_between_tests` handles
the *between-test* case. Neither of the above is a between-test problem — they both
occur within a single test — so the fixture cannot help.
