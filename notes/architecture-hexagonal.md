---
title: Hexagonal Architecture Overview
status: active
description: >
  Hexagonal architecture layer model, boundaries, rules, and review checklist
  for Vultron.
related_notes:
  - vultron/core/ports/AGENTS.md
  - notes/architecture-adapters.md
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

- **Driving adapters**: trigger core execution (HTTP inbox, CLI, MCP).
- **Driven adapters**: core calls them for persistence/delivery.
- **Connector adapters**: third-party tracker/event translation.
- **Wire adapters**: parser/extractor stage in inbound pipeline.

---

## File Layout (Target)

- `vultron/core/`: domain models, use cases, ports, errors.
- `vultron/wire/as2/`: AS2 vocabulary, parser, extractor, serializer.
- `vultron/adapters/`: driving, driven, connectors.

Key enforced principle: core has no FastAPI, wire, or transport imports.

---

## Rules 1-9

1. Core has no wire-format imports.
2. Core has no framework imports.
3. `MessageSemantics` is defined in core.
4. Semantic extractor is the only AS2-to-domain mapping point.
5. Core functions accept/return domain types.
6. Driven adapters are injected via ports.
7. Connectors translate at the boundary only.
8. Wire layer is replaceable as a unit.
9. Port interfaces must not use `BaseModel` as boundary type hints.

---

## Core Models Must Be Richer Than Wire Models

Core models are authoritative. Wire models are projections. Fields represented
on the wire must be representable in core.

---

## Adapter Category Discipline

Avoid mixing driving and driven concerns in one module. If both directions are
needed, implement one module in `adapters/driving/` and one in
`adapters/driven/`.

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

1. **Core >= Wire**: core represents all wire fields.
2. **Fail-fast models**: required domain invariants validated at construction.
3. **ActivityStreams alignment** for protocol-exposed objects.
4. **Adapter/core boundary**: adapters own transport/wire construction.
5. **Non-breaking BT migration**: layer cleanup and behavior changes are staged.
6. **Dispatcher port preservation** until a validated replacement exists.
