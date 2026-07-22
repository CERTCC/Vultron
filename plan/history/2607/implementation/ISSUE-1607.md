---
source: ISSUE-1607
timestamp: '2026-07-22T17:44:50.502944+00:00'
title: Add upward-reflection signal taxonomy to build/bugfix/learn skills
type: implementation
---

## Issue #1607 — build/bugfix skills signal taxonomy

Added mandatory upward-reflection checklist and typed signal taxonomy to
`build/SKILL.md`, `bugfix/SKILL.md`, `learn/SKILL.md`,
`notes/agentic-workflow.md`, and `specs/build-workflow.yaml`.

Agents now scan for seven signal types (spec-gap, spec-ambiguity,
spec-contradiction, design-question, concern, tooling-issue, process-issue)
before closing any build or bugfix session. An optional `signal:` frontmatter
field in learning files lets the `learn` skill triage by urgency. BW-07 spec
group added with three normative requirements.

PR: <https://github.com/CERTCC/Vultron/pull/1610>
