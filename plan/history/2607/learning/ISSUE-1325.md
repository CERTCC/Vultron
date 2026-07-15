---
title: "Always check BTBridge.execute_with_setup return value"
type: learning
timestamp: 2026-07-13T00:00:00Z
source: ISSUE-1325
---

`BTBridge.execute_with_setup` never raises — it catches all exceptions from
the inner BT tick and returns a `BTExecutionResult(status=FAILURE)`.  If the
caller ignores the return value and falls through to `return Status.SUCCESS`,
the node silently succeeds even when the BT subtree failed.

Pattern to follow:

```python
result = BTBridge(...).execute_with_setup(tree=commit_tree, actor_id=self.actor_id)
if result.status != Status.SUCCESS:
    raise RuntimeError(f"subtree failed: {result.feedback_message}")
```

Raising inside the outer `except Exception` handler ensures the calling node
returns FAILURE rather than SUCCESS.

**Promoted**: 2026-07-15 — captured in notes/bt-integration.md.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1458>8>8>8>8>.
