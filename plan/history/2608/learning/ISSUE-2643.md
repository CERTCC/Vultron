---
title: "issueType: null in GraphQL requires content-based fallback"
type: learning
timestamp: "2026-08-26T00:00:00Z"
source: ISSUE-2643
signal: process-issue
---

Issues #2643 and #2644 both returned `issueType: null` from the
`query-issue-type.sh` GraphQL query. The `work-issue` routing skill says
to stop on unrecognized types, but the issues clearly belonged to the
Task/Feature path based on their body structure (AC-N acceptance criteria,
implementation-focused summary).

When `issueType` is null, inspect the issue body before stopping: presence
of `- [ ] AC-N:` items and an implementation-focused Summary section reliably
identifies Task-type issues. Proceed with the Task routing path rather than
halting on the null.

This is distinct from a genuinely unrecognized type (e.g., a string value
not in the supported set). A null type signals "no type set in GitHub" — it
does not signal an unsupported type.

**Promoted**: 2026-08-27 — archived (already in specs/notes/AGENTS.md or tracked as GitHub issue). Docs PR: <pending>.
