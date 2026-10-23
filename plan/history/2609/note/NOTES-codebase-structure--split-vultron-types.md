---
source: NOTES-codebase-structure--split-vultron-types
timestamp: '2026-09-17T17:13:37.674532+00:00'
title: 'Core Object Modules: Split vultron_types.py (TECHDEBT-14)'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) split delivered into vultron/core/models/ package
**Superseded by:** vultron/core/models/

---

## Core Object Modules: Split `vultron_types.py` (TECHDEBT-14)

`vultron/core/models/vultron_types.py` currently bundles multiple core object
types into a single file. These SHOULD be split into individual modules for
better organization, following the same pattern used in `vultron/wire/as2/vocab/objects/`:

- Each core domain object class gets its own module
  (e.g., `vultron/core/models/report.py`, `vultron/core/models/case.py`)
- `vultron/core/models/__init__.py` or a thin re-export module can re-export
  all types for callers that import from `vultron.core.models`

This makes individual classes easier to find, reduces merge conflicts, and
matches the source layout pattern already established in the wire layer.

**Priority**: Low. No blocking impact; purely organizational.
**Related**: `notes/domain-model-separation.md` "DRY Core Domain Models"
proposes consolidating `vultron_types.py` and `events.py` under a shared
`VultronObject` base class as part of this cleanup.

---
