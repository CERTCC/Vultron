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
