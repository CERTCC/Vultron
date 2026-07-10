---
source: ISSUE-599
timestamp: '2026-07-10T18:26:54.635994+00:00'
title: Move misplaced Explanation content to Reference
type: implementation
---

## Issue #599 — [Docs] Move misplaced Explanation content to Reference

Moved content misclassified as Explanation (per Diátaxis) from docs/topics/ to docs/reference/: notation.md, terms.md, versioning.md, measuring_cvd/ (8 pages), user_stories/ (111 stories), and formal_protocol/worked_example.md. Deleted topics/formal_protocol/index.md (thin redirect) and topics/background/overview.md (meta-doc). Updated mkdocs.yml nav, not_in_nav glob, all cross-links in 20+ files, and reference/index.md grid cards. Validated: zero Doc file broken-link warnings in uv run mkdocs build --strict. PR #1344.
