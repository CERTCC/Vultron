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

### 2026-04-30 P472-LATEX — #234/#235 (conclusion.md / transitions.md) not directly patched

Commit `2c116d57` claims to close #234 (unrendered LaTeX in `conclusion.md`)
and #235 (unrendered LaTeX in `transitions.md`) but neither file was modified.
The rationale is that the `\label{}` removal from `formal_protocol/index.md`
(same MathJax context) resolved the rendering indirectly. Neither file
contains `\label{}` commands. If LaTeX rendering issues resurface on those
pages, investigate:

1. Whether MathJax version or config changed.
2. Whether any `$$…$$` block inside an admonition needs explicit blank-line
   separation (pymdownx.arithmatex `generic: true` quirk).
3. Whether the 4-space vs 8-space indentation rule applies.

### 2026-04-30 P472-BUG386 — Closed via sender-side inline-object fix

TASK-BUG-386 (deferred handling for unresolvable `Accept.object_` URIs) was
resolved by commit `62cdc48e` which made the parser embed the full inline typed
object in every `Accept`/`Reject` activity before it leaves the outbox. The
receiver-side dead-letter path (`UnresolvableObjectUseCase`) remains in place
for non-compliant or legacy senders; it was not changed. If a future need arises
to auto-retry deferred activities, implement a `DeferredActivityRecord` model
and a dispatcher post-hook (see issue #386 description for design sketch).
