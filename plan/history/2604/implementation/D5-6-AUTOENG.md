---
title: "D5-6-AUTOENG \u2014 Auto-engage after invitation acceptance (2026-04-08)"
type: implementation
date: '2026-04-08'
source: D5-6-AUTOENG
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 4922
legacy_heading: "D5-6-AUTOENG \u2014 Auto-engage after invitation acceptance\
  \ (2026-04-08)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-08'
---

## D5-6-AUTOENG — Auto-engage after invitation acceptance (2026-04-08)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:4922`
**Canonical date**: 2026-04-08 (git blame)
**Legacy heading**

```text
D5-6-AUTOENG — Auto-engage after invitation acceptance (2026-04-08)
```

**Legacy heading dates**: 2026-04-08

**Task**: D5-6-AUTOENG (PRIORITY-310)

**Summary**: Invitation acceptance now completes the RM engagement step
automatically, so invited actors reach RM.ACCEPTED and emit an engage activity
without a separate demo-runner trigger.

### Changes made

1. **Auto-engage in receive-side use case**
   (`vultron/core/use_cases/received/actor.py`):
   `AcceptInviteActorToCaseReceivedUseCase` now invokes
   `SvcEngageCaseUseCase` immediately after creating the participant record and
   pre-seeding RECEIVED/VALID RM states. This advances the invited actor to
   RM.ACCEPTED and queues an `RmEngageCaseActivity` in the actor outbox.

2. **Receive-side regression coverage**
   (`test/core/use_cases/received/test_actor.py`): Updated invitation-acceptance
   tests to persist the invited actor in the DataLayer, assert direct
   RM.ACCEPTED auto-engagement, and verify that a Join/engage activity is
   queued in the invited actor's outbox.

3. **Demo workflow cleanup**
   (`vultron/demo/three_actor_demo.py`,
   `vultron/demo/multi_vendor_demo.py`): Removed the manual `engage-case`
   trigger calls that followed invite acceptance. The demos now rely on the
   protocol flow triggered by `Accept(Invite(...))`.

### Files changed

- `vultron/core/use_cases/received/actor.py`
- `test/core/use_cases/received/test_actor.py`
- `vultron/demo/three_actor_demo.py`
- `vultron/demo/multi_vendor_demo.py`

### Validation

- `uv run black vultron/ test/`
- `uv run flake8 vultron/ test/`
- `uv run mypy`
- `uv run pyright`
- `uv run pytest --tb=short 2>&1 | tail -5` → `1262 passed, 5581 subtests passed in 34.21s`
