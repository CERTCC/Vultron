---
source: ISSUE-881
timestamp: '2026-06-12T20:04:33.391050+00:00'
title: Split received/case.py and received/actor.py into subpackages
type: implementation
---

## Issue #881 — Split large received use-case modules

Converted two 800+ line use-case modules into focused subpackages.

**`received/case/`** submodules: `_helpers.py`, `create.py`, `update.py`,
`engage_defer.py`, `lifecycle.py`, `validate.py`, `__init__.py`. All submodules
under 500 lines (max: 273).

**`received/actor/`** submodules: `suggest.py`, `case_manager_role.py`,
`ownership.py`, `invite.py`, `announce.py`, `__init__.py`. All submodules
under 500 lines (max: 270).

Test layout migrated to mirror source split: flat `test_case.py`,
`test_actor.py`, `test_case_bootstrap_trust.py`, `test_actor_announce_case.py`
replaced by per-submodule files in `test/core/use_cases/received/case/` and
`test/core/use_cases/received/actor/`.

All existing import paths preserved via re-exporting `__init__.py` (AC-3).
3205 unit tests pass, all four linters clean.

PR: [#941](https://github.com/CERTCC/Vultron/pull/941)
