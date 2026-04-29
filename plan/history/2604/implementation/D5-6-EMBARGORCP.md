---
title: "D5-6-EMBARGORCP \u2014 Remove Redundant Embargo Announce Activity"
type: implementation
date: '2026-04-08'
source: D5-6-EMBARGORCP
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 5008
legacy_heading: "D5-6-EMBARGORCP \u2014 Remove Redundant Embargo Announce\
  \ Activity (COMPLETE 2026-04-11)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-11'
---

## D5-6-EMBARGORCP — Remove Redundant Embargo Announce Activity

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:5008`
**Canonical date**: 2026-04-08 (git blame)
**Legacy heading**

```text
D5-6-EMBARGORCP — Remove Redundant Embargo Announce Activity (COMPLETE 2026-04-11)
```

**Legacy heading dates**: 2026-04-11

### What was done

Removed the standalone `Announce(embargo)` activity from
`InitializeDefaultEmbargoNode.update()` in
`vultron/core/behaviors/case/nodes.py`. The node was creating a generic
`VultronActivity(type_="Announce")` with no `to` field and queuing it to the
outbox — an unaddressed broadcast. Per `notes/protocol-event-cascades.md`
Option 2, this is redundant: the finder already receives embargo information
via `VulnerabilityCase.active_embargo` embedded in the `Create(Case)`
activity sent by `CreateCaseActivity` / `EmitCreateCaseActivity`.

Updated docstring to reflect that embargo info flows via `Create(Case)`.
Replaced the old `test_validate_report_tree_logs_announce_type_for_embargo`
test with two new tests verifying the correct behavior:

- `test_validate_report_tree_case_has_active_embargo`
- `test_validate_report_tree_create_case_activity_embeds_embargo`

### Files changed

- `vultron/core/behaviors/case/nodes.py` — removed ~25 lines from
  `InitializeDefaultEmbargoNode.update()`; updated docstring
- `test/core/behaviors/report/test_validate_tree.py` — replaced one test
  with two new tests

### Validation

- `uv run black vultron/ test/` → files reformatted; clean
- `uv run flake8 vultron/ test/` → no errors
- `uv run mypy` → no issues
- `uv run pyright` → 0 errors, 0 warnings
- `uv run pytest --tb=short 2>&1 | tail -5` → `1267 passed, 5581 subtests passed in 32.59s`
