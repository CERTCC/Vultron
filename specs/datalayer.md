# DataLayer Port Requirements

**Spec ID prefix**: DL  
**Status**: Draft  
**See also**: `notes/datalayer-design.md`, `specs/architecture.yaml` ARCH-03

---

## Overview

The `DataLayer` protocol (`vultron/core/ports/datalayer.py`) is the driven port
through which core domain logic accesses persistence. This spec defines the
behavioural contract that all DataLayer adapter implementations MUST satisfy.

---

## DL-01 — Auto-Rehydration on Read

### DL-01-001

`dl.read(id)` MUST return a **fully rehydrated, typed domain object**.

- The returned object MUST be a Pydantic model instance, not a raw storage
  record, untyped dict, or `StorableRecord`.
- All fields that were dehydrated to ID strings during storage (e.g., `object_`,
  `target`, `origin`) MUST be expanded back to their full typed objects before
  the value is returned to the caller.
- If the object identified by `id` does not exist, `dl.read(id)` MUST raise
  `VultronNotFoundError`.

**Rationale**: Core use cases must not contain coercion logic that translates
storage artefacts (dehydrated string references) back into typed objects. That
translation belongs in the adapter. See `notes/datalayer-design.md`
"Auto-Rehydration: `dl.read()` MUST Return Fully Typed Objects".

### DL-01-002

`dl.list(type_key)` MUST return an iterable of **fully rehydrated, typed domain
objects** of the requested type.

- Each item in the result MUST satisfy the same rehydration guarantee as
  DL-01-001.
- An empty result MUST be returned (not an error) when no objects of the given
  type exist.

### DL-01-003

Rehydration MUST cover **all fields that the adapter dehydrates on write**,
including but not limited to:

- `object_` — nested activity object
- `target` — target object reference
- `origin` — origin object reference

If a dehydrated field references an ID that is not present in the DataLayer,
the adapter MUST log a WARNING and return the ID string as-is rather than
raising an error. This preserves partial readability of records whose nested
objects have been deleted.

### DL-01-004

Core use cases MUST NOT contain manual coercion of `dl.read()` results.
Specifically, the following patterns are prohibited in `vultron/core/`:

- Calling `model_validate` on a `dl.read()` result to recover a nested
  object's type after stripping a dehydrated string.
- Calling `record_to_object()` on a `dl.read()` result.
- Type checks of the form `if isinstance(result, Document): ...`.

These patterns indicate that the adapter is not satisfying its rehydration
contract and MUST be resolved by fixing the adapter, not by adding more
coercion in core.

---

## DL-02 — Type-Safe Write Operations

### DL-02-001

`dl.save(obj)` MUST accept a typed Pydantic domain object directly and handle
all serialisation and dehydration internally.

- Core MUST NOT call `object_to_record()` before passing an object to
  `dl.save()`.
- The adapter is responsible for translating the domain object to the
  appropriate storage format.

### DL-02-002

`dl.save(obj)` MUST be idempotent with respect to the object's `id_`: saving
the same object twice with the same ID MUST result in the same stored state
as saving it once (upsert semantics).

---

## DL-03 — Port Isolation

### DL-03-001

The `DataLayer` port (`vultron/core/ports/datalayer.py`) MUST be defined
entirely in terms of core domain types. It MUST NOT import from:

- `vultron/wire/` (wire layer)
- `vultron/adapters/` (adapter layer)
- Any storage-specific library (SQLModel, TinyDB, etc.)

### DL-03-002

The DataLayer adapter MUST NOT expose vocabulary registry lookups or AS2 type
name resolution to core. The vocabulary registry
(`vultron/wire/as2/vocab/registry.py`) is a wire-layer concern; the adapter
must maintain its own internal mapping between domain object types and storage
keys.

---

## Verification

### DL-01-001, DL-01-002, DL-01-003 Verification

- Unit test: `dl.read(id)` for an activity with a dehydrated `object_` returns
  an object whose `object_` field is a typed Pydantic model, not a string.
- Unit test: `dl.list(type_key)` returns a list where every item's nested
  fields are fully typed.
- Unit test: `dl.read(id)` for a record whose nested object ID is missing from
  the DataLayer returns a result with the ID string preserved in that field
  (no exception).

### DL-01-004 Verification

- Static analysis (grep/rg): No `model_validate` calls on `dl.read()` results
  in `vultron/core/`.
- Static analysis: No `record_to_object()` calls in `vultron/core/`.
- Static analysis: No `isinstance(result, Document)` checks in `vultron/core/`.

### DL-02-001 Verification

- Unit test: `dl.save(typed_object)` does not raise when passed a Pydantic
  model instance.
- Static analysis: No `object_to_record()` calls before `dl.save()` in
  `vultron/core/`.

### DL-03-001 Verification

- Import check: `vultron/core/ports/datalayer.py` has no imports from
  `vultron/wire/`, `vultron/adapters/`, SQLModel, or TinyDB.

### DL-03-002 Verification

- Code review: `vultron/adapters/driven/datalayer_sqlite.py` does not call
  `find_in_vocabulary()` or import from `vultron/wire/as2/vocab/registry.py`
  for storage key resolution.

---

## Implementation Notes

- **Current state**: `_dehydrate_data` in `vultron/adapters/driven/db_record.py`
  dehydrates `object_` (and potentially other fields) to ID strings on write.
  The inverse rehydration on read is not yet implemented automatically;
  individual use cases perform manual coercion.
- **Migration**: Implement auto-rehydration in the adapter; then audit and
  remove all manual coercion patterns in `vultron/core/use_cases/`.
- **Implementation task**: `DL-REHYDRATE` in `plan/IMPLEMENTATION_PLAN.md`.
