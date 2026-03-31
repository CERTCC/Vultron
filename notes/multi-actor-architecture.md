# Multi-Actor Architecture — Pre-D5-2 Review

**Relates to**: D5-1 (PRIORITY-300), `plan/IMPLEMENTATION_PLAN.md`

**Purpose**: This document reviews the current architecture in preparation
for implementing D5-2 (Two-Actor Demo: Finder + Vendor in separate
containers) and subsequent multi-actor demo scenarios. It clarifies
assumptions about isolated actor/container operation and identifies gaps
to address before D5-2 can be implemented.

---

## 1. CA-2 Follow-up Confirmation

The PRIORITY-200 CA-2 follow-up (actor-first case-scoped action-rules
endpoint) is **confirmed complete**. The endpoint is available at:

```text
GET /api/v2/actors/{actor_id}/cases/{case_id}/action-rules
```

The `ActionRulesUseCase` resolves the `CaseParticipant` internally from
the `(actor_id, case_id)` pair using `actor_participant_index` with a
fallback scan of `case.case_participants`. Tests cover the 200, 404
(unknown case), and 404 (actor not in case) paths.

---

## 2. Current Architecture State

### 2.1 Hexagonal Architecture

All architectural violations (V-01 through V-24, TECHDEBT-13a–c)
identified in `notes/architecture-review.md` are fully resolved. The
codebase strictly follows the Ports and Adapters model:

- **Core** (`vultron/core/`): No AS2, FastAPI, or adapter imports.
- **Wire** (`vultron/wire/`): AS2 parsing and semantic extraction only.
- **Adapters** (`vultron/adapters/`):
  - Driving: FastAPI (HTTP inbox, trigger endpoints, outbox),
    CLI, MCP server
  - Driven: TinyDB DataLayer, HTTP delivery queue (`DeliveryQueueAdapter`)

### 2.2 Per-Actor DataLayer Isolation (ADR-0012)

Each actor has an isolated DataLayer namespace backed by TinyDB table
prefixes (e.g., `alice__Actor`, `alice__VulnerabilityCase`). The
`get_datalayer(actor_id)` factory returns a scoped `TinyDbDataLayer`
instance. All FastAPI routes that are actor-scoped use a closure lambda
`Depends(lambda actor_id=Path(...): get_datalayer(actor_id))`.

A shared/admin DataLayer (no actor prefix) is used for cross-actor
lookups and is passed as `shared_dl` where needed. The `inbox_handler`
and `outbox_handler` each accept both `actor_dl` (scoped) and `dl`
(shared).

### 2.3 Outbound Message Delivery (OX-1.x)

The outbox pipeline is implemented end-to-end:

1. Use cases append activity IDs to the DataLayer outbox via
   `dl.record_outbox_item(actor_id, activity_id)`.
2. `outbox_handler` (in `vultron/adapters/driving/fastapi/outbox_handler.py`)
   drains the outbox by reading undelivered activity IDs, loading each
   activity from the DataLayer, and calling `await emitter.emit(activity,
   recipients)`.
3. `DeliveryQueueAdapter` (in `vultron/adapters/driven/delivery_queue.py`)
   implements `ActivityEmitter` by deriving each recipient's inbox URL as
   `{actor_uri}/inbox/` and POSTing the JSON-serialised activity via
   `httpx.AsyncClient`. Per-recipient failures are logged and swallowed.
4. `outbox_handler` is invoked as a FastAPI `BackgroundTask` on inbox
   POST and on explicit outbox POST.

**Implication for multi-container demos**: If Finder POSTs to Vendor,
`DeliveryQueueAdapter` constructs Vendor's inbox URL as `{vendor_id}/inbox/`
— which must be a routable HTTP URL. In a single-container demo, this
resolves to the same process. In a multi-container setup, this must be an
actual network address.

### 2.4 CaseActor Model

`VultronCaseActor` (`vultron/core/models/case_actor.py`) is a domain model
with `type_="Service"`. A CaseActor record is stored in the DataLayer of
the actor instance that hosts it. The `_broadcast_case_update` method in
`UpdateCaseReceivedUseCase` locates the CaseActor by doing a `dl.by_type("Service")`
query, creates an Announce activity, and appends it to the CaseActor's
outbox. The broadcast is then picked up by `outbox_handler` on the next
outbox drain cycle.

**Important**: In the current single-container demo setup, CaseActor
lives in the shared DataLayer and its broadcast appends to the same
outbox that the outbox_handler will drain. In a multi-container setup,
CaseActor would need its own container with its own `actor_id`,
`VULTRON_BASE_URL`, and DataLayer.

### 2.5 Actor Identity and URL Model

Actor IDs are full HTTP URIs derived from `VULTRON_BASE_URL`
(environment variable; default `https://demo.vultron.local/`).
`make_id("Actor")` produces `{VULTRON_BASE_URL}Actor/{uuid}`.

`DeliveryQueueAdapter` derives inbox URLs as `{actor_id}/inbox/`
(no path transformation; ActivityPub convention). This means an actor
at `http://vendor:7999/api/v2/Actor/abc123` would have inbox
`http://vendor:7999/api/v2/Actor/abc123/inbox/`.

**Note**: The current routing mounts actors under `/api/v2/actors/`, not
`/api/v2/Actor/`. The actor's `id_` field stores the full canonical URI
(including the path used at registration time). Inbox delivery depends
on that stored URI being routable from the sending container's network.

### 2.6 RM State Tracking (PRIORITY-90, ADR-0013)

The global in-memory `STATUS` dict has been removed. RM state is now
tracked exclusively through persisted `VultronParticipantStatus` records
(appended to `CaseParticipant.participant_statuses`). The `ReportStatus`
model in `vultron/core/models/status.py` now contains only the
`OfferStatusEnum` and `ObjectStatus` models (offer/object tracking),
not the RM-state dict.

---

## 3. Assumptions for Isolated Actor/Container Scenarios

The following assumptions underpin the D5-2 and later multi-actor demo
designs.

### A. One Container = One Actor Role

Each actor (Finder, Vendor, Coordinator, CaseActor) runs as a separate
API server container. Within a container, the actor may have a single
actor record in its DataLayer. Other actors' data is **not** directly
accessible — actors communicate only via the Vultron Protocol (HTTP
inbox POST).

### B. `VULTRON_BASE_URL` is the Container's Identity Anchor

Each container is launched with a unique `VULTRON_BASE_URL` that
reflects its network address on the Docker bridge network (e.g.,
`http://finder:7999/api/v2/`, `http://vendor:7999/api/v2/`). All
actor IDs and object IDs generated in that container use this base URL.

**Consequence**: Actor IDs generated in `finder` are not portable to
the `vendor` container without explicit registration.

### C. Peer Actor Pre-Registration

Before a demo scenario can run, each container must have the remote
actors' records present in its DataLayer so that the outbox handler
can look up recipient URIs and the inbox handler can match activities
to known senders. Pre-registration is a setup step in the demo script,
not an automatic discovery process.

Concretely: the demo script bootstraps each container by POSTing actor
creation requests (or seeding the DataLayer) for all peers before the
main scenario begins.

### D. CaseActor Instantiation Strategy (D5-1-G3)

**Chosen strategy**: Pre-seeded container identity with lazy per-case
`VultronCaseActor` records.

#### Container identity (VultronService record)

Each actor container — including the dedicated `case-actor` container —
is pre-seeded on first setup by running `vultron-demo seed` against the
container's API. The seed command calls `POST /actors/` with the actor's
pre-configured `VULTRON_ACTOR_ID`, creating a `VultronService` record in
the container's DataLayer. This is the container's stable identity.

All three actors use **deterministic, pre-known IDs** set via
`VULTRON_ACTOR_ID` in `docker/docker-compose-multi-actor.yml`:

| Service      | Deterministic actor ID                                |
|:-------------|:------------------------------------------------------|
| `finder`     | `http://finder:7999/api/v2/actors/finder`             |
| `vendor`     | `http://vendor:7999/api/v2/actors/vendor`             |
| `case-actor` | `http://case-actor:7999/api/v2/actors/case-actor`     |

Peer registration is driven by seed config JSON files in
`docker/seed-configs/` (one per container). Each file lists the local
actor's deterministic ID and the full set of peer actors.
`VULTRON_SEED_CONFIG` is set in the compose file and consumed by
`vultron-demo seed` via `SeedConfig.load()`.

#### Per-case VultronCaseActor record

When a `VulnerabilityCase` is created (e.g., during the Vendor's
case-engagement BT execution), the `CreateCaseActorNode`
(`vultron/core/behaviors/case/nodes.py`) creates a `VultronCaseActor`
object with `context=case_id` in the **Vendor container's DataLayer**.
The `_broadcast_case_update` method in `UpdateCaseReceivedUseCase` then
locates this record by `type_="Service"` and `context=case_id` to emit
Announce activities.

**For D5-2 (Finder + Vendor)**: CaseActor co-locates in the Vendor
container. Vendor plays both Vendor and CaseActor roles. The dedicated
`case-actor` container is not required for D5-2 and can be omitted from
the scenario.

**For D5-3+**: The dedicated `case-actor` container is required. The
demo script (D5-1-G5) will register Finder and Vendor as participants
in the case-actor container's DataLayer, and trigger case creation there
so that the `VultronCaseActor` record is created in the case-actor
DataLayer rather than the Vendor DataLayer.

### E. Inbox URL Routing via Docker Network

On the Docker network, each container is reachable by its service name.
Inbox URLs derived from actor IDs must resolve to the correct container.
This requires that `VULTRON_BASE_URL` use the Docker service name as the
hostname (e.g., `http://finder:7999/api/v2/`).

### F. DataLayer Persistence Per Container

Each container uses its own TinyDB file (e.g., `/app/data/mydb.json`)
mounted as a Docker volume. DataLayer reset endpoints (`DELETE
/api/v2/datalayer/`) operate on that container's database only.

---

## 4. Gaps to Address Before D5-2

The following items were not implemented as of D5-1; completed items are
noted with their implementation reference.

### G1 — Base URL as First-Class Configuration ✅

Implemented in D5-1-G1. `GET /api/v2/info` returns `VULTRON_BASE_URL`
and the list of registered actor IDs. Tests in
`test/adapters/driving/fastapi/routers/test_info.py`.

### G2 — Actor Seeding / Bootstrap CLI Command ✅

Implemented in D5-1-G2. `vultron-demo seed` CLI sub-command creates the
local actor and registers peer actors. Reads configuration from
`VULTRON_SEED_CONFIG` (JSON file) or env vars. Tests in
`test/demo/test_seed.py` and `test/demo/test_seed_config.py`.

### G3 — CaseActor Instantiation Strategy ✅

Implemented in D5-1-G3. See §3-D for the chosen strategy:

- Deterministic actor IDs via `VULTRON_ACTOR_ID` in
  `docker/docker-compose-multi-actor.yml`.
- Per-container seed config JSON files in `docker/seed-configs/`.
- Per-case `VultronCaseActor` records still created by
  `CreateCaseActorNode` at case creation time.

Tests in `test/demo/test_multi_actor_seed.py`.

### G4 — Multi-Container Docker Compose Configuration ✅

Implemented in D5-1-G4. `docker/docker-compose-multi-actor.yml` defines
finder, vendor, and case-actor services with health checks, named volumes,
and deterministic actor IDs.

### G5 — Demo Script for Multi-Container Scenario

The existing demo scripts in `vultron/demo/` assume a single API server.
D5-2 requires a new demo script (or extended existing ones) that:

1. Sends requests to multiple containers by URL.
2. Orchestrates the setup (peer registration, actor seeding) before
   the main scenario.
3. Polls each container's DataLayer or status endpoints to verify state
   propagation.

### G6 — Inbox URL Derivation Consistency ✅

Implemented in D5-1-G6. Integration tests in
`test/adapters/driven/test_delivery_inbox_url.py` confirm that
`DeliveryQueueAdapter` produces inbox URLs consistent with the FastAPI
actors router route.

---

## 5. D5-2 Prerequisites Status

All G1–G4, G6 prerequisites are complete. G5 (demo script) is the
remaining prerequisite for D5-2.

---

## 6. Non-Goals for D5-2

The following are out of scope for D5-2 and should not block it:

- Cryptographic actor identity or message signing (`notes/encryption.md`)
- WebFinger or dynamic actor discovery
- RAFT consensus or log replication (SYNC-1 through SYNC-4; PRIORITY-400)
- Full ActivityPub compatibility (`notes/federation_ideas.md`)
- Production-grade MongoDB backing store (ADR-0012 deferred item)
- Fuzzer node re-implementation (PRIORITY-500)

---

## 7. Summary

The hexagonal architecture is clean and ready for multi-actor use. All
D5-1 gap items (G1–G4, G6) are complete. The key remaining work for D5-2
is the multi-container demo script (G5 / D5-1-G5):

- Per-container actor seeding and peer registration (via seed configs)
- Docker Compose multi-service configuration (complete)
- A demo script that orchestrates multiple containers
- CaseActor instantiation strategy (complete: pre-seeded with deterministic
  ID; co-located in Vendor for D5-2; dedicated container for D5-3+)

All core protocol mechanics (inbox handling, outbox delivery, RM/EM/CS
state machines, CaseActor broadcast) are implemented and tested in the
single-container context. The multi-container demo is primarily a
question of deployment configuration and demo orchestration.
