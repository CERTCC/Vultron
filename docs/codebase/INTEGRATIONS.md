# External Integrations

## Core Sections (Required)

### 1) Integration Inventory

| System | Type | Purpose | Auth model | Criticality | Evidence |
|--------|------|---------|------------|-------------|----------|
| SQLite (via SQLModel/SQLAlchemy) | Database | Persistent storage for domain objects and inbox/outbox queues | None (local file or `:memory:`) | High | `vultron/adapters/driven/datalayer_sqlite/` |
| Peer Vultron actors (HTTP/AS2) | Outbound HTTP API | ActivityStreams 2.0 message delivery to other Vultron nodes | [ASK USER] — not observed in source | High | `vultron/adapters/driven/prod_http_delivery.py` |
| ActivityPub / AS2 (inbound) | Inbound HTTP | Receive CVD coordination activities from other actors | [ASK USER] — HTTP auth mechanism not confirmed | High | `vultron/adapters/driving/fastapi/inbox_handler.py` |
| MCP server (Model Context Protocol) | Local adapter | Expose trigger use cases as AI agent tools | None (local) | Medium | `vultron/adapters/driving/mcp_server.py` |
| Third-party trackers (Jira, VINCE) | Connector adapter | Translate external tracker events to/from Vultron domain | [ASK USER] — example only, not production-wired | Low | `vultron/adapters/connectors/example/` |

### 2) Data Stores

| Store | Role | Access layer | Key risk | Evidence |
|-------|------|--------------|----------|----------|
| SQLite (file or `:memory:`) | Single canonical activity store for all domain objects | `SqliteDataLayer` in `vultron/adapters/driven/datalayer_sqlite/` | Single-process SQLite has no concurrent multi-writer support; not suitable for multi-node deployment without migration | `vultron/adapters/driven/datalayer_sqlite/schema.py` |
| In-memory (tests) | Isolated per-test data store | `reset_datalayer()` + `sqlite:///:memory:` | None (intended ephemeral use) | `test/conftest.py` |

### 3) Secrets and Credentials Handling

- **Credential sources**: `VULTRON_CONFIG` YAML file and/or environment variables; only `PROJECT_NAME` is documented in `.env.example`
- **Hardcoding checks**: no hardcoded credentials observed in source; database URL is always injected via config
- **Rotation or lifecycle notes**: [ASK USER] — no secrets manager integration observed; credential rotation strategy unknown

### 4) Reliability and Failure Behavior

- **Retry/backoff behavior**: [TODO] — not observed in `prod_http_delivery.py` surface scan; pending deeper review
- **Timeout policy**: pytest test timeout is 5 s (via `pytest-timeout`); HTTP client timeout for outbound delivery not confirmed — [TODO]
- **Circuit-breaker or fallback**: not observed

### 5) Observability for Integrations

- **Logging around external calls**: `logging.getLogger(__name__)` used throughout; log calls appear in adapter modules
- **Metrics/tracing**: no dedicated metrics or distributed tracing framework observed (no Prometheus, OpenTelemetry, Datadog)
- **Missing visibility gaps**: no structured log correlation IDs between inbound AS2 activity and outbound delivery confirmation; no health-check metrics for outbound delivery failures

### 6) Evidence

- `vultron/adapters/driven/datalayer_sqlite/`
- `vultron/adapters/driven/prod_http_delivery.py`
- `vultron/adapters/driving/fastapi/inbox_handler.py`
- `vultron/adapters/driving/mcp_server.py`
- `vultron/adapters/connectors/example/`
- `.env.example`
