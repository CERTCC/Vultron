# External Integrations

## Core Sections (Required)

### 1) Integration Inventory

| System | Type (API/DB/Queue/etc) | Purpose | Auth model | Criticality | Evidence |
|--------|---------------------------|---------|------------|-------------|----------|
| SQLite via SQLModel | DB | Persist Vultron objects and inbox/outbox queue entries | Local file or in-memory DB URL; no separate DB auth shown | high | `vultron/adapters/driven/datalayer_sqlite.py`, `docker/docker-compose-multi-actor.yml` |
| ASGIEmitter (in-process) | API | Deliver outbound AS2 activities to co-located actors via ASGI, bypassing HTTP | None required (same-process) | high | `vultron/adapters/driven/asgi_emitter.py`, `vultron/adapters/driving/fastapi/app.py` |
| Peer actor inboxes | API | Deliver outbound AS2 activities to remote actors with HTTP POST | `[TODO]` no auth/signing shown in sampled delivery code | high | `vultron/adapters/driven/delivery_queue.py` |
| HTTP delivery (stub) | API | Future signed HTTP delivery to remote inboxes | Intended to use HTTP Signature signing; not yet implemented | medium | `vultron/adapters/driven/http_delivery.py` |
| Shared inbox (stub) | API | ActivityPub shared-inbox fan-out to multiple local actors | HTTP Signature validation planned; not yet implemented | medium | `vultron/adapters/driving/shared_inbox.py` |
| Demo client to local API | API | Drive seeded/demo scenarios over HTTP | None shown beyond local base URL config | medium | `vultron/demo/utils.py`, `vultron/demo/cli.py` |
| MCP trigger adapter | Tool/API surface | Expose trigger use cases to MCP-compatible callers once registered | `[TODO]` not shown in current file | low | `vultron/adapters/driving/mcp_server.py` |

### 2) Data Stores

| Store | Role | Access layer | Key risk | Evidence |
|-------|------|--------------|----------|----------|
| SQLite `vultron_objects` | Primary object store | `SqliteDataLayer` | Single-node/local-file scaling and runtime dependency on local disk/SQLite semantics | `vultron/adapters/driven/datalayer_sqlite.py` |
| SQLite `vultron_queue` | Inbox/outbox queue persistence | `SqliteDataLayer` plus outbox/inbox handlers | Queue semantics are process-local and rely on actor scoping consistency | `vultron/adapters/driven/datalayer_sqlite.py`, `vultron/adapters/driving/fastapi/inbox_handler.py` |
| Named Docker volumes per actor | Persist per-actor SQLite DBs in multi-actor demos | Docker Compose | Operational complexity grows with actor count | `docker/docker-compose-multi-actor.yml` |

### 3) Secrets and Credentials Handling

- Credential sources: environment variables and Docker Compose env blocks
- Hardcoding checks: no API keys or secrets were present in the sampled config
  files; committed examples mostly define names and base URLs
- Rotation or lifecycle notes: `[TODO]` no secret-rotation or external secret
  manager configuration was found

### 4) Reliability and Failure Behavior

- Retry/backoff behavior: implemented for outbound HTTP delivery with
  exponential backoff and per-recipient failure isolation
- Timeout policy: outbound inbox delivery uses a 5.0 second HTTP timeout;
  Docker health checks define 2-5 second probe timeouts
- Circuit-breaker or fallback behavior: none found in sampled runtime files

### 5) Observability for Integrations

- Logging around external calls: yes; delivery attempts and demo HTTP calls log
  status and failures
- Metrics/tracing coverage: no metrics or tracing integration was found in the
  sampled runtime files
- Missing visibility gaps: no structured metrics/tracing for delivery retries,
  queue depth, or DB latency were found

### 6) Evidence

- `vultron/adapters/driven/datalayer_sqlite.py`
- `vultron/adapters/driven/delivery_queue.py`
- `vultron/adapters/driven/asgi_emitter.py`
- `vultron/demo/utils.py`
- `docker/docker-compose.yml`
- `docker/docker-compose-multi-actor.yml`
- `.env.example`
