---
source: CONCERN-3223
timestamp: '2026-09-14T19:34:31.323210+00:00'
title: sync _find_prev_actor_published sorts an already-ordered list
type: learning
---

## Summary

`vultron/core/sync_helpers.py:354`:

```python
matches.sort(key=lambda entry: entry.log_index)
```

`recorded_entries_for_case` returns entries ordered by `log_index` (ascending). Iterating `pool` in order and appending matching entries preserves that order in `matches`. The `sort` is therefore a no-op on every real call.

## Impact

Obscures that the function relies on pool ordering. If `recorded_entries_for_case` ever changes its sort key, the sort silently stops working (or the function silently stops being correct).

## Fix

Remove the redundant sort and document the pool-ordering dependency in the docstring. Planning noted the **identical** redundant sort also exists in `_find_equivalent_recorded_entry` (`vultron/core/sync_helpers.py:~285`), fed by the same pool; both sites are addressed so the concern does not regrow.

## Discovery

Surfaced during code review of #3189. Pre-existing in `vultron/core/sync_helpers.py:354`.

**Resolved**: 2026-09-14 — planned; implementation tracked in #3229 (combined with CONCERN-3222). Docs PR: <https://github.com/CERTCC/Vultron/pull/3231>.
