---
title: "Single-quoted YAML strings require '' to escape internal apostrophes"
type: learning
timestamp: "2026-08-20T00:00:00Z"
source: 20260820-SPEC-VAGUE-TERMS
signal: spec-gap
---

When editing YAML spec statements that use single-quoted strings (e.g. CS-21-001 statement field starting with `'Pydantic model fields...`), any apostrophe introduced in the replacement text must be doubled (`''`) to avoid YAML parse errors. The linter fails with an opaque "did not find expected key" parse error rather than pointing directly at the apostrophe. Symptom: `yaml.parser.ParserError` mentioning a column position coinciding with the apostrophe character.

**How to apply:** Before saving a spec edit that introduces `'s` or other apostrophes inside a single-quoted YAML value, either escape as `''s` or convert the field to a `>-` block scalar.

**Promoted**: 2026-08-24 — captured in AGENTS.md.
Docs PR: [PR URL TBD].
