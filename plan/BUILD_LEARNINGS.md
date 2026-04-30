## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

### 2026-04-29 BUG-471.6 — BTBridge.get_failure_reason vs result.feedback_message

When a `py_trees` Sequence fails because a child fails, the root Sequence
node's `feedback_message` is always `""`. Use `BTBridge.get_failure_reason(tree)`
(depth-first walk to the first failing leaf) to get a meaningful message.
Apply this pattern consistently wherever `result.feedback_message` is logged
after a BT failure — not just for EngageCaseBT.

### 2026-04-30 P472-BUG386 — Closed via sender-side inline-object fix

TASK-BUG-386 (deferred handling for unresolvable `Accept.object_` URIs) was
resolved by commit `62cdc48e` which made the parser embed the full inline typed
object in every `Accept`/`Reject` activity before it leaves the outbox. The
receiver-side dead-letter path (`UnresolvableObjectUseCase`) remains in place
for non-compliant or legacy senders; it was not changed. If a future need arises
to auto-retry deferred activities, implement a `DeferredActivityRecord` model
and a dispatcher post-hook (see issue #386 description for design sketch).

### 2026-04-30 TASK-DL-REHYDRATE — Do not name a method `list` in a Python class

Defining `def list(self, ...)` on a class causes Python to shadow the built-in
`list` type in the class body scope. Any annotation `list[str]` that appears
AFTER the `def list(...)` definition is evaluated at class-body execution time
with `list` resolving to the method (a function), producing `TypeError:
'function' object is not subscriptable`. `# type: ignore[valid-type]` only
suppresses mypy — it does NOT prevent the runtime error. Fix: rename the method
to avoid collision (e.g., `list_objects`). This affects any method that shares
a name with a Python built-in type (`dict`, `set`, `tuple`, etc.).
