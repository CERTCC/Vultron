# Multi-Actor Demo Specification

## Overview

Requirements for multi-actor demo scenarios, Docker Compose orchestration,
actor isolation, acceptance testing, and reproducibility.

**Source**: `plan/IMPLEMENTATION_PLAN.md` D5-1 through D5-5,
`plan/PRIORITIES.md` PRIORITY 300
**Cross-references**: `specs/demo-cli.md`, `specs/tech-stack.md`,
`specs/case-management.md`, `specs/observability.md`

---

## Cross-Actor Communication

- `DEMOMA-00-001` Cross-actor communication MUST occur exclusively via HTTP
  using the ActivityStreams inbox endpoint
  - No actor MAY read from or write to another actor's DataLayer directly;
    all coordination MUST pass through the inbox API

## Actor Isolation

- `DEMOMA-01-001` Each actor in a multi-actor demo MUST run in a separate
  container with its own DataLayer instance
  - Actor DataLayers MUST use logically isolated DataLayer instances even
    when containers share a storage volume; no actor's DataLayer records
    MUST be readable or writable by a sibling actor
- `DEMOMA-01-002` Each actor container MUST expose the actor's identity
  via its `/actors/{actor_id}` profile endpoint so that other containers
  can discover it at startup
- `DEMOMA-01-003` Demo startup MUST automatically reset all actor state to
  a known clean baseline before the scenario executes, without requiring
  manual user intervention
  - Documentation MUST describe how to seed initial actor state and how to
    trigger the automatic reset for a repeatable re-run

## Container Orchestration

- `DEMOMA-02-001` Docker Compose configurations for multi-actor demos MUST
  include a `healthcheck` for each actor service that probes the
  `/health/ready` endpoint
  - DEMOMA-02-001 refines IMPLTS-05-002 (tech-stack.md)
  - DEMOMA-02-001 depends-on OB-05-002 (observability.md): the
    `/health/ready` endpoint MUST check DataLayer connectivity
- `DEMOMA-02-002` (MUST) Dependent services (e.g., a demo orchestration container)
  MUST use `condition: service_healthy` for all actor service dependencies
- `DEMOMA-02-003` (MUST) Port mappings, network names, and required environment
  variables MUST be documented in the `docker-compose.yml` file or an
  accompanying `README.md`

## Acceptance Tests

- `DEMOMA-03-001` Each multi-actor demo scenario MUST include an acceptance
  test that validates the end-to-end workflow deterministically
  - The acceptance test MUST be runnable via a single command (e.g.,
    `docker compose up --abort-on-container-exit`)
- `DEMOMA-03-002` Acceptance tests MUST assert final state for each actor
  (e.g., correct RM/EM/CS state, expected case log entries)
- `DEMOMA-03-003` Acceptance tests MUST be reproducible: the same test on
  the same codebase MUST produce the same result on successive runs

## Scenario Coverage

- `DEMOMA-04-001` Multi-actor demo scenarios SHOULD be implemented
  progressively:
  - Scenario 1: two-actor (finder + vendor)
  - Scenario 2: three-actor (finder + vendor + coordinator)
  - Scenario 3: multi-vendor with ownership transfer
  - Each scenario SHOULD reuse and extend the prior scenario's Docker
    Compose configuration
- `DEMOMA-04-002` Each scenario SHOULD include a summary of the expected
  CVD workflow steps and the expected final RM/EM/CS state for each actor

## Demo Trigger Protocol

- `DEMOMA-05-001` All actor-initiated actions in scenario demos MUST be
  driven through the trigger API (`POST /actors/{actor_id}/trigger/{behavior-name}`),
  not by direct inbox injection or other mechanisms that bypass the actor's
  own protocol logic
  - **Rationale**: Using trigger endpoints ensures that the demo exercises
    the same code paths that a real actor would use, including BT execution,
    outbox queuing, and downstream cascading behaviors. Direct inbox injection
    spoofs protocol messages and does not validate that the initiating actor's
    behavior is correctly implemented.
  - DEMOMA-05-001 depends-on TRIG-01-001 (trigger endpoint format)
- `DEMOMA-05-002` Scenario demo scripts MUST NOT construct and POST raw
  ActivityStreams JSON directly to an actor's inbox as a substitute for
  calling that actor's trigger endpoint
  - DEMOMA-05-002 refines DEMOMA-00-001
