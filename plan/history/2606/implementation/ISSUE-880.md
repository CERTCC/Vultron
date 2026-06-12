---
source: ISSUE-880
timestamp: '2026-06-12T19:37:24.587673+00:00'
title: Split vultron/wire/as2/extractor.py into focused submodules
type: implementation
---

## Issue #880 — Split vultron/wire/as2/extractor.py into focused submodules

Converted the 826-line `vultron/wire/as2/extractor.py` into a proper
package `vultron/wire/as2/extractor/` with four focused submodules, all
under the 500-line CS-18-002 limit:

- `_pattern.py` (~78 lines): `ActivityPattern` class + `_match_activity_field`
- `_instances.py` (~315 lines): all 44 `*Pattern` module-level constants
- `_builders.py` (~431 lines): field-extraction helpers, domain-object
  builders, and `_build_object_kwargs` dispatch table
- `_extract.py` (~88 lines): `extract_intent` — sole AS2→domain translation
  point
- `__init__.py` (~126 lines): re-exports all 46 public names for backward
  compatibility (AC-4, CS-18-003)

All acceptance criteria met: no module exceeds 500 lines (AC-2), registry
order preserved and all 54 pattern-matching tests pass (AC-3), existing
callers require no changes (AC-4), `_validate_registry_order()` guard
remains import-time active (AC-5). Full suite: 3217 passed, 0 new failures.
Black, flake8, mypy, and pyright all clean.

Also updated `vultron/wire/as2/AGENTS.md` file-locations table and the
adding-a-pattern checklist to reference the new package layout.

PR: [#939](https://github.com/CERTCC/Vultron/pull/939)
