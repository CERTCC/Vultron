---
title: "GHA matrix boolean fields are coerced to strings in if: expressions"
type: learning
timestamp: 2026-08-06T14:55:00Z
source: ISSUE-1996-gha-boolean
signal: concern
---

In `.github/workflows/demo-integration.yml` (PR #2030), the `full_suite_only`
matrix field is declared as a YAML boolean (`false`/`true`) and referenced in
job `if:` conditions as:

```yaml
github.event_name != 'pull_request' || matrix.full_suite_only == false
```

GitHub Actions evaluates matrix context values as strings in `if:` expressions.
The boolean `false` may be coerced to the string `"false"`, causing
`matrix.full_suite_only == false` to always be `false` (a string never equals
a boolean). If so, all 8 scenarios would run on every PR, defeating the
minimum-set split.

The safe form is:

```yaml
github.event_name != 'pull_request' || matrix.full_suite_only != true
```

or declare the field as a string in the matrix (`full_suite_only: "false"`) and
compare as a string. This should be validated by observing the first PR that
fires after the workflow merges — if all 8 scenarios run on that PR instead of
3, the coercion bug is confirmed and the condition needs updating.

**Promoted**: 2026-08-17 — captured in GitHub #2327 (Concern: GHA matrix boolean full_suite_only coercion).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>0>0>0>0>0>0>0>0>0>.
