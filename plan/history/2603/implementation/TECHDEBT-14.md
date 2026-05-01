---
title: "TECHDEBT-14 \u2014 Split vultron_types.py into per-type modules"
type: implementation
timestamp: '2026-03-13T00:00:00+00:00'
source: TECHDEBT-14
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1410
legacy_heading: "TECHDEBT-14 \u2014 Split vultron_types.py into per-type modules"
date_source: git-blame
---

## TECHDEBT-14 — Split vultron_types.py into per-type modules

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1410`
**Canonical date**: 2026-03-13 (git blame)
**Legacy heading**

```text
TECHDEBT-14 — Split vultron_types.py into per-type modules
```

**Completed**: 2026-03-13

Split `vultron/core/models/vultron_types.py` (273 lines, 11 classes) into
individual per-type modules following the `wire/as2/vocab/objects/` pattern:

- `_helpers.py` — shared `_now_utc` / `_new_urn` factory functions
- `case_event.py` — `VultronCaseEvent`
- `case_status.py` — `VultronCaseStatus`
- `participant_status.py` — `VultronParticipantStatus`
- `participant.py` — `VultronParticipant`
- `case_actor.py` — `VultronCaseActor`, `VultronOutbox`
- `activity.py` — `VultronActivity`, `VultronOffer`, `VultronAccept`, `VultronCreateCaseActivity`
- `report.py` — `VultronReport`
- `case.py` — `VultronCase`
- `note.py` — `VultronNote`
- `embargo_event.py` — `VultronEmbargoEvent`

`vultron_types.py` retained as a backward-compatibility re-export shim.
All existing callers continue to work without modification. 887 tests pass.

Note: `test_remove_embargo` is a pre-existing flaky test (py_trees blackboard
global state) that passes in isolation but occasionally fails in full suite.
