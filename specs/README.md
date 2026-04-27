# Vultron API v2 Specifications

## Overview

This directory contains formal, testable specifications for the Vultron
API v2 implementation as structured YAML files validated by Pydantic
models in `vultron/metadata/specs/`.  Each specification defines
requirements using RFC 2119 keywords (MUST, SHOULD, MAY) with unique
requirement IDs and verification criteria.

**How to read specifications**: See `meta-specifications.md` for style
guide and conventions.

---

## Agent Loading Guide

Specs are stored as `specs/*.yaml` files validated by Pydantic models in
`vultron/metadata/specs/`.  Agents can consume specs in two ways:

### Option A: LLM-Optimized JSON (recommended)

Use the registry's LLM export for a flat, inheritance-resolved projection:

```bash
# All specs as compact JSON
python -m vultron.metadata.specs.render --format llm-json specs/

# Single topic (by file ID prefix)
python -m vultron.metadata.specs.render --format llm-json --topic CM specs/
```

The output is a single JSON object with `files`, `requirements`, and
`edges` arrays.  Each requirement has resolved `kind`/`scope` values,
denormalized `file`/`group` provenance, a `type` discriminator, and
inline `relationships`.

### Option B: Load YAML files directly

When an agent consumes specs directly, load files in two tiers to minimize
token overhead while ensuring full coverage.

### Always Load (any implementation task)

These 12 files (~82 KB) apply to virtually every code change:

| File | Covers |
|------|--------|
| `architecture.yaml` | Layer separation rules, adapter injection, wire boundary |
| `code-style.yaml` | Formatting, naming, import organization, type strictness |
| `tech-stack.yaml` | Approved runtime, tools, and dependency constraints |
| `handler-protocol.yaml` | Handler use-case contract and implementation patterns |
| `testability.yaml` | Test coverage requirements, test organization rules |
| `error-handling.yaml` | Exception hierarchy and error categories |
| `object-ids.yaml` | Object ID format (full URI) and blackboard key conventions |
| `use-case-organization.yaml` | Package layout for `vultron/core/use_cases/` |
| `prototype-shortcuts.yaml` | Permissible shortcuts at the prototype stage |
| `http-protocol.yaml` | HTTP status codes, Content-Type, error response format |
| `structured-logging.yaml` | Log format, correlation IDs, log levels |
| `idempotency.yaml` | Duplicate detection and idempotent processing |

### Load Contextually (by topic)

Load additional files only when the task touches the relevant area. See the
**Specification Structure** section below for the full topic index.

| Topic | Files to add |
|-------|-------------|
| Inter-actor communication / knowledge model | `actor-knowledge-model.yaml` |
| DataLayer adapter | `datalayer.md` |
| Handler pipeline | `inbox-endpoint.yaml`, `message-validation.yaml`, `semantic-extraction.yaml`, `dispatch-routing.yaml` |
| Behavior Trees | `behavior-tree-integration.yaml`, `behavior-tree-node-design.yaml`, `bt-composability.yaml`, `triggerable-behaviors.yaml`, `notes/trigger-classification.md` |
| Case / state management | `case-management.yaml`, `state-machine.yaml`, `case-log-processing.yaml` |
| Protocol conformance | `vultron-protocol-spec.yaml`, `vultron-as2-mapping.yaml` |
| Wire vocabulary | `vocabulary-model.yaml` |
| Activity factory functions | `activity-factories.yaml` |
| Response generation / outbox | `response-format.yaml`, `outbox.yaml` |
| Synchronization | `sync-log-replication.yaml` |
| Participant case replica lifecycle | `participant-case-replica.yaml` |
| Embargo / duration | `embargo-policy.yaml`, `duration.yaml` |
| Embargo default semantics | `embargo-policy.yaml`, `notes/embargo-default-semantics.md` |
| Configuration | `configuration.yaml` |
| Demo / CLI | `demo-cli.yaml`, `multi-actor-demo.yaml` |
| Event-driven control flow / cascade model | `event-driven-control-flow.yaml`, `notes/event-driven-control-flow.md` |
| Observability | `observability.yaml` |
| Security / CI | `ci-security.yaml`, `encryption.yaml` |
| Agentic API | `agentic-readiness.yaml` |
| Documentation work | `diataxis-requirements.yaml`, `project-documentation.yaml`, `traceability.yaml` |
| Plan organization / priorities | `project-documentation.yaml`, `notes/plan-organization.md` |
| Notes frontmatter / metadata tooling | `notes-frontmatter.yaml` |
| Spec registry / YAML requirement files | `spec-registry.yaml` |
| Bugfix skill / bug lifecycle | `bugfix-workflow.yaml` |

---

## Specification Structure

Specifications are organized by topic with minimal overlap. Cross-references link related requirements across files.

### Core Architecture

**System Architecture**:

- **`architecture.yaml`** - Hexagonal architecture (Ports and Adapters): layer
  separation rules, SemanticIntent placement, extractor isolation, adapter
  injection, connector plugins, wire replaceability, review checklist
  (ARCH-01 through ARCH-08)
- **`configuration.yaml`** - Unified YAML + Pydantic configuration management:
  `AppConfig` structure, `get_config()` / `reload_config()` API, env var
  naming conventions, `SeedConfig` alignment, `ActorConfig` abstraction with
  `default_case_roles`, testing patterns
  (CFG-01 through CFG-07)
- **`event-driven-control-flow.yaml`** - Event-driven processing model: primary
  event and cascade definitions, cascade chain, external decision nodes,
  BT-as-cascade-mechanism requirements, and demo script constraints
  (EDF-01 through EDF-05)
- **`vultron-protocol-spec.yaml`** - Requirements extracted from Vultron
  Protocol documentation: participant state tracking, RM/EM/CS messaging,
  model interactions, and implementation guidance

**Handler Pipeline** (message processing flow):

1. **`inbox-endpoint.yaml`** - FastAPI HTTP endpoint accepting ActivityStreams activities
2. **`message-validation.yaml`** - ActivityStreams 2.0 structure and semantic validation
3. **`semantic-extraction.yaml`** - Pattern matching to determine message semantics
4. **`dispatch-routing.yaml`** - Routing DispatchEvent to handler functions
5. **`handler-protocol.yaml`** - Handler function contract and implementation patterns

**DataLayer Port**:

- **`datalayer.md`** — DataLayer port requirements: auto-rehydration on read
  (DL-01), type-safe writes (DL-02), port isolation (DL-03). Formal requirements
  for the DL-REHYDRATE implementation task.

**Wire Vocabulary and Rehydration**:

- **`vocabulary-model.yaml`** - AS2 vocabulary registration, base model configuration
  (`alias_generator`, `validate_by_name`, `validate_by_alias`), type inference, Literal
  type narrowing, and the rehydration contract (`rehydrate(obj, dl)`) (VM-01 through VM-07)

- **`activity-factories.yaml`** - Factory function pattern for constructing outbound
  Vultron protocol activities; module structure under `vultron/wire/as2/factories/`,
  import boundary enforcement, error handling, TypeAlias cleanup, and migration
  requirements (AF-01 through AF-08)

**Semantic–Wire Mapping**:

- **`vultron-as2-mapping.yaml`** - Authoritative mapping from each `MessageSemantics`
  enum value to its ActivityStreams 2.0 wire representation: activity type,
  object type, target/context constraints, and nested-pattern conventions
  (VAM-01 through VAM-09). Foundational for hexagonal-architecture wire
  replaceability (ARCH-07-001).

**Behavior Tree Integration** (optional for complex workflows):

- **`behavior-tree-integration.yaml`** - BT execution model, bridge layer, DataLayer integration
- **`behavior-tree-node-design.yaml`** - BT node parameterization, composability, reuse,
  blackboard interface contracts, actor-config-driven roles, `CreateCaseOwnerParticipant`
  node design, and `CVDRoles.CASE_OWNER` requirement (BTND-01 through BTND-05)
- **`bt-composability.yaml`** - Simulator reference workflow (lookup before implementing),
  pre-definition requirement (core/behaviors/ as structure home), BT idioms over
  procedural code, and fractal composability principle at all depths
  (BTC-01 through BTC-04)
- **`triggerable-behaviors.yaml`** - Trigger API for actor-initiated behaviors (PRIORITY 30):
  endpoint format, RM/EM candidate behaviors, request/response schema,
  BT integration, per-actor DataLayer dependency, outbox activity requirement,
  trigger classification (general vs demo-only), `RunMode` StrEnum,
  demo endpoint prefix, `add-object-to-case` generalization
  (TRIG-01 through TRIG-10)

- **`actor-knowledge-model.yaml`** - Actor Knowledge Model: DataLayer isolation
  invariant, Actor knowledge boundaries, full-inline-object rule, stub-object
  exception, future object-tracking optimization (AKM-01 through AKM-04)

### Case and Actor Management

- **`case-management.yaml`** - CaseActor lifecycle, actor isolation, RM/EM/CS/VFD state model,
  object model relationships (Report/Case/CaseReference/VulnerabilityRecord), case update
  broadcast, CVD action rules API, redacted case view (CM-09), per-participant embargo
  acceptance tracking (CM-10)
- **`case-log-processing.yaml`** - Participant assertions, CaseActor-authored
  `CaseLogEntry` objects, case audit scope, recorded-history projection, and
  replication rules for recorded vs rejected log outcomes (CLP-01 through
  CLP-05)

**State Machines**:

- **`state-machine.yaml`** - RM/EM/CS/VFD state enum design, machine definitions, runtime
  transition guards, append-only history, state subsets, and wire/DataLayer compatibility
  (SM-01 through SM-08)

### Object Identifiers

- **`object-ids.yaml`** - Object ID format (full URI), DataLayer handling, blackboard key
  conventions, ADR requirement

### Cross-Cutting Concerns

**HTTP Protocol**:

- **`http-protocol.yaml`** - Status codes, Content-Type, size limits, error response format

**Logging and Observability**:

- **`structured-logging.yaml`** - Log format, correlation IDs, log levels, audit trail
- **`observability.yaml`** - Health check endpoints

**Error Handling**:

- **`error-handling.yaml`** - Exception hierarchy and error categories

**Quality Attributes**:

- **`idempotency.yaml`** - Duplicate detection and idempotent processing
- **`testability.yaml`** - Test coverage requirements, test organization,
  architecture boundary tests (TB-10, `PROD_ONLY`)

### Response Generation

**Future Implementation**:

- **`response-format.yaml`** - ActivityStreams response generation (Accept, Reject, etc.)
- **`outbox.yaml`** - Actor outbox structure, delivery, and addressing
  (OX-01 through OX-08)

### Synchronization

**Future Implementation**:

- **`sync-log-replication.yaml`** - Append-only case event log, replication
  transport, conflict handling, per-peer state, and retry semantics
  (SYNC-01 through SYNC-07)
- **`participant-case-replica.yaml`** - Participant case replica lifecycle:
  bootstrap via `Announce(VulnerabilityCase)`, single-writer update authority,
  case-context routing, reporter case discovery, and unknown-context handling
  (PCR-01 through PCR-07)

### Demo and Tooling

- **`demo-cli.yaml`** - Unified demo CLI: Click-based entry point, demo isolation, Docker,
  unit and integration test requirements
- **`multi-actor-demo.yaml`** - Multi-actor demo scenarios: Docker Compose orchestration,
  actor isolation, acceptance tests, scenario coverage (DEMOMA-01 through DEMOMA-04)

### Actor Profiles and Policies

- **`embargo-policy.yaml`** - Actor embargo policy record format, API, and
  default embargo semantics: tacit acceptance rule, PROPOSE+ACCEPT atomic
  transition, shortest-embargo-wins at case creation
  (EP-01 through EP-04)
- **`duration.yaml`** - Canonical ISO 8601 duration format for embargo
  policy fields: restricted grammar, validation rules, Pydantic mapping
  (DUR-01 through DUR-07)

### Security

- **`ci-security.yaml`** - GitHub Actions security: SHA pinning, secrets
  management, artifact integrity (CISEC-01 through CISEC-04)
- **`encryption.yaml`** - ActivityPub encryption and key management (`PROD_ONLY`)

### Code Standards

- **`code-style.yaml`** - Python formatting, import organization, circular import
  prevention, optional-field non-emptiness (CS-08-001), code reuse (CS-09-001),
  typed port/adapter interfaces (CS-10-001), domain event naming convention
  (`FooActivity` vs `FooEvent`, CS-10-002), type annotation strictness
  (no `Any`, CS-11-001), domain-centric class naming (CS-12-001)
- **`tech-stack.yaml`** - Normative technology constraints: runtime, persistence,
  tooling, code quality tooling (including pyright gradual adoption, IMPLTS-*),
  and Python runtime upgrade policy (IMPLTS-01-007)
- **`use-case-organization.yaml`** - Package layout for `vultron/core/use_cases/`
  (received/ vs triggers/), registry synchronization, test mirroring, and
  information flow documentation (UCORG-01 through UCORG-04)
- **`meta-specifications.md`** - How to write and maintain specifications

### Documentation Content and Organization

- **`diataxis-requirements.yaml`** - Requirements for organizing project
  documentation according to the Diátaxis framework (requirement IDs: `DF-NN-NNN`)
- **`traceability.yaml`** - Traceability matrix requirements: user story → spec
  mapping, coverage gaps, and maintenance cadence (TRACE-01 through TRACE-02)

### Project and Agent Guidance

- **`project-documentation.yaml`** - Documentation file structure and purpose;
  includes append-only history write protocol (PD-05) for `plan/*HISTORY.md`,
  and plan section organization rules (PD-06): `TASK-FOO` heading format,
  dot-notation task IDs, priority/plan decoupling
- **`prototype-shortcuts.yaml`** - Permissible shortcuts for the prototype stage,
  including performance testing deferral (PROTO-07) and backward-compatibility
  / change-completeness policy (PROTO-08)
- **`agentic-readiness.yaml`** - API and CLI requirements for automated agent integration
- **`bugfix-workflow.yaml`** - Bugfix skill requirements: root-cause depth analysis
  (Phase 2b), user engagement, issue escalation to `plan/BUGS.md`, and bug
  lifecycle archiving to `plan/IMPLEMENTATION_HISTORY.md`
  (BFW-01 through BFW-04)
- **`notes-frontmatter.yaml`** - YAML frontmatter schema for `notes/*.md` files:
  required fields (`title`, `status`), optional relationship fields, Pydantic
  loader in `vultron/metadata/notes/`, validation enforcement (pytest +
  pre-commit), migration requirements, and future registry/query tool notes
  (NF-01 through NF-07)
- **`spec-registry.yaml`** - YAML spec registry: converting `specs/*.md` to
  `specs/*.yaml` governed by Pydantic models in `vultron/metadata/specs/`;
  StrEnum vocabularies, discriminated union spec models, registry loader,
  linter, pytest marker integration, pre-commit hook, and context generation
  tool (SR-01 through SR-08)

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

**Note**: The `HP-` prefix is reserved for `handler-protocol.yaml`. The
`http-protocol.yaml` file uses the `HTTP-` prefix to avoid ambiguity. The
`diataxis-requirements.yaml` file uses the `DF-` prefix. The
`triggerable-behaviors.yaml` file uses the `TRIG-` prefix (not `TB-`, which
is reserved for `testability.yaml`).

### Prefix Registry

| Prefix | Specification file |
|--------|--------------------|
| `ARCH` | `architecture.yaml` |
| `AKM` | `actor-knowledge-model.yaml` |
| `AR` | `agentic-readiness.yaml` |
| `BT` | `behavior-tree-integration.yaml` |
| `BTC` | `bt-composability.yaml` |
| `BTND` | `behavior-tree-node-design.yaml` |
| `CISEC` | `ci-security.yaml` |
| `CLP` | `case-log-processing.yaml` |
| `CM` | `case-management.yaml` |
| `CS` | `code-style.yaml` |
| `DC` | `demo-cli.yaml` |
| `DEMOMA` | `multi-actor-demo.yaml` |
| `DF` | `diataxis-requirements.yaml` |
| `DL` | `datalayer.md` |
| `EH` | `error-handling.yaml` |
| `EP` | `embargo-policy.yaml` |
| `HP` | `handler-protocol.yaml` |
| `HTTP` | `http-protocol.yaml` |
| `IE` | `inbox-endpoint.yaml` |
| `IMPLTS` | `tech-stack.yaml` |
| `MV` | `message-validation.yaml` |
| `NF` | `notes-frontmatter.yaml` |
| `SR` | `spec-registry.yaml` |
| `OB` | `observability.yaml` |
| `OID` | `object-ids.yaml` |
| `OX` | `outbox.yaml` |
| `PD` | `project-documentation.yaml` |
| `PROTO` | `prototype-shortcuts.yaml` |
| `RF` | `response-format.yaml` |
| `SE` | `semantic-extraction.yaml` |
| `SM` | `state-machine.yaml` |
| `SL` | `structured-logging.yaml` |
| `PCR` | `participant-case-replica.yaml` |
| `SYNC` | `sync-log-replication.yaml` |
| `TB` | `testability.yaml` |
| `AF` | `activity-factories.yaml` |
| `TRACE` | `traceability.yaml` |
| `TRIG` | `triggerable-behaviors.yaml` |
| `UCORG` | `use-case-organization.yaml` |
| `VAM` | `vultron-as2-mapping.yaml` |
| `VM` | `vocabulary-model.yaml` |

## Requirement Tags

Some requirements carry special tags to indicate scope or applicability:

- **`PROD_ONLY`**: Requirement may be deferred during the prototype stage.
  See `prototype-shortcuts.yaml` PROTO-04-001 for the deferral policy.
  Tagged requirements have `scope: [production]` in their YAML definition.

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

- **`actor-knowledge-model.yaml`** consolidates Actor isolation and inline-object
  requirements from `case-management.yaml` (CM-01-001) and
  `message-validation.yaml` (MV-09-001); it is the authoritative basis for
  both.
- **`http-protocol.yaml`** consolidates HTTP requirements from `inbox-endpoint.yaml`,
  `message-validation.yaml`, `error-handling.yaml`, and `agentic-readiness.yaml`
- **`structured-logging.yaml`** consolidates logging requirements from `observability.yaml`,
  `error-handling.yaml`, `inbox-endpoint.yaml`
- **`idempotency.yaml`** consolidates duplicate detection requirements from
  `inbox-endpoint.yaml`, `message-validation.yaml`, `handler-protocol.yaml`,
  `response-format.yaml`
- **`case-management.yaml`** consolidates case state and actor isolation requirements
  from `behavior-tree-integration.yaml` (BT-09, BT-10), `notes/case-state-model.md`,
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
- **Diátaxis requirements**: `diataxis-requirements.yaml` — requirements for organizing
  project documentation according to the Diátaxis framework.
