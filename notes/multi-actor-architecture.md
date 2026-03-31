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

### D. CaseActor is a Dedicated Container or Logical Actor in a Coordinator

For D5-2 (Finder + Vendor only), CaseActor MAY be hosted within the
Vendor container (Vendor plays both roles) or as a third container. For
D5-3 onward, CaseActor SHOULD be a dedicated "case service" container:

- `VULTRON_BASE_URL=http://case-actor:7999/api/v2/`
- Actor ID registered as `http://case-actor:7999/api/v2/actors/{uuid}`
- Finder and Vendor pre-registered as participants in CaseActor's DataLayer

CaseActor instantiation (creation of the `VultronCaseActor` record) is
triggered by a case-creation event or a startup seed script.

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

The following items are not yet implemented and must be resolved before
D5-2 can be built.

### G1 — Base URL as First-Class Configuration

Currently `VULTRON_BASE_URL` is read from environment, but no startup
health check or API response reflects the configured base URL. A `GET
/api/v2/health/ready` or `GET /api/v2/info` endpoint should return the
configured base URL so demo scripts can confirm the container identity.

### G2 — Actor Seeding / Bootstrap CLI Command

Demo scripts need a reliable way to:

1. Create and persist the local actor record on container startup.
2. Register known peer actors (with their full inbox URLs) in the local
   DataLayer.

A `vultron-demo` sub-command (or a startup script called from the
container entrypoint) should handle this seeding. The seed data
(actor names, types, and peer URLs) can be passed as environment
variables or a JSON configuration file.

### G3 — CaseActor Instantiation Trigger

Currently, CaseActor records are created by behavior tree nodes in
`vultron/core/behaviors/case/nodes.py::CreateCaseActorNode`. This is
invoked during case creation in the single-container demo. For the
multi-container demo, CaseActor instantiation needs to be decoupled:

- Either CaseActor is pre-seeded at container startup (fixed identity),
- Or CaseActor is instantiated on demand via a trigger endpoint called
  from the case-creation flow.

This design choice should be made before implementing D5-2.

### G4 — Multi-Container Docker Compose Configuration

The existing `docker/docker-compose.yml` defines a single `api-dev`
container. D5-2 requires at minimum three services:

- `finder`: Finder actor API server
- `vendor`: Vendor actor API server
- `case-actor`: CaseActor API server (optional for D5-2; required for D5-3)

Each service needs:

- A unique `VULTRON_BASE_URL` env var
- Its own volume for `mydb.json`
- A healthcheck
- Membership in the shared Docker network (`vultron-network`)

### G5 — Demo Script for Multi-Container Scenario

The existing demo scripts in `vultron/demo/` assume a single API server.
D5-2 requires a new demo script (or extended existing ones) that:

1. Sends requests to multiple containers by URL.
2. Orchestrates the setup (peer registration, actor seeding) before
   the main scenario.
3. Polls each container's DataLayer or status endpoints to verify state
   propagation.

### G6 — Inbox URL Derivation Consistency

`DeliveryQueueAdapter` derives inbox URLs as `{actor_id}/inbox/`. This
must be consistent with the routing in `vultron/adapters/driving/fastapi/
routers/actors.py`, which registers the inbox endpoint at
`/{actor_id}/inbox/` under the `/api/v2/actors` prefix. The resulting
inbox URL must therefore be the actor's `id_` with `/inbox/` appended.

**Verify**: The actor's stored `id_` value must include the full path
that matches the FastAPI route. For an actor registered as
`http://finder:7999/api/v2/actors/finder-uuid`, the inbox URL must be
`http://finder:7999/api/v2/actors/finder-uuid/inbox/`.

This should be validated with an integration test before D5-2 is merged.

---

## 5. Recommended D5-2 Prerequisites

Before implementing D5-2, resolve the following in priority order:

1. **G2** — Implement an actor seeding/bootstrap mechanism (a `seed`
   sub-command in the demo CLI or a startup script).
2. **G4** — Add a multi-container Docker Compose configuration for the
   Finder + Vendor scenario.
3. **G6** — Add an integration test confirming that `DeliveryQueueAdapter`
   produces inbox URLs that match the FastAPI routing.
4. **G3** — Decide on CaseActor instantiation strategy and implement it.
5. **G5** — Write the D5-2 demo script.
6. **G1** — Add a `/info` or `/health/ready` response that returns
   `VULTRON_BASE_URL` (informational; useful for debugging).

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

The hexagonal architecture is clean and ready for multi-actor use. The
key remaining work for D5-2 is **operational** rather than
architectural:

- Per-container actor seeding and peer registration
- Docker Compose multi-service configuration
- A demo script that orchestrates multiple containers
- CaseActor instantiation strategy (simplest first: pre-seeded in a
  dedicated container)

All core protocol mechanics (inbox handling, outbox delivery, RM/EM/CS
state machines, CaseActor broadcast) are implemented and tested in the
single-container context. The multi-container demo is primarily a
question of deployment configuration and demo orchestration.
