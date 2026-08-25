---
title: Ratchet regex misses aliased-local-variable append pattern
type: learning
timestamp: '2026-08-17T00:00:00+00:00'
source: ISSUE-2295
signal: concern
---

The `_MUTATION_RE` pattern in `test/architecture/test_validate_assignment_ratchet.py`
only matches direct-chained access (`obj.participant_statuses.append(...)`). Two sites
in `vultron/core/behaviors/case/nodes/participant/` use the aliased pattern:

```python
participant_statuses = getattr(obj, "participant_statuses", None)
participant_statuses.append(...)
```

These were never listed in `_COLLECTION_MUTATION_BACKLOG` because the regex never caught them,
so emptying the backlog in #2295 did not require converting them. They remain as live
direct-append violations invisible to the ratchet.

Follow-up issue #2343 covers both converting the two sites and extending the ratchet scan
to detect the aliased pattern (e.g., via AST variable-binding tracking or a complementary
grep for `getattr.*participant_statuses` + `.append`).

**Promoted**: 2026-08-24 — captured in archive only (issue #2343 already closed).
Docs PR: [PR URL TBD].
