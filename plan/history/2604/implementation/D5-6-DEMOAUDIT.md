---
title: "D5-6-DEMOAUDIT \u2014 Audit and refactor all demos for protocol compliance\
  \ (2026-04-07)"
type: implementation
date: '2026-04-08'
source: D5-6-DEMOAUDIT
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 4865
legacy_heading: "D5-6-DEMOAUDIT \u2014 Audit and refactor all demos for protocol\
  \ compliance (2026-04-07)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-07'
---

## D5-6-DEMOAUDIT — Audit and refactor all demos for protocol compliance (2026-04-07)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:4865`
**Canonical date**: 2026-04-08 (git blame)
**Legacy heading**

```text
D5-6-DEMOAUDIT — Audit and refactor all demos for protocol compliance (2026-04-07)
```

**Legacy heading dates**: 2026-04-07

**Task**: D5-6-DEMOAUDIT (PRIORITY-310)

**Summary**: Audited multi-actor demo scripts against the protocol documentation
and applied targeted fixes to ensure demos demonstrate genuine protocol-driven
behavior rather than puppeteered workflows.

### Changes made

1. **CreateCaseActivity `to` field and full case embedding**
   (`vultron/core/behaviors/report/nodes.py`): The `CreateCaseActivity` node in
   the validate-report BT now derives addressees from `offer.actor`,
   `report.attributedTo`, and `offer.to` (excluding the sending actor). The full
   `VulnerabilityCase` is embedded as `object_` so receiving actors can store
   the case immediately from the activity payload without a separate fetch.

2. **CreateFinderParticipantNode `to` field**
   (`vultron/core/behaviors/case/nodes.py`): The `Add(CaseParticipant)`
   notification activity now sets `to=[finder_actor_id]` so the finder's inbox
   receives the participant-added notification.

3. **outbox_handler case object expansion**
   (`vultron/adapters/driving/fastapi/outbox_handler.py`): `handle_outbox_item`
   now expands `Create` activity `object_` from the DataLayer before delivery,
   so recipients receive the full domain object (e.g., `VulnerabilityCase`)
   rather than just an ID string reference.

4. **Finder case verification** (`vultron/demo/two_actor_demo.py`): Added
   `wait_for_finder_case()` polling helper and a `demo_check` verification block
   to confirm the finder received the case via cross-container protocol message
   delivery (not manual injection). The verification polls the finder's
   `/actors/{id}/objects/` endpoint until the case appears or a timeout elapses.

5. **Test updates**: Assertions in `test_nodes.py` and `test_validate_tree.py`
   updated to use `by_type()` raw data dicts for `Create`/`Add` activities
   (bypasses vocabulary deserialization for domain activity types that are not
   yet in the standard registry).

6. **Remaining gaps documented**: The `InitializeDefaultEmbargoNode` still
   creates `Announce(embargo)` with no `to` field (D5-6-EMBARGORCP remains
   open); `EmitCreateCaseActivity` in `case/nodes.py` (create-case BT) still
   lacks a `to` field (D5-6-CASEPROP partially open); auto-engagement after
   invitation acceptance is not yet implemented (D5-6-AUTOENG open); note
   broadcast to participants is not yet implemented (D5-6-NOTECAST open).

### Files changed

- `vultron/core/behaviors/report/nodes.py`
- `vultron/core/behaviors/case/nodes.py`
- `vultron/adapters/driving/fastapi/outbox_handler.py`
- `vultron/demo/two_actor_demo.py`
- `test/core/behaviors/report/test_nodes.py`
- `test/core/behaviors/report/test_validate_tree.py`
