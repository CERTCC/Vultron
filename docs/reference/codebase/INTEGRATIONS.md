---
stakeholder_type: [project-contributor]
---

# External Integrations

## Core Sections (Required)

### 1) Integration Inventory

| System | Type | Purpose | Auth model | Criticality | Evidence |
|--------|------|---------|------------|-------------|----------|
| SQLite (via SQLModel/SQLAlchemy) | Database | Persistent storage for domain objects, received-activity archive, inbox/outbox queues, and inbox/outbox dead-letter stores | None (local file or `:memory:`) | High | `vultron/adapters/driven/datalayer_sqlite/` |
| Peer Vultron actors (HTTP/AS2) | Outbound HTTP API | ActivityStreams 2.0 message delivery to other actors' inboxes | None implemented. ADR-0164 (`accepted-provisional`) puts an object-level proof (FEP-8b32, `eddsa-jcs-2022`, seeded Ed25519 keys) inside every sent activity and defers HTTP Signatures to productionization (#1184); the `prod_http_delivery.py` stub docstring still describes HTTP Signatures (OX-10-004) | High | `vultron/adapters/driven/prod_http_delivery.py`, `vultron/adapters/driven/demo_http_delivery.py` |
| ActivityPub / AS2 (inbound) | Inbound HTTP | Receive CVD coordination activities at `POST /actors/{actor_id}/inbox` | None implemented; the inbox accepts any well-formed body. ADR-0164 calls for strict proof verification with no switch, pinned by strict-`xfail` tests until it lands; the shared-inbox stub (OX-11-001 to OX-11-004) still plans signature validation | High | `vultron/adapters/driving/fastapi/routers/actors/_routes.py`, `vultron/adapters/driving/shared_inbox.py`, `test/adapters/driving/fastapi/test_signed_delivery_refusal.py` |
| Dedicated CaseActor service | Outbound HTTP API | A case proposal goes to the CaseActor at `{case_actor_service_url}/actors/case-actor`, one per container (CP-04-005, CP-08-001) | None (as for peer actors) | High | `vultron/config/actor.py`, `docker/docker-compose-multi-actor.yml` |
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
- **Rotation or lifecycle notes**: no secrets manager integration observed.
  ADR-0164 computes each prototype actor's signing key from a fixed seed, which makes no security claim; production key generation, private-key storage and rotation are deferred to #1184.
  No signing key of either kind is implemented yet.

### 4) Reliability and Failure Behavior

- **Per-recipient retry**: `HttpDeliveryAdapter` in `vultron/adapters/driven/http_delivery.py` retries 5xx and network errors with exponential backoff (`DEFAULT_MAX_RETRIES`, `DEFAULT_INITIAL_DELAY`, `DEFAULT_BACKOFF_MULTIPLIER`, `DEFAULT_MAX_DELAY`; SYNC-05-001, SYNC-05-002).
  A 4xx response is terminal and raises `DeliveryError` at once without consuming retries (OX-13-005).
- **Position statements**: each hosted participant sends `Read(CaseLedgerEntry)` naming its tail for each case it holds after every restart, so a lost last entry is replayed (SYNC-17-007; `ledger_position_statements.py`).
  It repeats every `LedgerConfig.position_statement_interval_seconds`, which defaults to `None` (off).
  A participant also sends one when a case copy first seeds its replica, naming the copy's position, so the CASE_MANAGER can resend an Invite the participant dropped before the copy arrived (SYNC-17-008; `StateSeededLedgerPositionNode` in `case_copy.py`).
- **Unanswered-Invite resend (CASE_MANAGER)**: when a participant states a position its ledger holds, the CASE_MANAGER requeues the sealed body of each Invite that participant still owes an answer to, through `SyncActivityPort.resend_sealed_activity` (SYNC-20; `ResendOwedInvitesNode` in `sync/nodes/invite_resend.py`).
  The cooldown per Invite and participant starts at `LedgerConfig.invite_resend_cooldown_seconds` (30 s) and doubles per resend up to `LedgerConfig.invite_resend_max_cooldown_seconds` (600 s).
- **Total-attempt bound (outbox)**: `outbox_handler.py` counts cumulative attempts per activity across drain passes and moves an activity to the outbox dead-letter store at `MAX_TOTAL_ATTEMPTS` (ADR-0066, OX-13-002; `vultron/adapters/outbox_dead_letter.py`).
- **Total-attempt bound (inbox)**: `run_inbox_pipeline` (`inbox_orchestration.py`) counts cumulative processing attempts per activity it replays from the inbox queue using the same `QueueAttemptEntry` table and moves an exhausted item to the inbox dead-letter store after `AppConfig.max_inbox_retry_attempts` attempts (IE-06-004; `InboxDeadLetterEntry` in `vultron/adapters/outbox_dead_letter.py`).
  Each attempt commits as one DataLayer transaction (IE-06-005), and the app lifespan replays every hosted actor's queue once at startup (IE-06-006; `inbox_startup_replay.py`).
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
- `vultron/config/actor.py`
- `docs/adr/0164-actors-sign-content-with-object-level-proofs-from-seeded-keys.md`
