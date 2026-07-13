---
title: Domain Object Validation — Strict vs. Loose Boundaries
status: active
description: >
  Where in the pipeline domain objects transition from "loose" (possibly
  None/unresolved fields) to "strict" (all required fields guaranteed),
  and how helpers must fail fast when strict guarantees are violated.
related_specs:
  - specs/architecture.yaml (ARCH-10-001, ARCH-15-001 through ARCH-15-004)
related_notes:
  - notes/architecture-hexagonal.md
  - notes/bt-integration.md
---

# Domain Object Validation — Strict vs. Loose Boundaries

## The Strict/Loose Distinction

Domain objects in Vultron move through two zones:

- **Loose zone**: Objects freshly deserialized from the wire or DataLayer.
  Optional fields may be `None`, IDs may be unresolved strings or inline
  objects, and required-field invariants have not yet been checked in
  context.
- **Strict zone**: Objects that have been validated and are ready for
  domain logic. All fields required for the current operation are
  non-None and of the expected type.

The boundary is not a single conversion step — it is a series of
**fail-fast checkpoints** at the entry to each domain operation.
Pydantic model construction (ARCH-10-001) enforces structural
invariants. Runtime helpers enforce relational invariants (e.g., "this
case has a Case Manager participant with a resolvable actor ID").

---

## Conversion Points

Objects transition from loose to strict at:

1. **Use-case `execute()` entry** — required inputs (case ID, actor ID,
   activity) must be non-None before any DataLayer mutation.
2. **BT node `update()` entry** — blackboard keys expected to be present
   must be verified; missing keys return `Status.FAILURE` (not
   `Status.SUCCESS`) so the BT sequence propagates failure correctly.
3. **Helper function boundaries** — helpers that require a non-None result
   from a field access must check and raise immediately. Helpers whose
   callers may legitimately pass `None` must remain lenient.

---

## Pattern: Fail Fast at the Conversion Point

When a helper or node requires a non-None value, check it explicitly
and raise or return `FAILURE` immediately:

```python
# In a helper that requires a valid ID
case_id = _as_id(case)
if case_id is None:
    raise VultronValidationError(
        f"Cannot process case with no resolvable id (got {case!r})"
    )

# In a BT node update() that requires a blackboard key
case_obj = self._read_case_obj()
if case_obj is None:
    self.feedback_message = f"{self.name}: 'create_case_obj' not on blackboard"
    return Status.FAILURE
```

**Never return `Status.SUCCESS` when a required input is absent.** A
missing required value means the subtree cannot produce its intended
effect; returning `SUCCESS` misleads the BT sequence and silently drops
protocol behavior (ledger entries not written, broadcasts not sent,
routing never attempted).

---

## Pattern: Lenient Helpers Remain Lenient

`_as_id()` is intentionally lenient — it returns `None` when the input
is `None` because many callers legitimately probe optional fields (e.g.,
`case.active_embargo` is `None` when no embargo is active). Do **not**
make `_as_id()` raise.

The strict guarantee lives in the **caller**, not in the helper:

```python
# Lenient use — None is a valid outcome
active_embargo_id = _as_id(case.active_embargo)  # may be None

# Strict use — None means something went wrong
manager_id = _as_id(participant.attributed_to)
if manager_id is None:
    raise VultronValidationError("CASE_MANAGER participant has no attributed_to")
```

---

## Canonical Helper Locations

Helpers that extract IDs or look up participants belong in
`vultron/core/use_cases/_helpers.py` — the neutral module importable
from both `behaviors/` and `use_cases/` layers without circular imports.

Duplicate copies in other modules (e.g., `services/embargo_lifecycle.py`,
`behaviors/status/nodes/broadcast.py`) MUST import from
`use_cases/_helpers` and not maintain their own copies.

---

## Routing Failures vs. Validation Failures

Two distinct error types are used for fail-fast signals:

- **`VultronValidationError`** (`vultron/errors.py`) — a domain object
  or request fails a required invariant (missing field, wrong type).
- **`UnroutableActivityError`** (`vultron/errors.py`) — an inbound
  activity cannot be routed to a case because no case ID could be
  extracted from the event. This is a routing failure, not a data
  validation failure. The dispatcher caller MUST handle it explicitly
  rather than silently dropping the activity.

```python
# Dispatcher site: raise, don't return None
if case_id is None:
    raise UnroutableActivityError(
        activity_id=event.id_,
        reason="No case_id attribute found on event",
    )
```

---

## Summary of Named Silent-Failure Sites (CONCERN-1360)

| Site | Old behavior | New behavior |
|---|---|---|
| `_as_id()` in `embargo_lifecycle.py` | Duplicate copy | Removed; callers import from `use_cases._helpers` |
| `_find_case_manager_*` (3 copies) | 3 independent copies returning `None` | 1 canonical function in `use_cases/_helpers`; others removed |
| `_extract_case_id()` in dispatcher | Returns `None`; activity silently not indexed | Raises `UnroutableActivityError` |
| `AppendCaseLedgerEntryNode.update()` | Returns `Status.SUCCESS` on missing `case_id` | Returns `Status.FAILURE` |
| `_read_case_obj()` in communication.py | Swallows `KeyError`; no diagnostic | Sets `feedback_message`; caller returns `Status.FAILURE` |

See `specs/architecture.yaml` ARCH-15-001 through ARCH-15-004 for
normative requirements derived from this concern.
