# Architecture Specification

## Overview

Defines the architectural constraints for the Vultron codebase. The system
follows **Hexagonal Architecture** (Ports and Adapters): the core domain
is isolated from all external systems. External systems interact with the
core through defined **ports**, via thin **adapters**.

**Source**: `notes/architecture-ports-and-adapters.md`,
`notes/architecture-review.md`

**Cross-references**: `code-style.md` CS-05-001 (circular import
prevention), `notes/domain-model-separation.md` (wire/domain/persistence
separation), `notes/architecture-review.md` (violation inventory and
remediation history), `docs/adr/0009-hexagonal-architecture.md` (decision
rationale)

---

## Layer Separation

- `ARCH-01-001` The `core/` package (or equivalent domain layer) MUST NOT
  import from `wire/`, `adapters/`, or any external framework
  - Prohibited: `fastapi`, `typer`, `mcp`, `httpx`, `celery`, `nats`,
    connector libraries, AS2 libraries (`pyld`, `rdflib`, JSON-LD tooling)
  - **Rationale**: Keeps domain logic replaceable without touching the wire
    or transport layer
  - **Current state**: Partially achieved. `vultron/core/` has no wire/framework
    imports; `vultron/api/` still uses FastAPI and imports from `vultron/wire/`.
    Remaining wire imports in `vultron/core/use_cases/triggers/` are tracked
    as ARCH-01-001 violations to be resolved by WIRE-TRANS-01.
  - ARCH-01-001 is-derived-by CS-05-001
- `ARCH-01-002` Core functions MUST accept and return domain types only
  - Raw dicts, AS2 types, JSON strings, and framework objects MUST NOT
    enter the domain
  - The inbound pipeline MUST complete parse → extract steps before calling
    into core
  - **Current state**: `InboundPayload` domain type introduced (ARCH-1.2);
    parse → extract pipeline stages in `vultron/wire/as2/`. Trigger modules
    still construct wire activity objects directly; see WIRE-TRANS-01.
- `ARCH-01-003` The `wire/` layer (AS2 parser, semantic extractor) MUST NOT
  contain handler logic, case management, or journal management
  - **Rationale**: Wire format concerns are structurally distinct from
    domain concerns; mixing them prevents future wire format substitution

## SemanticIntent Enum

- `ARCH-02-001` The `MessageSemantics` enum (`SemanticIntent`) MUST be
  defined in the domain layer, not in the wire layer
  - The enum expresses the authoritative vocabulary of what can happen
    in the system, as the domain understands it
  - Wire layer pattern maps are an implementation detail of the extractor,
    not part of the domain definition
  - **Current location**: `vultron/core/models/events.py` (remediated in
    ARCH-1.1); re-exported from `vultron/enums.py` for compatibility. AS2
    structural enums moved to `vultron/wire/as2/enums.py` (ARCH-CLEANUP-2).

## Semantic Extractor

- `ARCH-03-001` AS2 vocabulary MUST be mapped to domain concepts in exactly
  one location: the semantic extractor
  - No other module maps AS2 activity patterns to domain semantics
  - Handler code MUST NOT inspect AS2 types to infer message meaning
  - **Rationale**: Isolates the single seam where wire format changes are
    absorbed
  - **Current state**: ✅ Achieved. `vultron/wire/as2/extractor.py` is the
    sole location of AS2-to-domain vocabulary mapping (ARCH-1.3,
    ARCH-CLEANUP-1). Handler code no longer inspects AS2 types (ARCH-CLEANUP-3).

## Driven Adapter Injection

- `ARCH-04-001` (MUST) Driven adapters (persistence, delivery queue, DNS resolver,
  HTTP delivery) MUST be injected into core services via port interfaces
  - Core services MUST NOT instantiate concrete adapter implementations
    directly
  - **Rationale**: Enables testing core logic with in-memory ports and
    swapping production backends without touching domain code
  - **Current state**: ✅ Achieved. All handlers receive `dl: DataLayer` via
    parameter injection (ARCH-1.4). `get_datalayer()` is no longer called
    inside handler bodies.

## Connector Plugins

- `ARCH-05-001` Connector plugins (tracker integrations) MUST be discovered
  via Python entry points (`importlib.metadata`); the core MUST NOT import
  them directly
- `ARCH-05-002` Connector plugins MUST translate only — no case handling
  logic, authorization, or journal management belongs in a connector

## Wire Layer Replaceability

- `ARCH-06-001` The wire layer (`wire/as2/`) SHOULD be replaceable as a
  unit without touching the core or adapter layers
  - If a change to the wire format requires changes in the core, a
    boundary has been violated
  - **Current state**: Substantially achieved. `DispatchEvent.payload` is
    now typed as `InboundPayload` (domain type), not `as_Activity` (ARCH-1.2).
    Full wire replaceability requires completing P60-3 (adapters package).

## Handler Isolation

- `ARCH-07-001` Handler functions MUST NOT re-invoke semantic extraction
  - The semantic type MUST be pre-computed and carried in the dispatch
    wrapper (`DispatchEvent.semantic_type`)
  - Semantic verification decorators MUST compare `dispatchable.semantic_type`
    directly, not re-run pattern matching
  - **Current state**: ✅ Achieved. Semantic type validation occurs at dispatch
    time via `USE_CASE_MAP` key lookup in `vultron/core/dispatcher.py`;
    no re-invocation of `find_matching_semantics`.

## Driving Adapter Boundary

- `ARCH-08-001` Driving adapters (HTTP inbox, CLI, MCP server) MUST invoke
  the wire pipeline before calling into the core
  - AS2 parsing and semantic extraction are stages of the inbound pipeline,
    not responsibilities of the driving adapter itself
  - **Rationale**: Any driving adapter that needs to ingest AS2 can reuse
    the wire pipeline; there is no duplication
  - **Current state**: ✅ Achieved. `parse_activity()` is in
    `vultron/wire/as2/parser.py`; the router calls it as a thin wrapper
    (ARCH-1.3).

## Wire-Domain Translation Boundary

- `ARCH-12-001` The wire-layer `VultronObject` base class in
  `vultron/wire/as2/vocab/objects/base.py` MUST be renamed `VultronAS2Object`;
  all reference sites MUST be updated accordingly.
  The core domain `VultronObject` (in `vultron/core/models/base.py`) retains
  its name — only the wire base is renamed.
  - **Rationale**: Two classes named `VultronObject` in different packages
    causes confusion in search, type-checking, and code completion.

- `ARCH-12-002` Every concrete subclass of `VultronAS2Object` MUST implement
  a `from_core(cls, core_obj: <DomainType>) -> "<WireType>"` classmethod that
  converts a core domain object to its wire representation.
  `VultronAS2Object` MUST provide a base stub that raises `NotImplementedError`
  so that unimplemented subclasses fail loudly at runtime.
  - Ownership of core→wire translation MUST reside in the wire type (the
    destination), not in the core layer that constructs the source.
  - **Implemented**: `WireCaseLogEntry.from_core()` (commit `f8eede75`)

- `ARCH-12-003` Every concrete subclass of `VultronAS2Object` MUST implement
  a `to_core(self) -> <DomainType>` instance method that converts a wire
  object back to its core domain representation.
  `VultronAS2Object` MUST provide a base stub that raises `NotImplementedError`.

- `ARCH-12-004` `VultronAS2Object` MUST define a `_field_map: ClassVar[dict[str,
  str]] = {}` class variable as a transitional escape hatch for field name
  mismatches between domain and wire types.
  `from_core()` and `to_core()` MUST apply `_field_map` key substitutions
  before calling `model_validate()`.
  The goal is for `_field_map` to be empty on all subclasses once domain and
  wire field names are aligned.

- `ARCH-12-005` Wire activity base classes MUST provide a generic
  `from_core(cls, domain_activity)` classmethod that maps grammatical AS2
  fields (`actor`, `object_`, `target`, `context`, `in_reply_to`) by calling
  `WireType.from_core()` on any field value that is a `VultronObject` instance,
  and passing URI strings through unchanged.
  Subclasses MUST narrow the `domain_activity` type annotation to their
  specific domain activity counterpart.

- `ARCH-12-006` `vultron/wire/as2/serializer.py` MUST be removed.
  All standalone `domain_xxx_to_wire()` functions in that module MUST be
  migrated to `from_core()` classmethods on the corresponding wire types.
  No compatibility shims or re-exports are permitted.
  - **Cross-reference**: `plan/IMPLEMENTATION_PLAN.md` task WIRE-TRANS-01

- `ARCH-12-007` The default `from_core()` / `to_core()` implementation for
  concrete wire types MAY use a JSON round-trip
  (`cls.model_validate(core_obj.model_dump(mode="json"))`) as its body.
  Where field names differ, the `_field_map` escape hatch (ARCH-12-004) MUST
  be used rather than bespoke field-by-field mapping logic.

- `ARCH-09-001` Core domain models MUST be as rich as or richer than their
  wire-layer counterparts
  - Wire models are projections of core models — not simplified views and
    not independent representations
  - Any field present in a wire model MUST be representable in the
    corresponding core domain model
  - **Rationale**: A thinner core model forces piecemeal additions as
    handlers are implemented, causing boundary leakage and implementation
    drift
  - **Cross-reference**: `notes/architecture-ports-and-adapters.md`
    "Core Models Must Be Richer Than Wire Models"

## Fail-Fast Domain Objects

- `ARCH-10-001` Domain events and domain models MUST validate required
  fields at construction time and fail immediately if required invariants
  are not satisfied
  - Fields that are required for a specific event subtype MUST NOT be
    typed as `Field | None` in that subtype
  - Parent classes MAY use `Field | None` for fields that are genuinely
    optional at the parent level; subclasses MUST narrow optional parent
    fields to required when the field is always present for that subtype
  - **Rationale**: Late validation masks missing data and makes debugging
    harder; fail-fast ensures errors surface at the point of construction
  - **Cross-reference**: `notes/architecture-ports-and-adapters.md`
    "Design Constraints and Invariants" invariant 2

## Port Inbound/Outbound Discrimination

- `ARCH-11-001` Core ports SHOULD be organized into inbound (driving)
  and outbound (driven) categories
  - **Inbound ports (driving)**: interfaces that external adapters call
    into core (e.g., `UseCase`, `ActivityDispatcher`)
  - **Outbound ports (driven)**: interfaces that core calls out to external
    systems through (e.g., `DataLayer`, `ActivityEmitter`)
  - Port files in `core/ports/` that no longer correspond to active
    interfaces SHOULD be removed rather than left as stubs
  - **Cross-reference**: `notes/architecture-ports-and-adapters.md`
    "Core Port Taxonomy: Inbound vs Outbound"

---

## Review Checklist

Use this checklist during code review to catch boundary violations.

### Core / domain layer

- [ ] No imports from `wire/`, `adapters/`, or any framework
- [ ] `MessageSemantics` enum defined here, not in the wire layer
- [ ] All service functions take domain types, not AS2 types or raw dicts
- [ ] No direct instantiation of DB, HTTP, or queue clients

### Wire layer

- [ ] Structural AS2 types contain no domain logic
- [ ] Extractor is the sole location of AS2-to-domain vocabulary mapping
- [ ] Wire types expose `from_core()` / `to_core()` for domain↔wire
  translation; no standalone serializer module with conversion functions
- [ ] No handler logic or case management in the wire layer

### Adapters

- [ ] Inbound adapters invoke the wire pipeline before calling core
- [ ] Outbound adapters receive serialized wire objects — no AS2 construction
- [ ] Each adapter function is thin — translation and dispatch only

### Connectors

- [ ] Plugins translate only — no business logic
- [ ] Discovered via entry points, not hardcoded imports

### Tests

- [ ] Core tests use domain types directly — no AS2, no HTTP
- [ ] Wire tests verify parsing and extraction independently of domain logic
- [ ] Adapter tests mock ports, not external systems

---

## Remediation Status

The following architectural requirements had known violations that have been
remediated through incremental refactoring (ARCH-1.1 through ARCH-CLEANUP-3).
See `docs/adr/0009-hexagonal-architecture.md` for full violation inventory.

**Remediated (ARCH-1.x and ARCH-CLEANUP-x):**

- ARCH-02-001 (`MessageSemantics` in core) — ✅ ARCH-1.1
- ARCH-03-001 (sole mapping point) — ✅ ARCH-1.3, ARCH-CLEANUP-1
- ARCH-04-001 (adapter injection) — ✅ ARCH-1.4
- ARCH-06-001 (wire replaceability) — ✅ substantially achieved (ARCH-1.2)
- ARCH-07-001 (no re-invocation) — ✅ ARCH-1.2/1.3
- ARCH-08-001 (parse in wire layer) — ✅ ARCH-1.3

**ARCH-12 (Wire-domain translation boundary) — in progress:**

- ARCH-12-002 partially: `WireCaseLogEntry.from_core()` implemented (commit
  `f8eede75`). Full rollout across all wire types is task WIRE-TRANS-01 in
  `plan/IMPLEMENTATION_PLAN.md`.

**Wire imports in core triggers — tolerated, tracked:**

- `vultron/core/use_cases/triggers/` still imports wire types for activity
  construction. These are ARCH-01-001 violations tolerated until WIRE-TRANS-01
  is complete; at that point, trigger modules will call wire `from_core()`
  methods rather than importing wire types directly.
  See `plan/IMPLEMENTATION_PLAN.md` task WIRE-TRANS-01.

**Not yet started (PRIORITY-60):**

- P60-3: `vultron/adapters/` package structure stub — see
  `plan/IMPLEMENTATION_PLAN.md`

See `notes/architecture-review.md` for full violation inventory and
remediation history (R-01 to R-06).
