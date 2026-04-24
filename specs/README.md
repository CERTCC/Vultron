# Vultron API v2 Specifications

## Overview

This directory contains formal, testable specifications for the Vultron API v2 implementation. Each specification defines requirements using RFC 2119 keywords (MUST, SHOULD, MAY) with unique requirement IDs and verification criteria.

**How to read specifications**: See `meta-specifications.md` for style guide and conventions.

---

## Agent Loading Guide

When an agent consumes specs, load files in two tiers to minimize token
overhead while ensuring full coverage.

### Always Load (any implementation task)

These 12 files (~82 KB) apply to virtually every code change:

| File | Covers |
|------|--------|
| `architecture.md` | Layer separation rules, adapter injection, wire boundary |
| `code-style.md` | Formatting, naming, import organization, type strictness |
| `tech-stack.md` | Approved runtime, tools, and dependency constraints |
| `handler-protocol.md` | Handler use-case contract and implementation patterns |
| `testability.md` | Test coverage requirements, test organization rules |
| `error-handling.md` | Exception hierarchy and error categories |
| `object-ids.md` | Object ID format (full URI) and blackboard key conventions |
| `use-case-organization.md` | Package layout for `vultron/core/use_cases/` |
| `prototype-shortcuts.md` | Permissible shortcuts at the prototype stage |
| `http-protocol.md` | HTTP status codes, Content-Type, error response format |
| `structured-logging.md` | Log format, correlation IDs, log levels |
| `idempotency.md` | Duplicate detection and idempotent processing |

### Load Contextually (by topic)

Load additional files only when the task touches the relevant area. See the
**Specification Structure** section below for the full topic index.

| Topic | Files to add |
|-------|-------------|
| DataLayer adapter | `datalayer.md` |
| Handler pipeline | `inbox-endpoint.md`, `message-validation.md`, `semantic-extraction.md`, `dispatch-routing.md` |
| Behavior Trees | `behavior-tree-integration.md`, `behavior-tree-node-design.md`, `triggerable-behaviors.md` |
| Case / state management | `case-management.md`, `state-machine.md`, `case-log-processing.md` |
| Protocol conformance | `vultron-protocol-spec.md`, `vultron-as2-mapping.md` |
| Wire vocabulary | `vocabulary-model.md` |
| Response generation / outbox | `response-format.md`, `outbox.md` |
| Synchronization | `sync-log-replication.md` |
| Embargo / duration | `embargo-policy.md`, `duration.md` |
| Embargo default semantics | `embargo-policy.md`, `notes/embargo-default-semantics.md` |
| Configuration | `configuration.md` |
| Demo / CLI | `demo-cli.md`, `multi-actor-demo.md` |
| Observability | `observability.md` |
| Security / CI | `ci-security.md`, `encryption.md` |
| Agentic API | `agentic-readiness.md` |
| Documentation work | `diataxis-requirements.md`, `project-documentation.md`, `traceability.md` |
| Writing/updating specs | `meta-specifications.md` |
| Bugfix skill / bug lifecycle | `bugfix-workflow.md` |

---

## Specification Structure

Specifications are organized by topic with minimal overlap. Cross-references link related requirements across files.

### Core Architecture

**System Architecture**:

- **`architecture.md`** - Hexagonal architecture (Ports and Adapters): layer
  separation rules, SemanticIntent placement, extractor isolation, adapter
  injection, connector plugins, wire replaceability, review checklist
  (ARCH-01 through ARCH-08)
- **`configuration.md`** - Unified YAML + Pydantic configuration management:
  `AppConfig` structure, `get_config()` / `reload_config()` API, env var
  naming conventions, `SeedConfig` alignment, testing patterns
  (CFG-01 through CFG-06)
- **`vultron-protocol-spec.md`** - Requirements extracted from Vultron
  Protocol documentation: participant state tracking, RM/EM/CS messaging,
  model interactions, and implementation guidance

**Handler Pipeline** (message processing flow):

1. **`inbox-endpoint.md`** - FastAPI HTTP endpoint accepting ActivityStreams activities
2. **`message-validation.md`** - ActivityStreams 2.0 structure and semantic validation
3. **`semantic-extraction.md`** - Pattern matching to determine message semantics
4. **`dispatch-routing.md`** - Routing DispatchEvent to handler functions
5. **`handler-protocol.md`** - Handler function contract and implementation patterns

**DataLayer Port**:

- **`datalayer.md`** — DataLayer port requirements: auto-rehydration on read
  (DL-01), type-safe writes (DL-02), port isolation (DL-03). Formal requirements
  for the DL-REHYDRATE implementation task.

**Wire Vocabulary and Rehydration**:

- **`vocabulary-model.md`** - AS2 vocabulary registration, base model configuration
  (`alias_generator`, `validate_by_name`, `validate_by_alias`), type inference, Literal
  type narrowing, and the rehydration contract (`rehydrate(obj, dl)`) (VM-01 through VM-07)

**Semantic–Wire Mapping**:

- **`vultron-as2-mapping.md`** - Authoritative mapping from each `MessageSemantics`
  enum value to its ActivityStreams 2.0 wire representation: activity type,
  object type, target/context constraints, and nested-pattern conventions
  (VAM-01 through VAM-09). Foundational for hexagonal-architecture wire
  replaceability (ARCH-07-001).

**Behavior Tree Integration** (optional for complex workflows):

- **`behavior-tree-integration.md`** - BT execution model, bridge layer, DataLayer integration
- **`behavior-tree-node-design.md`** - BT node parameterization, composability, reuse, and
  blackboard interface contracts (BTND-01 through BTND-04)
- **`triggerable-behaviors.md`** - Trigger API for actor-initiated behaviors (PRIORITY 30):
  endpoint format, RM/EM candidate behaviors, request/response schema,
  BT integration, per-actor DataLayer dependency, outbox activity requirement

### Case and Actor Management

- **`case-management.md`** - CaseActor lifecycle, actor isolation, RM/EM/CS/VFD state model,
  object model relationships (Report/Case/CaseReference/VulnerabilityRecord), case update
  broadcast, CVD action rules API, redacted case view (CM-09), per-participant embargo
  acceptance tracking (CM-10)
- **`case-log-processing.md`** - Participant assertions, CaseActor-authored
  `CaseLogEntry` objects, case audit scope, recorded-history projection, and
  replication rules for recorded vs rejected log outcomes (CLP-01 through
  CLP-05)

**State Machines**:

- **`state-machine.md`** - RM/EM/CS/VFD state enum design, machine definitions, runtime
  transition guards, append-only history, state subsets, and wire/DataLayer compatibility
  (SM-01 through SM-08)

### Object Identifiers

- **`object-ids.md`** - Object ID format (full URI), DataLayer handling, blackboard key
  conventions, ADR requirement

### Cross-Cutting Concerns

**HTTP Protocol**:

- **`http-protocol.md`** - Status codes, Content-Type, size limits, error response format

**Logging and Observability**:

- **`structured-logging.md`** - Log format, correlation IDs, log levels, audit trail
- **`observability.md`** - Health check endpoints

**Error Handling**:

- **`error-handling.md`** - Exception hierarchy and error categories

**Quality Attributes**:

- **`idempotency.md`** - Duplicate detection and idempotent processing
- **`testability.md`** - Test coverage requirements, test organization,
  architecture boundary tests (TB-10, `PROD_ONLY`)

### Response Generation

**Future Implementation**:

- **`response-format.md`** - ActivityStreams response generation (Accept, Reject, etc.)
- **`outbox.md`** - Actor outbox structure, delivery, and addressing
  (OX-01 through OX-08)

### Synchronization

**Future Implementation**:

- **`sync-log-replication.md`** - Append-only case event log, replication
  transport, conflict handling, per-peer state, and retry semantics
  (SYNC-01 through SYNC-07)

### Demo and Tooling

- **`demo-cli.md`** - Unified demo CLI: Click-based entry point, demo isolation, Docker,
  unit and integration test requirements
- **`multi-actor-demo.md`** - Multi-actor demo scenarios: Docker Compose orchestration,
  actor isolation, acceptance tests, scenario coverage (DEMO-MA-01 through DEMO-MA-04)

### Actor Profiles and Policies

- **`embargo-policy.md`** - Actor embargo policy record format, API, and
  default embargo semantics: tacit acceptance rule, PROPOSE+ACCEPT atomic
  transition, shortest-embargo-wins at case creation
  (EP-01 through EP-04)
- **`duration.md`** - Canonical ISO 8601 duration format for embargo
  policy fields: restricted grammar, validation rules, Pydantic mapping
  (DUR-01 through DUR-07)

### Security

- **`ci-security.md`** - GitHub Actions security: SHA pinning, secrets
  management, artifact integrity (CI-SEC-01 through CI-SEC-04)
- **`encryption.md`** - ActivityPub encryption and key management (`PROD_ONLY`)

### Code Standards

- **`code-style.md`** - Python formatting, import organization, circular import
  prevention, optional-field non-emptiness (CS-08-001), code reuse (CS-09-001),
  typed port/adapter interfaces (CS-10-001), domain event naming convention
  (`FooActivity` vs `FooEvent`, CS-10-002), type annotation strictness
  (no `Any`, CS-11-001), domain-centric class naming (CS-12-001)
- **`tech-stack.md`** - Normative technology constraints: runtime, persistence,
  tooling, code quality tooling (including pyright gradual adoption, IMPL-TS-*),
  and Python runtime upgrade policy (IMPL-TS-01-007)
- **`use-case-organization.md`** - Package layout for `vultron/core/use_cases/`
  (received/ vs triggers/), registry synchronization, test mirroring, and
  information flow documentation (UC-ORG-01 through UC-ORG-04)
- **`meta-specifications.md`** - How to write and maintain specifications

### Documentation Content and Organization

- **`diataxis-requirements.md`** - Requirements for organizing project
  documentation according to the Diátaxis framework (requirement IDs: `DF-NN-NNN`)
- **`traceability.md`** - Traceability matrix requirements: user story → spec
  mapping, coverage gaps, and maintenance cadence (TRACE-01 through TRACE-02)

### Project and Agent Guidance

- **`project-documentation.md`** - Documentation file structure and purpose;
  includes append-only history write protocol (PD-05) for `plan/*HISTORY.md`
- **`prototype-shortcuts.md`** - Permissible shortcuts for the prototype stage,
  including performance testing deferral (PROTO-07) and backward-compatibility
  / change-completeness policy (PROTO-08)
- **`agentic-readiness.md`** - API and CLI requirements for automated agent integration
- **`bugfix-workflow.md`** - Bugfix skill requirements: root-cause depth analysis
  (Phase 2b), user engagement, issue escalation to `plan/BUGS.md`, and bug
  lifecycle archiving to `plan/IMPLEMENTATION_HISTORY.md`
  (BFW-01 through BFW-04)

---

## Reading Order

**For new contributors**:

1. Start with `meta-specifications.md` to understand spec structure
2. Read handler pipeline specs in order (inbox → validation → extraction → dispatch → handler)
3. Consult cross-cutting specs as needed

**For implementing features**:

1. Identify relevant specifications from structure above
2. Read requirements with verification criteria
3. Follow cross-references for related requirements
4. Check `plan/IMPLEMENTATION_PLAN.md` for implementation status

**For reviewing code**:

1. Verify requirements are met per verification criteria
2. Check cross-referenced specs for related constraints
3. Ensure tests cover verification scenarios

---

## Requirement ID Format

Each requirement has a unique ID: `PREFIX-NN-NNN`

- **PREFIX**: Specification abbreviation (e.g., `HP` = Handler Protocol, `IE` = Inbox Endpoint)
- **NN**: Category number within specification
- **NNN**: Requirement number within category

Example: `HP-04-002` = Handler Protocol, category 4 (Payload Access), requirement 2

**Note**: The `HP-` prefix is reserved for `handler-protocol.md`. The
`http-protocol.md` file uses the `HTTP-` prefix to avoid ambiguity. The
`diataxis-requirements.md` file uses the `DF-` prefix. The
`triggerable-behaviors.md` file uses the `TRIG-` prefix (not `TB-`, which
is reserved for `testability.md`).

### Prefix Registry

| Prefix | Specification file |
|--------|--------------------|
| `ARCH` | `architecture.md` |
| `AR` | `agentic-readiness.md` |
| `BT` | `behavior-tree-integration.md` |
| `BTND` | `behavior-tree-node-design.md` |
| `CI-SEC` | `ci-security.md` |
| `CLP` | `case-log-processing.md` |
| `CM` | `case-management.md` |
| `CS` | `code-style.md` |
| `DC` | `demo-cli.md` |
| `DEMO-MA` | `multi-actor-demo.md` |
| `DF` | `diataxis-requirements.md` |
| `DL` | `datalayer.md` |
| `EH` | `error-handling.md` |
| `EP` | `embargo-policy.md` |
| `HP` | `handler-protocol.md` |
| `HTTP` | `http-protocol.md` |
| `IE` | `inbox-endpoint.md` |
| `IMPL-TS` | `tech-stack.md` |
| `MV` | `message-validation.md` |
| `OB` | `observability.md` |
| `OID` | `object-ids.md` |
| `OX` | `outbox.md` |
| `PD` | `project-documentation.md` |
| `PROTO` | `prototype-shortcuts.md` |
| `RF` | `response-format.md` |
| `SE` | `semantic-extraction.md` |
| `SM` | `state-machine.md` |
| `SL` | `structured-logging.md` |
| `SYNC` | `sync-log-replication.md` |
| `TB` | `testability.md` |
| `TRACE` | `traceability.md` |
| `TRIG` | `triggerable-behaviors.md` |
| `UC-ORG` | `use-case-organization.md` |
| `VAM` | `vultron-as2-mapping.md` |
| `VM` | `vocabulary-model.md` |

## Requirement Tags

Some requirements carry special tags to indicate scope or applicability:

- **`PROD_ONLY`**: Requirement may be deferred during the prototype stage.
  See `prototype-shortcuts.md` PROTO-04-001 for the deferral policy.
  Tagged requirements appear inline after the requirement ID:
  `-`REQ-ID``PROD_ONLY`Requirement statement`

  Common categories of `PROD_ONLY` requirements include:
  - Authentication and authorization (per PROTO-01-001)
  - Federation and cross-server delivery (per PROTO-02-001/02-002)
  - Rate limiting and request size enforcement
  - Correlation ID propagation and structured log format
  - Audit and data access logging
  - Execution timeout enforcement
  - Future performance optimizations

---

Some specifications consolidate requirements from multiple sources to create a single source of truth:

- **`http-protocol.md`** consolidates HTTP requirements from `inbox-endpoint.md`,
  `message-validation.md`, `error-handling.md`, and `agentic-readiness.md`
- **`structured-logging.md`** consolidates logging requirements from `observability.md`,
  `error-handling.md`, `inbox-endpoint.md`
- **`idempotency.md`** consolidates duplicate detection requirements from
  `inbox-endpoint.md`, `message-validation.md`, `handler-protocol.md`,
  `response-format.md`
- **`case-management.md`** consolidates case state and actor isolation requirements
  from `behavior-tree-integration.md` (BT-09, BT-10), `notes/case-state-model.md`,
  and `plan/PRIORITIES.md` (Priority 100, 200); also captures domain model
  architecture guidance (CM-08)

When requirements appear consolidated, the consolidating spec is the authoritative
source.

---

## Implementation Status

See `plan/IMPLEMENTATION_PLAN.md` for current implementation status by
specification.

---

## Updating Specifications

When updating specifications:

1. Follow `meta-specifications.md` style guide
2. Keep requirements atomic and testable
3. Update verification criteria when changing requirements
4. Add cross-references for related requirements
5. Update this README if adding/removing specifications
6. Consider consolidation to reduce redundancy

---

## Related Documentation

- **Implementation Plan**: `plan/IMPLEMENTATION_PLAN.md`
- **Architecture Decisions**: `docs/adr/*.md`
- **Design Insights**: `notes/` — durable design insights and lessons learned
- **ActivityPub Workflows**: `docs/howto/activitypub/activities/*.md`
- **Agent Instructions**: `AGENTS.md` (AI coding agent guidance)
- **Copilot Instructions**: Embedded in system context (development guidance)
- **Diátaxis requirements**: `diataxis-requirements.md` — requirements for organizing
  project documentation according to the Diátaxis framework.
