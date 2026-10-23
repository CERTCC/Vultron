---
source: ISSUE-799
timestamp: '2026-06-05T20:18:31.580776+00:00'
title: Wire as_Base/as_Object onto shared VultronBase/VultronObject roots
type: implementation
---

## Issue #799 — Wire base wiring: as_Base inherits VultronBase, as_Object inherits VultronObject

Implemented ARCH-12-001 and ARCH-12-002: connected the AS2 wire base class
hierarchy to the shared core root established by the #699 migration chain.

### Changes

- `vultron/wire/as2/vocab/base/base.py`: `as_Base` now inherits `VultronBase`
  instead of `BaseModel` directly.
- `vultron/wire/as2/vocab/base/objects/base.py`: `as_Object` now inherits
  `(as_Base, VultronObject)` — diamond via `VultronBase`.
- `vultron/core/models/base.py`: `VultronObject` extended with all shared AS2
  object fields at lenient types to satisfy ARCH-12-002.
- `test/wire/as2/vocab/base/test_wire_base_hierarchy.py`: 16 new boundary tests
  covering all 4 acceptance criteria (AC-1 through AC-4), including MRO shape,
  field-precedence runtime checks, and registry isolation.

### Outcome

All 4 acceptance criteria met. 3021 unit tests pass; all four linters clean.
MRO is `as_Object → as_Base → VultronObject → VultronBase → BaseModel`.
Wire lenient types win over core narrowed types via MRO for all shared fields.

PR: [#814](https://github.com/CERTCC/Vultron/pull/814)
