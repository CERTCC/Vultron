---
source: ISSUE-969
timestamp: '2026-06-16T16:16:10.944627+00:00'
title: Split triggers/embargo.py into focused submodules
type: implementation
---

## Issue #969 — Split triggers embargo use-case module into focused submodules

Replaced the 514-line flat `vultron/core/use_cases/triggers/embargo.py`
with a one-class-per-file package following the same pattern used for
`triggers/case/`. Each use-case class lives in its own submodule:
`propose.py`, `accept.py`, `terminate.py`, `reject.py`, `revise.py`.
The `__init__.py` re-exports all public names (including `_is_case_owner`)
for full backward compatibility.

The flat `test/core/use_cases/triggers/test_embargo.py` was replaced by a
mirrored subpackage `test/core/use_cases/triggers/embargo/` with per-submodule
test files and shared fixtures in `conftest.py`. All 12 existing tests are
preserved. No submodule exceeds 140 lines.

All 3392 unit tests pass. Black, flake8, mypy, pyright all clean.

PR: [#999](https://github.com/CERTCC/Vultron/pull/999)
