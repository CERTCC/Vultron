---
source: ISSUE-1326
timestamp: '2026-07-10T18:12:41.304110+00:00'
title: 'test: AcceptActorRecommendationReceivedUseCase and RejectActorRecommendationReceivedUseCase
  dedicated execute() unit tests'
type: implementation
---

## Issue #1326 — test: AcceptActorRecommendationReceivedUseCase and RejectActorRecommendationReceivedUseCase dedicated execute() unit tests

Added 6 new `execute()`-path unit tests in `test/core/use_cases/received/actor/test_suggest.py`:

- `TestAcceptActorRecommendationReceivedUseCase`: happy path (asserts ≥2 outbox entries — Accept notification + Invite), missing `case_id`, no local actor
- `TestRejectActorRecommendationReceivedUseCase`: happy path (asserts ≥1 outbox entry — Reject notification), missing `case_id`, no local actor

Key fix during code review: `_build_accept_reject_dl()` initially omitted the original recommendation activity from the DataLayer. Without it, `dl.read(recommendation_id)` returned `None` and `recommender_id` silently fell back to `""`, meaning the recommender-notification tree branch was never exercised. Fixed by storing the recommendation (`recommend_actor_activity(...)`) in the DataLayer and strengthening the Accept happy-path assertion from `>= 1` to `>= 2`.

PR: <https://github.com/CERTCC/Vultron/pull/1340>
