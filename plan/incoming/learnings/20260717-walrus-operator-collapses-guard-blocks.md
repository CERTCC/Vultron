---
title: Walrus operator collapses two-line guard blocks to one
type: learning
timestamp: 2026-07-17T21:30:00Z
source: ISSUE-1499
---

When extracting guard helpers that return `Status | None`, the pattern:

```python
fail = self._require_factory()
if fail is not None:
    self.logger.warning(...)
    return fail
```

Can be collapsed to a single check using the walrus operator:

```python
if (f := self._require_factory()) is not None:
    self.logger.warning(...)
    return f
```

This saves 2 lines per guard, which matters when reducing `update()` methods
from ~40-60 lines to ≤30 lines.

**Promoted**: 2026-07-20 — captured in `AGENTS.md` ("Walrus Operator for
Single-Assignment Guard Blocks" pitfall bullet).
Docs PR: <!-- filled in after PR opens -->
