---
stakeholder_type: [project-contributor]
---

# External Integrations

## Core Sections (Required)

### 1) Integration Inventory

| System | Type | Purpose | Auth model | Criticality | Evidence |
|--------|------|---------|------------|-------------|----------|
| SQLite (via SQLModel/SQLAlchemy) | Database | Persistent storage for domain objects and inbox/outbox queues | None (local file or `:memory:`) | High | `vultron/adapters/driven/datalayer_sqlite/` |
| Peer Vultron actors (HTTP/AS2) | Outbound HTTP API | ActivityStreams 2.0 message delivery to other Vultron nodes | HTTP Signatures (intended) — the production adapter docstring specifies "sign the request with the local actor's HTTP Signature private key" (OX-10-004); adapter is a `NotImplementedError` stub, so unauthenticated in the demo path | High | `vultron/adapters/driven/prod_http_delivery.py` |
| ActivityPub / AS2 (inbound) | Inbound HTTP | Receive CVD coordination activities from other actors | [ASK USER] — no inbound auth/signature verification observed on the inbox handler | High | `vultron/adapters/driving/fastapi/inbox_handler.py` |
| Third-party trackers (Jira, VINCE) | Connector adapter | Translate external tracker events to/from Vultron domain | [ASK USER] — example only, not production-wired | Low | `vultron/adapters/connectors/example/` |
| Docker Compose (multi-actor demo) | Orchestration | Stands up multiple actor containers sharing an AS2 network for the end-to-end demo | None (local demo) | Low | `docker/docker-compose-multi-actor.yml`, `docker/demo-entrypoint.sh` |

### 2) Data Stores

| Store | Role | Access layer | Key risk | Evidence |
|-------|------|--------------|----------|----------|
| SQLite (one file per actor, or `:memory:`) | Per-actor activity store: each hosted actor gets its own store holding only that actor's knowledge (ADR-0073) | `SqliteDataLayer` in `vultron/adapters/driven/datalayer_sqlite/`, resolved per actor by `get_datalayer(actor_id)` | Single-process SQLite has no concurrent multi-writer support; not suitable for multi-node deployment without migration. There is no migration path from a pre-ADR-0073 shared store | `vultron/adapters/driven/datalayer_sqlite/schema.py`, `vultron/adapters/driven/datalayer.py` |
| In-memory (tests) | Isolated per-test data store | `reset_datalayer()` + `sqlite:///:memory:` | None (intended ephemeral use) | `test/conftest.py` |

### 3) Secrets and Credentials Handling

- **Credential sources**: `VULTRON_CONFIG` YAML file and/or environment variables; only `PROJECT_NAME` is documented in `.env.example`
- **Hardcoding checks**: no hardcoded credentials observed in source; database URL is always injected via config
- **Rotation or lifecycle notes**: [ASK USER] — no secrets manager integration observed; credential rotation strategy unknown. The outbound-delivery design anticipates a per-actor HTTP Signature **private key** (`prod_http_delivery.py` docstring, OX-10-004), but no key storage, loading, or rotation is implemented yet

### 4) Reliability and Failure Behavior

- **Retry/backoff behavior**: implemented in `vultron/adapters/driven/http_delivery.py` — exponential backoff with configurable `max_retries`, `initial_delay`, `backoff_multiplier`, and `max_delay` constants (SYNC-05-001, SYNC-05-002); exhausting retries for one recipient logs at ERROR and raises `DeliveryError` for outbox requeue (OX-05-002); **no session-level total-retry bound** (ADR-0066 tracks the known compose-to-unbounded concern — GitHub #2314 added per-period limit)
- **Timeout policy**: pytest test timeout is 5 s per-test (via `pytest-timeout`); HTTP client timeout for outbound delivery configurable via httpx defaults
- **Circuit-breaker or fallback**: not observed

### 5) Observability for Integrations

- **Logging around external calls**: `logging.getLogger(__name__)` used throughout; log calls appear in adapter modules
- **Metrics/tracing**: no dedicated metrics or distributed tracing framework observed (no Prometheus, OpenTelemetry, Datadog)
- **Missing visibility gaps**: no structured log correlation IDs between inbound AS2 activity and outbound delivery confirmation; no health-check metrics for outbound delivery failures

### 6) Evidence

- `vultron/adapters/driven/datalayer_sqlite/`
- `vultron/adapters/driven/http_delivery.py`
- `vultron/adapters/driven/prod_http_delivery.py` (stub — not yet implemented)
- `vultron/adapters/driven/wire_render/as2.py` (new 2026-08: AS2 wire render adapter)
- `vultron/core/ports/wire_render.py` (new 2026-08: `WireRenderPort` Protocol)
- `vultron/adapters/driving/fastapi/inbox_handler.py`
- `vultron/adapters/connectors/example/`
- `.env.example`
