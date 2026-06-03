# Codebase Concerns

## Core Sections (Required)

### 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| high | Demo helpers still depend on `requests`, but `requests` is not declared in `project.dependencies` | `vultron/demo/utils.py`, `vultron/demo/helpers/verification.py`, `pyproject.toml` | Fresh non-dev installs may fail when demo or verification helpers make HTTP calls; `httpx` (`>=0.28.1`) is already a declared runtime dep | Migrate demo HTTP helpers from `requests` to `httpx` — tracked in GitHub issue #517 |
| high | Legacy globals and cached DataLayers still influence the deployed FastAPI path despite newer `create_app()` isolation rules | `vultron/adapters/driving/fastapi/main.py`, `vultron/adapters/driving/fastapi/app.py`, `vultron/adapters/driving/fastapi/inbox_handler.py`, `vultron/adapters/driving/fastapi/outbox_handler.py`, `vultron/adapters/driven/datalayer_sqlite.py` | Cross-app state leakage or startup-order bugs can still appear in co-located or shared-process setups | Continue migrating the mounted app path toward per-app state and keep regression tests around actor isolation |
| medium | Outbox draining is implemented as a 1-second polling loop over all actor DataLayers | `vultron/adapters/driving/fastapi/outbox_monitor.py` | Polling cost grows with actor count and can hide queue-depth issues | Consider event-driven wakeups or queue metrics if actor count grows |
| medium | Several source files still exceed 500 lines and mix multiple responsibilities | `vultron/core/behaviors/case/nodes.py` (1502 lines), `vultron/adapters/driven/datalayer_sqlite.py` (1108 lines), `vultron/demo/scenario/two_actor_demo.py` (863 lines), `vultron/wire/as2/extractor.py` (821 lines), `vultron/core/use_cases/triggers/embargo.py` (902 lines) | Large, multi-responsibility files are harder to test, review, and maintain; several are also high-churn | Incrementally extract cohesive sub-modules; prioritize `nodes.py`, `extractor.py`, and `datalayer_sqlite.py` |
| medium | Current remote delivery uses plain HTTP POST via `DeliveryQueueAdapter`; signing and shared-inbox support remain stubbed | `vultron/adapters/driven/delivery_queue.py`, `vultron/adapters/driven/http_delivery.py`, `vultron/adapters/driving/shared_inbox.py` | Multi-party interoperability and security posture are limited until signed delivery paths exist | Treat signed delivery/shared inbox as explicit future work and avoid implying these flows are production-ready |

### 2) Technical Debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| 15 outstanding TODO/FIXME/HACK comments remain in the production package | Incremental development; partially-finished refactors remain in core, wire, example, and legacy BT modules | `vultron/core/states/cs.py`, `vultron/wire/as2/vocab/objects/embargo_event.py`, `vultron/wire/as2/vocab/examples/*.py`, `vultron/wire/as2/vocab/activities/case_participant.py`, `vultron/wire/as2/vocab/base/objects/*.py`, `vultron/bt/report_management/_behaviors/report_to_others.py`, `vultron/bt/base/bt_node.py`, `vultron/bt/base/demo/pacman.py` | Ambiguous future work and partially-finished refactors accumulate silently | Triage each TODO into a tracked issue or remove it; do not leave long-lived TODOs in protocol-significant paths |
| `http_delivery.py` and `shared_inbox.py` are stubs with no implementation | Placeholder-driven design for future signed HTTP delivery and shared-inbox fan-out | `vultron/adapters/driven/http_delivery.py`, `vultron/adapters/driving/shared_inbox.py` | No production delivery path for signed or shared-inbox flows; callers may assume these are functional | Implement or clearly gate behind feature flags before any production use |
| Documentation/code drift around architecture targets | Notes describe both target and current structure; new ASGIEmitter rules now live in a separate note | `notes/architecture-hexagonal.md`, `notes/architecture-ports.md`, `notes/architecture-adapters.md`, `notes/asgi-emitter.md`, `AGENTS.md` | New contributors may confuse target layout with what exists today | Keep onboarding docs explicitly split into "current reality" vs "target direction" and cite the ASGIEmitter note where relevant |
| High churn in planning and guidance files | Planning/spec docs evolve rapidly during active development | `plan/BUILD_LEARNINGS.md`, `AGENTS.md` (79) in the latest scan window | Agent guidance and task context can go stale quickly | Treat `plan/` and guidance docs as volatile areas during onboarding; re-read before each session |
| `vultron/semantic_registry/` was a 783-line centralized dispatch table | Single module consolidated all message-type to handler wiring | `vultron/semantic_registry/` (refactored in #702) | Previously any new message type required editing one large file; now split into domain sub-modules | Split completed — see `vultron/semantic_registry/` package |

### 3) Security Concerns

| Risk | OWASP category (if applicable) | Evidence | Current mitigation | Gap |
|------|--------------------------------|----------|--------------------|-----|
| No explicit auth/signing was evident in sampled outbound or inbound HTTP delivery paths | A01 / N/A | `vultron/adapters/driven/delivery_queue.py`, `vultron/adapters/driving/fastapi/app.py`, `vultron/adapters/driving/fastapi/routers/actors.py` | Local actor IDs and inbox URLs are explicit | Authentication, authorization, or message-signing behavior was not evident in sampled files |
| Secret handling appears to rely on plain env vars and Compose files | A05 / N/A | `.env.example`, `docker/docker-compose.yml`, `docker/docker-compose-multi-actor.yml` | Example files avoid committed secrets | No secret-rotation or secret-manager integration was found |

### 4) Performance and Scaling Concerns

| Concern | Evidence | Current symptom | Scaling risk | Suggested improvement |
|---------|----------|-----------------|-------------|-----------------------|
| Polling outbox handler scans every actor DataLayer once per second | `vultron/adapters/driving/fastapi/outbox_monitor.py` | Constant polling work even when queues are empty | More actors mean more unnecessary wakeups and reads | Add queue-driven wakeups or adaptive polling |
| SQLite is the only active persistence backend exposed by the facade | `vultron/adapters/driven/datalayer.py`, `vultron/adapters/driven/datalayer_sqlite.py` | Local-file DB is simple for tests and demos | Multi-writer or higher-volume deployments may hit SQLite limits | Define the next backend/operational profile before scaling beyond demos |

### 5) Fragile/High-Churn Areas

| Area | Why fragile | Churn signal | Safe change strategy |
|------|-------------|-------------|----------------------|
| `plan/` documentation set | Planning/history docs change very frequently | `plan/BUILD_LEARNINGS.md` and `plan/PRIORITIES.md` top the current churn output | Read current files immediately before editing; expect stale assumptions |
| `AGENTS.md` and spec guidance | Repo rules change often and affect coding behavior | `AGENTS.md` (79 changes in the latest scan window), `specs/README.md` in high-churn output | Re-read guidance before non-trivial changes |
| `vultron/core/behaviors/case/nodes.py` | Encodes case-protocol BT semantics; largest source file at 1502 lines | 47 churn hits in the latest scan window | Make narrow changes with focused tests; extract sub-modules to reduce blast radius |
| `vultron/wire/as2/extractor.py` | AS2-to-domain semantic extraction; pattern ordering is order-sensitive | 36 churn hits in the latest scan window | Run `test/test_semantic_activity_patterns.py` after every edit; add pattern tests before adding patterns |
| `vultron/core/use_cases/triggers/embargo.py` | Embargo use-case trigger logic; 37 churn hits at 902 lines | 37 churn hits in the latest scan window | Narrow PRs with explicit test coverage for each embargo state transition |

### 6) Open Questions

1. Demo HTTP helpers still use `requests`, while the declared runtime HTTP
   client is `httpx`. Migration is tracked in GitHub issue #517 (child of
   bug #501). No timeline is set.
2. `http_delivery.py` and `shared_inbox.py` remain architectural placeholders;
   confirm whether they are near-term deliverables or intentionally dormant.
3. The `{key:path}` Starlette path converter is the current tactical mitigation
   for full-URI IDs in URL path segments (see GitHub concern #618). The deeper
   question — whether to adopt ActivityPub's surrogate-key routing model — is
   still open.

### 7) Evidence

- `docs/reference/codebase/.codebase-scan.txt`
- `pyproject.toml`
- `docker/Dockerfile`
- `vultron/adapters/driving/fastapi/main.py`
- `vultron/adapters/driving/fastapi/app.py`
- `vultron/adapters/driving/fastapi/deps.py`
- `vultron/adapters/driving/fastapi/inbox_handler.py`
- `vultron/adapters/driving/fastapi/outbox_monitor.py`
- `vultron/adapters/driving/fastapi/outbox_handler.py`
- `vultron/adapters/driving/shared_inbox.py`
- `vultron/adapters/driven/datalayer.py`
- `vultron/adapters/driven/datalayer_sqlite.py`
- `vultron/adapters/driven/delivery_queue.py`
- `vultron/adapters/driven/asgi_emitter.py`
- `vultron/adapters/driven/http_delivery.py`
- `vultron/adapters/driven/sync_activity_adapter.py`
- `vultron/adapters/driven/trigger_activity_adapter.py`
- `vultron/demo/utils.py`
- `vultron/demo/helpers/verification.py`
- `vultron/semantic_registry.py`
- `vultron/core/behaviors/case/nodes.py`
- `vultron/wire/as2/extractor.py`
- `vultron/core/use_cases/triggers/embargo.py`
- `notes/asgi-emitter.md`
- `git log --since="90 days ago"` (churn data)
