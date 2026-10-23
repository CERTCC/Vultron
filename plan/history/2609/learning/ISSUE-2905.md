---
title: "inbox_handler and inbox_pipeline call rehydrate() outside try/except"
type: learning
timestamp: 2026-09-01T00:00:00Z
source: ISSUE-2905
signal: concern
---

In `vultron/adapters/driving/fastapi/inbox_handler.py:418` and
`vultron/adapters/driving/fastapi/inbox_pipeline.py:80`, `rehydrate()` is
called **outside** any try/except block.

Issue #2905 was caused by `VultronProtocolViolationError` (a plain
`VultronError` subclass) escaping Pydantic's `model_validate()` and
propagating all the way through `rehydrate()` into the bare call site,
crashing the `while` loop in `inbox_handler` and dropping all subsequent
inbox items.

The fix (adding `ValueError` to `VultronProtocolViolationError`'s MRO) makes
Pydantic absorb the exception for the specific validator that triggered it.
However, the structural fragility remains: any future Pydantic validator that
raises a new custom exception type **not** in the `(ValueError, TypeError,
AssertionError)` set would cause the same class of crash.

Recommend either:

1. Wrapping the `rehydrate()` call in `inbox_handler` and `inbox_pipeline`
   with a broad `except Exception` guard that logs and skips the bad item, or
2. Documenting a project convention that all exceptions raised from Pydantic
   validators MUST inherit from `ValueError`.

## Audit disposition (2026-09-02)

Filed as #3044.
