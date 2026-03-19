---
status: accepted
date: 2026-03-10
deciders:
  - vultron maintainers
consulted:
  - project stakeholders
informed:
  - contributors
---

# Adopt Hexagonal Architecture (Ports and Adapters) for Vultron

## Context and Problem Statement

The Vultron codebase grew incrementally from a prototype, causing concerns
from different layers to accumulate in the same modules. ActivityStreams 2.0
(AS2) structural types leaked into domain logic; semantic extraction was
scattered across multiple files; handler functions instantiated the
persistence layer directly; and the root `vultron/` package mixed domain
enums with wire-format enums. An architectural review (`notes/architecture-review.md`)
catalogued twelve violations of the intended separation of concerns, ranging
in severity from minor to critical. A clear architecture decision was needed
to guide remediation and prevent the same violations from re-accumulating.

## Decision Drivers

- **Wire format replaceability**: AS2 is the current wire format because its
  vocabulary matches Vultron's domain vocabulary. That match must not collapse
  the boundary between wire concerns and domain concerns.  If AS2 is replaced
  or extended, the change must be absorbable in the wire layer alone.
- **Testability**: Core domain logic should be testable with plain domain
  objects, without constructing AS2 activities or making HTTP requests.
- **Single extraction seam**: The mapping from AS2 vocabulary to domain
  semantics must live in exactly one place so that future wire format changes
  have a single point of entry.
- **Dependency injection over direct instantiation**: Driven adapters
  (persistence, delivery) must be injectable to support testing and alternate
  backends.
- **Alignment with existing clean points**: Several existing patterns are
  already architecturally sound (the `DataLayer` Protocol, `DispatchEvent`
  wrapper, `MessageSemantics` enum vocabulary, FastAPI 202 + BackgroundTasks)
  and should be preserved.

## Considered Options

- **Continue organic layering** — Impose light conventions without a formal
  architecture pattern. Enforce import rules via linting. Let the structure
  evolve.
- **Adopt hexagonal architecture (Ports and Adapters)** — Define explicit
  layers (`core/`, `wire/`, `adapters/`), ports (abstract interfaces), and
  adapters (thin translation layers). Use a separate wire layer for AS2
  parsing and semantic extraction.
- **Clean layered architecture (no hexagon)** — Impose strict top-down
  layering (controller → service → repository) without the explicit
  driving/driven adapter distinction.

## Decision Outcome

Chosen option: **Adopt hexagonal architecture (Ports and Adapters)**, because
it directly addresses the identified violations, provides the single
extraction seam the project needs, and cleanly separates the wire format from
the domain — a property that is especially important given that AS2 and the
Vultron domain vocabulary are semantically isomorphic and will otherwise
naturally collapse.

### Layer Model

Four layers are defined:

```text
wire (AS2 JSON)
    ↓
AS2 Parser          (vultron/wire/as2/parser.py)
    ↓
Semantic Extractor  (vultron/wire/as2/extractor.py)
    ↓
Handler Dispatch    (vultron/behavior_dispatcher.py)
    ↓
Domain Logic        (vultron/core/ — no AS2 awareness)
```

The `wire/` package is structurally separate from both `core/` and
`adapters/` to reflect its status as a distinct inbound pipeline stage, not
an adapter of a particular external system.

### Key Rules

1. `core/` MUST NOT import from `wire/`, `adapters/`, or any framework.
2. `core/` functions MUST accept and return domain types, not AS2 types.
3. `MessageSemantics` (`SemanticIntent`) is a domain type, defined in
   `core/`.
4. The semantic extractor is the **only** place AS2 vocabulary is mapped to
   domain concepts.
5. Driven adapters are injected via port interfaces, never instantiated
   directly.
6. The `wire/` layer is replaceable as a unit without touching `core/`.

### Consequences

- Good, because domain logic is testable with plain Pydantic objects and no
  AS2 or HTTP dependencies.
- Good, because a future wire format (binary encoding, revised federation
  standard) can be introduced by adding `wire/new_protocol/` without touching
  `core/` or `adapters/`.
- Good, because the single extraction seam (`wire/as2/extractor.py`) means
  new activity types require exactly one file change to add a new pattern.
- Good, because dependency injection via port interfaces enables alternative
  backends (in-memory, TinyDB, PostgreSQL) to be swapped without modifying
  handler code.
- Bad, because the transition from the organic prototype structure to the
  hexagonal layout requires incremental refactoring across multiple modules.
- Bad, because the semantic match between AS2 vocabulary and the Vultron
  domain vocabulary means some violations are subtle and may re-accumulate
  without active review.

## Validation

- Violations V-01 through V-12 (see `notes/architecture-review.md`)
  serve as the acceptance criteria: each is tracked and remediated
  incrementally.
- The review checklist in `notes/architecture-ports-and-adapters.md`
  (Core, Wire, Adapters, Connectors, Tests sections) is applied during code
  review.
- Import boundary rules are enforced by code review and, where practical,
  by `pylint`/`flake8` import order checks.

## Violation Inventory and Remediation Status

The architectural review identified twelve violations. Each has been assigned
to a remediation task.

### Remediated (ARCH-1.x and ARCH-CLEANUP-x)

| ID   | Severity | Summary                                                 | Addressed by      |
|------|----------|---------------------------------------------------------|-------------------|
| V-01 | Major    | `MessageSemantics` co-located with AS2 enums in `enums.py` | ARCH-1.1, ARCH-CLEANUP-2 |
| V-02 | Critical | `DispatchEvent.payload` typed as `as_Activity`       | ARCH-1.2          |
| V-03 | Critical | `behavior_dispatcher.py` imports AS2 type directly      | ARCH-1.2          |
| V-04 | Major    | `find_matching_semantics` called twice (extractor + decorator) | ARCH-1.3   |
| V-05 | Major    | Pattern matching logic split across `activity_patterns.py` and `semantic_map.py` | ARCH-1.3 |
| V-06 | Major    | `parse_activity` in HTTP router instead of wire layer   | ARCH-1.3          |
| V-07 | Major    | `inbox_handler.py` imports and uses AS2 `VOCABULARY`    | ARCH-1.3          |
| V-08 | Critical | `handle_inbox_item` collapses three pipeline stages     | ARCH-1.3          |
| V-09 | Major    | `semantic_handler_map.py` lazy-imports adapter-layer handlers | ARCH-1.4    |
| V-10 | Major    | All handlers call `get_datalayer()` directly            | ARCH-1.4          |
| V-11 | Major    | Handlers use `isinstance` checks against AS2 types      | ARCH-CLEANUP-3    |
| V-12 | Minor    | Dispatcher test constructs AS2 types for core test inputs | ARCH-CLEANUP-3  |

Shims left at `vultron/activity_patterns.py`, `vultron/semantic_map.py`, and
`vultron/semantic_handler_map.py` for backward compatibility were removed in
ARCH-CLEANUP-1. AS2 structural enums were moved from `vultron/enums.py` to
`vultron/wire/as2/enums.py` in ARCH-CLEANUP-2.

### Completed (PRIORITY-60 package relocation)

Package relocations that have been completed as part of PRIORITY-60:

- **P60-1** ✅: `vultron/as_vocab/` moved to `vultron/wire/as2/vocab/`. All
  internal and external imports updated; old `vultron/as_vocab/` deleted.
- **P60-2** ✅: `vultron/behaviors/` moved to `vultron/core/behaviors/`. All
  internal and external imports updated; old `vultron/behaviors/` deleted.

### Remaining (PRIORITY-60 — in progress)

The following structural move is deferred to PRIORITY-60 and is tracked
in `plan/IMPLEMENTATION_PLAN.md`:

- **P60-3**: Stub the `vultron/adapters/` package per the target layout in
  `notes/architecture-ports-and-adapters.md`.

## Pros and Cons of the Options

### Continue organic layering

- Good: no migration cost; conventions can be enforced incrementally.
- Bad: violations re-accumulate naturally because AS2 and domain vocabulary
  look identical; without a formal pattern, there is no shared vocabulary for
  "this is a violation" across reviewers.
- Bad: import chains between layers remain implicit and hard to enforce.

### Adopt hexagonal architecture (chosen)

- Good: explicit layer vocabulary (core / wire / adapters / ports) that all
  contributors can reference.
- Good: violations have a clear label and a known remediation pattern.
- Good: enables future extension points (MCP adapter, alternative wire
  formats, connector plugins) without core changes.
- Neutral: incremental migration is possible; the codebase does not need to
  be fully restructured before benefits are realized.
- Bad: transition work is non-trivial and must be done incrementally without
  breaking the running system.

### Clean layered architecture (no hexagon)

- Good: familiar pattern for most Python web developers.
- Bad: does not provide the driving/driven adapter distinction needed to
  support CLI, MCP, and HTTP inbox as parallel entry points.
- Bad: does not explicitly model the wire layer as separate from adapters,
  which is the core architectural tension in this project.

## More Information

- `notes/architecture-ports-and-adapters.md` — canonical layer model,
  file layout target, code patterns, and review checklist.
- `notes/architecture-review.md` — full violation inventory (V-01 to V-12)
  and remediation plans (R-01 to R-06).
- `specs/architecture.md` — testable requirements derived from this decision
  (ARCH-01-001 through ARCH-03-001 and beyond).
- `plan/PRIORITIES.md` — PRIORITY 50 (hexagonal architecture starting with
  triggers.py), PRIORITY 60 (continue package relocation).
- `plan/IMPLEMENTATION_PLAN.md` — task-level tracking for ARCH-1.1 through
  ARCH-1.4, ARCH-CLEANUP-1 through ARCH-CLEANUP-3, and P60-1 through P60-3.
- Related ADRs:
  - [ADR-0005](0005-activitystreams-vocabulary-as-vultron-message-format.md)
    — rationale for choosing AS2 as wire format.
  - [ADR-0007](0007-use-behavior-dispatcher.md) — introduces the
    `DispatchEvent` wrapper and `ActivityDispatcher` Protocol that this
    architecture refines.
