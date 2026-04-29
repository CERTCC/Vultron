---
title: "P347-SUGGESTBT \u2014 SuggestActorToCase BT Handler"
type: implementation
date: '2026-04-18'
source: P347-SUGGESTBT
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6787
legacy_heading: "P347-SUGGESTBT \u2014 SuggestActorToCase BT Handler"
date_source: git-blame
---

## P347-SUGGESTBT — SuggestActorToCase BT Handler

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6787`
**Canonical date**: 2026-04-18 (git blame)
**Legacy heading**

```text
P347-SUGGESTBT — SuggestActorToCase BT Handler
```

**Completed**: P347-SUGGESTBT

### Summary

Replaced the stub `SuggestActorToCaseReceivedUseCase.execute()` with a proper
behavior tree that enforces case-ownership preconditions, idempotency, and
outbox emission.

### New File

- `vultron/core/behaviors/case/suggest_actor_tree.py` — 4 BT nodes and factory:
  - `CheckIsCaseOwnerNode`: reads case from DataLayer, compares
    `case.attributed_to` to `actor_id`; returns FAILURE to silently skip if
    not owner.
  - `CheckNoExistingInviteNode`: uses a deterministic UUID-v5 invite ID to
    check for duplicate invite; returns FAILURE to skip if already sent.
  - `EmitAcceptRecommendationNode`: creates and queues
    `AcceptActorRecommendationActivity` (with full inline
    `RecommendActorActivity` as required `object_`).
  - `EmitInviteToCaseNode`: creates and queues `RmInviteToCaseActivity` with
    the same deterministic ID used by the idempotency check.
  - `create_suggest_actor_tree()`: factory returning the Sequence.

### Updated File

- `vultron/core/use_cases/received/actor.py` —
  `SuggestActorToCaseReceivedUseCase.execute()` now:
  1. Persists incoming recommendation via `_idempotent_create`.
  2. Finds local actor via `_find_local_actor_id`.
  3. Builds the BT via `create_suggest_actor_tree()`.
  4. Runs via `BTBridge.execute_with_setup()`.

### Tests Added

- `test/core/use_cases/received/test_actor.py` — merged into existing
  `TestSuggestActorUseCases`:
  - `test_suggest_actor_emits_both_activities_when_owner`
  - `test_suggest_actor_skips_when_not_case_owner`
  - `test_suggest_actor_idempotent_when_invite_exists`

### Test Result

1628 passed, 12 skipped, 182 deselected, 5581 subtests passed
