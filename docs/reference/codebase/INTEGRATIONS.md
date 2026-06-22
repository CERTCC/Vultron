# External Integrations

## Core Sections (Required)

### 1) Integration Inventory

| System | Type (API/DB/Queue/etc) | Purpose | Auth model | Criticality | Evidence |
|--------|---------------------------|---------|------------|-------------|----------|
| SQLite via SQLModel | DB | Persist Vultron objects and queue records | DB URL only; no separate DB auth shown | high | `vultron/adapters/driven/datalayer_sqlite/datalayer.py`, `config.example.yaml` |
| `ASGIEmitter` | In-process API | Deliver outbound activities to co-located actors through the mounted ASGI app | Same-process; no network auth | high | `vultron/adapters/driven/asgi_emitter.py`, `vultron/adapters/driving/fastapi/main.py` |
| `DemoHttpDeliveryAdapter` | Remote HTTP API | POST outbound activities to recipient inbox URLs | No signing/auth shown in this adapter | high | `vultron/adapters/driven/demo_http_delivery.py` |
| `SyncActivityAdapter` | Internal driven port adapter | Convert domain log entries to wire activities and queue them | N/A (in-process) | high | `vultron/adapters/driven/sync_activity_adapter.py` |
| `TriggerActivityAdapter` | Internal driven port adapter | Convert trigger-side domain actions into wire activities | N/A (in-process) | high | `vultron/adapters/driven/trigger_activity_adapter/__init__.py` |
| Demo HTTP clients | API client | Seed actors, drive demos, and verify flows over HTTP | Base URL config only | medium | `vultron/demo/utils.py`, `vultron/demo/helpers/verification.py` |
| MCP tool surface | In-process tool/API surface | Expose trigger use cases as callable functions pending SDK registration | None shown | low | `vultron/adapters/driving/mcp_server.py` |
| `ProdHttpDeliveryAdapter` | Remote HTTP API stub | Placeholder for signed remote delivery | `[TODO]` not implemented | medium | `vultron/adapters/driven/prod_http_delivery.py` |
| `SharedInboxAdapter` | Shared inbox stub | Placeholder for ActivityPub shared-inbox fan-out | `[TODO]` not implemented | medium | `vultron/adapters/driving/shared_inbox.py` |

### 2) Data Stores

| Store | Role | Access layer | Key risk | Evidence |
|-------|------|--------------|----------|----------|
| SQLite object store | Primary persistence for typed Vultron objects | `SqliteDataLayer` | Single-node/local-file limits | `vultron/adapters/driven/datalayer_sqlite/__init__.py`, `vultron/adapters/driven/datalayer_sqlite/datalayer.py` |
| SQLite inbox/outbox queues | Actor-scoped queue persistence | `SqliteDataLayer` queue methods plus inbox/outbox handlers | Queue behavior depends on correct actor scoping | `vultron/core/ports/datalayer.py`, `vultron/adapters/driving/fastapi/outbox_handler.py` |
| Named Docker volumes per actor | Persist multi-actor demo databases | Docker Compose | Operational complexity rises with actor count | `docker/docker-compose-multi-actor.yml` |

### 3) Secrets and Credentials Handling

- Credential sources: environment variables, YAML config, and Docker Compose env
  blocks
- Hardcoding checks: no API keys or passwords were found in sampled committed
  config files; examples primarily define base URLs and actor IDs
- Rotation or lifecycle notes: `[TODO]` no secret-rotation or external secret
  manager configuration was found

### 4) Reliability and Failure Behavior

- Retry/backoff behavior: `DemoHttpDeliveryAdapter` retries per recipient with
  exponential backoff (`DEFAULT_MAX_RETRIES = 3`, `DEFAULT_INITIAL_DELAY = 0.5`,
  multiplier `2.0`, max delay `30.0`)
- Timeout policy: local ASGI delivery uses `10.0` seconds; remote HTTP delivery
  uses `5.0` seconds; Docker health checks use short `curl -f` probes
- Circuit-breaker or fallback behavior: `ASGIEmitter` falls back to
  `DemoHttpDeliveryAdapter` on local delivery failures; no broader circuit
  breaker was found

### 5) Observability for Integrations

- Logging around external calls: yes; emitters and outbox handling log delivery
  attempts and failures
- Metrics/tracing coverage: no metrics or tracing integration was found in the
  sampled runtime files
- Missing visibility gaps: queue-depth metrics, retry counters, DB latency, and
  signed-delivery telemetry were not found

### 6) Evidence

- `vultron/adapters/driven/datalayer_sqlite/datalayer.py`
- `vultron/adapters/driven/asgi_emitter.py`
- `vultron/adapters/driven/demo_http_delivery.py`
- `vultron/adapters/driven/sync_activity_adapter.py`
- `vultron/adapters/driven/trigger_activity_adapter/__init__.py`
- `vultron/adapters/driving/fastapi/outbox_handler.py`
- `vultron/demo/utils.py`
- `vultron/adapters/driving/mcp_server.py`
- `vultron/adapters/driven/prod_http_delivery.py`
- `vultron/adapters/driving/shared_inbox.py`
- `docker/docker-compose-multi-actor.yml`
