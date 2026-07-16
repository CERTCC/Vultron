---
source: ISSUE-1328
timestamp: '2026-07-10T20:00:19.707495+00:00'
title: fix _CASE singleton mutation in create_case() example
type: implementation
---

## Issue #1328 — [Bug] mkdocs build: markdown_exec code blocks fail due to_CASE singleton reuse

`create_case()` in `vultron/wire/as2/vocab/examples/case.py` was calling
`case()` (the shared `_CASE` module-level singleton) and then calling
`add_participant()` on it. The second `markdown_exec` code block invocation
during `mkdocs build --strict` found the vendor actor already registered in
`actor_participant_index` from the first call, raising
`VultronValidationError`. Fix: call `case(random_id=True)` so each
`create_case()` invocation gets a fresh `VulnerabilityCase` instance with an
empty `actor_participant_index`.

Updated `test_create_case` to assert non-empty id (since the case id is now
random per call), and added regression test
`test_create_case_multiple_calls_do_not_raise`.

PR: <https://github.com/CERTCC/Vultron/pull/1350>
