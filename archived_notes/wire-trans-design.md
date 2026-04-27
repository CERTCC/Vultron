# Wire-Domain Translation Boundary: Pre-Implementation Design (Archived)

**Archived from**: `notes/domain-model-separation.md`
**Reason**: PRIORITY-340 (WIRE-TRANS-01 through WIRE-TRANS-05) is fully
complete. The "Current Status" and "Recommended Next Steps" sections described
pre-implementation state and design decisions that have now been implemented.

---

## Current Status (as of 2026-04-15)

### Inheritance Boundary: Already Clean

The AS2 inheritance coupling described in early design notes is **resolved**.
Domain objects (`VulnerabilityCase`, `VultronReport`, `VultronCaseLogEntry`,
`VultronCaseActor`, `VultronParticipant`, etc.) are already pure Pydantic
`BaseModel` — they do NOT inherit from AS2 types. This was accomplished during
the ARCH-1.x and ARCH-CLEANUP refactor phases. `PROTO-06-001` (which permitted
the prototype to use direct AS2 inheritance) has been removed from
`specs/prototype-shortcuts.yaml` because its structural concern is resolved.

The naming collision that still causes confusion: there are **two classes
named `VultronObject`**:

- `vultron.core.models.base.VultronObject` → `VultronBase` → `BaseModel`
  (pure Pydantic; the canonical base for domain objects)
- `vultron.wire.as2.vocab.objects.base.VultronObject` → `as_Object` →
  `as_Base` → `BaseModel` (AS2 wire base; used only in the wire layer)

The wire `VultronObject` will be renamed `VultronAS2Object` as part of
task WIRE-TRANS-01 (see `plan/IMPLEMENTATION_PLAN.md`).

### Translation Boundary: Not Yet Implemented (except `CaseLogEntry`)

What remains is the formal `from_core()` / `to_core()` translation contract
on wire types. Currently, some trigger modules in `vultron/core/use_cases/`
import wire types directly to construct outbound activities — this violates
ARCH-01-001 but has been tolerated pending WIRE-TRANS-01.

**First implementation** (`from_core()` on `WireCaseLogEntry`, commit
`f8eede75`) proves the pattern works:

```python
# In vultron/wire/as2/vocab/objects/case_log_entry.py
@classmethod
def from_core(cls, entry: VultronCaseLogEntry) -> "CaseLogEntry":
    return cls.model_validate(entry.model_dump(mode="json"))
```

The pattern places conversion ownership in the **destination** type (wire), so
core never needs to know about wire internals.

### Agreed Design Decisions (2026-04-15 Architecture Session)

1. **`VultronAS2Object` rename** (ARCH-12-001): Wire `VultronObject` →
   `VultronAS2Object` to eliminate the naming collision.

2. **`from_core()` classmethod** (ARCH-12-002): Every concrete `VultronAS2Object`
   subclass MUST implement `from_core(cls, core_obj) -> "<WireType>"`. The base
   class provides a stub that raises `NotImplementedError`.

3. **`to_core()` method** (ARCH-12-003): Every concrete `VultronAS2Object`
   subclass MUST implement `to_core(self) -> <DomainType>`. Base class stub
   raises `NotImplementedError`.

4. **`_field_map` escape hatch** (ARCH-12-004): `ClassVar[dict[str, str]] = {}`
   on `VultronAS2Object` for transitional field name mismatches. Applied as key
   substitution before `model_validate()`. Goal: empty on all types once field
   names are aligned.

5. **Activity base class generic translation** (ARCH-12-005): Wire activity
   base class gets generic `from_core(domain_activity)` that maps grammatical
   AS2 fields (actor, object_, target, context, in_reply_to) by calling
   `WireType.from_core()` on any `VultronObject` value and passing URI strings
   through unchanged. Subclasses narrow the input type.

6. **Delete `serializer.py`** (ARCH-12-006): `vultron/wire/as2/serializer.py`
   has 6 standalone `domain_xxx_to_wire()` functions that duplicate what
   `from_core()` classmethods will do. Delete the file once all callers are
   migrated. No compatibility shims.

7. **No wire imports from core triggers**: Once `from_core()` exists on all
   relevant wire types, trigger modules will call `WireType.from_core(domain_obj)`
   instead of importing and constructing wire objects directly, closing the
   remaining ARCH-01-001 violations.

The formal requirements are in `specs/architecture.yaml` (ARCH-12-001 through
ARCH-12-007). The implementation task is WIRE-TRANS-01 in
`plan/IMPLEMENTATION_PLAN.md`.

Some wire-layer vocabulary objects still expose convenience methods that mutate
protocol state directly. `VulnerabilityCase.set_embargo()` is the clearest
example: it changes `current_status.em_state`, which is domain behaviour rather
than wire formatting.

The durable direction is:

- keep transport-only shaping, aliases, and serialization concerns in wire DTOs
- move state-mutation helpers to core domain objects or core protocols
- let any temporary wire helper delegate to the core implementation instead of
  owning the state transition itself

This matters directly to ADR-0013 follow-up work because helpers such as
`CaseParticipant.append_rm_state()` sit on the boundary between persisted RM
history and transport-layer convenience APIs.

---

## Recommended Next Steps (now completed as WIRE-TRANS-01–05)

These were captured as task WIRE-TRANS-01 in `plan/IMPLEMENTATION_PLAN.md`:

1. **Rename** wire `VultronObject` → `VultronAS2Object` in
   `vultron/wire/as2/vocab/objects/base.py` (ARCH-12-001).
2. **Add stubs** `from_core()`, `to_core()`, and `_field_map` to
   `VultronAS2Object` (ARCH-12-002 through ARCH-12-004).
3. **Implement `from_core()`** on all concrete wire object types, replacing
   the standalone functions in `vultron/wire/as2/serializer.py` (ARCH-12-006).
4. **Implement `from_core()` on wire activity base class** for generic
   grammatical-field mapping (ARCH-12-005).
5. **Delete `serializer.py`** and update all callers (ARCH-12-006).
6. **Align field names** to empty `_field_map` on all types (ARCH-12-004 goal).

Once WIRE-TRANS-01 is complete, core trigger modules can call
`WireType.from_core(domain_obj)` instead of importing wire types directly,
closing remaining ARCH-01-001 violations.
