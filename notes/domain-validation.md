---
title: Domain Object Validation — Strict vs. Loose Boundaries
status: active
description: >
  Where in the pipeline domain objects transition from "loose" (possibly
  None/unresolved fields) to "strict" (all required fields guaranteed),
  and how helpers must fail fast when strict guarantees are violated.
related_specs:
  - specs/architecture.yaml (ARCH-10-001, ARCH-15-001 through ARCH-15-004,
    ARCH-21-001 through ARCH-21-005)
  - specs/case-management.yaml (CM-27-001 through CM-27-003)
  - specs/participant-role-management.yaml (PRM-03-003)
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

Layer-neutral utilities with no dependencies above `models/` belong in
`vultron/core/models/_helpers.py` — the bottom of the hexagonal stack,
safely importable by **all** layers (`behaviors/`, `use_cases/`, `services/`,
`adapters/`). Examples: `_as_id()`, `_report_phase_status_id()`.

Higher-level helpers that depend on ports, state machines, or use-case
logic belong in `vultron/core/use_cases/_helpers.py`. Examples:
`_idempotent_create`, `update_participant_rm_state`, `add_activity_to_outbox`.

Duplicate copies in other modules MUST NOT be maintained — import from the
canonical location instead.
`behaviors/status/nodes/broadcast.py` was deleted in #1378 after its only
content (`_find_case_manager_id`) was consolidated into `_resolve_case_manager_id`.

### Exception: shape guards live in `models/_wire_spelling.py`

`vultron/core/models/_helpers.py` cannot import from `vultron.core.states` —
that is a circular import through `states/__init__.py`. Shape guards tend to
grow state references (a guard that knows about `rm` eventually wants `RM`), so
they live in `vultron/core/models/_wire_spelling.py` instead of being colocated
with `_as_id()` and friends. This is a deliberate deviation from the rule above,
not an oversight; it exists so the cycle cannot be reintroduced by the next
guard that needs a state enum.

The trap: `states/rm.py`'s own imports look clean (logging, enum, transitions,
`states.common`), so inspecting the target module tells you nothing. The cycle
runs through the package `__init__.py` — `models/base.py` imports `_helpers`,
which triggers `states/__init__.py`, which pulls `states/cs.py` → `states/common.py`
→ back into `models/base.py` while it is still partially initialised. The error
looks like a missing symbol in `models.base`, not a cycle.

### Type-specific canonical readers live with their type

A helper that reads one dimension of one model type (e.g. `participant_status_rm_state`)
belongs in the same module as that type (`vultron/core/models/participant_status.py`),
not in `_helpers.py`. Two reasons:

1. It cannot go to `_helpers.py` if it needs a state enum (see above).
2. Colocating the canonical reader with the type keeps the authorship contract
   clear: the module that defines a type owns its read semantics.

The distinction from shape guards in `_wire_spelling.py`: shape guards are
cross-cutting (they need to know about the core/wire boundary across multiple
types); canonical readers are type-specific. Cross-cutting → `_wire_spelling.py`;
type-specific → the type's own module.

BT-node-level wrappers that combine multiple readers (e.g. `read_rm_states()`)
live in `vultron/core/behaviors/helpers.py`, which has no circular-import
restriction (it is below use-cases, above models, and can import from either).

---

## Shape Guards: One Canonical Reader per Dimension (#2232)

`ParticipantStatus` exists in two incompatible shapes: core nests
`rm: RmDimension` / `vfd: VfdDimension` (SDO-03-002, ADR-0036), while the wire
projection carries flat `rm_state` / `vfd_state`. Reading a dimension off the
wrong shape yields `None` — which every reader then quietly substituted an
initial state for, resetting the participant's ladder (#2264).

**Read a dimension only through its canonical reader.** Both live in
`vultron/core/models/participant_status.py`:

| Reader | Returns | Raises |
|---|---|---|
| `participant_status_rm_state(status)` | the `RM` state | `VultronValidationError` on a non-core shape |
| `participant_status_vfd_state(status)` | the `CS_vfd` state | `VultronValidationError` on a non-core shape |

```python
# Wrong — a wire-shaped status degrades to the initial state, silently.
rm_dim = getattr(status, "rm", None)
state = getattr(rm_dim, "state", None)
if not isinstance(state, RM):
    state = RM.START

# Right — absence and shape mismatch are different outcomes.
state = participant_status_rm_state(status)
```

This is the strict/loose rule applied to *shape*: an **empty** status list is a
legitimate absence and callers must handle it (check `participant_statuses`
before calling); a status that exists but exposes no usable dimension is a shape
mismatch and must raise (ARCH-15-001, ARCH-15-002).

**Where a raise is wrong.** At a wire→core ingress boundary, a wire-shaped
status is *legitimate inbound data*, not a corrupt row. Those sites must
**project** before reading — `as_ParticipantStatus.to_core()`, or
`_project_to_core_participant()` in
`vultron/core/use_cases/received/case/_helpers.py` — rather than let the reader
raise. Making the reader strict without projecting at ingress first aborted the
entire received-case behavior tree on every inbound `Announce`, which is how the
first fix for #2232 regressed.

The mirror-image guard is `reject_wire_spelled_keys()` in
`vultron/core/models/_wire_spelling.py`: a core type validated against a
wire-spelled (camelCase) payload drops every snake-only key in silence, because
Pydantic v2 ignores unknown keys. It is computed per exact class, so a
`CaseParticipant` role subclass that adds a field is covered without any
registration step.

---

## Post-Construction Mutation: Three Doors, One Lock (#2261)

Pydantic v2 validates a model at **construction**. Nothing else. The same value
the constructor rejects is silently accepted through two other doors:

```python
case = VulnerabilityCase(case_participants=[wire_obj])  # ValidationError
case.case_participants = [wire_obj]                     # accepted
case.case_participants.append(wire_obj)                 # accepted
```

Combine that with the shape duality above and you get the #2232 / #2264 failure:
a wire-shaped object in a core-typed field does not raise when read — it reads as
*absent*, so the reader substitutes an initial state and the participant's ladder
silently resets.

**The two remedies are different mechanisms, because they close different
doors.** `validate_assignment=True` closes the assignment door. It does
*nothing* for `append` — an in-place list mutation is not an attribute
assignment, so Pydantic never observes it. That door is closed by prohibition
plus canonical mutators plus an architecture ratchet (CM-27-001, PRM-03-003),
the same way PRM-03-001 closed it for `case_roles`.

### Where `validate_assignment` goes — and where it must not

| Layer | `validate_assignment` | Why |
|---|---|---|
| Core models (`vultron/core/models/`) | **on** (ARCH-21-001) | Core fields carry a shape guarantee that readers depend on |
| `VultronBase` | **never** (ARCH-21-002) | Shared base of both branches; `as_Base` inherits it (ARCH-12-001/002) |
| Wire (`vultron/wire/`) | **never** (ARCH-21-003) | Inbound data is legitimately loose; strictness belongs at the projection |

Setting the flag on `VultronBase` is the one-line fix that looks right and is
not. It contradicts ARCH-12-002 and, when measured, produced the largest blast
radius of any variant (747 failed, 423 errors).

### Pitfall: never assign to `self` in a `mode="after"` validator

This is the trap that makes the whole change non-trivial, and it is invisible
from reading the model:

```python
# Wrong — with validate_assignment on, this recurses until the stack is gone.
@model_validator(mode="after")
def _set_role(self) -> FinderParticipant:
    self.case_roles = []          # assignment re-runs this validator...
    self.add_role(CVDRole.FINDER)
    return self

# Right — derive before validation, so the derived value is itself validated.
@model_validator(mode="before")
@classmethod
def _set_role(cls, data: Any) -> Any:
    ...
```

`validate_assignment` re-runs **every** `mode="after"` validator on each
assignment, so a validator that writes to `self` re-enters itself. A guarded one
(`if self.name is None: self.name = ...`) terminates at depth 2; an unguarded one
never terminates. Enabling the flag before this rule holds aborts 400+ tests with
`RecursionError` **and nothing else** — the recursion masks every real type
failure, so the actual blast radius cannot be measured until the validators are
fixed. ARCH-21-004 makes this a MUST NOT for `vultron/core/`.

Writing the field through `self.__dict__["field"]` was considered and rejected:
it stops the recursion but leaves the derived value unvalidated, trading one
silent hole for a smaller one.

Wire-layer validators are **exempt by design** — the wire branch never enables
the flag, so they cannot re-enter. Twelve of them still assign to `self`. If the
wire branch ever gains `validate_assignment`, this trap returns.

### Cost

Scalar attribute assignment measured **475 ns → 1464 ns** (3.1×, ~1 µs
absolute) — immaterial for BT tick loops. The cost that still needs watching is
collection fields: assigning `case_participants` re-validates all N items, so it
is O(N) per assignment.

See ADR-0064 for the decision and the three-step rollout, and
`test/architecture/test_validate_assignment_ratchet.py` for the enumerated
backlogs that track it.

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
| `_as_id()` in `embargo_lifecycle.py` | Duplicate copy | Removed; moved to `core.models._helpers` (#1428) |
| `_find_case_manager_*` (3 copies) | 3 independent copies returning `None` | 1 canonical function in `use_cases/_helpers`; others removed |
| `_extract_case_id()` in dispatcher | Returns `None`; activity silently not indexed | Raises `UnroutableActivityError` |
| `CommitCaseLedgerEntryNode.update()` | Returns `Status.SUCCESS` on missing `case_id` | Returns `Status.FAILURE` |
| `_read_case_obj()` in communication.py | Swallows `KeyError`; no diagnostic | Sets `feedback_message`; caller returns `Status.FAILURE` |

See `specs/architecture.yaml` ARCH-15-001 through ARCH-15-004 for
normative requirements derived from this concern.

---

## Pitfall: `getattr(obj, name, default)` Does Not Catch `ValueError`

Python's three-argument `getattr` suppresses only `AttributeError`. If a
property getter raises `ValueError` — as `VulnerabilityCase.current_status`
does when `case_statuses` has no materialised entries — the default is
**never returned** and the `ValueError` propagates.

The `getattr(case, "current_status", None)` idiom is therefore a latent bug
wherever a property may raise.

**Pattern — safe property access when a property may raise:**

```python
try:
    current_status = case.current_status
except (AttributeError, ValueError):
    current_status = None
```

Use `except (AttributeError, ValueError)` rather than a bare `except` so that
unexpected exception types still surface. Apply this pattern at BT node or
use-case entry points wherever a case property is accessed on an
object that may be only partially initialised (e.g., freshly constructed
from a DataLayer read before all derived fields are available).

Source: ISSUE-1455 — three call sites fixed across BT nodes and use cases.
