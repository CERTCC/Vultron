---
source: ISSUE-1329
timestamp: '2026-07-10T20:52:42.316781+00:00'
title: suppress context and pytest griffe false-positive warnings in mkdocs build
type: implementation
---

## Issue #1329 — suppress context and pytest griffe false-positive warnings

Added `context` and `pytest` to the false-positive suppression pattern in `.github/scripts/mkdocs-build-strict.sh`. These keywords were being misinterpreted as bibliography citation keys by `mkdocs_bibtex` when griffe encountered `@context` and `@pytest` in docstrings. The fix reduces real warning count from 5 to 1 (the remaining one being a pre-existing pages-not-in-nav issue).

PR: <https://github.com/CERTCC/Vultron/pull/1355>
