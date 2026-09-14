---
source: CONCERN-3222
timestamp: '2026-09-14T19:34:30.923197+00:00'
title: sync CLP-14-006 message prints mixed timezone offsets
type: learning
---

## Summary

`vultron/core/behaviors/sync/nodes/canonical_entry.py:222`:

```python
case_published = _as_utc(case.published)       # keeps sender's local offset
entry_published = parse_published(entry.published)  # always UTC (+00:00)
```

`_as_utc` only attaches UTC to *naive* datetimes; an aware non-UTC `case_published` (e.g. `+05:30`) passes through unchanged. `entry_published` is always `.astimezone(timezone.utc)`.

The arithmetic comparison is correct (Python compares aware datetimes across offsets), but the CLP-14-006 violation message prints `case_published` in the sender's local offset while `entry_published` is in `+00:00`, making the log appear to compare unlike quantities.

## Fix

Apply `parse_published` (or `.astimezone(timezone.utc)`) to `case_published` as well, matching the docstring's claim ("converts non-UTC-offset aware inputs"). `parse_published` exists for exactly this reason.

## Discovery

Surfaced during code review of #3189. Pre-existing in `vultron/core/behaviors/sync/nodes/canonical_entry.py:222`.

**Resolved**: 2026-09-14 — planned; implementation tracked in #3229 (combined with CONCERN-3223). Docs PR: <https://github.com/CERTCC/Vultron/pull/3231>.
