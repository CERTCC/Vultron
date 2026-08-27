---
title: "_EmitSingleActivityBase: _on_success() must live outside the try block"
type: learning
timestamp: "2026-08-25T00:00:00Z"
source: ISSUE-2582
signal: design-question
---

When writing base-class emit nodes that follow the guard+emit+outbox pattern,
the `_on_success()` hook must be called **outside** the `try/except` block,
not inside it.

If `_on_success()` is inside the `try`, any exception it raises causes the
`except` to catch it and return `Status.FAILURE` — even though the outbox
write (`record_outbox_item`) and `_captured` update have **already committed**.
The BT parent sees FAILURE and may retry or compensate against a write that
already landed, producing a duplicate outbox entry or incorrect state.

**Rule for all future `_Emit*Base` classes:**

```python
try:
    activity_id, activity_dict = self._call_factory()
    dl.record_outbox_item(...)
    if self._captured is not None:
        self._captured["activity"] = activity_dict
except Exception as e:
    ...
    return Status.FAILURE
# _on_success OUTSIDE the try
self._on_success(activity_id, activity_dict)
return Status.SUCCESS
```

The `activity_id` / `activity_dict` variables are guaranteed to be in scope
here because the `except` always returns — Python (and pyright) handle this
correctly without "possibly unbound" errors.

Follow-up: #2609 (add test for `_on_success` raising after committed write).

**Promoted**: 2026-08-27 — captured in notes/bt-pitfalls.md and AGENTS.md. Docs PR: <pending>.
