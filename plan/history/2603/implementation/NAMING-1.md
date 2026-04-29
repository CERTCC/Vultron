---
title: "NAMING-1 \u2014 Standardize `as_`-prefixed field names (2026-03-30)"
type: implementation
date: '2026-03-30'
source: NAMING-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3710
legacy_heading: "NAMING-1 \u2014 Standardize `as_`-prefixed field names (2026-03-30)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-30'
---

## NAMING-1 — Standardize `as_`-prefixed field names (2026-03-30)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3710`
**Canonical date**: 2026-03-30 (git blame)
**Legacy heading**

```text
NAMING-1 — Standardize `as_`-prefixed field names (2026-03-30)
```

**Legacy heading dates**: 2026-03-30

**Task**: Rename all `as_`-prefixed Pydantic field names to the trailing-underscore
convention throughout the codebase (both wire layer and core layer).

**Changes**:

- Renamed 4 field names across 130 Python files (~2756 occurrences):
  - `as_id` → `id_`
  - `as_type` → `type_`
  - `as_object` → `object_`
  - `as_context` → `context_`
- Renames cover: field definitions, attribute accesses (`.as_id` etc.),
  keyword arguments (`as_id=...`), string references in `getattr`/`hasattr`
  calls, and docstrings/comments.
- Class names (`as_Activity`, `as_Object`, etc.) are **not** renamed.
- Pydantic field aliases (`validation_alias`, `serialization_alias`) are
  unchanged — JSON serialization and deserialization behavior is preserved.
- Updated `specs/code-style.yaml` CS-07-001 through CS-07-003 to reflect
  migration complete (MUST-level policy now).
- Updated `AGENTS.md` naming conventions, pattern-matching example, and
  all pitfall code snippets to use `id_`, `type_`, `object_`.

**Tests**: 1080 passed, 5581 subtests passed.
