---
source: CONCERN-515
timestamp: '2026-06-03T19:29:46.546754+00:00'
title: SEMANTIC_REGISTRY order guard and design notes
type: learning
---

## Summary

`vultron/wire/as2/extractor.py` (821 lines, 36 changes in 90 days) contains the
ordered list of `ActivityPattern` definitions used for AS2 semantic extraction.
Pattern ordering is order-sensitive: more-specific patterns must precede
more-general ones. Ordering errors can cause the wrong use case to be invoked
silently.

## Category

- [x] Fragile / high-churn area

## Severity

medium

## Evidence

- `vultron/wire/as2/extractor.py` (821 lines, 36 changes in 90 days)
- `test/test_semantic_activity_patterns.py`

## Impact if Ignored

A misplaced pattern causes the wrong handler to be invoked for an incoming activity,
silently corrupting protocol state with no immediate error signal.

## Resolution

**Root cause**: No structural guard exists to prevent a less-specific
`SemanticEntry` from preceding a more-specific one in `SEMANTIC_REGISTRY`, AND
the ordering rationale (groups, specific-before-general rule) was undocumented.

**Approach**: Add an import-time `_validate_registry_order()` call at the bottom
of the semantic registry module that raises `RegistryOrderError` if ordering
is violated — making mis-ordering impossible to miss. Document the group
structure and ordering rationale inline and in a new notes file.

**Resolved**: 2026-06-03 — implementation tracked in #708.
Docs PR: [#707](https://github.com/CERTCC/Vultron/pull/707).
