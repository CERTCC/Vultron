---
title: "spec kind: field has a constrained enum — implementation is not valid"
type: learning
timestamp: 2026-08-20
source: ISSUE-2258
signal: spec-ambiguity
---

When adding a spec entry to a `specs/*.yaml` file, the `kind:` field accepts
only: `protocol`, `architecture`, `project`, `process`.

`implementation` is NOT a valid value and causes the spec registry linter to
reject the file at commit time. The error surfaced as a pre-commit hook failure
(`Spec registry linter`) that is easy to misread as a YAML syntax error.

The closest substitute for "this is an implementation constraint" is
`kind: protocol` (if the requirement is a protocol obligation) or
`kind: architecture` (if it is a structural constraint on the system).

**How to apply**: whenever writing a new spec entry, verify `kind:` is one of
the four valid values before committing. Check existing entries in the same
spec file for context.
