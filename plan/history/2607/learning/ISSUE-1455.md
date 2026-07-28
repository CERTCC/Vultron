---
title: getattr(obj, name, default) does not suppress ValueError from property getters
type: learning
timestamp: "2026-07-17T00:00:00Z"
source: ISSUE-1455
---

Python's `getattr(obj, attr, default)` only catches `AttributeError`. If a property getter raises `ValueError` (as `VulnerabilityCase.current_status` does when `case_statuses` has no materialized entries), the default is never returned and the `ValueError` propagates.

Pattern to use when `current_status` (or any property that may raise) must be accessed safely:

```python
try:
    current_status = case.current_status
except (AttributeError, ValueError):
    current_status = None  # or return the safe default
```

The old `getattr(case, "current_status", None)` idiom was a latent bug across multiple BT nodes and use cases. All three call sites in ISSUE-1455 scope were fixed with `try/except` guards.

**Promoted**: 2026-07-20 — captured in `notes/domain-validation.md` § "Pitfall:
`getattr(obj, name, default)` Does Not Catch `ValueError`" and `AGENTS.md` pitfall bullet.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1523>3>
