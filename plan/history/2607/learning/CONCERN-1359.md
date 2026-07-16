---
source: CONCERN-1359
timestamp: '2026-07-13T18:33:01.042481+00:00'
title: None defaults for collection-typed parameters should be empty collections
type: learning
---

## Summary

Several function parameters and dataclass fields use `None` as a default for
collection-typed values (`dict`, `set`). Every call-site then guards with
`x or {}` / `x or set()` before use, spreading defensive boilerplate across
the codebase.

## Affected sites

| Parameter | File | Current default | Call-site guard |
|---|---|---|---|
| `payload_snapshot: dict[str, Any] \| None` | `core/models/case_ledger.py:399`, `core/behaviors/sync/nodes/chain.py:353` | `None` | `payload_snapshot or {}` |
| `excluded_actor_ids: set[str] \| None` | `core/behaviors/case/update_support.py:98`, `core/use_cases/received/case/update.py:58` | `None` | `excluded_actor_ids or set()` |

## Impact

Callers must remember to guard before every use. A missed guard causes a
`TypeError` at iteration/subscript time rather than at the boundary. The
`or {}` pattern also silently coerces falsy non-None values.

## Recommended fix

Change parameter defaults to the appropriate empty collection (`{}` /
`set()`). Remove the `or {}` / `or set()` guards at all call-sites.

Note: `BTExecutionResult.errors`, `VultronActivity.to/cc`, and
`CaseReference.tags` are intentional `None`-as-sentinel fields and should
**not** be changed.

**Resolved**: 2026-07-13 — implementation tracked in #1371.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1370>.
Spec: `specs/code-style.yaml` (CS-21-001).
