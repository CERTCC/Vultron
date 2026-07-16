---
source: ISSUE-1304
timestamp: '2026-07-10T17:13:18.577159+00:00'
title: mkdocs nav ADRs 0007-0030
type: implementation
---

## Issue #1304 — docs: mkdocs nav is missing ADRs 0007–0025

Added ADRs 0007–0030 to the mkdocs Decision Records nav in numeric order and
added a `validation.nav.omitted_files: warn` guard (with `not_in_nav`
declarations for intentional maintainer/agent omissions: `agents/*.md`,
`developer/**/*.md`, `reference/inbox_handler.md`,
`reference/code/hexagonal_architecture.md`) to prevent future un-navved pages.
All 31 ADR files (0000–0030) now appear in the nav with no orphans. Docs-only.

PR: <https://github.com/CERTCC/Vultron/pull/1333>
