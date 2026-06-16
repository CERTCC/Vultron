---
source: ISSUE-990
timestamp: '2026-06-16T15:09:33.901486+00:00'
title: DRY up logging setup across demo scripts
type: implementation
---

## Issue #990 — DRY up logging setup in `vultron/demo`

Extracted the repeated `_setup_logging()` function from all 16 demo scripts
into a single canonical `setup_demo_logging()` in `vultron/demo/utils.py`.

All 16 files under `vultron/demo/exchange/` (13 files) and
`vultron/demo/scenario/` (3 files) defined identical or near-identical
private functions that silenced `httpx2` and configured a root
`StreamHandler(sys.stdout)`. The refactor removes ~200 lines of duplication
and ensures any future logging changes apply in one place.

Also removed inline `import logging as _logging` statements that Black had
left inside 7 function bodies, and added `import sys` to `utils.py`.

PR: [#992](https://github.com/CERTCC/Vultron/pull/992)
