---
title: Consolidate find_matching_semantics into semantic_registry
type: implementation
timestamp: '2026-04-30T14:39:05+00:00'

source: TASK-RFC-402
---

## TASK-RFC-402 — Consolidate find_matching_semantics into semantic_registry

Moved `find_matching_semantics()` from `vultron/wire/as2/extractor.py` to
`vultron/semantic_registry.py`, where it now iterates `SEMANTIC_REGISTRY`
directly. Deleted the duplicate `_PATTERN_SEMANTICS` list (~90 lines) and
`_ACTIVITY_TYPES_WITH_PATTERNS` from `extractor.py`. Added `matches_semantics()`
predicate to `semantic_registry.py`. Updated 3 import sites:
`datalayer_sqlite.py`, `test/test_semantic_activity_patterns.py`,
`test/wire/as2/test_extractor.py`. Net change: ~-100 lines, no new files.
All 1962 unit tests pass, all 4 linters clean.
