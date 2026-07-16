---
source: ISSUE-1313
timestamp: '2026-07-10T14:52:38.064686+00:00'
title: 'Fix docs/index.md: promote "what is Vultron" from README, reposition WIP warning'
type: implementation
---

## Issue #1313 — [Docs] Fix docs/index.md: promote "what is Vultron" from README, reposition WIP warning

Rewrote `docs/index.md` so the first thing a reader sees is a clear orientation
paragraph and the promoted "So what is Vultron?" and "What is Vultron not?"
sections from the README. The WIP callout was downgraded from a
`!!! warning inline end` (first-impression blocker) to a `!!! note` block
placed after the intro. Two stray mkdocs Material template placeholder lines
were also removed. Docs-only change; markdownlint clean; docs build warning
count unchanged from main.

PR: <https://github.com/CERTCC/Vultron/pull/1323>
