# DataLayer Boundary Refactor (TECHDEBT-32)

## Purpose

This note documents the findings of the TECHDEBT-32 audit of the
`core`/`DataLayer` boundary. It captures layer violations, proposes the
minimal refactoring needed to fix them, and records decisions about
`Record`/`StorableRecord` and the vocabulary registry.

---

## Layer Rules (Recap)

| Layer | Module path | Allowed imports |
|---|---|---|
| Core | `vultron/core/` | Core only + shared neutral modules |
| Wire | `vultron/wire/` | Core + wire internals |
| Adapters | `vultron/adapters/` | All layers |

---

## 1. `object_to_record()` / `record_to_object()` Call Sites

### Calls from adapter layer (acceptable)

All of the following are in `vultron/adapters/driven/datalayer_tinydb.py`
and `vultron/adapters/driven/db_record.py` — adapter code calling adapter
utilities. No architectural issue.

### Calls from core layer (**violation** — CS-05-001)

Two core modules import `object_to_record` from the adapter:

| File | Line | Call |
|---|---|---|
| `vultron/core/use_cases/triggers/embargo.py` | 26, 137, 217, 293 | `object_to_record(case)` passed to `dl.update()` |
| `vultron/core/use_cases/triggers/_helpers.py` | 26, 118, 157 | `object_to_record(...)` passed to `dl.update()` |

Both files use the pattern:

```python
from vultron.adapters.driven.db_record import object_to_record
...
dl.update(obj.as_id, object_to_record(obj))
```

**Fix**: The `DataLayer` Protocol already exposes `save(obj: BaseModel) -> None`,
which performs the same operation internally (inside the adapter where
`object_to_record` belongs). Replace all occurrences with:

```python
dl.save(obj)
```

This eliminates all adapter imports from core.

---

## 2. `find_in_vocabulary()` Call Sites

| File | Layer | Status |
|---|---|---|
| `vultron/wire/as2/vocab/base/registry.py` | Wire | Definition — OK |
| `vultron/adapters/driven/db_record.py` | Adapter | Adapter imports wire — OK |
| `vultron/wire/as2/rehydration.py` | Wire | Wire-to-wire — OK |
| `vultron/adapters/driving/fastapi/routers/actors.py` | Adapter | Adapter imports wire — OK |
| `vultron/adapters/driving/fastapi/helpers.py` | Adapter | Adapter imports wire — OK |

**No core violations** for `find_in_vocabulary`.

---

## 3. Core Branching on DataLayer Return Types

No evidence of core code doing `isinstance(result, Record)` or
`isinstance(result, Document)`. The one `isinstance` check involving
`StorableRecord` is in `TinyDbDataLayer.create()` — adapter code, acceptable.

---

## 4. `Record` / `StorableRecord` Architecture

| Class | Location | Status |
|---|---|---|
| `StorableRecord` | `vultron/core/ports/datalayer.py` | Core port — correct |
| `Record` | `vultron/adapters/driven/db_record.py` | Adapter subclass — correct |

`StorableRecord` defines the minimal 3-field contract (`id_`, `type_`,
`data_`). `Record` extends it with `from_obj()` / `to_obj()` adapter
helpers. The hierarchy is sound; no changes needed to these classes.

**Canonical save pattern for core code**:

| Pattern | Where used | Status |
|---|---|---|
| `dl.update(id, object_to_record(obj))` | `triggers/embargo.py`, `triggers/_helpers.py` | **Violation** — imports adapter |
| `save_to_datalayer(dl, obj)` | BT `case/nodes.py`, `report/nodes.py` | Works, but redundant helper |
| `dl.save(obj)` | `use_cases/embargo.py`, `use_cases/case.py`, etc. | **Correct** — use this |

**Recommendation**: Standardise on `dl.save(obj)` across all core code.
Remove `save_to_datalayer()` from `vultron/core/behaviors/helpers.py` once
all callers are migrated.

---

## 5. Vocabulary Registry Entanglement

`find_in_vocabulary` (wire) is used by the driven adapter (`db_record.py`)
to reconstitute domain objects from stored records. This is an intentional
design: the adapter needs the wire vocabulary to deserialise stored records.

`vultron/wire/as2/rehydration.py` uses `find_in_vocabulary` for wire-to-wire
type promotion — acceptable.

The one concern is `rehydration.py` also importing `get_datalayer` from the
TinyDB adapter as a fallback:

```python
from vultron.adapters.driven.datalayer_tinydb import get_datalayer
```

This is a **wire-imports-adapter violation** (CS-05-001). It exists only
for backward compatibility on code paths where no `DataLayer` is in scope.

**Fix proposal (TECHDEBT-32c — separate task)**: Remove the fallback; make
`dl` a required parameter in `rehydrate()`, or inject a factory via a
neutral port. All current callers in the production path already pass `dl`
explicitly; the fallback serves only old test paths.

---

## 6. Implementation Tasks

### TECHDEBT-32b — Fix core adapter imports (✅ completed in TECHDEBT-32b, 2026-03-24)

All items completed:

- Removed `from vultron.adapters.driven.db_record import object_to_record`
  from `triggers/embargo.py` and `triggers/_helpers.py`.
- Replaced all `dl.update(obj.as_id, object_to_record(obj))` calls with
  `dl.save(obj)` across core use cases and triggers.
- Removed `save_to_datalayer(self.datalayer, obj)` calls from BT nodes;
  now directly call `self.datalayer.save(obj)`.
- Removed `save_to_datalayer()` helper from `vultron/core/behaviors/helpers.py`.

Core layer now has zero adapter-layer imports for persistence. All DataLayer
access uses the port-defined interface exclusively.

### TECHDEBT-32c — Fix wire/rehydration.py adapter import (⏳ pending)

Remove `from vultron.adapters.driven.datalayer_tinydb import get_datalayer`
from `vultron/wire/as2/rehydration.py`. Make `dl` a required parameter or
provide a core-level factory port.

---

## References

- `specs/code-style.md` CS-05-001 (no core imports from adapter)
- `docs/adr/0009-hexagonal-architecture.md`
- `docs/adr/0012-per-actor-datalayer-isolation.md`
- `vultron/core/ports/datalayer.py` — `DataLayer` Protocol and
  `StorableRecord`
- `plan/IMPLEMENTATION_PLAN.md` — TECHDEBT-32, TECHDEBT-32b, TECHDEBT-32c
