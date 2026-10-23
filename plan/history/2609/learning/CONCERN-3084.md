---
source: CONCERN-3084
timestamp: '2026-09-22T14:13:57.849820+00:00'
title: 'concern(bridge): four nearly-identical exception-handler blocks across execute_tree
  and execute_with_setup'
type: learning
---

`execute_tree` and `execute_with_setup` each have two exception-handler blocks (`VultronError` and `Exception`) that are near-identical. Extending `BTExecutionResult` requires four coordinated edits with no compiler enforcement, and the execute_with_setup VultronError block was already missed in PR #3064 (wrong log level, tracked #3080). A private `_error_result()` helper would collapse this to four one-line call sites and enforce consistency at the definition, preventing the log-level divergence that created #3080.

**Resolved**: 2026-09-22 — implementation tracked in #3510.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3509>.
