---
title: Hexagonal Architecture Overview
status: active
kind: guidance
description: >
  Hexagonal architecture layer model, adapter categories, boundaries, rules,
  and review checklist for Vultron.
related_notes:
  - vultron/core/ports/AGENTS.md
  - notes/architecture-adapters.md
  - notes/domain-validation.md
  - notes/use-case-protocol.md
  - notes/activity-factories.md
  - notes/datalayer-design.md
  - notes/inbox-orchestration.md
  - notes/inbox-pipeline.md
  - notes/predicates-rule-layer.md
relevant_packages:
  - vultron/core
  - vultron/wire/as2
  - vultron/adapters
---

# Hexagonal Architecture Overview

## Overview

Vultron follows **Hexagonal Architecture** (Ports and Adapters). The core
domain logic is isolated from external systems. External systems interact with
core only through ports, implemented by adapters.

Vultron also has an explicit **wire format layer**. ActivityStreams 2.0 is a
wire format with close semantic overlap to the domain, but it is still outside
the domain boundary.

---

## Wire Format vs Domain Semantics

AS2 was selected because it maps cleanly to Vultron semantics. That does not
make AS2 a domain dependency.

Why the boundary matters:

1. Wire formats can change; domain logic should not.
2. Parsing/shape validation are wire concerns, not domain concerns.

---

## Layer Model

### Inbound pipeline

```text
AS2 JSON (wire)
  -> AS2 parser (structural validity)
  -> semantic extractor (AS2 pattern -> domain intent)
  -> handler dispatch
  -> domain logic (no AS2 awareness)
```

### Outbound pipeline

```text
domain logic
  -> AS2 serializer
  -> AS2 JSON (wire)
  -> outbound transport adapter
```

`MessageSemantics` is a domain enum. AS2-to-domain coupling happens only in the
semantic extractor.

---

## The Hexagon

```text
DRIVING ADAPTERS -> CORE DOMAIN -> DRIVEN ADAPTERS

CLI / MCP / HTTP inbox      Case, Participant, CaseActor       Activity store
AS2 parser + extractor      domain events, semantics            Delivery queue
                                                          ->    Outbound HTTP
```

---

## Adapter Categories

This note holds the canonical list; `notes/architecture-adapters.md` covers
adapter patterns and boundary invariants.

- **Driving adapters** (`adapters/driving/`): receive external input and trigger
  core execution (HTTP inbox, CLI, MCP).
- **Driven adapters** (`adapters/driven/`): implement outbound dependencies core
  calls through ports (persistence, delivery).
- **Connector adapters** (`adapters/connectors/`): translate to and from
  third-party trackers and systems at the boundary.
- **Wire adapters** (`wire/as2/`): the parser/extractor stage of the inbound
  pipeline.

Do not mix driving and driven concerns in one module: a feature that needs both
directions gets one module in `adapters/driving/` and one in `adapters/driven/`.

---

## File Layout

- `vultron/core/`: domain models, use cases, ports, errors.
- `vultron/wire/as2/`: AS2 vocabulary, parser, extractor, serializer.
- `vultron/adapters/`: driving, driven, connectors.

Core has no FastAPI, wire, or transport imports. The wire and adapter halves are
enforced by `test/architecture/test_core_no_wire_imports.py` and
`test/architecture/test_core_no_adapter_imports.py`.

---

## Rules 1-10

1. Core has no wire-format imports.
2. Core has no framework imports.
3. `MessageSemantics` is defined in core.
4. Semantic extractor is the only AS2-to-domain mapping point.
5. Core functions accept/return domain types.
6. Driven adapters are injected via ports.
7. Connectors translate at the boundary only.
8. Wire layer is replaceable as a unit.
9. Port interfaces must not use wire-layer or adapter-layer models as boundary
    type hints. A core-owned domain model (`VultronEvent`, `TriggerRequest`,
    `UseCaseResult`) is the correct boundary type even though it is a Pydantic
    `BaseModel`; the rule targets the layer a type belongs to, not the library
    it is built with. Driving ports are O(1) in the behaviors behind them: one
    `dispatch()`/`trigger()` method over a registry, never one method per verb
    (ADR-0110).
10. Edge adapters promote loose wire objects to strict core types before
    calling core functions. Core helpers raise a descriptive exception on
    failure; they never return `None` as a failure signal. See ADR-0032.

---

## Review Checklist

**Core (`core/`)**

- [ ] No imports from wire/adapters/frameworks.
- [ ] Domain types only at boundaries.
- [ ] No direct DB/HTTP/queue client construction.

**Wire (`wire/as2/`)**

- [ ] Structural AS2 modeling only.
- [ ] Extractor is sole semantic mapping point.
- [ ] No case/business logic.

**Adapters (`adapters/`)**

- [ ] Driving adapters parse/extract before core calls.
- [ ] Driven adapters stay thin and transport-focused.

**Connectors (`adapters/connectors/`)**

- [ ] Plugins translate at boundaries only.
- [ ] No case/business logic in connector modules.

### Tests

- [ ] Core tests avoid AS2/HTTP.
- [ ] Wire tests isolate parsing/extraction.
- [ ] Adapter tests mock ports.

---

## Design Constraints and Invariants

1. **Core >= Wire**: core models are authoritative and wire models are
   projections, so every field represented on the wire is representable in
   core.
2. **Fail-fast models**: required domain invariants validated at construction.
   Core helpers raise a descriptive exception rather than returning `None` on
   failure (ADR-0032). Collection-typed fields default to the empty collection
   (`[]`, `{}`, `set()`); `None` is reserved for fields where absence is
   semantically distinct from empty.
3. **ActivityStreams alignment** for protocol-exposed objects.
4. **Adapter/core boundary**: adapters own transport/wire construction.
5. **Non-breaking BT migration**: stage layer cleanup and behavior changes in
   separate changes.
6. **Dispatcher port preservation**: keep the dispatcher port until a validated
   replacement exists.
