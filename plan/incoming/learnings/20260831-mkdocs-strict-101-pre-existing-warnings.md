---
title: mkdocs build --strict has 101 pre-existing warnings from markdown_exec failures
type: learning
timestamp: 2026-08-31T18:45:00Z
source: ISSUE-2525
signal: concern
---

During #2525, `uv run mkdocs build --strict` was run to verify the site builds cleanly.
It aborts with 101 warnings in strict mode. All warnings are from `markdown_exec` —
Python code blocks embedded in howto documentation pages that fail at build time with
Pydantic errors:

- `ValidationError` for frozen instances (e.g., `_UpdateCaseActivity.published`)
- `AttributeError` for missing attributes (e.g., `as_VulnerabilityCase.add_report`)
- `ValidationError` for frozen fields in `as_CaseStatus`, `as_CaseParticipant`, etc.

These are NOT caused by the current PR's changes. The `docs/reference/formal_protocol/`
pages build cleanly. The failures are in `docs/howto/activitypub/` code blocks that use
AS2 model objects whose API has drifted from the embedded examples.

This should be tracked as a Concern: the strict build cannot pass until the code
examples in the howto docs are updated to match the current AS2 model API.
