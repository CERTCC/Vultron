---
title: "Happy-path DataLayer seeds must include origin activities for use cases that call dl.read()"
type: learning
timestamp: "2026-07-10"
source: ISSUE-1326
---

When a use case calls `dl.read(some_id)` to resolve a related entity (e.g.
`recommender_id` from the original recommendation offer), the happy-path test
fixture must store that entity in the DataLayer or the use case silently falls
back to `""` / `None`.

In `AcceptActorRecommendationReceivedUseCase` and
`RejectActorRecommendationReceivedUseCase`, the `origin` field of the inner
`Offer(CaseParticipant)` carries the original recommendation activity ID.
The use case calls `self._dl.read(recommendation_id)` to look up that activity
and extract `recommender_id`. If the activity is absent, `recommender_id=""`
and the recommender-notification branch of the BT tree silently no-ops —
but `len(outbox) >= 1` passes anyway because other tree nodes emit to the
outbox. This hides the broken path.

**Fix pattern**: after building the inner offer with `origin=<recommendation_id>`,
call `dl.create(recommend_actor_activity(..., id_=<recommendation_id>))` in
the fixture so `dl.read()` resolves correctly.

**Assertion depth**: the Accept happy path emits both an Accept notification
and an Invite (2 activities). Assert `len(outbox) >= 2` — not `>= 1` — to
catch the case where only one of the two required activities was emitted.
