---
title: 'D5-6-STORE: Dehydrate nested AS2 objects before TinyDB storage'
type: implementation
date: '2026-04-06'
source: D5-6-STORE
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 4598
legacy_heading: 'D5-6-STORE: Dehydrate nested AS2 objects before TinyDB storage'
date_source: git-blame
---

## D5-6-STORE: Dehydrate nested AS2 objects before TinyDB storage

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:4598`
**Canonical date**: 2026-04-06 (git blame)
**Legacy heading**

```text
D5-6-STORE: Dehydrate nested AS2 objects before TinyDB storage
```

**Task**: PRIORITY-310 / D5-6-STORE
**Status**: Complete

### Problem

The TinyDB adapter stored transitive activities (e.g., `Offer(VulnerabilityReport)`)
with the full inline nested object serialised into the activity record. This
caused redundant storage and could cause `rehydrate()` to pick up stale inline
data instead of the live DataLayer record.

### Solution

1. **`vultron/adapters/driven/db_record.py`**: Added `_AS_OBJECT_REF_FIELDS`
   allowlist (`object_`, `target`, `origin`, `result`, `instrument`) and
   `_dehydrate_data()` function. `Record.from_obj` now calls
   `_dehydrate_data(obj.model_dump(mode="json"))`, which replaces any inline
   nested object in an allowlisted field with its ID string, provided the
   nested object has an `id_` key and its `type_` does not start with `as_`
   (domain objects only; core AS2 objects are left inline).

2. **`vultron/adapters/driving/fastapi/routers/actors.py`**: `post_actor_inbox`
   now pre-stores any inline domain-typed nested object in the DataLayer
   BEFORE storing the parent activity. This ensures `rehydrate()` can resolve
   the ID reference produced by dehydration.

3. **`vultron/core/behaviors/case/nodes.py`**: `CheckCaseAlreadyExists`
   updated to check whether the case has been FULLY INITIALISED (has at least
   one participant) rather than merely existing in the DataLayer. A pre-stored
   but uninitialised case (empty `case_participants`) now returns FAILURE,
   allowing the BT `CreateCaseFlow` to run and add participants.

4. **`vultron/demo/utils.py`**: Updated `verify_object_stored` log message.

### Tests added

- `test/adapters/driven/test_db_record.py`: 8 unit tests for `_dehydrate_data`
  and 2 integration tests for `object_to_record`.
- `test/adapters/driven/test_tinydb_backend.py`: 5 TinyDB round-trip
  integration tests.

### Lessons learned

- **`CheckCaseAlreadyExists` idempotency scope**: Idempotency checks for BT
  case creation must distinguish between a pre-stored stub (empty participants)
  and a fully-initialised case. A simple `dl.read(case_id) is not None` check
  is insufficient when the inbox endpoint pre-stores nested objects.
- **Allowlist approach for dehydration is essential**: Dehydrating ALL nested
  dicts (any dict with an `id_` key) causes broad failures — actor `inbox`/
  `outbox` fields, participant status lists, etc. Only the five canonical AS2
  transitive-activity object fields are safe candidates.
- **Lists must never be dehydrated**: List items in domain objects are either
  string lists or embedded sub-object lists; dehydrating list items breaks
  `model_validate` reconstruction.

### Validation

`uv run pytest --tb=short 2>&1 | tail -5` → 1236 passed, 5581 subtests;
black/flake8/mypy/pyright all clean.
