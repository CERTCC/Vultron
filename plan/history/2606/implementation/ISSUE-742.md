---
source: ISSUE-742
timestamp: '2026-06-09T16:00:10.825593+00:00'
title: Split case trigger use cases into subpackage
type: implementation
---

## Issue #742 — Split vultron/core/use_cases/triggers/case.py into a triggers/case/ subpackage by use case

Implemented the case trigger module split by replacing `vultron/core/use_cases/triggers/case.py` with a `triggers/case/` subpackage containing one use-case module per trigger (engage, defer, create, add_object, add_report, add_participant_status). Added `triggers/case/__init__.py` re-exports so existing imports from `vultron.core.use_cases.triggers.case` continue to work unchanged.

Mirrored the layout in tests by moving case trigger tests under `test/core/use_cases/triggers/case/` and adding per-verb engage/defer test files. Updated `notes/triggers-test-coverage.md` to reflect the new structure.

PR: [#842](https://github.com/CERTCC/Vultron/pull/842)
