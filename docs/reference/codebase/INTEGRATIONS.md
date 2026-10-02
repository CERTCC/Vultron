---
stakeholder_type: [project-contributor]
---

# External Integrations

## Core Sections (Required)

### 1) Integration Inventory

| System | Type | Purpose | Auth model | Criticality | Evidence |
|--------|------|---------|------------|-------------|----------|
| SQLite (via SQLModel/SQLAlchemy) | Database | Persistent storage for domain objects, received-activity archive, inbox/outbox queues and the outbox dead-letter store | None (local file or `:memory:`) | High | `vultron/adapters/driven/datalayer_sqlite/` |
| Peer Vultron actors (HTTP/AS2) | Outbound HTTP API | ActivityStreams 2.0 message delivery to other actors' inboxes | HTTP Signatures (intended) — the production adapter docstring specifies signing with the local actor's private key (OX-10-004); that adapter is a `NotImplementedError` stub, so the demo path is unauthenticated | High | `vultron/adapters/driven/prod_http_delivery.py`, `vultron/adapters/driven/demo_http_delivery.py` |
| ActivityPub / AS2 (inbound) | Inbound HTTP | Receive CVD coordination activities at `POST /actors/{actor_id}/inbox` | None implemented. Signature validation is planned for the shared-inbox adapter, which is a `NotImplementedError` stub (OX-11-001 to OX-11-004) | High | `vultron/adapters/driving/fastapi/routers/actors/_routes.py`, `vultron/adapters/driving/shared_inbox.py` |
| Third-party trackers (Jira, VINCE) | Connector adapter | Translate external tracker events to/from Vultron domain; plugins are meant to be discovered via the `vultron.connectors` entry-point group | [ASK USER] — examples only; the plugin loader is a stub | Low | `vultron/adapters/connectors/example/`, `vultron/adapters/connectors/loader.py` |
| Docker Compose (multi-actor demo) | Orchestration | Stands up multiple actor containers sharing an AS2 network for the end-to-end demo | None (local demo) | Low | `docker/docker-compose-multi-actor.yml`, `docker/demo-entrypoint.sh` |
| GitHub Pages | Static hosting | Publishes the MkDocs site | GitHub Actions token | Low | `.github/workflows/deploy_site.yml` |

### 2) Data Stores

| Store | Role | Access layer | Key risk | Evidence |
|-------|------|--------------|----------|----------|
| SQLite (one file per actor, or `:memory:`) | Per-actor activity store: each hosted actor gets its own store holding only that actor's knowledge (ADR-0073) | `SqliteDataLayer` in `vultron/adapters/driven/datalayer_sqlite/`, resolved per actor by `get_datalayer(actor_id)` | Single-process SQLite has no concurrent multi-writer support and is not suitable for multi-node deployment without migration; there is no migration path from a pre-ADR-0073 shared store | `vultron/adapters/driven/datalayer_sqlite/schema.py`, `vultron/adapters/driven/datalayer.py` |
| In-memory (tests) | Isolated per-test data store | `reset_datalayer()` + `sqlite:///:memory:` | None (intended ephemeral use) | `test/conftest.py` |

### 3) Secrets and Credentials Handling

- **Credential sources**: `VULTRON_CONFIG` YAML file and/or `VULTRON_`-prefixed environment variables; only `PROJECT_NAME` is documented in `.env.example`
- **Hardcoding checks**: no hardcoded credentials observed in source; the database URL is injected via config
- **Rotation or lifecycle notes**: [ASK USER] — no secrets manager integration observed, and the credential rotation strategy is unknown.
  The outbound-delivery design anticipates a per-actor HTTP Signature private key (`prod_http_delivery.py` docstring, OX-10-004), but no key storage, loading, or rotation is implemented yet.

### 4) Reliability and Failure Behavior

- **Per-recipient retry**: `HttpDeliveryAdapter` in `vultron/adapters/driven/http_delivery.py` retries 5xx and network errors with exponential backoff (`DEFAULT_MAX_RETRIES`, `DEFAULT_INITIAL_DELAY`, `DEFAULT_BACKOFF_MULTIPLIER`, `DEFAULT_MAX_DELAY`; SYNC-05-001, SYNC-05-002).
  A 4xx response is terminal and raises `DeliveryError` at once without consuming retries (OX-13-005).
- **Total-attempt bound**: `outbox_handler.py` counts cumulative attempts per activity across drain passes and moves an activity to the dead-letter store at `MAX_TOTAL_ATTEMPTS` (ADR-0066, OX-13-002; `vultron/adapters/outbox_dead_letter.py`).
- **Ordering**: delivery is per recipient in enqueue order, with one drain per actor (ADR-0112, `outbox_lanes.py`); the outbound body is the sealed JSON stored at emission (`vultron/adapters/outbox_sealed_body.py`).
- **Timeout policy**: outbound HTTP requests use `DEFAULT_DELIVERY_TIMEOUT` (30 s) unless the adapter is constructed with another value
- **Circuit-breaker or fallback**: not observed

### 5) Observability for Integrations

- **Logging around external calls**: `logging.getLogger(__name__)` is used throughout; delivery success logs at INFO, retries at WARNING and terminal failures at ERROR in `http_delivery.py`
- **Metrics/tracing**: no dedicated metrics or distributed tracing framework observed (no Prometheus, OpenTelemetry, Datadog)
- **Missing visibility gaps**: no structured log correlation IDs between inbound AS2 activity and outbound delivery confirmation; no health-check metrics for outbound delivery failures beyond the dead-letter store

### 6) Evidence

- `vultron/adapters/driven/datalayer_sqlite/`
- `vultron/adapters/driven/http_delivery.py`
- `vultron/adapters/driven/prod_http_delivery.py` (stub — not yet implemented)
- `vultron/adapters/driven/demo_http_delivery.py`
- `vultron/adapters/driving/fastapi/outbox_handler.py`
- `vultron/adapters/driving/fastapi/outbox_lanes.py`
- `vultron/adapters/outbox_dead_letter.py`
- `vultron/adapters/outbox_sealed_body.py`
- `vultron/adapters/driving/shared_inbox.py` (stub — not yet implemented)
- `vultron/adapters/driving/fastapi/routers/actors/_routes.py`
- `vultron/adapters/connectors/example/`
- `vultron/adapters/connectors/loader.py`
- `.github/workflows/deploy_site.yml`
- `.env.example`
