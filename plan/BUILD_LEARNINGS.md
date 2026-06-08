## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

### 2026-06-08 ISSUE-654 — Surrogate-key routing collision handling

- Surrogate-key resolution must treat ambiguous matches as errors, not
  first-match wins; otherwise actor/case lookups become non-deterministic when
  multiple canonical IDs share a tail segment.
- Case-key resolution should continue to short-key fallback even when
  `dl.read(key)` returns a non-case object; otherwise non-case IDs can shadow
  valid case keys and produce false 404/validation failures.
