---
title: spec-dump --kind filter has no SR-07 spec entry
type: learning
timestamp: '2026-08-20T00:00:00+00:00'
source: ISSUE-2389
signal: spec-gap
---

SR-07-005 requires that "the JSON exporter SHOULD support filtering by `kind`,
`scope`, `tags`, or `priority`". This covers `export_json` (the generic JSON
exporter in `render.py`), but the `spec-dump` / `main_llm_json` / `to_llm_json`
LLM-optimized path has no corresponding spec entry.

ISSUE-2389 implemented `--kind` CLI support for `spec-dump`, but no spec entry
was added to `specs/spec-registry.yaml` covering this requirement.

A follow-up should add an SR-07 entry such as:
> The `spec-dump` CLI entry point SHOULD support a `--kind` flag accepting one
> or more comma-separated `SpecKind` values, filtering the LLM-optimized JSON
> output to matching requirements. An unknown kind value MUST produce a clear
> error and exit 2.

**Promoted**: 2026-08-24 — captured in archive only (SR-07-006 already covers it).
Docs PR: [PR URL TBD].
