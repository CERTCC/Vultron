---
title: ARCH-01-001 Fix + Wire Translation Boundary Design [2026-04-15]
type: implementation
timestamp: '2026-04-15T00:00:00+00:00'
source: LEGACY-2026-04-15-arch-01-001-fix-wire-translation-boundary-design
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6197
legacy_heading: ARCH-01-001 Fix + Wire Translation Boundary Design [2026-04-15]
date_source: git-blame
legacy_heading_dates:
- '2026-04-15'
---

## ARCH-01-001 Fix + Wire Translation Boundary Design [2026-04-15]

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6197`
**Canonical date**: 2026-04-15 (git blame)
**Legacy heading**

```text
ARCH-01-001 Fix + Wire Translation Boundary Design [2026-04-15]
```

**Legacy heading dates**: 2026-04-15

### from_core() Refactor (commit f8eede75)

Review of commit `87961536` (BUG-26041501) identified an ARCH-01-001 violation:
`_to_wire_entry()` in `vultron/core/use_cases/triggers/sync.py` was a core
module importing from `vultron.wire` and embedding conversion logic. The fix
moves conversion ownership to the wire type:

- Added `WireCaseLogEntry.from_core(cls, entry: VultronCaseLogEntry)` classmethod
  in `vultron/wire/as2/vocab/objects/case_log_entry.py` using JSON round-trip:
  `cls.model_validate(entry.model_dump(mode="json"))`
- Removed `_to_wire_entry()` from `vultron/core/use_cases/triggers/sync.py`
- Updated both call sites to `WireCaseLogEntry.from_core(entry)`

1404 tests pass; all linters clean.

### Architecture Design Session (grill-me on PROTO-06-001)

Extended design conversation established these decisions (captured in
`specs/architecture.yaml` ARCH-12-001 through ARCH-12-007):

**Key finding**: Domain objects are already pure Pydantic BaseModel — they do
NOT inherit from AS2 types. PROTO-06-001's structural concern is resolved.
PROTO-06-001 removed from `specs/prototype-shortcuts.yaml`.

**Two VultronObject classes**: `vultron.core.models.base.VultronObject` (domain
base, pure Pydantic) and `vultron.wire.as2.vocab.objects.base.VultronObject`
(AS2 wire base) cause confusion. Wire version to be renamed `VultronAS2Object`.

**Decisions made**:

1. Wire base renamed `VultronAS2Object` (ARCH-12-001)
2. `from_core(cls, core_obj)` classmethod on all wire types; base raises
   `NotImplementedError`; default uses JSON round-trip (ARCH-12-002, 007)
3. `to_core(self)` instance method on all wire types; base raises
   `NotImplementedError` (ARCH-12-003)
4. `_field_map: ClassVar[dict[str, str]] = {}` escape hatch for field name
   mismatches (ARCH-12-004)
5. Generic `from_core(domain_activity)` on wire activity base class mapping
   grammatical AS2 fields (ARCH-12-005)
6. `vultron/wire/as2/serializer.py` to be deleted; callers migrated to
   `WireType.from_core()` (ARCH-12-006)
7. Once WIRE-TRANS-05 completes, trigger modules' direct wire imports are
   unnecessary → closes remaining ARCH-01-001 violations

**Meta-policy decision**: Superseded specs MUST be removed, not deprecated.
Deprecated specs are agent noise. Added to `specs/meta-specifications.yaml`.

**Documentation updates**:

- `specs/architecture.yaml`: ARCH-12 section added; review checklist and
  remediation status updated; PROTO-06-001 references removed
- `specs/prototype-shortcuts.yaml`: PROTO-06-001 section replaced with removal
  comment
- `specs/case-management.yaml`: CM-08-002 upgraded from SHOULD to MUST, updated
  to reflect current clean inheritance status
- `specs/meta-specifications.yaml`: "Lifecycle of Superseded Requirements"
  section added
- `notes/domain-model-separation.md`: "Current Status" completely rewritten
  to reflect 2026-04-15 findings; "Recommended Next Steps" updated to
  reference WIRE-TRANS-01 task
- `plan/IMPLEMENTATION_PLAN.md`: PRIORITY-340 / WIRE-TRANS-01–05 task block
  added; header updated (refresh #74)
- `plan/IMPLEMENTATION_NOTES.md`: 2026-04-15 session notes appended

---

### WIRE-TRANS-01 (shim removal) + WIRE-TRANS-02 (from_core/to_core)

**Date**: 2026-04-15

**WIRE-TRANS-01 completion** — removed the `VultronObject = VultronAS2Object`
backward-compatibility alias from `vultron/wire/as2/vocab/objects/base.py`.
No external callers of the wire-layer alias existed; all `VultronObject`
references in the codebase import from `vultron.core.models.base` (the core
domain type), not from the wire module.

**WIRE-TRANS-02** — added to `VultronAS2Object`:

- `_field_map: ClassVar[dict[str, str]] = {}` — class variable for
  domain-to-wire field name translation; subclasses override when wire field
  names differ from core field names.
- `from_core(cls, core_obj: Any) -> "VultronAS2Object"` — default JSON
  round-trip implementation: `core_obj.model_dump(mode="json")`, apply
  `_field_map` renames, then `cls.model_validate(data)`. Subclasses narrow
  the parameter type and can override for complex cases.
- `to_core(self) -> Any` — raises `NotImplementedError`; subclasses with a
  well-defined reverse mapping SHOULD override.

Docstrings document the `_field_map` contract and expected subclass narrowing.

`from_core()` provides a working default (not a bare `NotImplementedError`
stub) because the `CaseLogEntry.from_core()` already demonstrated the pattern
and it is uniform enough to be a safe base-class default.

**Files changed**:

- `vultron/wire/as2/vocab/objects/base.py` — shim removed; `_field_map`,
  `from_core()`, `to_core()` added
- `test/wire/as2/vocab/test_vultron_as2_object.py` — 14 new tests
- `plan/IMPLEMENTATION_PLAN.md` — WIRE-TRANS-01, WIRE-TRANS-02 marked done;
  header updated (refresh #75)
- `plan/IMPLEMENTATION_HISTORY.md` — this entry

**Test counts**: 1418 passed, 12 skipped (up from 1404; +14 new tests).
